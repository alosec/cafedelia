#!/bin/bash
# Setup script for cafed backend

set -e

echo "🚀 Setting up Cafedelia backend (cafed)..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2)
REQUIRED_VERSION="18.0.0"

if ! npx semver -r ">=18.0.0" "$NODE_VERSION" &> /dev/null; then
    echo "❌ Node.js version $NODE_VERSION is too old. Please install Node.js 18+ first."
    exit 1
fi

echo "✅ Node.js version $NODE_VERSION detected"

# Navigate to cafed directory
cd "$(dirname "$0")/../cafed"

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Install TypeScript globally if not available
if ! command -v tsc &> /dev/null; then
    echo "📦 Installing TypeScript globally..."
    npm install -g typescript
fi

# Build TypeScript
echo "🔨 Building TypeScript..."
npm run build

echo "✅ Cafed backend setup complete!"
echo ""
echo "Available commands:"
echo "  npm run dev     - Start in development mode with file watching"
echo "  npm run start   - Start in production mode"
echo "  npm run build   - Build TypeScript"
echo ""
echo "🎯 To start the backend: cd cafed && npm run dev"
