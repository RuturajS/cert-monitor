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
    hostname: "https://brandintelle.com"
    port: 443
    alert_days: [30, 14, 7, 3, 1]
    notification_group: "default"

  - name: "Internal QA"
    hostname: "https://qa.brandintelle.com"
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

---

## 📂 File Structure
- `config/sites.yaml`: Main configuration file.
- `state/ssl_state.json`: (Auto-generated) Stores the last alert status to ensure rate limiting.
- `logs/ssl_monitor.log`: Detailed operation logs.

---

## 👤 Author
Created by **Ruturaj Sharbidre**