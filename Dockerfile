# Use Python 3.13 for latest performance
FROM python:3.13-slim

WORKDIR /app

# Install uv for faster package management
RUN pip install --no-cache-dir uv

# Copy requirements and install with uv globally (faster)
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# Run with system python3 (packages installed globally)
CMD ["python3", "server.py"]
