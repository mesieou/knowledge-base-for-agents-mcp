FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy requirements file
COPY requirements.txt .

# Install dependencies with uv
RUN uv venv
RUN uv pip install -r requirements.txt

COPY server.py .

EXPOSE 8000

CMD ["uv", "run", "server.py"]
