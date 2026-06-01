"""Configuration loader — reads config.yaml and exposes typed settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator


CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 11434
    threads: int = 6
    ctx_size: int = 4096
    batch_size: int = 512
    mlock: bool = True
    mmap: bool = True


class LLMConfig(BaseModel):
    model_dir: str = "~/models"
    default_model: str = "qwen2.5-coder-3b-instruct-q4_k_m.gguf"
    server: ServerConfig = ServerConfig()

    @field_validator("model_dir")
    @classmethod
    def expand_home(cls, v: str) -> str:
        return str(Path(v).expanduser())


class AgentConfig(BaseModel):
    max_steps: int = 15
    max_output_chars: int = 4000
    timeout_seconds: int = 180
    temperature: float = 0.7
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    allowed_directories: list[str] = ["~"]
    allow_shell: bool = True
    allow_web_search: bool = True

    @field_validator("allowed_directories")
    @classmethod
    def expand_dirs(cls, v: list[str]) -> list[str]:
        return [str(Path(d).expanduser()) for d in v]


class RouterConfig(BaseModel):
    code_keywords: list[str] = []
    simple_task_max_words: int = 10


class AppConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080


class Config(BaseModel):
    app: AppConfig = AppConfig()
    llm: LLMConfig = LLMConfig()
    agent: AgentConfig = AgentConfig()
    router: RouterConfig = RouterConfig()


def load_config(path: Path | None = None) -> Config:
    """Load configuration from YAML file."""
    config_path = path or CONFIG_PATH
    if config_path.exists():
        with open(config_path) as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return Config(**data)
    return Config()


config = load_config()
