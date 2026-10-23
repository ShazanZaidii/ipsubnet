#!/bin/sh
# Installs the latest ipsubnet binary for macOS or Linux.
#   curl -fsSL https://raw.githubusercontent.com/ShazanZaidii/ipsubnet/main/scripts/install.sh | sh
set -eu

REPO="ShazanZaidii/ipsubnet"

case "$(uname -s)" in
  Linux)  os=linux ;;
  Darwin) os=macos ;;
  *) echo "Unsupported OS: $(uname -s). On Windows use install.ps1." >&2; exit 1 ;;
esac
case "$(uname -m)" in
  x86_64|amd64)  arch=x64 ;;
  arm64|aarch64) arch=arm64 ;;
  *) echo "Unsupported CPU: $(uname -m)" >&2; exit 1 ;;
esac

url="https://github.com/$REPO/releases/latest/download/ipsubnet-$os-$arch"

if [ -n "${IPSUBNET_DIR:-}" ]; then
  dir="$IPSUBNET_DIR"
elif [ -w /usr/local/bin ]; then
  dir=/usr/local/bin
else
  dir="$HOME/.local/bin"
fi
mkdir -p "$dir"

echo "Downloading $url"
tmp="$(mktemp)"
curl -fSL --progress-bar "$url" -o "$tmp"
chmod +x "$tmp"
mv "$tmp" "$dir/ipsubnet"

echo "Installed: $dir/ipsubnet"
case ":$PATH:" in
  *":$dir:"*) "$dir/ipsubnet" --version ;;
  *) echo "Add $dir to your PATH, e.g.:  echo 'export PATH=\"$dir:\$PATH\"' >> ~/.profile" ;;
esac
