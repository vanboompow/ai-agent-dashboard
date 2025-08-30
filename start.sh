#!/bin/bash

echo "🚀 Starting AI Agent Dashboard..."
echo "================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
fi

# Build and start services
echo "🔨 Building Docker images..."
docker-compose build

echo "🎯 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "✅ Checking service health..."
curl -s http://localhost:8000/healthz > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Backend API is running"
else
    echo "⚠️  Backend API might still be starting..."
fi

echo ""
echo "================================"
echo "✅ AI Agent Dashboard is running!"
echo ""
echo "🌐 Frontend: http://localhost:5173"
echo "📡 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"
echo "================================"