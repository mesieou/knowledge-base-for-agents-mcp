FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy requirements file
COPY requirements.txt .

# Install dependencies with uv
RUN uv pip install --system -r requirements.txt

COPY server.py .

EXPOSE 8050

CMD ["python", "server.py"]
