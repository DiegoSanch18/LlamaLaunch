FROM lscr.io/linuxserver/webtop:ubuntu-xfce

# Set environment variables for non-interactive installs
ENV DEBIAN_FRONTEND=noninteractive

# Install Python and dependencies for PyWebView on Ubuntu (GTK / WebKit2 4.1)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-tk \
    python3-gi \
    gir1.2-webkit2-4.1 \
    libwebkit2gtk-4.1-0 \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy the application files
COPY . /app/

# Install python requirements (pywebview, requests, psutil)
RUN pip3 install --no-cache-dir pywebview requests psutil

# Download Linux build of llama-server (fallback if not present)
RUN mkdir -p /app/llamaLauncher/bin/llama.cpp/llama-bin-ubuntu-x64 && \
    cd /tmp && \
    (wget https://github.com/ggerganov/llama.cpp/releases/download/b3000/llama-b3000-bin-ubuntu-x64.zip || true) && \
    (unzip -o llama-b3000-bin-ubuntu-x64.zip -d /app/llamaLauncher/bin/llama.cpp/llama-bin-ubuntu-x64 || true) && \
    (chmod +x /app/llamaLauncher/bin/llama.cpp/llama-bin-ubuntu-x64/llama-server || true) && \
    rm -f /tmp/llama-b3000-bin-ubuntu-x64.zip

# Ports exposed:
# 3000: Webtop desktop interface
# 8080: llama-server endpoint
# 8081: LlamaLaunch Inference Gateway
EXPOSE 3000 8080 8081

# The container will start the XFCE desktop automatically.
# Inside the web interface, users can open terminal and run:
# python3 /app/llamaLauncher/app.py
