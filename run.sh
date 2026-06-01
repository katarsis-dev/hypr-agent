#!/usr/bin/env bash
# hypr-agent — one-command startup
# Starts llama-server + FastAPI backend

set -e

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Load config
CONFIG_FILE="$(dirname "$0")/config.yaml"
MODEL_DIR=$(grep 'model_dir:' "$CONFIG_FILE" | awk '{print $2}' | tr -d '"' | sed "s|~|$HOME|")
DEFAULT_MODEL=$(grep 'default_model:' "$CONFIG_FILE" | awk '{print $2}' | tr -d '"')
THREADS=$(grep 'threads:' "$CONFIG_FILE" | head -1 | awk '{print $2}')
CTX_SIZE=$(grep 'ctx_size:' "$CONFIG_FILE" | awk '{print $2}')
BATCH_SIZE=$(grep 'batch_size:' "$CONFIG_FILE" | awk '{print $2}')
MLOCK=$(grep 'mlock:' "$CONFIG_FILE" | awk '{print $2}')
LLM_PORT=$(grep -A5 'server:' "$CONFIG_FILE" | grep 'port:' | head -1 | awk '{print $2}')
APP_PORT=$(grep -A2 '^app:' "$CONFIG_FILE" | grep 'port:' | awk '{print $2}')

# Defaults
THREADS=${THREADS:-6}
CTX_SIZE=${CTX_SIZE:-4096}
BATCH_SIZE=${BATCH_SIZE:-512}
LLM_PORT=${LLM_PORT:-11434}
APP_PORT=${APP_PORT:-8080}
MODEL_PATH="${MODEL_DIR}/${DEFAULT_MODEL}"

echo -e "${CYAN}"
echo '  _                                                _   '
echo ' | |__  _   _ _ __  _ __       __ _  __ _  ___ _ __ | |_ '
echo ' | '\''_ \| | | | '\''_ \| '\''__|____ / _` |/ _` |/ _ \ '\''_ \| __|'
echo ' | | | | |_| | |_) | | |_____| (_| | (_| |  __/ | | | |_ '
echo ' |_| |_|\__, | .__/|_|        \__,_|\__, |\___|_| |_|\__|'
echo '        |___/|_|                    |___/                '
echo -e "${NC}"

# Check model exists
if [ ! -f "$MODEL_PATH" ]; then
    echo -e "${RED}Error: Model not found at ${MODEL_PATH}${NC}"
    echo -e "${YELLOW}Available models in ${MODEL_DIR}:${NC}"
    ls "$MODEL_DIR"/*.gguf 2>/dev/null || echo "  (none found)"
    echo ""
    echo "Download a model:"
    echo "  ollama pull qwen2.5:7b-instruct-q4_K_M"
    echo "  or download GGUF from https://huggingface.co"
    exit 1
fi

# Find llama-server binary (handles different install locations)
LLAMA_SERVER=""
SEARCH_PATHS=(
    "$HOME/Dev/llama.cpp/build/bin/llama-server"
    "$HOME/llama.cpp/build/bin/llama-server"
    "/opt/llama-cpp/bin/llama-server"
    "/usr/local/bin/llama-server"
    "/usr/bin/llama-server"
)

if command -v llama-server &> /dev/null; then
    LLAMA_SERVER="llama-server"
else
    for path in "${SEARCH_PATHS[@]}"; do
        if [ -x "$path" ]; then
            LLAMA_SERVER="$path"
            break
        fi
    done
fi

if [ -z "$LLAMA_SERVER" ]; then
    echo -e "${RED}Error: llama-server not found${NC}"
    echo "Searched: PATH, ${SEARCH_PATHS[*]}"
    echo ""
    echo "Build from source (recommended):"
    echo "  git clone https://github.com/ggerganov/llama.cpp.git"
    echo "  cd llama.cpp && cmake -B build -DCMAKE_BUILD_TYPE=Release"
    echo "  cmake --build build --config Release -j\$(nproc)"
    echo ""
    echo "Or install: pacman -S llama.cpp"
    exit 1
fi
echo -e "  Binary: ${LLAMA_SERVER}"

# Check Python
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python not found${NC}"
    exit 1
fi
PYTHON=$(command -v python3 || command -v python)

# Build llama-server flags
LLAMA_FLAGS="-m ${MODEL_PATH} --port ${LLM_PORT} --threads ${THREADS} --ctx-size ${CTX_SIZE} --batch-size ${BATCH_SIZE}"
if [ "$MLOCK" = "true" ]; then
    LLAMA_FLAGS="${LLAMA_FLAGS} --mlock"
fi

echo -e "${GREEN}Starting llama-server...${NC}"
echo -e "  Model: ${DEFAULT_MODEL}"
echo -e "  Threads: ${THREADS} | Context: ${CTX_SIZE} | Port: ${LLM_PORT}"
echo ""

# Start llama-server in background
$LLAMA_SERVER $LLAMA_FLAGS &
LLAMA_PID=$!

# Wait for llama-server to be ready
echo -n "Waiting for llama-server..."
for i in $(seq 1 30); do
    if curl -s "http://127.0.0.1:${LLM_PORT}/health" > /dev/null 2>&1; then
        echo -e " ${GREEN}ready!${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

echo ""
echo -e "${GREEN}Starting hypr-agent backend...${NC}"
echo -e "  URL: http://127.0.0.1:${APP_PORT}"
echo ""
echo -e "${CYAN}Open your browser: http://127.0.0.1:${APP_PORT}${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop everything.${NC}"
echo ""

# Trap Ctrl+C to kill both processes
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $LLAMA_PID 2>/dev/null
    wait $LLAMA_PID 2>/dev/null
    echo -e "${GREEN}Done.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start FastAPI
$PYTHON -m uvicorn src.main:app --host 127.0.0.1 --port ${APP_PORT}

# If uvicorn exits, clean up
cleanup
