# AI Claims Intake System

An AI-powered phone claims intake system using Twilio, Google Gemini STT, Groq LLM, and Gradium TTS.

## Overview

This system provides an automated phone-based claims intake service that:
- Accepts incoming calls via Twilio
- Transcribes speech using Google Gemini STT
- Processes conversations using Groq LLM
- Synthesizes responses using Gradium TTS
- Manages dialog flow through a state machine
- Stores claims in PostgreSQL

## Architecture

See [`architecture.md`](architecture.md) for detailed architecture documentation.

## Features

- **Multilingual Support**: English, German, Spanish, French, Portuguese
- **AI Disclosure**: Legally compliant AI disclosure at call start
- **Recording Consent**: Explicit consent gathering before data collection
- **Natural Conversation**: LLM-driven dialog for natural interaction
- **Low Latency**: Sub-1500ms response time for natural phone conversation
- **Barge-in Support**: Caller can interrupt agent speech
- **State Management**: Robust dialog state machine
- **PII Protection**: GDPR-compliant data handling

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Twilio account with phone number
- API keys for:
  - Google Gemini
  - Groq
  - Gradium

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd hackathon-big-berlin-hack
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -e .
# Or for development:
pip install -e ".[dev]"
```

### 4. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

### 5. Start infrastructure

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
```

### 6. Run database migrations

```bash
alembic upgrade head
```

## Running the Application

### Local Development

```bash
uvicorn app.main:app --reload --port 8000
```

### Expose to Twilio (using ngrok)

```bash
ngrok http 8000
```

Then configure your Twilio phone number's Voice webhook to:
```
https://<your-ngrok-url>/twilio/voice
```

### Using Docker

```bash
docker compose -f infra/docker-compose.yml up
```

## Configuration

All configuration is done via environment variables. See [`.env.example`](.env.example) for all available options.

Key configurations:
- `TWILIO_*`: Twilio credentials and phone number
- `GEMINI_API_KEY`: Google Gemini API key
- `GROQ_API_KEY`: Groq API key
- `GRADIUM_API_KEY`: Gradium TTS API key
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SUPPORTED_LANGUAGES`: Comma-separated language codes

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=app --cov-report=html
```

Run specific test file:

```bash
pytest tests/test_dialog_flow.py
```

## Project Structure

```
.
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── telephony/           # Twilio integration
│   ├── stt/                 # Speech-to-text (Gemini)
│   ├── llm/                 # Language model (Groq)
│   ├── tts/                 # Text-to-speech (Gradium)
│   ├── dialog/              # Dialog state management
│   ├── claims/              # Claims models and service
│   └── utils/               # Utilities (audio, language)
├── tests/                   # Test suite
├── infra/                   # Infrastructure (Docker)
├── alembic/                 # Database migrations
├── architecture.md          # Architecture documentation
└── README.md               # This file
```

## API Endpoints

- `GET /` - Health check
- `GET /health` - Detailed health status
- `POST /twilio/voice` - Twilio voice webhook
- `WS /media-stream` - Twilio Media Stream WebSocket
- `POST /twilio/status` - Twilio status callback

## Dialog Flow

1. **GREETING** - Initial greeting
2. **DISCLOSURE** - AI disclosure (legally required)
3. **CONSENT** - Recording consent request
4. **INTAKE** - Gather claim information
5. **CONFIRM** - Confirm gathered information
6. **CLOSE** - Provide claim ID and next steps

## Development

### Code Style

The project uses:
- `ruff` for linting and formatting
- `mypy` for type checking

Run checks:

```bash
ruff check app/
mypy app/
```

### Adding Dependencies

Update `pyproject.toml` and reinstall:

```bash
pip install -e .
```

### Database Migrations

Create a new migration:

```bash
alembic revision --autogenerate -m "Description"
```

Apply migrations:

```bash
alembic upgrade head
```

## Deployment

### Environment Variables

Ensure all required environment variables are set in production:
- Use strong `SECRET_KEY`
- Set `LOG_LEVEL=INFO` or `WARNING`
- Configure proper `DATABASE_URL` with SSL
- Set `PUBLIC_BASE_URL` to your production domain

### Security Considerations

- Enable HTTPS/WSS in production
- Rotate API keys regularly
- Implement rate limiting
- Monitor for suspicious activity
- Regular security audits

### Monitoring

- Monitor latency metrics (p95 < 1500ms)
- Track STT confidence scores
- Monitor error rates
- Track claim creation success rate

## Troubleshooting

### Common Issues

**WebSocket connection fails:**
- Check that `PUBLIC_BASE_URL` is correct
- Ensure ngrok/proxy is running
- Verify Twilio webhook configuration

**Audio quality issues:**
- Check audio codec conversions
- Verify sample rates (8kHz Twilio, 16kHz STT, 24kHz TTS)
- Monitor for packet loss

**High latency:**
- Check network connectivity to AI services
- Monitor database query performance
- Verify streaming is enabled (not buffering)

## License

See [LICENSE](LICENSE) file.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Support

For issues and questions, please open a GitHub issue.