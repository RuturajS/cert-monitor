# 🐳 Docker Usage Guide

This guide provides instructions on how to build and run the SSL Certificate Monitor using Docker on Linux.

## 1. Build the Docker Image

Build the image locally from the project root directory:

```bash
docker build -t cert-monitor .
```

## 2. Run the Container

To run the container, you need to mount the configuration and state directories to ensure your settings are read and data persists.

### Standard Run (Daemon Mode)

This starts the monitor in the background (detached mode), checking for certificate expiry every 24 hours (default).

```bash
docker run -d \
  --name cert-monitor \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/state:/app/state \
  -v $(pwd)/logs:/app/logs \
  -e SLACK_WEBHOOK_URL="your_slack_webhook_url" \
  -e DISCORD_WEBHOOK_URL="your_discord_webhook_url" \
  -e TELEGRAM_BOT_TOKEN="your_telegram_bot_token" \
  -e TELEGRAM_CHAT_ID="your_telegram_chat_id" \
  cert-monitor
```

### Custom Check Interval

To check more frequently (e.g., every hour), override the default command:

```bash
# Check every 1 hour (3600 seconds)
docker run -d \
  --name cert-monitor \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/state:/app/state \
  -v $(pwd)/logs:/app/logs \
  -e SLACK_WEBHOOK_URL="your_webhook_url" \
  cert-monitor python ssl_check.py --daemon --interval 3600
```

## 3. Managing the Container

**View Logs:**
```bash
docker logs -f cert-monitor
```

**Stop the Container:**
```bash
docker stop cert-monitor
```

**Remove the Container:**
```bash
docker rm cert-monitor
```
