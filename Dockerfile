FROM python:3.10-slim

WORKDIR /app

# Optional: System-Pakete für quixstreams oder redis
RUN apt-get update && apt-get install -y gcc libffi-dev && rm -rf /var/lib/apt/lists/*

COPY . .

# Falls du pyproject.toml verwendest
# RUN pip install --no-cache-dir .

# Oder requirements.txt:
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "receiver.py"]  # passe an, falls Datei anders heißt
