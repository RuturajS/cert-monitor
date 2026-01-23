# 🛡️ SSL Certificate Monitoring System

A robust, Python-based tool to monitor SSL certificate expiry dates and forward alerts to **Slack, Discord, and Telegram**.

## ✨ Features
- **Multi-Channel Support**: Send alerts to Slack, Discord, and Telegram independently.
- **Group-Based Routing**: Route notifications to different channels (e.g., `dev` team gets alerts on Discord, `prod` team on Slack).
- **Intelligent Parsers**: Supports both raw domains (`example.com`) and full URLs (`https://example.com/login`).
- **State Persistence**: Tracks alert history to prevent spamming users with duplicate notifications.
- **Auto-Renewal Detection**: Automatically detects when a certificate has been renewed and sends a success message.
- **Customizable Thresholds**: Configure specific days to trigger alerts (e.g., 30, 7, 1 day remaining).

---

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/RuturajS/cert-monitor.git
   cd cert-monitor
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Set your webhook URLs and tokens. This keeps your secrets safe from version control.
   ```bash
   # Slack
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
   export SLACK_WEBHOOK_DEV="https://hooks.slack.com/services/..."

   # Discord
   export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."

   # Telegram
   export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
   export TELEGRAM_CHAT_ID="-1001234567890"
   ```

---

## ⚙️ Configuration (`config/sites.yaml`)

### 1. Define Notification Groups
Map logical groups to your environment variables. You can mix and match services.

```yaml
notification_groups:
  default:
    slack_webhook_url: "SLACK_WEBHOOK_URL"
    discord_webhook_url: "DISCORD_WEBHOOK_URL"
  
  dev_team:
    discord_webhook_url: "DISCORD_WEBHOOK_DEV"
    telegram_bot_token: "TELEGRAM_BOT_TOKEN"
    telegram_chat_id: "TELEGRAM_CHAT_ID"

  critical_prod:
    slack_webhook_url: "SLACK_WEBHOOK_PROD"
```

### 2. Configure Sites
Assign each site to a `notification_group`.

```yaml
sites:
  - name: "Public Website"
    hostname: "https://google.com"
    port: 443
    alert_days: [30, 14, 7, 3, 1]
    notification_group: "default"

  - name: "Internal QA"
    hostname: "https://bing.com"
    notification_interval_hours: 12
    notification_group: "dev_team"
```

---

## 🏃‍♂️ Usage

**Run Manually:**
```bash
python3 ssl_check.py
```

**Run via Cron (Linux/Mac):**
Check every morning at 9:00 AM.
```cron
0 9 * * * /usr/bin/python3 /path/to/cert-monitor/ssl_check.py >> /var/log/ssl_monitor.log 2>&1
```

**Run as Daemon (Continuous Loop):**
Run constantly in the background, checking every 24 hours (default) or at a custom interval.
```bash
# Check every 24 hours (default)
python3 ssl_check.py --daemon

# Check every 1 hour (3600 seconds)
python3 ssl_check.py --daemon --interval 3600
```
---


## 🐳 Docker Support

Build and run the application using Docker to isolate dependencies.

### 1. Quick Start (from Docker Hub)
Pull the pre-built image directly from Docker Hub:

```bash
docker pull ruturajs/cert-monitor:latest
```

Run it immediately (Windows PowerShell example):
```powershell
docker run -d `
  --name ssl-monitor `
  -v ${PWD}/config:/app/config `
  -v ${PWD}/state:/app/state `
  -v ${PWD}/logs:/app/logs `
  -e SLACK_WEBHOOK_URL="your_webhook_url" `
  ruturajs/cert-monitor:latest
```

### 💡 Custom Interval (Docker)
By default, the container checks every 24 hours. To check every 1 hour (3600s), override the command:
```powershell
docker run -d `
  --name ssl-monitor `
  -v ${PWD}/config:/app/config `
  -v ${PWD}/state:/app/state `
  -v ${PWD}/logs:/app/logs `
  -e SLACK_WEBHOOK_URL="..." `
  ruturajs/cert-monitor:latest python ssl_check.py --daemon --interval 3600
```

### 2. Run the Container
You must mount the `config`, `state`, and `logs` directories so that your configuration is read and your data persists.

**Linux/Mac:**
```bash
docker run -d \
  --name ssl-monitor \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/state:/app/state \
  -v $(pwd)/logs:/app/logs \
  -e SLACK_WEBHOOK_URL="your_webhook_url" \
  cert-monitor
```

**Windows (PowerShell):**
```powershell
docker run -d `
  --name ssl-monitor `
  -v ${PWD}/config:/app/config `
  -v ${PWD}/state:/app/state `
  -v ${PWD}/logs:/app/logs `
  -e SLACK_WEBHOOK_URL="your_webhook_url" `
  cert-monitor
```


## 📂 File Structure
- `config/sites.yaml`: Main configuration file.
- `state/ssl_state.json`: (Auto-generated) Stores the last alert status to ensure rate limiting.
- `logs/ssl_monitor.log`: Detailed operation logs.

---

## 👤 Author
Created by **Ruturaj Sharbidre**