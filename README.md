# WZML-X Leech (Telegram leech only)

Stripped-down WZML-X: **Telegram leech only**. Mirror, clone, Google Drive, rclone, Mega,
JDownloader, NZB/Usenet, uphosters, RSS, torrent search and IMDb were removed.

## Commands
| Command | What it does |
|---|---|
| `/leech <link>` | direct links, magnets, `.torrent`, Telegram files, hoster links (aria2) |
| `/qbleech <link>` | magnet / torrent through qBittorrent |
| `/ytdlleech <link>` | yt-dlp supported sites |

Flags work on these commands, including **`-z`** (zip first; all three) and **`-e`** (extract archive then leech; `/leech` and `/qbleech`),
plus `-n` rename, `-s` select files, `-sp` split size, `-doc`/`-med`, `-i` multi, `-b` bulk, `-sv`, `-ss`, `-t`, `-meta`, `-ff`.
Admin tools kept: `/bsetting`, `/usetting`, `/status`, `/stats`, `/cancel`, `/select`, `/forcestart`,
`/authorize`, `/addsudo`, `/broadcast`, `/shell`, `/exec`, `/log`, `/restart`.

## Database (Neon / PostgreSQL)
Set `DATABASE_URL` to your Neon connection string. Tables are created automatically on first start.
Stores bot settings, user settings, thumbnails/cookies and the incomplete-task notifier.

## Deploy on Render
1. Push this folder to your own GitHub repo.
2. Render -> **New -> Blueprint** -> pick the repo (uses `render.yaml`), or **New -> Web Service -> Docker**.
3. Fill the env vars from `.env.example` (at least `BOT_TOKEN`, `OWNER_ID`, `TELEGRAM_API`, `TELEGRAM_HASH`, `DATABASE_URL`, `BASE_URL`).
4. Deploy, then send `/start` to the bot.

Notes: the free plan has 512 MB RAM and an ephemeral disk, so big torrents will fail; use a paid
instance for serious leeching. `BASE_URL` makes the bot ping itself every 10 minutes to avoid idling.
