FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY uv.lock .

# Install dependencies with uv
RUN uv sync --frozen

COPY server.py .

EXPOSE 8050

CMD ["uv", "run", "server.py"]
