#!/usr/bin/env bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Auto-escalate to sudo if not root
if [ "$EUID" -ne 0 ]; then
  echo "[*] Escalating to sudo..."
  exec sudo -E PATH="$PATH" PYTHONPATH="$DIR/src:$PYTHONPATH" "$0" "$@"
fi

export PYTHONPATH="$DIR/src:$PYTHONPATH"
python3 "$DIR/src/main.py" "$@"
