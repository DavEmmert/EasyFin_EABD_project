FROM python:3.10-slim

WORKDIR /app

# Optional: System-Pakete für quixstreams oder redis
RUN apt-get update && apt-get install -y gcc libffi-dev && rm -rf /var/lib/apt/lists/*

COPY . .

# Falls du pyproject.toml verwendest
# RUN pip install --no-cache-dir .


ADD . /app
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv
RUN uv pip compile pyproject.toml -o requirements.txt
RUN uv pip install --system -r requirements.txt

CMD ["python", "01_receiver.py"]   passe an, falls Datei anders heißt
