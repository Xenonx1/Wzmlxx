FROM mysterysd/wzmlx:v3

WORKDIR /usr/src/app

# Make sure the helper programs exist, and expose them under the names the bot calls.
RUN set -e; \
    need=""; \
    command -v qbittorrent-nox >/dev/null 2>&1 || command -v stormtorrent >/dev/null 2>&1 || need="$need qbittorrent-nox"; \
    command -v aria2c >/dev/null 2>&1 || command -v blitzfetcher >/dev/null 2>&1 || need="$need aria2"; \
    command -v ffmpeg >/dev/null 2>&1 || command -v mediaforge >/dev/null 2>&1 || need="$need ffmpeg"; \
    command -v curl >/dev/null 2>&1 || need="$need curl"; \
    command -v pkill >/dev/null 2>&1 || need="$need procps"; \
    if [ -n "$need" ]; then \
        apt-get update && apt-get install -y --no-install-recommends $need && rm -rf /var/lib/apt/lists/*; \
    fi; \
    if ! command -v 7z >/dev/null 2>&1; then \
        (apt-get update && (apt-get install -y --no-install-recommends p7zip-full || apt-get install -y --no-install-recommends 7zip) && rm -rf /var/lib/apt/lists/*) || true; \
    fi; \
    for pair in stormtorrent:qbittorrent-nox blitzfetcher:aria2c mediaforge:ffmpeg; do \
        alias="${pair%%:*}"; real="${pair##*:}"; \
        if ! command -v "$alias" >/dev/null 2>&1 && command -v "$real" >/dev/null 2>&1; then \
            ln -s "$(command -v $real)" "/usr/bin/$alias"; \
        fi; \
    done; \
    [ -e /bin/mediaforge ] || ln -s "$(command -v mediaforge)" /bin/mediaforge 2>/dev/null || true

RUN chmod 777 /usr/src/app
RUN uv venv --system-site-packages

COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh setpkgs.sh

CMD ["bash", "start.sh"]
