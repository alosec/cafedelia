#!/bin/bash
# Test script for cafed backend

set -e

echo "🧪 Testing Cafedelia Backend..."

# Set default port
CAFED_PORT=${CAFED_PORT:-8001}
BASE_URL="http://localhost:$CAFED_PORT"

echo "📍 Testing against $BASE_URL"

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local description=$2
    
    echo -n "  Testing $description... "
    
    if curl -s -f "$BASE_URL$endpoint" > /dev/null; then
        echo "✅ OK"
        return 0
    else
        echo "❌ FAIL"
        return 1
    fi
}

# Function to test endpoint with JSON output
test_endpoint_json() {
    local endpoint=$1
    local description=$2
    
    echo -n "  Testing $description... "
    
    local response=$(curl -s -f "$BASE_URL$endpoint" 2>/dev/null)
    if [ $? -eq 0 ] && echo "$response" | jq . > /dev/null 2>&1; then
        echo "✅ OK"
        echo "    Response: $(echo "$response" | jq -c .)"
        return 0
    else
        echo "❌ FAIL"
        return 1
    fi
}

# Check if backend is running
echo -n "🔍 Checking if cafed backend is running... "
if curl -s -f "$BASE_URL/health" > /dev/null; then
    echo "✅ Running"
else
    echo "❌ Not running"
    echo "Please start the backend first:"
    echo "  ./scripts/start-cafed.sh"
    exit 1
fi

echo ""
echo "🚀 Running API tests..."

# Test health endpoint
test_endpoint_json "/health" "Health check"

# Test sessions endpoint
test_endpoint_json "/api/sessions" "Sessions list"

# Test projects endpoint  
test_endpoint_json "/api/projects" "Projects list"

# Test summary endpoint
test_endpoint_json "/api/summary" "Session summary"

echo ""
echo "✅ All tests completed!"
echo ""
echo "💡 To see detailed responses:"
echo "  curl $BASE_URL/health | jq ."
echo "  curl $BASE_URL/api/sessions | jq ."
echo "  curl $BASE_URL/api/projects | jq ."
echo "  curl $BASE_URL/api/summary | jq ."
