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

### 1. Install llama.cpp

You need the `llama-server` binary. Choose one method:

#### Option A: Build from source (recommended — most reliable)

```bash
cd ~/Dev  # or wherever you keep projects
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j$(nproc)

# Binary will be at: ~/Dev/llama.cpp/build/bin/llama-server
# run.sh auto-detects this path
```

To update later:
```bash
cd ~/Dev/llama.cpp
git pull
cmake --build build --config Release -j$(nproc)
```

#### Option B: Pacman (if available in repos)

```bash
pacman -S llama.cpp
```

#### Option C: AUR

```bash
yay -S llama-cpp-git
```

> **Note:** AUR packages can break after updates (shared library mismatches).
> If you get `symbol lookup error` or `libcudart.so` errors, switch to Option A.

### 2. Install Python

```bash
pacman -S python python-pip
```

### 3. Clone and set up

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

### 4. Get a model

Download a GGUF model to your models directory (default: `~/models`):

```bash
mkdir -p ~/models

# Option A: Download directly from HuggingFace
# (Qwen 2.5 7B Instruct — recommended for agentic tasks)
# https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF

# Option B: If you have Ollama, export a model
# ollama pull qwen2.5:7b-instruct-q4_K_M
```

### 5. Configure

Edit `config.yaml`:

```yaml
llm:
  model_dir: "~/models"
  default_model: "qwen2.5-7b-instruct-q4_k_m.gguf"  # your model filename
  server:
    threads: 6       # adjust for your CPU
    ctx_size: 4096
```

### 6. Run

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

## llama.cpp Configuration

### Binary Detection

`run.sh` searches these paths in order:
1. System PATH (`llama-server`)
2. `~/Dev/llama.cpp/build/bin/llama-server` (source build)
3. `~/llama.cpp/build/bin/llama-server` (source build alt)
4. `/opt/llama-cpp/bin/llama-server` (AUR CUDA package)
5. `/usr/local/bin/llama-server` (manual install)
6. `/usr/bin/llama-server` (pacman)

### Server Flags

| Flag | Default | Description |
|------|---------|-------------|
| `-m <path>` | from config.yaml | Path to the GGUF model file |
| `--port` | `11434` | Port for the OpenAI-compatible API |
| `--threads` | `6` | CPU threads for inference (leave 2 for OS) |
| `--ctx-size` | `4096` | Max context window in tokens |
| `--batch-size` | `512` | Tokens processed per batch (affects prompt processing speed) |
| `--mlock` | enabled | Lock model in RAM, prevent swap |

### Performance Tuning

```bash
# For Ryzen 5 3500U (4c/8t, 15W):
llama-server -m ~/models/your-model.gguf \
    --threads 6 \
    --ctx-size 4096 \
    --batch-size 512 \
    --mlock \
    --mmap

# For faster responses (smaller context, less accuracy):
    --ctx-size 2048

# For longer conversations (more RAM):
    --ctx-size 8192

# KV cache quantization (saves ~30% RAM):
    --cache-type-k q4_0 --cache-type-v q4_0
```

### Model Recommendations

| Model | Size | RAM | Speed (Ryzen 5 3500U) | Best for |
|-------|------|-----|----------------------|----------|
| Qwen 2.5 7B Instruct Q4_K_M | 4.4 GB | ~5.2 GB | 6-10 tok/s | Agentic tasks, tool use |
| Qwen 2.5 Coder 3B Q4_K_M | 2.0 GB | ~2.8 GB | 12-18 tok/s | Code generation |
| Qwen 2.5 1.5B Instruct Q4_K_M | 1.0 GB | ~1.5 GB | 20-30 tok/s | Quick Q&A, routing |
| Qwen 3.5 0.8B Q4_K_M | 0.5 GB | ~0.8 GB | 30-50 tok/s | Intent detection, classification |

### Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `llama-server not found` | Binary not in search paths | Build from source (see Quick Start step 1) |
| `symbol lookup error: undefined symbol` | AUR package lib mismatch | Remove AUR package, build from source |
| `libcudart.so: cannot open` | CUDA package but no NVIDIA GPU | `pacman -R llama-cpp-cuda-git`, use CPU build |
| `mlock failed` | Insufficient memory lock limit | `ulimit -l unlimited` or edit `/etc/security/limits.conf` |
| `model not found` | Wrong filename in config.yaml | Check `ls ~/models/` and update `default_model` |

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
| `git` | Git operations: status, log, diff, commit, branch |
| `screenshot` | Take screenshots (full/region/window) via grim+slurp |
| `hyprland` | Control Hyprland: windows, workspaces, focus, resize |
| `pdf_reader` | Extract text from PDF files |
| `document_convert` | Convert between PDF/DOCX/MD/TXT/HTML/ODT |
| `clipboard` | Read/write Wayland clipboard |
| `notify` | Send desktop notifications |
| `weather` | Get weather for any location |

## Adding New Skills

Two ways to add skills — no restart needed, just add the file and restart the server.

### Way 1: YAML skill (easiest — no Python)

Create a `.yaml` file in the `skills/` folder:

```yaml
# skills/my_skill.yaml
name: my_skill
description: What this skill does — the agent reads this.
timeout: 30

commands:
  action_one: "echo 'Hello ${input}'"
  action_two: "ls ${path}"

default_action: action_one
```

That's it. The agent auto-detects it on next startup.

See `skills/_template.yaml` for a full reference.

### Way 2: Python tool (more control)

Drop a `.py` file in `src/tools/`:

```python
# src/tools/my_tool.py
from __future__ import annotations
from typing import Any

class MyTool:
    name = "my_tool"
    description = "What this tool does."
    input_schema = '{"param": "description"}'

    async def execute(self, **kwargs: Any) -> str:
        param = kwargs.get("param", "")
        return f"Result: {param}"
```

No imports or registration needed — auto-discovered on startup.

See `src/tools/_template.py` for a full reference.

### Rules

- Files starting with `_` are ignored (use for templates/drafts)
- Each tool needs: `name`, `description`, `input_schema`, `execute()`
- YAML skills are great for wrapping shell commands
- Python tools are better when you need logic, async, or error handling

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
- **Conversation history sidebar** — click to resume past conversations
- Model selector dropdown (auto-detects GGUFs in your model_dir)
- Real-time agent step visualization (THOUGHT → ACTION → OBSERVATION)
- Temperature / context / thread controls
- Collapsible sidebar (toggle with ☰ button)
- New conversation button (+)
- Keyboard shortcut: Enter to send, Shift+Enter for newline

## Project Structure

```
hypr-agent/
├── config.yaml          # All configuration
├── run.sh               # One-command startup
├── pyproject.toml       # Python dependencies
├── skills/              # ← Drop YAML skills here (auto-detected)
│   ├── _template.yaml   # Template for new YAML skills
│   ├── clipboard.yaml   # Wayland clipboard
│   ├── notify.yaml      # Desktop notifications
│   └── weather.yaml     # Weather via wttr.in
├── src/
│   ├── main.py          # FastAPI app
│   ├── config.py        # Config loader
│   ├── agent/
│   │   ├── loop.py      # ReAct agent loop
│   │   ├── prompt.py    # System prompts
│   │   └── memory.py    # Conversation storage
│   ├── llm/
│   │   └── client.py    # llama-server HTTP client
│   ├── tools/           # ← Drop Python tools here (auto-detected)
│   │   ├── _template.py # Template for new Python tools
│   │   ├── filesystem.py
│   │   ├── shell.py
│   │   ├── system.py
│   │   ├── code.py
│   │   ├── search.py
│   │   └── yaml_skill.py # YAML skill engine
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
