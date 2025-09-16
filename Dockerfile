# Use Python 3.11 slim image as base (more common, faster to download)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv using pip (simpler than copying from another image)
RUN pip install uv

# Copy requirements first (for better Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN uv pip install --system -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Expose the port your MCP server runs on
EXPOSE 8050

# Health check (using Python instead of curl)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8050/health')" || exit 1

# Run the MCP server
CMD ["python", "mcp/server.py"]
