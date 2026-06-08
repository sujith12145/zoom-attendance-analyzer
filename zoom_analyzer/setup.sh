#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh  –  One-command setup for Zoom Attendance Analyzer
# Usage:  chmod +x setup.sh && ./setup.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     🎓  Zoom Attendance Analyzer – Setup Script      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Python version check ───────────────────────────────────────────────────
PYTHON=$(which python3 || which python)
PYTHON_VER=$($PYTHON --version 2>&1)
echo "✅ Using: $PYTHON_VER"

# ── Virtual environment ────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment…"
    $PYTHON -m venv venv
fi

echo "🔧 Activating virtual environment…"
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

# ── Dependencies ───────────────────────────────────────────────────────────
echo "📦 Installing dependencies…"
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "✅ All dependencies installed."

# ── Sample data ────────────────────────────────────────────────────────────
echo "🧪 Generating sample data…"
python generate_sample_data.py

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅  Setup complete!                                  ║"
echo "║                                                      ║"
echo "║  To start the application:                           ║"
echo "║    streamlit run app.py                              ║"
echo "║                                                      ║"
echo "║  Then open: http://localhost:8501                    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
