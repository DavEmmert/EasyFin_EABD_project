FROM python:3.13-slim

ADD . /app
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install uv
RUN uv pip compile pyproject.toml -o requirements.txt
RUN uv pip install --system -r requirements.txt

# Starte das Streamlit-Dashboard beim Containerstart
CMD ["streamlit", "run", "04_dashboard.py", "--server.port=80", "--server.enableCORS=false"]
