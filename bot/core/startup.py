from asyncio import create_subprocess_exec, create_subprocess_shell, sleep
from importlib import import_module
from os import environ, getenv, path as ospath

from aiofiles import open as aiopen
from aiofiles.os import makedirs, remove, path as aiopath
from aioshutil import rmtree

from .. import (
    LOGGER,
    aria2_options,
    auth_chats,
    shortener_dict,
    var_list,
    user_data,
    excluded_extensions,
    qbit_options,
    sudo_users,
)
from ..helper.ext_utils.db_handler import database
from .config_manager import Config, BinConfig
from .tg_client import TgClient
from .torrent_manager import TorrentManager


async def update_qb_options():
    LOGGER.info("Get qBittorrent options from server")
    if not qbit_options:
        if not TorrentManager.qbittorrent:
            LOGGER.warning(
                "qBittorrent is not initialized. Skipping qBittorrent options update."
            )
            return
        opt = await TorrentManager.qbittorrent.app.preferences()
        qbit_options.update(opt)
        del qbit_options["listen_port"]
        for k in list(qbit_options.keys()):
            if k.startswith("rss"):
                del qbit_options[k]
        qbit_options["web_ui_password"] = "admin1234"
        await TorrentManager.qbittorrent.app.set_preferences(
            {"web_ui_password": "admin"}
        )
    else:
        await TorrentManager.qbittorrent.app.set_preferences(qbit_options)


async def update_aria2_options():
    LOGGER.info("Get aria2 options from server")
    if not aria2_options:
        op = await TorrentManager.aria2.getGlobalOption()
        aria2_options.update(op)
    else:
        await TorrentManager.aria2.changeGlobalOption(aria2_options)


async def load_settings():
    if not Config.DATABASE_URL:
        return
    for p in ["thumbnails"]:
        if await aiopath.exists(p):
            await rmtree(p, ignore_errors=True)
    await database.connect()
    if database.db is None:
        return

    BOT_ID = Config.BOT_TOKEN.split(":", 1)[0]
    try:
        settings = import_module("config")
        config_file = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in vars(settings).items()
            if not key.startswith("__")
        }
    except ModuleNotFoundError:
        config_file = {}
    config_file.update(
        {
            key: value.strip() if isinstance(value, str) else value
            for key, value in environ.items()
            if key in var_list
        }
    )

    old_config = await database.get_settings("deployConfig", BOT_ID)
    if old_config is None:
        await database.set_settings("deployConfig", config_file, BOT_ID)
    if old_config and old_config != config_file:
        LOGGER.info("Saving.. Deploy Config imported from Bot")
        await database.set_settings("deployConfig", config_file, BOT_ID)
        config_dict = await database.get_settings("config", BOT_ID) or {}
        config_dict.update(config_file)
        if config_dict:
            Config.load_dict(config_dict)
    else:
        LOGGER.info("Updating.. Saved Config imported from Database")
        config_dict = await database.get_settings("config", BOT_ID)
        if config_dict:
            Config.load_dict(config_dict)

    for name, content in (await database.get_private_files(BOT_ID)).items():
        if content:
            async with aiopen(name, "wb+") as f:
                await f.write(content)

    if a2c_options := await database.get_settings("aria2c", BOT_ID):
        aria2_options.update(a2c_options)

    if not Config.DISABLE_TORRENTS:
        if qbit_opt := await database.get_settings("qbittorrent", BOT_ID):
            qbit_options.update(qbit_opt)

    if users := await database.get_all_users(BOT_ID):
        for uid, info in users.items():
            row = dict(info["data"])
            paths = {
                "THUMBNAIL": f"thumbnails/{uid}.jpg",
                "USER_COOKIE_FILE": f"cookies/{uid}/cookies.txt",
            }
            for key, path in paths.items():
                content = info["docs"].get(key)
                if content:
                    dir_path = ospath.dirname(path)
                    if not await aiopath.exists(dir_path):
                        await makedirs(dir_path)
                    async with aiopen(path, "wb") as f:
                        await f.write(content)
                    row[key] = path
            user_data[uid] = row
        LOGGER.info("Users Data has been imported from Database")


async def save_settings():
    if database.db is None:
        return
    await database.update_config(Config.get_all())
    if await database.get_settings("aria2c") is None:
        await database.merge_settings("aria2c", dict(aria2_options))
    if await database.get_settings("qbittorrent") is None:
        await database.save_qbit_settings()


async def update_variables():
    if (
        Config.LEECH_SPLIT_SIZE > TgClient.MAX_SPLIT_SIZE
        or Config.LEECH_SPLIT_SIZE == 2097152000
        or not Config.LEECH_SPLIT_SIZE
    ):
        Config.LEECH_SPLIT_SIZE = TgClient.MAX_SPLIT_SIZE

    Config.HYBRID_LEECH = bool(Config.HYBRID_LEECH and TgClient.IS_PREMIUM_USER)
    Config.USER_TRANSMISSION = bool(
        Config.USER_TRANSMISSION and TgClient.IS_PREMIUM_USER
    )

    if Config.AUTHORIZED_CHATS:
        aid = Config.AUTHORIZED_CHATS.split()
        for id_ in aid:
            chat_id, *thread_ids = id_.split("|")
            chat_id = int(chat_id.strip())
            if thread_ids:
                thread_ids = list(map(lambda x: int(x.strip()), thread_ids))
                auth_chats[chat_id] = thread_ids
            else:
                auth_chats[chat_id] = []

    if Config.SUDO_USERS:
        aid = Config.SUDO_USERS.split()
        for id_ in aid:
            sudo_users.append(int(id_.strip()))

    if Config.EXCLUDED_EXTENSIONS:
        fx = Config.EXCLUDED_EXTENSIONS.split()
        for x in fx:
            x = x.lstrip(".")
            excluded_extensions.append(x.strip().lower())

    if await aiopath.exists("shortener.txt"):
        async with aiopen("shortener.txt", "r+") as f:
            lines = await f.readlines()
            for line in lines:
                temp = line.strip().split()
                if len(temp) == 2:
                    shortener_dict[temp[0]] = temp[1]


async def load_configurations():
    if not await aiopath.exists(".netrc"):
        async with aiopen(".netrc", "w"):
            pass

    await (
        await create_subprocess_shell(
            f"chmod 600 .netrc && cp .netrc /root/.netrc && chmod +x setpkgs.sh && ./setpkgs.sh {BinConfig.ARIA2_NAME}"
        )
    ).wait()

    PORT = getenv("PORT", "") or Config.BASE_URL_PORT
    if PORT:
        await create_subprocess_shell(
            f"gunicorn -k uvicorn.workers.UvicornWorker -w 1 web.wserver:app --bind 0.0.0.0:{PORT}"
        )
        await create_subprocess_shell("python3 cron_boot.py")

    await TorrentManager.initiate()

    if Config.DISABLE_TORRENTS:
        LOGGER.info("Torrents are disabled. Skipping qBittorrent initialization.")
    else:
        try:
            await TorrentManager.qbittorrent.app.set_preferences(qbit_options)
        except Exception as e:
            LOGGER.error(f"Failed to configure qBittorrent: {e}")
