FROM python:3.11-slim

LABEL maintainer="DiegoSanch18"
LABEL description="LlamaLaunch Web Suite (:3000) - Native Browser App without X11/Linux Desktop"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=3000 \
    GATEWAY_HOST=0.0.0.0 \
    GATEWAY_PORT=8082 \
    DEFAULT_LOCAL_BACKEND=http://host.docker.internal:8080

WORKDIR /app

# Install lightweight dependencies (bottle, requests, psutil)
RUN pip install --no-cache-dir bottle requests psutil

# Copy application files
COPY . /app/

# Expose ports:
# 3000: Web Application UI (Direct browser access)
# 8080: llama-server endpoint
# 8082: LlamaLaunch Inference Gateway
EXPOSE 3000 8080 8082

CMD ["python", "llamaLauncher/server.py"]
