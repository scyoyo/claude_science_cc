#!/bin/bash

# Virtual Lab Setup Verification Script

echo "================================================"
echo "Virtual Lab - Setup Verification"
echo "================================================"
echo ""

# Check if Docker is running
echo "1. Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi
echo "✅ Docker is running"
echo ""

# Check if docker-compose is available
echo "2. Checking docker-compose..."
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install docker-compose."
    exit 1
fi
echo "✅ docker-compose is available"
echo ""

# Navigate to project directory
cd single-user-local

# Start services
echo "3. Starting services..."
docker-compose up -d
echo ""

# Wait for services to be ready
echo "4. Waiting for services to be ready..."
sleep 10
echo ""

# Check backend health
echo "5. Checking backend health..."
BACKEND_HEALTH=$(curl -s http://localhost:8000/health | grep -o "healthy")
if [ "$BACKEND_HEALTH" == "healthy" ]; then
    echo "✅ Backend is healthy"
else
    echo "❌ Backend health check failed"
    docker-compose logs backend
    exit 1
fi
echo ""

# Check if database file was created
echo "6. Checking database..."
if [ -f "backend/data/virtuallab.db" ]; then
    echo "✅ Database file created"
else
    echo "❌ Database file not found"
    exit 1
fi
echo ""

# Run tests
echo "7. Running tests..."
docker-compose exec -T backend pytest tests/ -v
if [ $? -eq 0 ]; then
    echo "✅ All tests passed"
else
    echo "❌ Some tests failed"
    exit 1
fi
echo ""

# Test API endpoints
echo "8. Testing API endpoints..."

# Test create team
TEAM_RESPONSE=$(curl -s -X POST http://localhost:8000/api/teams/ \
    -H "Content-Type: application/json" \
    -d '{"name": "Test Team", "description": "A test team"}')
TEAM_ID=$(echo $TEAM_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

if [ ! -z "$TEAM_ID" ]; then
    echo "✅ Create team endpoint works (Team ID: $TEAM_ID)"
else
    echo "❌ Create team endpoint failed"
    exit 1
fi

# Test create agent
AGENT_RESPONSE=$(curl -s -X POST http://localhost:8000/api/agents/ \
    -H "Content-Type: application/json" \
    -d "{
        \"team_id\": \"$TEAM_ID\",
        \"name\": \"Dr. Smith\",
        \"title\": \"Research Lead\",
        \"expertise\": \"Machine Learning\",
        \"goal\": \"Develop ML models\",
        \"role\": \"Lead research\",
        \"model\": \"gpt-4\"
    }")
AGENT_ID=$(echo $AGENT_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

if [ ! -z "$AGENT_ID" ]; then
    echo "✅ Create agent endpoint works (Agent ID: $AGENT_ID)"
else
    echo "❌ Create agent endpoint failed"
    exit 1
fi

# Test get team with agents
TEAM_WITH_AGENTS=$(curl -s http://localhost:8000/api/teams/$TEAM_ID)
if echo $TEAM_WITH_AGENTS | grep -q "Dr. Smith"; then
    echo "✅ Get team with agents works"
else
    echo "❌ Get team with agents failed"
    exit 1
fi

echo ""
echo "================================================"
echo "✅ All checks passed!"
echo "================================================"
echo ""
echo "Your Virtual Lab backend is ready!"
echo ""
echo "Access points:"
echo "  - Backend API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Frontend: http://localhost:3000 (not yet implemented)"
echo ""
echo "To stop services: docker-compose down"
echo "To view logs: docker-compose logs -f"
echo ""
