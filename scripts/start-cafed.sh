#!/bin/bash
# Start script for cafed backend

set -e

CAFED_DIR="$(dirname "$0")/../cafed"
CAFED_PORT=${CAFED_PORT:-8001}

echo "🚀 Starting Cafedelia backend server..."
echo "📍 Directory: $CAFED_DIR"
echo "🔌 Port: $CAFED_PORT"

# Check if cafed directory exists
if [ ! -d "$CAFED_DIR" ]; then
    echo "❌ Cafed directory not found at $CAFED_DIR"
    exit 1
fi

# Navigate to cafed directory
cd "$CAFED_DIR"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "❌ Node modules not installed. Run './scripts/setup-cafed.sh' first."
    exit 1
fi

# Export port for the backend
export CAFED_PORT

# Start the backend server
echo "✅ Starting cafed backend on port $CAFED_PORT..."
exec npm run dev
