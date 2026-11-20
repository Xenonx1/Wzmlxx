"""PostgreSQL (Neon) storage layer.

Drop-in replacement for the old MongoDB handler. All persistent data lives in
a handful of small tables that are created automatically on first connect:

    settings   (bot_id, kind, data jsonb)       -> config / aria2c / qbittorrent / deployConfig
    files      (bot_id, name, content bytea)    -> private files such as config.py, .netrc
    users      (bot_id, user_id, data jsonb)    -> per-user settings
    user_docs  (bot_id, user_id, key, content)  -> per-user binary files (thumbnail, cookies)
    pm_users   (bot_id, user_id)                -> users that started the bot in PM
    tasks      (bot_id, link, cid, tag)         -> incomplete task notifier

Neon notes:
  * the DSN must use SSL (Neon strings already contain ``sslmode=require``)
  * ``channel_binding`` is not understood by asyncpg, so it is stripped
  * prepared statements are disabled so Neon's pooled (pgbouncer) endpoints work
"""

from importlib import import_module
from json import dumps, loads
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath

from ... import LOGGER, qbit_options, user_data
from ...core.config_manager import Config
from ...core.tg_client import TgClient

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None

# user keys that hold *file paths* in memory; their bytes live in `user_docs`
USER_FILE_KEYS = ("THUMBNAIL", "USER_COOKIE_FILE")

SCHEMA = """
CREATE TABLE IF NOT EXISTS wzml_settings (
    bot_id TEXT NOT NULL,
    kind   TEXT NOT NULL,
    data   JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (bot_id, kind)
);
CREATE TABLE IF NOT EXISTS wzml_files (
    bot_id  TEXT  NOT NULL,
    name    TEXT  NOT NULL,
    content BYTEA NOT NULL,
    PRIMARY KEY (bot_id, name)
);
CREATE TABLE IF NOT EXISTS wzml_users (
    bot_id  TEXT   NOT NULL,
    user_id BIGINT NOT NULL,
    data    JSONB  NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (bot_id, user_id)
);
CREATE TABLE IF NOT EXISTS wzml_user_docs (
    bot_id  TEXT   NOT NULL,
    user_id BIGINT NOT NULL,
    key     TEXT   NOT NULL,
    content BYTEA  NOT NULL,
    PRIMARY KEY (bot_id, user_id, key)
);
CREATE TABLE IF NOT EXISTS wzml_pm_users (
    bot_id  TEXT   NOT NULL,
    user_id BIGINT NOT NULL,
    PRIMARY KEY (bot_id, user_id)
);
CREATE TABLE IF NOT EXISTS wzml_tasks (
    bot_id TEXT   NOT NULL,
    link   TEXT   NOT NULL,
    cid    BIGINT NOT NULL,
    tag    TEXT   NOT NULL DEFAULT '',
    PRIMARY KEY (bot_id, link)
);
"""

TABLES = {"settings", "files", "users", "user_docs", "pm_users", "tasks"}


def _json_default(obj):
    if isinstance(obj, (set, frozenset, tuple)):
        return list(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", "ignore")
    return str(obj)


def _dumps(obj):
    return dumps(obj, default=_json_default)


def _clean_dsn(url):
    """Make a Neon connection string safe for asyncpg."""
    url = (url or "").strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    parts = urlparse(url)
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in ("channel_binding",)
    ]
    if not any(k.lower() == "sslmode" for k, _ in query):
        query.append(("sslmode", "require"))
    return urlunparse(parts._replace(query=urlencode(query)))


class DbManager:
    def __init__(self):
        self._return = True
        self._pool = None
        self.db = None  # truthy (the pool) once connected, None otherwise

    @property
    def _bot(self):
        return str(TgClient.ID)

    # ------------------------------------------------------------------ #
    # connection
    # ------------------------------------------------------------------ #
    async def connect(self):
        if asyncpg is None:
            LOGGER.error("asyncpg is not installed; database features disabled.")
            self._return, self.db, self._pool = True, None, None
            return
        try:
            if self._pool is not None:
                await self._pool.close()
            self._pool = await asyncpg.create_pool(
                dsn=_clean_dsn(Config.DATABASE_URL),
                min_size=1,
                max_size=5,
                max_inactive_connection_lifetime=60,  # recycle before Neon auto-suspends
                command_timeout=30,
                statement_cache_size=0,  # required for pgbouncer / Neon pooler
            )
            async with self._pool.acquire() as conn:
                await conn.execute(SCHEMA)
            self.db = self._pool
            self._return = False
            LOGGER.info("Connected to PostgreSQL (Neon) database.")
        except Exception as e:
            LOGGER.error(f"Error in DB connection: {e}")
            self.db = None
            self._return = True
            self._pool = None

    async def disconnect(self):
        self._return = True
        self.db = None
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception as e:
                LOGGER.error(f"Error closing DB pool: {e}")
        self._pool = None

    # ------------------------------------------------------------------ #
    # settings (config / aria2c / qbittorrent / deployConfig)
    # ------------------------------------------------------------------ #
    async def get_settings(self, kind, bot_id=None):
        if self._return:
            return None
        row = await self._pool.fetchrow(
            "SELECT data::text AS data FROM wzml_settings WHERE bot_id=$1 AND kind=$2",
            str(bot_id or self._bot),
            kind,
        )
        return loads(row["data"]) if row else None

    async def set_settings(self, kind, data, bot_id=None):
        """Replace the whole document."""
        if self._return:
            return
        await self._pool.execute(
            """INSERT INTO wzml_settings (bot_id, kind, data) VALUES ($1, $2, $3::text::jsonb)
               ON CONFLICT (bot_id, kind) DO UPDATE SET data = EXCLUDED.data""",
            str(bot_id or self._bot),
            kind,
            _dumps(data),
        )

    async def merge_settings(self, kind, data):
        """Merge keys into the document (like Mongo's $set)."""
        if self._return:
            return
        await self._pool.execute(
            """INSERT INTO wzml_settings (bot_id, kind, data) VALUES ($1, $2, $3::text::jsonb)
               ON CONFLICT (bot_id, kind)
               DO UPDATE SET data = wzml_settings.data || EXCLUDED.data""",
            self._bot,
            kind,
            _dumps(data),
        )

    async def update_deploy_config(self):
        if self._return:
            return
        try:
            settings = import_module("config")
        except ModuleNotFoundError:
            return
        config_file = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in vars(settings).items()
            if not key.startswith("__")
        }
        await self.set_settings("deployConfig", config_file)

    async def update_config(self, dict_):
        await self.merge_settings("config", dict_)

    async def update_aria2(self, key, value):
        await self.merge_settings("aria2c", {key: value})

    async def update_qbittorrent(self, key, value):
        await self.merge_settings("qbittorrent", {key: value})

    async def save_qbit_settings(self):
        await self.merge_settings("qbittorrent", dict(qbit_options))

    # ------------------------------------------------------------------ #
    # private files (config.py, .netrc, shortener.txt, ...)
    # ------------------------------------------------------------------ #
    async def update_private_file(self, path):
        if self._return:
            return
        if await aiopath.exists(path):
            async with aiopen(path, "rb+") as pf:
                pf_bin = await pf.read()
            await self._pool.execute(
                """INSERT INTO wzml_files (bot_id, name, content) VALUES ($1, $2, $3)
                   ON CONFLICT (bot_id, name) DO UPDATE SET content = EXCLUDED.content""",
                self._bot,
                path,
                pf_bin,
            )
            if path == "config.py":
                await self.update_deploy_config()
        else:
            await self._pool.execute(
                "DELETE FROM wzml_files WHERE bot_id=$1 AND name=$2", self._bot, path
            )

    async def get_private_files(self, bot_id=None):
        if self._return:
            return {}
        rows = await self._pool.fetch(
            "SELECT name, content FROM wzml_files WHERE bot_id=$1", str(bot_id or self._bot)
        )
        return {r["name"]: bytes(r["content"]) for r in rows}

    # ------------------------------------------------------------------ #
    # users
    # ------------------------------------------------------------------ #
    async def update_user_data(self, user_id):
        if self._return:
            return
        data = dict(user_data.get(user_id, {}))
        for key in (*USER_FILE_KEYS, "RCLONE_CONFIG", "TOKEN_PICKLE"):
            data.pop(key, None)
        await self._pool.execute(
            """INSERT INTO wzml_users (bot_id, user_id, data) VALUES ($1, $2, $3::text::jsonb)
               ON CONFLICT (bot_id, user_id) DO UPDATE SET data = EXCLUDED.data""",
            self._bot,
            int(user_id),
            _dumps(data),
        )

    async def update_user_doc(self, user_id, key, path=""):
        if self._return:
            return
        if path:
            async with aiopen(path, "rb+") as doc:
                doc_bin = await doc.read()
            await self._pool.execute(
                """INSERT INTO wzml_user_docs (bot_id, user_id, key, content)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (bot_id, user_id, key)
                   DO UPDATE SET content = EXCLUDED.content""",
                self._bot,
                int(user_id),
                key,
                doc_bin,
            )
        else:
            await self._pool.execute(
                "DELETE FROM wzml_user_docs WHERE bot_id=$1 AND user_id=$2 AND key=$3",
                self._bot,
                int(user_id),
                key,
            )

    async def get_all_users(self, bot_id=None):
        """Return {user_id: {"data": dict, "docs": {key: bytes}}}."""
        if self._return:
            return {}
        bot = str(bot_id or self._bot)
        users = {}
        for r in await self._pool.fetch(
            "SELECT user_id, data::text AS data FROM wzml_users WHERE bot_id=$1", bot
        ):
            users[r["user_id"]] = {"data": loads(r["data"]), "docs": {}}
        for r in await self._pool.fetch(
            "SELECT user_id, key, content FROM wzml_user_docs WHERE bot_id=$1", bot
        ):
            users.setdefault(r["user_id"], {"data": {}, "docs": {}})["docs"][
                r["key"]
            ] = bytes(r["content"])
        return users

    # ------------------------------------------------------------------ #
    # PM users
    # ------------------------------------------------------------------ #
    async def get_pm_uids(self):
        if self._return:
            return
        rows = await self._pool.fetch(
            "SELECT user_id FROM wzml_pm_users WHERE bot_id=$1", self._bot
        )
        return [r["user_id"] for r in rows]

    async def set_pm_users(self, user_id):
        if self._return:
            return
        result = await self._pool.execute(
            """INSERT INTO wzml_pm_users (bot_id, user_id) VALUES ($1, $2)
               ON CONFLICT DO NOTHING""",
            self._bot,
            int(user_id),
        )
        if result.endswith(" 1"):
            LOGGER.info(f"New PM User Added : {user_id}")

    async def rm_pm_user(self, user_id):
        if self._return:
            return
        await self._pool.execute(
            "DELETE FROM wzml_pm_users WHERE bot_id=$1 AND user_id=$2",
            self._bot,
            int(user_id),
        )

    # ------------------------------------------------------------------ #
    # incomplete tasks
    # ------------------------------------------------------------------ #
    async def add_incomplete_task(self, cid, link, tag):
        if self._return:
            return
        await self._pool.execute(
            """INSERT INTO wzml_tasks (bot_id, link, cid, tag) VALUES ($1, $2, $3, $4)
               ON CONFLICT (bot_id, link) DO UPDATE SET cid=EXCLUDED.cid, tag=EXCLUDED.tag""",
            self._bot,
            link,
            int(cid),
            tag or "",
        )

    async def rm_complete_task(self, link):
        if self._return:
            return
        await self._pool.execute(
            "DELETE FROM wzml_tasks WHERE bot_id=$1 AND link=$2", self._bot, link
        )

    async def get_incomplete_tasks(self):
        notifier_dict = {}
        if self._return:
            return notifier_dict
        rows = await self._pool.fetch(
            "SELECT link, cid, tag FROM wzml_tasks WHERE bot_id=$1", self._bot
        )
        for row in rows:
            notifier_dict.setdefault(row["cid"], {}).setdefault(row["tag"], []).append(
                row["link"]
            )
        await self._pool.execute("DELETE FROM wzml_tasks WHERE bot_id=$1", self._bot)
        return notifier_dict

    async def trunc_table(self, name):
        """Clear this bot's rows of a table (name is whitelisted)."""
        if self._return or name not in TABLES:
            return
        await self._pool.execute(f"DELETE FROM wzml_{name} WHERE bot_id=$1", self._bot)


database = DbManager()
