#!/bin/bash
set -e

echo "=== Installing Python dependencies (fresh) ==="
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir

echo "=== Building Tailwind CSS ==="
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run build
cd ..

echo "=== Build complete ==="