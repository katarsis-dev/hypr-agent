# hypr-agent

Lightweight local agentic AI with a terminal-inspired web UI.  
Optimized for low-spec hardware (Ryzen 5 3500U / 16GB RAM / no dGPU).

```
 _                                                _
| |__  _   _ _ __  _ __       __ _  __ _  ___ _ __ | |_
| '_ \| | | | '_ \| '__|____ / _` |/ _` |/ _ \ '_ \| __|
| | | | |_| | |_) | | |_____| (_| | (_| |  __/ | | | |_
|_| |_|\__, | .__/|_|        \__,_|\__, |\___|_| |_|\__|
       |___/|_|                    |___/
```

## What is this?

A personal AI agent that runs 100% locally on your machine. It can:

- **Think step-by-step** using a ReAct (Reason + Act) loop
- **Use tools**: file operations, shell commands, web search, code execution, system info
- **Switch models on the fly** — pick from any GGUF in your models folder
- **Stream responses** via WebSocket for real-time feedback
- **Remember conversations** (stored as JSON, zero overhead)

No cloud. No API keys. No telemetry. Just your hardware.

## Architecture

```
Browser (localhost:8080)
    │
    ▼ WebSocket
FastAPI Backend (Python, ~50MB RAM)
    │
    ▼ HTTP
llama-server (llama.cpp, model in RAM)
```

## Requirements

- **OS**: Arch Linux (or any Linux distro)
- **Python**: 3.10+
- **llama.cpp**: `llama-server` binary
- **A GGUF model** (7B recommended for agentic use)

## Quick Start (Arch Linux)

### 1. Install dependencies

```bash
# llama.cpp (provides llama-server)
pacman -S llama.cpp

# Python (if not already installed)
pacman -S python python-pip
```

### 2. Clone and set up

```bash
git clone https://github.com/katarsis-dev/hypr-agent.git
cd hypr-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -e .

# Optional: web search support
pip install -e ".[search]"
```

### 3. Get a model

Download a GGUF model to your models directory (default: `~/models`):

```bash
mkdir -p ~/models

# Option A: Download directly from HuggingFace
# (Qwen 2.5 7B Instruct — recommended for agentic tasks)
# https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF

# Option B: If you have Ollama, export a model
# ollama pull qwen2.5:7b-instruct-q4_K_M
```

### 4. Configure

Edit `config.yaml`:

```yaml
llm:
  model_dir: "~/models"
  default_model: "qwen2.5-7b-instruct-q4_k_m.gguf"  # your model filename
  server:
    threads: 6       # adjust for your CPU
    ctx_size: 4096
```

### 5. Run

```bash
chmod +x run.sh
./run.sh
```

Open http://127.0.0.1:8080 in your browser.

## Manual Start (two terminals)

```bash
# Terminal 1: llama-server
llama-server -m ~/models/qwen2.5-7b-instruct-q4_k_m.gguf \
    --port 11434 --threads 6 --ctx-size 4096 --batch-size 512 --mlock

# Terminal 2: hypr-agent
source .venv/bin/activate
python -m uvicorn src.main:app --host 127.0.0.1 --port 8080
```

## Configuration

All settings live in `config.yaml`:

| Setting | Default | Description |
|---------|---------|-------------|
| `llm.model_dir` | `~/models` | Directory containing your GGUF files |
| `llm.default_model` | `qwen2.5-coder-3b...` | Model filename to load |
| `llm.server.threads` | `6` | CPU threads for inference |
| `llm.server.ctx_size` | `4096` | Max context window (tokens) |
| `llm.server.batch_size` | `512` | Batch size for prompt processing |
| `llm.server.mlock` | `true` | Pin model in RAM (prevents swap) |
| `agent.max_steps` | `15` | Max reasoning steps per task |
| `agent.temperature` | `0.7` | LLM creativity (0=deterministic, 1.5=wild) |
| `agent.allow_shell` | `true` | Allow shell command execution |
| `agent.allow_web_search` | `true` | Allow DuckDuckGo search |

## Available Tools

| Tool | Description |
|------|-------------|
| `filesystem` | Read, write, list, search files |
| `shell` | Execute shell commands |
| `system_info` | CPU, RAM, disk, processes, OS info |
| `run_code` | Execute Python code snippets |
| `web_search` | Search the web (DuckDuckGo) |

## Hardware Tuning Guide

### Ryzen 5 3500U (4c/8t, 15W)

```yaml
llm.server.threads: 6      # leave 2 threads for OS responsiveness
llm.server.ctx_size: 4096   # higher = more RAM usage
llm.server.batch_size: 512  # matches Zen+ L2 cache
llm.server.mlock: true      # prevents thrashing when RAM is tight
```

### General guidelines

| RAM | Recommended model size |
|-----|----------------------|
| 8 GB | 1.5B - 3B only |
| 16 GB | 3B - 7B (sweet spot) |
| 32 GB | 7B - 13B |

## Web UI Features

- Dark terminal-inspired theme
- Model selector dropdown (auto-detects GGUFs in your model_dir)
- Real-time agent step visualization (THOUGHT → ACTION → OBSERVATION)
- Temperature / context / thread controls
- Conversation history
- Keyboard shortcut: Enter to send, Shift+Enter for newline

## Project Structure

```
hypr-agent/
├── config.yaml          # All configuration
├── run.sh               # One-command startup
├── pyproject.toml       # Python dependencies
├── src/
│   ├── main.py          # FastAPI app
│   ├── config.py        # Config loader
│   ├── agent/
│   │   ├── loop.py      # ReAct agent loop
│   │   ├── prompt.py    # System prompts
│   │   └── memory.py    # Conversation storage
│   ├── llm/
│   │   └── client.py    # llama-server HTTP client
│   ├── tools/
│   │   ├── filesystem.py
│   │   ├── shell.py
│   │   ├── system.py
│   │   ├── code.py
│   │   └── search.py
│   └── api/
│       ├── routes.py    # REST + WebSocket endpoints
│       └── models.py    # Request/response schemas
├── static/
│   ├── css/style.css    # Dark theme
│   ├── js/app.js        # Frontend logic
│   └── favicon.svg
└── templates/
    └── index.html       # Single-page app
```

## License

MIT
