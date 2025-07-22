#!/bin/bash
# Start script for cafed backend - Docker container management

set -e

PROJECT_ROOT="$(dirname "$0")/.."
CAFED_PORT=${CAFED_PORT:-8001}
MODE=${1:-production}

echo "🚀 Starting Cafedelia backend server with Docker..."
echo "📍 Project root: $PROJECT_ROOT"
echo "🔌 Port: $CAFED_PORT"
echo "🎯 Mode: $MODE"

# Navigate to project root
cd "$PROJECT_ROOT"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please run './scripts/setup-cafed.sh' first."
    exit 1
fi

# Function to check if container is running
is_container_running() {
    docker ps --format "table {{.Names}}" | grep -q "cafedelia-backend\|cafedelia-dev"
}

# Function to start production container
start_production() {
    echo "✅ Starting cafed backend in production mode..."
    docker compose up -d cafed
    
    # Wait for health check
    echo "🔍 Waiting for health check..."
    sleep 5
    
    if curl -s http://localhost:$CAFED_PORT/health > /dev/null; then
        echo "✅ Backend is healthy and running on http://localhost:$CAFED_PORT"
    else
        echo "⚠️  Backend started but health check failed. Check logs with: docker compose logs cafed"
    fi
}

# Function to start development container
start_development() {
    echo "✅ Starting cafed backend in development mode with hot reload..."
    docker compose --profile dev up cafed-dev
}

# Function to stop containers
stop_containers() {
    echo "🛑 Stopping cafed backend containers..."
    docker compose down
}

# Handle stop command first
if [ "$MODE" = "stop" ]; then
    stop_containers
    exit 0
fi

# Check if container is already running
if is_container_running; then
    echo "ℹ️  Cafed backend is already running."
    echo "   To restart: docker compose restart"
    echo "   To stop: docker compose down"
    echo "   To view logs: docker compose logs -f cafed"
    exit 0
fi

# Start based on mode
case "$MODE" in
    "production"|"prod")
        start_production
        ;;
    "development"|"dev")
        start_development
        ;;
    "stop")
        stop_containers
        ;;
    *)
        echo "Usage: $0 [production|development|stop]"
        echo "  production  - Start in production mode (default)"
        echo "  development - Start in development mode with hot reload"
        echo "  stop        - Stop all containers"
        exit 1
        ;;
esac
