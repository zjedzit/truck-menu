FROM python:3.11-slim

WORKDIR /app

# Kopiujemy najpierw listę bibliotek
COPY requirements.txt .

# Instalujemy dockera do orkiestracji SaaS oraz curl do pobrania compose
RUN apt-get update && apt-get install -y docker.io curl && \
    mkdir -p /usr/local/lib/docker/cli-plugins/ && \
    curl -SL https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose && \
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose && \
    rm -rf /var/lib/apt/lists/*

# Instalujemy biblioteki (gunicorn i uvicorn są w requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy całą resztę aplikacji (to trwa najkrócej)
COPY . .

# Komenda startowa uruchamiająca aplikację na porcie 8080
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080", "main:app"]