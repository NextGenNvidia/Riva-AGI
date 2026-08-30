#!/usr/bin/env bash
# Launch RIVA Web Application & Gateway Server

set -e

# Change directory to project root
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROJECT_ROOT="$( cd "$DIR/.." >/dev/null 2>&1 && pwd )"
cd "$PROJECT_ROOT"

# Initialize virtual environment if missing
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Always sync dependencies (picks up requirements.txt changes)
.venv/bin/pip install -q -r voice_speech/requirements.txt

# Activate virtual environment
source .venv/bin/activate

# Add project root to PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

echo "==============================================================="
echo "  RIVA — Real-Time Voice Interface (Voice/Speech Engine)"
echo "  Server running on http://localhost:8000"
echo "==============================================================="

exec python -m voice_speech.web_server
