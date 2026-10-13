#!/usr/bin/env python3
"""Prepare writable directories without opening or changing a database."""
import os
from pathlib import Path
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[2]
load_dotenv(root / ".env", override=False)
value = Path(os.environ.get("APP_RUNTIME_DIR", "runtime")).expanduser()
runtime = value if value.is_absolute() else root / value
for name in ("", "media", "private_credentials", "logs", "static"):
    directory = runtime / name
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
print("Runtime directories prepared; no database changes made.")
