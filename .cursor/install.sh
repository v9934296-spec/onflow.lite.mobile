#!/usr/bin/env bash
# Cloud Agent install script for OnFlow Lite.
# Idempotent: safe to re-run. Sets up the Expo mobile app (root) and the
# FastAPI + ARQ backend (services/api) so both can run against local SQLite.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- System dependency: python3.12-venv (not in the default base image) ---
if ! dpkg -s python3.12-venv >/dev/null 2>&1; then
  echo "Installing python3.12-venv..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv
fi

# --- Local env files (dev defaults; real secrets never committed) ---
[ -f .env ] || cp .env.example .env
[ -f services/api/.env ] || cp services/api/.env.example services/api/.env

# --- Frontend (Expo Router / React Native) ---
npm ci

# --- Backend (FastAPI + ARQ worker) ---
cd services/api
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "Install complete."
