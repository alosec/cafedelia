#!/bin/bash
# Setup script for cafed backend - Docker deployment

set -e

echo "🚀 Setting up Cafedelia backend (cafed) with Docker..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null 2>&1 && ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "   Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker detected"

# Navigate to project root
cd "$(dirname "$0")/.."

# Check if Claude projects directory exists
if [ ! -d "$HOME/.claude/projects" ]; then
    echo "⚠️  Warning: Claude projects directory not found at $HOME/.claude/projects"
    echo "   Creating directory for session discovery..."
    mkdir -p "$HOME/.claude/projects"
fi

echo "✅ Claude projects directory available"

# Build Docker image
echo "🔨 Building Docker image..."
docker build -t cafedelia-backend .

# Create logs directory if it doesn't exist
mkdir -p logs

echo "✅ Cafed backend Docker setup complete!"
echo ""
echo "Available commands:"
echo "  docker compose up -d          - Start in production mode (detached)"
echo "  docker compose up cafed       - Start in production mode (foreground)"
echo "  docker compose --profile dev up cafed-dev  - Start in development mode"
echo "  docker compose down           - Stop all services"
echo "  docker compose logs -f cafed  - View logs"
echo ""
echo "🎯 To start the backend: docker compose up -d"
echo "🔍 Check health: curl http://localhost:8001/health"
