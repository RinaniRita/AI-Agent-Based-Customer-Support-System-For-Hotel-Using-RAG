# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app

# Create and set working directory
WORKDIR $APP_HOME

# Install system dependencies (build-essential for some python packages if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Ensure the entrypoint script is executable
RUN chmod +x entrypoint.sh

# Expose the API port
EXPOSE 8000

# Set the volume for persistent data (Database and Vector Store)
VOLUME ["/app/data"]

# Run the entrypoint script
CMD ["./entrypoint.sh"]
