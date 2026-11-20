
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

# Install and configure helper programs
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        qbittorrent-nox \
        aria2 \
        ffmpeg \
        curl \
        procps; \
    rm -rf /var/lib/apt/lists/*; \
    FFMPEG="$(type -P ffmpeg)"; \
    ARIA2="$(type -P aria2c)"; \
    QBIT="$(type -P qbittorrent-nox)"; \
    test -x "$FFMPEG"; \
    test -x "$ARIA2"; \
    test -x "$QBIT"; \
    ln -sf "$FFMPEG" /usr/bin/mediaforge; \
    ln -sf "$FFMPEG" /bin/mediaforge; \
    ln -sf "$QBIT" /usr/bin/stormtorrent; \
    ln -sf "$ARIA2" /usr/bin/blitzfetcher; \
    echo "=== Verify helper programs ==="; \
    command -v mediaforge; \
    mediaforge -version; \
    command -v stormtorrent; \
    command -v blitzfetcher; \
    aria2c --version

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
