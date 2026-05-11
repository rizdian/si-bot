FROM python:3.13-slim

WORKDIR /app

# install dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# copy requirements first for better docker cache
COPY requirements.txt .

# install python deps
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -U yt-dlp

# copy app
COPY . .

# create data directory for cookies
RUN mkdir -p /app/data

CMD ["python", "bot.py"]