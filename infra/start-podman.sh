#!/bin/bash
# Quick start script for Podman with ngrok integration

set -e

echo "🚀 Starting AI Claims Intake System with Podman and Ngrok"
echo "=========================================================="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file. Please edit it with your credentials:"
    echo "   - NGROK_AUTHTOKEN (get from https://dashboard.ngrok.com/get-started/your-authtoken)"
    echo "   - TWILIO_ACCOUNT_SID"
    echo "   - TWILIO_AUTH_TOKEN"
    echo "   - GEMINI_API_KEY"
    echo "   - GRADIUM_API_KEY"
    echo ""
    read -p "Press Enter after updating .env file..."
fi

# Check if NGROK_AUTHTOKEN is set
if ! grep -q "NGROK_AUTHTOKEN=.*[^=]" .env; then
    echo "❌ NGROK_AUTHTOKEN not set in .env file"
    echo "   Get your token from: https://dashboard.ngrok.com/get-started/your-authtoken"
    exit 1
fi

# Stop any existing services to ensure clean state
echo ""
echo "🛑 Stopping any existing services..."
podman-compose -f infra/docker-compose.podman.yml down 2>/dev/null || true

# Start services with fresh build to pick up .env changes
echo ""
echo "📦 Building and starting services with podman-compose..."
podman-compose -f infra/docker-compose.podman.yml up -d --build

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
    echo ""
    echo "📝 Update your .env file with:"
    echo "   PUBLIC_BASE_URL=$NGROK_URL"
    echo ""
    
    # Ask if user wants to update .env automatically
    read -p "Update .env file automatically? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Update PUBLIC_BASE_URL in .env
        if grep -q "PUBLIC_BASE_URL=" .env; then
            sed -i.bak "s|PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=$NGROK_URL|" .env
            echo "✅ Updated PUBLIC_BASE_URL in .env"
        else
            echo "PUBLIC_BASE_URL=$NGROK_URL" >> .env
            echo "✅ Added PUBLIC_BASE_URL to .env"
        fi
        
        # Restart app to pick up new URL
        echo ""
        echo "🔄 Restarting app service..."
        podman-compose -f infra/docker-compose.podman.yml restart app
    fi
fi

echo ""
echo "✅ Services are running!"
echo ""
echo "📊 Service URLs:"
echo "   - Application (local):  http://localhost:8000"
echo "   - Application (public): $NGROK_URL"
echo "   - Ngrok Dashboard:      http://localhost:4040"
echo "   - PostgreSQL:           localhost:5432"
echo ""
echo "🔧 Configure Twilio webhook:"
echo "   1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming"
echo "   2. Select your phone number"
echo "   3. Set 'A CALL COMES IN' webhook to:"
echo "      $NGROK_URL/twilio/voice"
echo ""
echo "📋 View logs:"
echo "   podman-compose -f infra/docker-compose.podman.yml logs -f"
echo ""
echo "🛑 Stop services:"
echo "   podman-compose -f infra/docker-compose.podman.yml down"