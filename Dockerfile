# Use Python 3.9 as the base image
FROM python:3.9-slim-bookworm

# 1. Install FFmpeg and Git (Required for music processing)
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

# 2. Set the working directory
WORKDIR /app

# 3. Copy your code into the container
COPY . /app

# 4. Install your Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. Run the bot
CMD ["python3", "main.py"]
