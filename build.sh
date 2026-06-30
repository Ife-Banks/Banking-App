#!/bin/bash
set -e

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir

echo "=== Building Tailwind CSS ==="
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
fi
chmod +x node_modules/.bin/tailwindcss 2>/dev/null || true
node ./node_modules/.bin/tailwindcss -i ./css/styles.css -o ./js/tailwind.css --minify
cd ..

echo "=== Build complete ==="