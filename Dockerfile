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
COPY client.py .

EXPOSE 8050

CMD ["uv", "run", "server.py"]
