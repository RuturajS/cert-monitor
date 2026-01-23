import os
import ssl
import socket
import json
import yaml
import logging
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone
from typing import List, Dict, Optional

# Constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'sites.yaml')
STATE_PATH = os.path.join(BASE_DIR, 'state', 'ssl_state.json')
LOG_PATH = os.path.join(BASE_DIR, 'logs', 'ssl_monitor.log')

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Config file not found: {CONFIG_PATH}")
        return {"sites": []}
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        logger.warning("State file corrupted or unreadable. Starting fresh.")
        return {}

def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)

def get_slack_webhook(config: dict) -> Optional[str]:
    env_name = config.get('slack_webhook_env_name', 'SLACK_WEBHOOK_URL')
    
    # Check if the user accidentally put the URL directly in the config
    if env_name and env_name.startswith('http'):
        return env_name
        
    webhook_url = os.environ.get(env_name)
    if not webhook_url:
        logger.warning(f"Slack webhook environment variable '{env_name}' not set.")
    return webhook_url

def resolve_webhook(site: dict, config: dict, default_url: Optional[str]) -> Optional[str]:
    """
    Determine the best webhook URL for a specific site.
    Priority:
    1. Site-specific 'webhook_group' looked up in 'webhook_groups'
    2. Default webhook URL passed in
    """
    group_name = site.get('webhook_group')
    if group_name and 'webhook_groups' in config:
        env_var_name = config['webhook_groups'].get(group_name)
        if env_var_name:
            if env_var_name.startswith('http'):
                return env_var_name
            
            val = os.environ.get(env_var_name)
            if val:
                return val
            else:
                logger.warning(f"Webhook group '{group_name}' maps to env var '{env_var_name}' which is not set.")
        else:
            logger.warning(f"Webhook group '{group_name}' not found in configuration.")
            
    return default_url

def send_slack_notification(webhook_url: str, message: str, color: str = "#36a64f"):
    if not webhook_url:
        return
    
    payload = {
        "attachments": [
            {
                "text": message,
                "color": color,
                "ts": datetime.now().timestamp()
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")

def get_ssl_expiry(hostname: str, port: int) -> datetime:
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            # cert['notAfter'] format: 'Mar 24 23:59:59 2026 GMT'
            expiry_str = cert['notAfter']
            expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
            return expiry_date.replace(tzinfo=timezone.utc)

def process_site(site: dict, state: dict, webhook_url: str):
    name = site['name']
    env = site.get('environment', 'N/A')
    original_hostname = site['hostname']
    
    # Parse hostname if a URL was provided
    if original_hostname.startswith('http'):
        hostname = urlparse(original_hostname).hostname
    else:
        hostname = original_hostname
        
    port = site.get('port', 443)
    alert_days = sorted(site.get('alert_days', [30, 15, 7, 3, 1]), reverse=True)
    interval_hours = site.get('notification_interval_hours', 24)
    
    site_key = f"{hostname}:{port}"
    site_state = state.get(site_key, {
        "last_expiry": None,
        "notified_thresholds": [],
        "last_notification_sent": None
    })
    
    try:
        logger.info(f"Checking SSL for {name} ({hostname})...")
        current_expiry = get_ssl_expiry(hostname, port)
        now = datetime.now(timezone.utc)
        remaining_days = (current_expiry - now).days
        
        logger.info(f"Site: {name} | Expiry: {current_expiry.strftime('%Y-%m-%d')} | Days Left: {remaining_days}")
        
        # 1. Check for Renewal
        last_expiry_str = site_state.get('last_expiry')
        if last_expiry_str:
            last_expiry = datetime.fromisoformat(last_expiry_str)
            if current_expiry > last_expiry:
                msg = f"✅ *SSL Certificate Renewed*\n" \
                      f"*Site*: {name} ({env})\n" \
                      f"*Host*: {hostname}\n" \
                      f"*New Expiry*: {current_expiry.strftime('%Y-%m-%d')}\n" \
                      f"*Days remaining*: {remaining_days}"
                logger.info(f"Renewal detected for {name} ({env})")
                send_slack_notification(webhook_url, msg, color="#2eb886")
                # Reset state for new certificate
                site_state['notified_thresholds'] = []
        
        site_state['last_expiry'] = current_expiry.isoformat()
        
        # 2. Check Thresholds
        triggered_threshold = None
        for threshold in alert_days:
            if remaining_days <= threshold:
                triggered_threshold = threshold
                # thresholds are sorted descending, so we pick the highest one matched
                # but we only alert if it hasn't been notified yet for THIS expiry
        
        if triggered_threshold is not None and triggered_threshold not in site_state['notified_thresholds']:
            # Check Rate Limit (Interval)
            last_sent_str = site_state.get('last_notification_sent')
            should_send = True
            if last_sent_str:
                last_sent = datetime.fromisoformat(last_sent_str)
                secs_since_last = (now - last_sent).total_seconds()
                if secs_since_last < (interval_hours * 3600):
                    should_send = False
                    logger.info(f"Skipping alert for {name} (threshold {triggered_threshold}) - within interval.")
            
            if should_send:
                emoji = "⚠️" if triggered_threshold > 7 else "🚨"
                msg = f"{emoji} *SSL Expiry Warning*\n" \
                      f"*Site*: {name} ({env})\n" \
                      f"*Host*: {hostname}\n" \
                      f"*Days remaining*: *{remaining_days}* (Threshold: {triggered_threshold})\n" \
                      f"*Expiry Date*: {current_expiry.strftime('%Y-%m-%d')}"
                
                logger.info(f"Sending alert for {name} ({env}) - {remaining_days} days left.")
                send_slack_notification(webhook_url, msg, color="#daa038" if triggered_threshold > 7 else "#e01e5a")
                
                site_state['notified_thresholds'].append(triggered_threshold)
                site_state['last_notification_sent'] = now.isoformat()
                
    except Exception as e:
        error_msg = f"❌ *SSL Check Failed*\n*Site*: {name} ({env})\n*Host*: {hostname}\n*Error*: `{str(e)}`"
        logger.error(f"Error checking {name} ({env}): {e}")
        send_slack_notification(webhook_url, error_msg, color="#e01e5a")
    
    state[site_key] = site_state

def main():
    config = load_config()
    state = load_state()
    default_webhook_url = get_slack_webhook(config)
    
    if not config.get('sites'):
        logger.warning("No sites configured in sites.yaml")
        return

    # Process each site with its specific webhook
    for site in config['sites']:
        # Determine which webhook to use
        site_webhook_url = resolve_webhook(site, config, default_webhook_url)
        process_site(site, state, site_webhook_url)
    
    save_state(state)
    logger.info("SSL Check completed.")

if __name__ == "__main__":
    main()
