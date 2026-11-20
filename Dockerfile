
FROM mysterysd/wzmlx:v3

WORKDIR /usr/src/app

# Repair and verify Aria2 installation
RUN apt-get update && \
    apt-get install -y --reinstall --no-install-recommends aria2 && \
    echo "=== Aria2 package files ===" && \
    dpkg -L aria2 | grep -E 'aria2c$' && \
    echo "=== Aria2 executable ===" && \
    command -v aria2c && \
    aria2c --version && \
    rm -rf /var/lib/apt/lists/*

# Install helper programs and create bot aliases
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        qbittorrent-nox \
        aria2 \
        ffmpeg \
        curl \
        procps; \
    rm -rf /var/lib/apt/lists/*; \
    test -x /usr/bin/ffmpeg; \
    test -x /usr/bin/aria2c; \
    test -x /usr/bin/qbittorrent-nox; \
    ln -sf /usr/bin/ffmpeg /usr/bin/mediaforge; \
    ln -sf /usr/bin/ffmpeg /bin/mediaforge; \
    ln -sf /usr/bin/qbittorrent-nox /usr/bin/stormtorrent; \
    ln -sf /usr/bin/aria2c /usr/bin/blitzfetcher; \
    echo "=== Verify FFmpeg alias ==="; \
    /usr/bin/mediaforge -version; \
    echo "=== Verify qBittorrent alias ==="; \
    /usr/bin/stormtorrent --version; \
    echo "=== Verify Aria2 alias ==="; \
    /usr/bin/blitzfetcher --v

# Set application permissions
RUN chmod 777 /usr/src/app

# Create Python virtual environment
RUN uv venv --system-site-packages

# Install Python dependencies
COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy bot source code
COPY . .

# Make startup scripts executable
RUN chmod +x start.sh setpkgs.sh

# Start bot
CMD ["bash", "start.sh"]
