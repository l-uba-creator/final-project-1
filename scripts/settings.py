"""Загрузка конфигурации проекта: .env (доступ к БД) + config.yaml (параметры генерации)."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

with open(PROJECT_ROOT / "config" / "config.yaml", "r", encoding="utf-8") as f:
    _CONFIG = yaml.safe_load(f)

GENERATION = _CONFIG["generation"]

DATA_DIR = PROJECT_ROOT / _CONFIG["paths"]["data_dir"]
LOG_DIR = PROJECT_ROOT / _CONFIG["paths"]["log_dir"]
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB", "retail"),
    "user": os.getenv("POSTGRES_USER", "retail_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "retail_pass"),
}
