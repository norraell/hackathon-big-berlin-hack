# Setup Checklist for AI Claims Intake System

This checklist will guide you through setting up the project from scratch.

## ✅ Completed

- [x] `.env` file created from `.env.example`
- [x] `.gitignore` updated to protect credentials
- [x] `requirements.txt` fixed (removed problematic git reference)

## 🔧 Required Configuration

### 1. Environment Variables (.env file)

You need to configure the following in your `.env` file:

#### **Critical - Required for Basic Operation:**
```bash
# Twilio (for phone calls)
TWILIO_ACCOUNT_SID=your_account_sid_here          # Get from https://console.twilio.com
TWILIO_API_KEY_SID=your_api_key_here            # Get from https://console.twilio.com
TWILIO_PHONE_NUMBER=+1234567890                   # Your Twilio phone number

# AI Services
GEMINI_API_KEY=your_gemini_api_key_here          # Get from https://aistudio.google.com/app/apikey
GRADIUM_API_KEY=your_gradium_api_key_here        # Get from Gradium dashboard

# Database
DATABASE_URL=postgresql+asyncpg://claims_user:claims_password@localhost:5432/claims_db

# Security
SECRET_KEY=your_secret_key_here_change_in_production  # Generate: openssl rand -hex 32
```

#### **For Google Cloud STT (Recommended):**
```bash
# Google Cloud Speech-to-Text
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/gcp-stt-key.json
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
STT_PROVIDER=google_cloud
```

See [`documentation/GOOGLE_CLOUD_STT_SETUP.md`](documentation/GOOGLE_CLOUD_STT_SETUP.md) for detailed setup.

#### **For Local Development with Twilio:**
```bash
# Ngrok (for exposing local server to Twilio)
NGROK_AUTHTOKEN=your_ngrok_auth_token_here       # Get from https://dashboard.ngrok.com
PUBLIC_BASE_URL=https://your-ngrok-url.ngrok-free.app  # Update after starting ngrok
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### 3. Database Setup

```bash
# Start PostgreSQL (using Docker)
docker compose -f infra/docker-compose.yml up -d postgres

# Run migrations
alembic upgrade head

# Optional: Generate mock data for testing
python scripts/generate_mock_data.py
```

### 4. API Keys Setup

#### **Twilio Setup:**
1. Sign up at https://www.twilio.com/try-twilio
2. Get a phone number with Voice capabilities
3. Copy Account SID and Auth Token to `.env`

#### **Google Gemini Setup:**
1. Go to https://aistudio.google.com/app/apikey
2. Create API key
3. Copy to `.env` as `GEMINI_API_KEY`

#### **Gradium TTS Setup:**
1. Contact Gradium for API access
2. Get API key and voice IDs
3. Update `.env` with credentials

#### **Google Cloud STT Setup (Recommended):**
Follow the detailed guide: [`documentation/GOOGLE_CLOUD_STT_SETUP.md`](documentation/GOOGLE_CLOUD_STT_SETUP.md)

### 5. Local Development with Twilio

```bash
# Option A: Using Podman (Recommended)
./infra/start-podman.sh

# Option B: Manual setup
# Terminal 1: Start the application
uvicorn app.main:app --reload --port 8000

# Terminal 2: Start ngrok
ngrok http 8000

# Copy the ngrok URL (e.g., https://abc123.ngrok-free.app)
# Update PUBLIC_BASE_URL in .env

# Configure Twilio webhook:
# Go to https://console.twilio.com/us1/develop/phone-numbers/manage/incoming
# Set Voice webhook to: https://your-ngrok-url.ngrok-free.app/twilio/voice
```

## 🗑️ Files to Remove/Clean Up

### Already Handled:
- ✅ Commented out problematic git reference in `requirements.txt`
- ✅ Added credential patterns to `.gitignore`

### Optional Cleanup:
- `infra/terraform/` - Empty directory (only contains `.gitignore`)
  - **Action:** Can be removed if not planning AWS deployment
  - **Keep if:** Planning to add AWS Terraform configuration later

## 📋 Testing Your Setup

### 1. Test Database Connection
```bash
python scripts/init_db.py
```

### 2. Test Google Cloud STT (if configured)
```bash
python scripts/test_google_cloud_stt.py
```

### 3. Test Verification Logic
```bash
python scripts/test_verification.py
```

### 4. Run Full Test Suite
```bash
pytest
```

### 5. Test the Application
```bash
# Start the server
uvicorn app.main:app --reload

# Check health endpoint
curl http://localhost:8000/health

# Make a test call to your Twilio number
```

## 🚀 Deployment Options

### Local Development
- Use Docker Compose: `docker compose -f infra/docker-compose.yml up`
- Or Podman: `./infra/start-podman.sh`

### Production Deployment
- **GCP (Recommended):** See [`infra/terraform-gcp/README.md`](infra/terraform-gcp/README.md)
- **AWS:** See [`infra/DEPLOYMENT.md`](infra/DEPLOYMENT.md)

## 🔒 Security Checklist

- [ ] Never commit `.env` file
- [ ] Never commit credential JSON files
- [ ] Use strong `SECRET_KEY` (min 32 characters)
- [ ] Rotate API keys regularly (every 90 days)
- [ ] Enable HTTPS/WSS in production
- [ ] Set up monitoring and alerts
- [ ] Review and limit service account permissions
- [ ] Enable database backups
- [ ] Set up rate limiting

## 📚 Additional Documentation

- [`README.md`](README.md) - Main project documentation
- [`documentation/architecture.md`](documentation/architecture.md) - System architecture
- [`documentation/GOOGLE_CLOUD_STT_SETUP.md`](documentation/GOOGLE_CLOUD_STT_SETUP.md) - STT setup guide
- [`documentation/DATABASE_SETUP.md`](documentation/DATABASE_SETUP.md) - Database configuration
- [`infra/DEPLOYMENT.md`](infra/DEPLOYMENT.md) - Deployment guide
- [`infra/PODMAN.md`](infra/PODMAN.md) - Podman setup guide

## ❓ Troubleshooting

### "Module not found" errors
```bash
pip install -r requirements.txt
```

### Database connection errors
```bash
# Check if PostgreSQL is running
docker compose -f infra/docker-compose.yml ps

# Restart PostgreSQL
docker compose -f infra/docker-compose.yml restart postgres
```

### Twilio webhook errors
- Verify `PUBLIC_BASE_URL` is correct in `.env`
- Check ngrok is running: http://localhost:4040
- Verify Twilio webhook URL matches your ngrok URL

### Google Cloud STT errors
- See [`documentation/GEMINI_STT_TROUBLESHOOTING.md`](documentation/GEMINI_STT_TROUBLESHOOTING.md)
- Verify `GOOGLE_APPLICATION_CREDENTIALS` path is correct
- Check service account has correct permissions

## 🎯 Next Steps

1. **Configure all required environment variables** in `.env`
2. **Set up Google Cloud STT** (recommended for production)
3. **Start the database** with Docker Compose
4. **Run database migrations** with Alembic
5. **Test the application** locally
6. **Configure Twilio webhook** with ngrok
7. **Make a test call** to verify everything works
8. **Deploy to production** when ready

---

**Need Help?** Open an issue on GitHub or check the documentation links above.