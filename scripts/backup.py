#!/usr/bin/env python3
"""Backup script for Gracia Clothing database and uploads."""

import os
import sys
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BASE_DIR / "backups"
DB_PATH = BASE_DIR / "backend" / "gracia.db"
UPLOADS_DIR = BASE_DIR / "uploads"
ENV_PATH = BASE_DIR / ".env"


def load_env():
    if not ENV_PATH.exists():
        return {}
    env = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def backup_sqlite():
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_DIR / ts
    backup_dir.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        shutil.copy2(DB_PATH, backup_dir / "gracia.db")
        print(f"  -> SQLite: {backup_dir / 'gracia.db'}")

    if UPLOADS_DIR.exists():
        shutil.copytree(UPLOADS_DIR, backup_dir / "uploads", dirs_exist_ok=True)
        print(f"  -> Uploads: {backup_dir / 'uploads'}")

    return backup_dir


def backup_postgres(env: dict):
    host = env.get("DB_HOST", "localhost")
    port = env.get("DB_PORT", "5432")
    name = env.get("DB_NAME", "gracia_clothing")
    user = env.get("DB_USER", "postgres")
    password = env.get("DB_PASSWORD", "")

    backup_dir = BACKUP_DIR / "postgres"
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dump_path = backup_dir / f"dump_{ts}.sql"

    os.environ["PGPASSWORD"] = password
    cmd = [
        "pg_dump",
        "--host", host,
        "--port", port,
        "--username", user,
        "--dbname", name,
        "--file", str(dump_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  -> PostgreSQL dump: {dump_path}")
        return dump_path
    else:
        print(f"  !! PostgreSQL backup failed: {result.stderr}")
        return None


def cleanup(keep: int = 7):
    entries = sorted(BACKUP_DIR.iterdir()) if BACKUP_DIR.exists() else []
    for entry in entries[:-keep] if len(entries) > keep else []:
        if entry.is_dir():
            shutil.rmtree(entry)
            print(f"  -> Cleaned old backup: {entry}")


def main():
    print(f"[Backup] Starting at {datetime.utcnow().isoformat()}")
    print(f"[Backup] Target: {BASE_DIR}")

    backup_dir = backup_sqlite()
    env = load_env()

    if env.get("DATABASE_URL", "").startswith("postgresql"):
        print("[Backup] Detected PostgreSQL, performing pg_dump…")
        backup_postgres(env)
    else:
        print("[Backup] Using SQLite (backup completed)")

    cleanup(keep=7)
    print(f"[Backup] Done — stored in {BACKUP_DIR}")


if __name__ == "__main__":
    main()
