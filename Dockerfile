FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy requirements file
COPY requirements.txt .

# Install dependencies with uv
RUN uv venv
RUN uv pip install -r requirements.txt

# Copy all application code
COPY . .

EXPOSE 8000

# Use python3 explicitly to run the server
CMD ["uv", "run", "python3", "server.py"]
