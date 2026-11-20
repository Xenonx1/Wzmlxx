FROM mysterysd/wzmlx:v3

WORKDIR /usr/src/app

RUN chmod 777 /usr/src/app
RUN uv venv --system-site-packages

COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh setpkgs.sh

CMD ["bash", "start.sh"]
