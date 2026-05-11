#!/usr/bin/env bash
set -euo pipefail

# PumpGuard — one-liner install
# curl -fsSL https://raw.githubusercontent.com/yksanjo/pumpguard/main/scripts/install.sh | bash

REPO="yksanjo/pumpguard"
BRANCH="main"

echo "🛡️  Installing PumpGuard..."

# Check Python
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
        MAJOR=${VER%.*}
        MINOR=${VER#*.}
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "✗ Python >=3.10 required. Install it first."
    exit 1
fi
echo "✓ Found $($PYTHON --version)"

# Clone or pull
TARGET="$HOME/.pumpguard"
if [ -d "$TARGET" ]; then
    echo "Updating existing installation..."
    cd "$TARGET" && git pull origin "$BRANCH"
else
    echo "Cloning into $TARGET..."
    git clone --branch "$BRANCH" "https://github.com/$REPO.git" "$TARGET"
    cd "$TARGET"
fi

# Create venv
if [ ! -d "$TARGET/.venv" ]; then
    "$PYTHON" -m venv "$TARGET/.venv"
fi
source "$TARGET/.venv/bin/activate"
pip install -e . > /dev/null 2>&1

# Symlink to ~/bin or /usr/local/bin
if [ -d "$HOME/bin" ]; then
    ln -sf "$TARGET/.venv/bin/pumpguard" "$HOME/bin/pumpguard"
    echo "✓ Linked to ~/bin/pumpguard"
elif [ -w "/usr/local/bin" ]; then
    ln -sf "$TARGET/.venv/bin/pumpguard" "/usr/local/bin/pumpguard"
    echo "✓ Linked to /usr/local/bin/pumpguard"
else
    echo ""
    echo "Add to your PATH:"
    echo "  export PATH=\"\$TARGET/.venv/bin:\$PATH\""
fi

echo ""
echo "🛡️  PumpGuard installed! Run:"
echo "  pumpguard doctor"
echo "  pumpguard watch --window 60 --dry-run"
