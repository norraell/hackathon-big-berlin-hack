#!/bin/bash
# Reload Podman containers with updated .env values
# This script stops, rebuilds, and restarts all services to ensure
# the latest .env configuration is loaded

set -e

echo "🔄 Reloading Podman containers with updated .env values"
echo "========================================================"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "   Please create one from .env.example first"
    exit 1
fi

# Stop all services
echo ""
echo "🛑 Stopping all services..."
podman-compose -f infra/docker-compose.podman.yml down

# Remove any cached images to force rebuild
echo ""
echo "🧹 Cleaning up old images..."
podman-compose -f infra/docker-compose.podman.yml rm -f 2>/dev/null || true

# Rebuild and start services with updated .env
echo ""
echo "🔨 Rebuilding services with latest .env values..."
podman-compose -f infra/docker-compose.podman.yml build --no-cache

echo ""
echo "🚀 Starting services..."
podman-compose -f infra/docker-compose.podman.yml up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Get ngrok URL
echo ""
echo "🔍 Fetching ngrok URL..."
sleep 3

# Try to get ngrok URL from API
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | grep -o 'https://[^"]*' | head -1)

if [ -z "$NGROK_URL" ]; then
    echo "⚠️  Could not automatically fetch ngrok URL"
    echo "   Please check http://localhost:4040 to get your ngrok URL"
else
    echo "✅ Ngrok URL: $NGROK_URL"
fi

echo ""
echo "✅ Services reloaded successfully!"
echo ""
echo "📊 Service URLs:"
echo "   - Application (local):  http://localhost:8000"
echo "   - Application (public): $NGROK_URL"
echo "   - Ngrok Dashboard:      http://localhost:4040"
echo "   - PostgreSQL:           localhost:5432"
echo ""
echo "📋 View logs:"
echo "   podman-compose -f infra/docker-compose.podman.yml logs -f"
echo ""
echo "🔍 Check service status:"
echo "   podman-compose -f infra/docker-compose.podman.yml ps"