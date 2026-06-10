# LlamaLaunch 🦙🚀

LlamaLaunch is a Desktop Inference Suite that provides an easy-to-use graphical interface (GUI) to manage and run local large language models (LLMs) via `llama.cpp`.

## Features
- **Local Inference**: Run powerful AI models completely offline on your own hardware.
- **Model Management**: Download, manage, and categorize your `.gguf` models easily.
- **Hardware Acceleration**: Auto-detects and optimizes parameters for your CPU, Nvidia CUDA, or Vulkan.
- **Docker & TrueNAS Support**: Run the application fully containerized via WebTop (accessible from your browser).

## Running via Docker (TrueNAS / Server)
To run this application headless on a NAS like TrueNAS Scale or an Ubuntu server, you can use the provided Docker setup which utilizes a WebTop container to expose the graphical interface over a web browser.

1. Clone the repository:
   ```bash
   git clone https://github.com/DiegoSanch18/LlamaLaunch.git
   cd LlamaLaunch
   ```

2. Start the container:
   ```bash
   docker-compose up -d
   ```

3. Access the graphical interface by opening your browser and navigating to:
   ```
   http://YOUR_SERVER_IP:3000
   ```

4. Once inside the WebTop desktop, open the terminal and run:
   ```bash
   python3 /app/llamaLauncher/app.py
   ```

## Running Natively (Windows)
1. Ensure you have Python installed.
2. Install the requirements (`pywebview`, `requests`, `psutil`).
3. Download the `llama.cpp` Windows binaries and place them in the `llamaLauncher/bin/llama.cpp` folder.
4. Run:
   ```cmd
   python llamaLauncher/app.py
   ```