FROM mysterysd/wzmlx:v3

WORKDIR /usr/src/app

# (Re)install the helper programs and expose them under the names the bot calls.
RUN set -e; \
    apt-get update; \
    apt-get install -y --reinstall --no-install-recommends aria2 ffmpeg qbittorrent-nox curl procps; \
    (apt-get install -y --no-install-recommends p7zip-full || apt-get install -y --no-install-recommends 7zip) || true; \
    rm -rf /var/lib/apt/lists/*; \
    for pair in stormtorrent:qbittorrent-nox blitzfetcher:aria2c mediaforge:ffmpeg; do \
        a="${pair%%:*}"; r="${pair##*:}"; \
        p="$(command -v "$r" || true)"; \
        if [ -z "$p" ] || [ ! -x "$p" ]; then echo "MISSING PROGRAM: $r"; exit 1; fi; \
        ln -sf "$p" "/usr/bin/$a"; \
    done; \
    [ -e /bin/mediaforge ] || ln -s /usr/bin/mediaforge /bin/mediaforge; \
    ls -l /usr/bin/stormtorrent /usr/bin/blitzfetcher /usr/bin/mediaforge; \
    blitzfetcher --version | head -n 1; \
    mediaforge -version | head -n 1

RUN chmod 777 /usr/src/app
RUN uv venv --system-site-packages

COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh setpkgs.sh

CMD ["bash", "start.sh"]
