# Podman Setup Guide with Ngrok for Twilio Integration

This guide explains how to use the Podman-compatible docker-compose file for the claims processing application with ngrok for exposing your local server to Twilio webhooks.

## Prerequisites

1. **Install Podman**:
   - macOS: `brew install podman`
   - Linux: `sudo apt-get install podman` or `sudo dnf install podman`
   - Windows: Download from [Podman Desktop](https://podman-desktop.io/)

2. **Install podman-compose**:
   ```bash
   pip install podman-compose
   ```

3. **Initialize Podman Machine** (macOS/Windows only):
   ```bash
   podman machine init
   podman machine start
   ```

## Quick Start (Recommended)

For the fastest setup, use the provided start script:

```bash
./infra/start-podman.sh
```

This script will:
1. Check if `.env` file exists (creates from `.env.example` if not)
2. Validate ngrok auth token is set
3. Start all services with podman-compose
4. Automatically fetch your ngrok public URL
5. Optionally update your `.env` file with the ngrok URL
6. Restart the app to pick up the new configuration
7. Display all service URLs and Twilio configuration instructions

## Manual Setup

If you prefer to set up manually, follow these steps:

### Ngrok Setup (Required for Twilio Integration)

### 1. Get Your Ngrok Auth Token

1. Sign up for a free account at [ngrok.com](https://ngrok.com/)
2. Get your auth token from [https://dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
3. Add it to your `.env` file:

```bash
echo "NGROK_AUTHTOKEN=your_token_here" >> .env
```

### 2. Configure Your Application

Add the ngrok URL to your `.env` file (this will be updated after starting ngrok):

```bash
# This will be your ngrok URL after starting the services
PUBLIC_BASE_URL=https://your-ngrok-url.ngrok-free.app
```

## Usage

### Starting the Services

### Starting All Services (Including Ngrok)

Run the following command from the project root:

```bash
podman-compose -f infra/docker-compose.podman.yml up
```

Or run in detached mode:

```bash
podman-compose -f infra/docker-compose.podman.yml up -d
```

### Getting Your Ngrok URL

After starting the services, you need to get your ngrok public URL:

1. **Option 1: Check ngrok web interface**
   - Open http://localhost:4040 in your browser
   - Copy the "Forwarding" URL (e.g., `https://abc123.ngrok-free.app`)

2. **Option 2: Check ngrok logs**
   ```bash
   podman-compose -f infra/docker-compose.podman.yml logs ngrok
   ```
   Look for a line like: `url=https://abc123.ngrok-free.app`

3. **Update your `.env` file** with the ngrok URL:
   ```bash
   PUBLIC_BASE_URL=https://abc123.ngrok-free.app
   ```

4. **Restart the app service** to pick up the new URL:
   ```bash
   podman-compose -f infra/docker-compose.podman.yml restart app
   ```

### Configuring Twilio

Once you have your ngrok URL, configure your Twilio phone number:

1. Go to [Twilio Console](https://console.twilio.com/)
2. Navigate to Phone Numbers → Manage → Active Numbers
3. Select your phone number
4. Under "Voice Configuration":
   - **A CALL COMES IN**: Webhook
   - **URL**: `https://your-ngrok-url.ngrok-free.app/twilio/voice`
   - **HTTP**: POST
5. Under "Status Callback URL" (optional):
   - **URL**: `https://your-ngrok-url.ngrok-free.app/twilio/status`
6. Click "Save"

### Testing the Integration

1. Call your Twilio phone number
2. The call should be routed to your local application via ngrok
3. Monitor the logs:
   ```bash
   podman-compose -f infra/docker-compose.podman.yml logs -f app
   ```

### Stopping the Services

```bash
podman-compose -f infra/docker-compose.podman.yml down
```

### Viewing Logs

```bash
# All services
podman-compose -f infra/docker-compose.podman.yml logs

# Specific service
podman-compose -f infra/docker-compose.podman.yml logs app
```

### Rebuilding Images

```bash
podman-compose -f infra/docker-compose.podman.yml build
podman-compose -f infra/docker-compose.podman.yml up
```

## Key Differences from Docker

1. **Rootless by Default**: Podman runs containers without root privileges by default
2. **No Daemon**: Podman doesn't require a background daemon process
3. **User Namespace**: The `userns_mode: keep-id` setting ensures proper file permissions in rootless mode
4. **Network Configuration**: Explicit bridge network configuration for better compatibility

## Troubleshooting

### Permission Issues

If you encounter permission issues with volumes:

```bash
# Check SELinux context (Linux only)
podman unshare chown -R 999:999 postgres_data
```

### Port Already in Use

If ports are already in use, modify the port mappings in [`docker-compose.podman.yml`](docker-compose.podman.yml):

```yaml
ports:
  - "5433:5432"  # Changed from 5432:5432
```

### Connection Issues

Ensure the Podman machine is running (macOS/Windows):

```bash
podman machine list
podman machine start
```

### Health Check Failures

If health checks fail, check the logs:

```bash
podman-compose -f infra/docker-compose.podman.yml logs postgres
```

## Environment Variables

Create a `.env` file in the project root with the required environment variables:

```bash
cp .env.example .env
# Edit .env with your configuration
```

## Accessing Services

- **Application (local)**: http://localhost:8000
- **Application (public via ngrok)**: https://your-ngrok-url.ngrok-free.app
- **Ngrok Web Interface**: http://localhost:4040
- **PostgreSQL**: localhost:5432

### Ngrok Web Interface Features

The ngrok web interface at http://localhost:4040 provides:
- Real-time request inspection
- Request/response details
- Replay requests for debugging
- Traffic statistics

## Important Notes for Twilio Integration

### Ngrok Free Tier Limitations

- URLs change on restart (unless you have a paid plan)
- You'll need to update Twilio webhook URLs after each restart
- Consider using ngrok's paid plan for a static domain

### Webhook Security

For production, implement webhook validation:
- Verify Twilio signatures
- Use HTTPS (ngrok provides this automatically)
- Implement rate limiting

### Debugging Webhooks

1. **Check ngrok logs**:
   ```bash
   podman-compose -f infra/docker-compose.podman.yml logs ngrok
   ```

2. **Check application logs**:
   ```bash
   podman-compose -f infra/docker-compose.podman.yml logs app
   ```

3. **Use ngrok web interface**: http://localhost:4040
   - Inspect all incoming requests
   - See request/response details
   - Replay requests for testing

## Alternative: Using Podman Directly

You can also use Podman's native pod functionality instead of podman-compose:

```bash
# Create a pod
podman pod create --name claims-pod -p 8000:8000 -p 5432:5432 -p 6379:6379

# Run containers in the pod
podman run -d --pod claims-pod --name postgres \
  -e POSTGRES_USER=claims_user \
  -e POSTGRES_PASSWORD=claims_password \
  -e POSTGRES_DB=claims_db \
  postgres:16-alpine

# Build and run the app
podman build -t claims-app -f infra/Dockerfile .
podman run -d --pod claims-pod --name app \
  --env-file .env \
  -e DATABASE_URL=postgresql+asyncpg://claims_user:claims_password@localhost:5432/claims_db \
  claims-app
```

## Compatibility Notes

- The Podman-compatible compose file maintains full compatibility with the original Docker Compose setup
- All services, volumes, and networking configurations are preserved
- You can switch between Docker and Podman without changing your application code