FROM python:3.12-slim

WORKDIR /app

# Copy requirements file first to utilize Docker build cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose default ports (can be mapped differently in docker-compose)
EXPOSE 5000 6000

# Ensure logs and stdout are printed immediately to container logs
ENV PYTHONUNBUFFERED=1
ENV HTTP_PORT=5000
ENV P2P_PORT=6000
ENV DATA_DIR=/data

# Declare the data mount point for persistence
VOLUME ["/data"]

# Run the Flask and TCP socket application
CMD ["python", "app.py"]
