FROM lscr.io/linuxserver/webtop:ubuntu-xfce

# Set environment variables for non-interactive installs
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and dependencies for PyWebView
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-tk \
    libwebkit2gtk-4.0-37 \
    gir1.2-webkit2-4.0 \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy the application files
COPY . /app/

# Install python requirements (pywebview, requests, psutil)
RUN pip3 install pywebview requests psutil

# Download Linux build of llama-server (fallback if not present)
RUN mkdir -p /app/llamaLauncher/bin/llama.cpp/llama-bin-ubuntu-x64 && \
    cd /tmp && \
    wget https://github.com/ggerganov/llama.cpp/releases/download/b3000/llama-b3000-bin-ubuntu-x64.zip || true && \
    unzip llama-b3000-bin-ubuntu-x64.zip -d /app/llamaLauncher/bin/llama.cpp/llama-bin-ubuntu-x64 || true && \
    chmod +x /app/llamaLauncher/bin/llama.cpp/llama-bin-ubuntu-x64/llama-server || true

# Webtop exposes port 3000 (web interface for desktop)
EXPOSE 3000

# The container will start the XFCE desktop automatically.
# Inside the web interface, users can open terminal and run:
# python3 /app/llamaLauncher/app.py
