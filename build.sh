#!/bin/bash
set -e

echo "=== Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== Building Tailwind CSS ==="
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run build
cd ..

echo "=== Build complete ==="