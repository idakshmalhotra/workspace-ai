#!/bin/bash
# Build script for Render deployment

set -e  # Exit on error

echo "🔧 Upgrading pip..."
pip install --upgrade pip setuptools wheel

echo "🔍 Checking Python version..."
python --version

echo "📦 Installing dependencies (without pandas to avoid compilation issues)..."
pip install -r requirements.txt

echo "📦 Attempting to install pandas with pre-built wheels only..."
# Try to install pandas only if pre-built wheels are available
pip install pandas==2.1.4 --only-binary :all: || echo "⚠️  pandas installation skipped (will use fallback logic)"

echo "✅ Build complete!"

