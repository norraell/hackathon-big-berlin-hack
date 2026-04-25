#!/bin/bash
# Quick setup script for AI Claims Intake System

set -e

echo "🚀 AI Claims Intake System - Quick Setup"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}⚠️  Please edit .env and add your API keys before continuing${NC}"
    echo ""
    exit 1
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Activate virtual environment
echo ""
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo ""
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Check if PostgreSQL is running
echo ""
echo "🗄️  Checking PostgreSQL..."
if docker compose -f infra/docker-compose.yml ps postgres | grep -q "Up"; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL is not running${NC}"
    echo "Starting PostgreSQL..."
    docker compose -f infra/docker-compose.yml up -d postgres
    echo "Waiting for PostgreSQL to be ready..."
    sleep 5
    echo -e "${GREEN}✓ PostgreSQL started${NC}"
fi

# Run database migrations
echo ""
echo "🔄 Running database migrations..."
alembic upgrade head
echo -e "${GREEN}✓ Database migrations complete${NC}"

# Summary
echo ""
echo "========================================"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your API keys:"
echo "   - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER"
echo "   - GEMINI_API_KEY"
echo "   - GRADIUM_API_KEY"
echo "   - GOOGLE_APPLICATION_CREDENTIALS (for Google Cloud STT)"
echo ""
echo "2. Set up Google Cloud STT (recommended):"
echo "   See: documentation/GOOGLE_CLOUD_STT_SETUP.md"
echo ""
echo "3. Start the application:"
echo "   uvicorn app.main:app --reload --port 8000"
echo ""
echo "4. For local development with Twilio:"
echo "   - Start ngrok: ngrok http 8000"
echo "   - Update PUBLIC_BASE_URL in .env with ngrok URL"
echo "   - Configure Twilio webhook to: https://your-ngrok-url/twilio/voice"
echo ""
echo "5. Run tests:"
echo "   pytest"
echo ""
echo "For detailed setup instructions, see: SETUP_CHECKLIST.md"
echo ""