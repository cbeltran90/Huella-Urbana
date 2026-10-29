#!/usr/bin/env bash
# Descarga el binario standalone de Tailwind CSS a bin/tailwindcss
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${TAILWIND_VERSION:-v4.1.11}"   # tiene que ser 4.x

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"
case "$os" in
  linux)  os=linux ;;
  darwin) os=macos ;;
  *) echo "Sistema no soportado: $os"; exit 1 ;;
esac
case "$arch" in
  x86_64|amd64)  arch=x64 ;;
  aarch64|arm64) arch=arm64 ;;
  *) echo "Arquitectura no soportada: $arch"; exit 1 ;;
esac

mkdir -p bin
curl -fsSL -o bin/tailwindcss \
  "https://github.com/tailwindlabs/tailwindcss/releases/download/${VERSION}/tailwindcss-${os}-${arch}"
chmod +x bin/tailwindcss
./bin/tailwindcss --help | head -n 1
