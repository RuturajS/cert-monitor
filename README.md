# SSL Certificate Monitoring System

A Python-based tool to monitor SSL certificate expiry dates and send alerts to Slack when thresholds are reached.

## Features
- Multi-site support with independent configurations.
- Native Python SSL handle (no external certificate tools required).
- **Flexible Hostnames**: Supports both raw domains (`example.com`) and full URLs (`https://example.com/v7/login`).
- **Flexible Slack Webhooks**: Supports both environment variables and direct URLs in configuration.
- State persistence to avoid duplicate alerts.
- Configurable alert thresholds (e.g., 30, 15, 7, 3, 1 days).
- Rate limiting for notifications.
- Automatic renewal detection and notification.
- Failure alerts for unreachable sites.

## Installation

1. **Clone/Copy the script** to your Linux server.
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure sites**:
   Edit `config/sites.yaml` to add your domains or URLs.
4. **Set Slack Webhook**:
   You can either paste your webhook URL directly into `config/sites.yaml` under `slack_webhook_env_name`, or export it as an environment variable:
   ```bash
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/XXXX/YYYY/ZZZZ"
   ```

## Configuration (`config/sites.yaml`)

```yaml
# You can put the ACTUAL URL here OR the name of an environment variable
slack_webhook_env_name: "https://hooks.slack.com/services/..." 

sites:
  - name: "Main Website"
    environment: "Production"
    hostname: "https://example.com/v7/login" # Full URLs are automatically parsed
    port: 443
    alert_days: [30, 15, 7, 3, 1]
    notification_interval_hours: 24
```

## Running the script

To run manually:
```bash
python3 ssl_check.py
```

## Cron Integration

To run the check every hour, add the following to your crontab (`crontab -e`):

```cron
0 * * * * /usr/bin/python3 /path/to/SSLScanner/ssl_check.py >> /path/to/SSLScanner/logs/cron.log 2>&1
```

## State Management
The system tracks notified thresholds in `state/ssl_state.json`. You can reset alerts for a specific site by deleting its entry in this file.

## Logs
Detailed logs are maintained in `logs/ssl_monitor.log`.
