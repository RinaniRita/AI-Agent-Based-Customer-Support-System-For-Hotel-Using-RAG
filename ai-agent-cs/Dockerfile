# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app

# Create and set working directory
WORKDIR $APP_HOME

# Install system dependencies (netcat for wait-for-it logic, dos2unix for CRLF fix)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    netcat-openbsd \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Ensure the entrypoint script is executable and has Linux line endings
RUN dos2unix entrypoint.sh && chmod +x entrypoint.sh

# Expose the API port
EXPOSE 8000

# Set the volume for persistent data (Database and Vector Store)
VOLUME ["/app/data"]

# Run the entrypoint script
CMD ["./entrypoint.sh"]
