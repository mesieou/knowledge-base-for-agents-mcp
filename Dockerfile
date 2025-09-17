# Use Python 3.13 for latest performance
FROM python:3.12-slim

# Install system dependencies and clean up apt cache
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for faster package management
RUN pip install --no-cache-dir --root-user-action=ignore uv

# Copy requirements and install with uv + CPU-only PyTorch (reduces from 7.6GB to ~1.7GB)
COPY requirements.txt .
RUN uv pip install --system --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match

# Copy application code
COPY . .

EXPOSE 8000

# Run server
CMD ["python3", "server.py"]
