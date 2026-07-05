# Use the modern, supported Python 3.12 image on Debian Bookworm
FROM python:3.12-slim-bookworm

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (ffmpeg, git) and clean up apt cache to save space
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Command to run the bot
CMD ["python", "main.py"]
