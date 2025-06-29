FROM python:3.13-slim

# The installer requires curl (and certificates) to download the release archive
#COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv
RUN uv pip compile pyproject.toml -o requirements.txt
RUN uv pip install --system -r requirements.txt

# Standardkommando (kann durch docker-compose überschrieben werden)
#CMD ["python", "main.py"]
