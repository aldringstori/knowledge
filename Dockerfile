FROM python:3.11-slim

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Set ownership of the app directory
RUN chown -R appuser:appuser /app

# Install basic system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/transcriptions /app/logs && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod 775 /app/transcriptions

# Switch to non-root user
USER appuser

# Expose port from environment variable
EXPOSE ${APP_PORT:-8501}

# Start the Streamlit app using environment variables
CMD ["sh", "-c", "streamlit run knowledge.py --server.port=${APP_PORT:-8501} --server.address=${APP_HOST:-0.0.0.0}"]