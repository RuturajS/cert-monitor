#Author : Ruturaj Sharbidre
#Date : 2026-01-23
#Version : 1.0
#Description : SSL Certificate Monitoring System

import os
import ssl
import socket
import json
import yaml
import logging
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

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

def get_env_var(config_val: str) -> Optional[str]:
    """Helper to get env var value whether it's the value itself (url) or a key."""
    if not config_val:
        return None
    if config_val.startswith('http') or config_val.startswith('https'):
        return config_val
    return os.environ.get(config_val)

def resolve_notifications(site: dict, config: dict, default_slack_url: Optional[str]) -> Dict[str, Any]:
    """
    Resolve all notification channels for a site.
    Returns a dict with keys: slack, discord, telegram_token, telegram_chat_id
    """
    channels = {
        'slack': default_slack_url,
        'discord': None,
        'telegram_token': None,
        'telegram_chat_id': None
    }
    
    group_name = site.get('notification_group')
    if group_name and 'notification_groups' in config:
        group_config = config['notification_groups'].get(group_name)
        if group_config:
            # Slack
            if 'slack_webhook_url' in group_config:
                channels['slack'] = get_env_var(group_config['slack_webhook_url'])
            
            # Discord
            if 'discord_webhook_url' in group_config:
                channels['discord'] = get_env_var(group_config['discord_webhook_url'])
                
            # Telegram
            if 'telegram_bot_token' in group_config and 'telegram_chat_id' in group_config:
                channels['telegram_token'] = get_env_var(group_config['telegram_bot_token'])
                channels['telegram_chat_id'] = get_env_var(group_config['telegram_chat_id'])
        else:
            logger.warning(f"Notification group '{group_name}' defined in site but not found in notification_groups configs.")
            
    return channels

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

def send_discord_notification(webhook_url: str, message: str, color: int = 3066993):
    """
    Send notification to Discord. Color is integer (green=3066993, red=15158332, orange=15105570).
    """
    if not webhook_url:
        return

    # Convert distinct slack markdown like *bold* to discord **bold** if needed, 
    # but for now sending simple text.
    payload = {
        "embeds": [
            {
                "description": message,
                "color": color,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send Discord notification: {e}")

def send_telegram_notification(bot_token: str, chat_id: str, message: str):
    if not bot_token or not chat_id:
        return
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")

def send_notifications(channels: Dict[str, Any], message: str, level: str = "info"):
    """
    Central function to dispatch notifications to all configured channels.
    level: info (green), warning (orange), error/alert (red)
    """
    # Color mapping
    slack_colors = {"info": "#2eb886", "warning": "#daa038", "error": "#e01e5a"}
    discord_colors = {"info": 3061894, "warning": 16766720, "error": 15158332} # Green, Gold, Red
    
    # Send Slack
    if channels.get('slack'):
        send_slack_notification(channels['slack'], message, slack_colors.get(level, "#36a64f"))
        
    # Send Discord
    if channels.get('discord'):
        send_discord_notification(channels['discord'], message, discord_colors.get(level, 3061894))
        
    # Send Telegram
    if channels.get('telegram_token') and channels.get('telegram_chat_id'):
        # Telegram doesn't support colors directly, just text
        send_telegram_notification(channels['telegram_token'], channels['telegram_chat_id'], message)

def get_ssl_expiry(hostname: str, port: int) -> datetime:
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            # cert['notAfter'] format: 'Mar 24 23:59:59 2026 GMT'
            expiry_str = cert['notAfter']
            expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
            return expiry_date.replace(tzinfo=timezone.utc)

def process_site(site: dict, state: dict, channels: Dict[str, Any]):
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
                
                send_notifications(channels, msg, level="info")
                
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
                level = "warning" if triggered_threshold > 7 else "error"
                
                msg = f"{emoji} *SSL Expiry Warning*\n" \
                      f"*Site*: {name} ({env})\n" \
                      f"*Host*: {hostname}\n" \
                      f"*Days remaining*: *{remaining_days}* (Threshold: {triggered_threshold})\n" \
                      f"*Expiry Date*: {current_expiry.strftime('%Y-%m-%d')}"
                
                logger.info(f"Sending alert for {name} ({env}) - {remaining_days} days left.")
                
                send_notifications(channels, msg, level=level)
                
                site_state['notified_thresholds'].append(triggered_threshold)
                site_state['last_notification_sent'] = now.isoformat()
                
    except Exception as e:
        error_msg = f"❌ *SSL Check Failed*\n*Site*: {name} ({env})\n*Host*: {hostname}\n*Error*: `{str(e)}`"
        logger.error(f"Error checking {name} ({env}): {e}")
        send_notifications(channels, error_msg, level="error")
    
    state[site_key] = site_state

import time
import argparse

def main():
    parser = argparse.ArgumentParser(description="SSL Certificate Monitor")
    parser.add_argument('--daemon', action='store_true', help="Run in daemon mode (continuous monitoring)")
    parser.add_argument('--interval', type=int, default=86400, help="Interval in seconds for daemon mode (default: 86400s / 24h)")
    args = parser.parse_args()

    logger.info("Starting SSL Monitor...")
    
    if args.daemon:
        logger.info(f"Running in DAEMON mode. Check interval: {args.interval} seconds.")
        while True:
            try:
                run_check()
            except Exception as e:
                logger.error(f"Unexpected error in daemon loop: {e}")
            
            # Sleep for the defined interval
            time.sleep(args.interval)
    else:
        # Run once and exit
        run_check()

def run_check():
    """
    Performs a single execution of the SSL check logic.
    """
    config = load_config()
    state = load_state()
    # Resolve default slack webhook
    slack_env = config.get('slack_webhook_env_name', 'SLACK_WEBHOOK_URL')
    default_webhook_url = get_env_var(slack_env)
    
    if not config.get('sites'):
        logger.warning("No sites configured in sites.yaml")
        return

    # Process each site with its specific webhook
    for site in config['sites']:
        # Determine which webhook channels to use
        site_channels = resolve_notifications(site, config, default_webhook_url)
        process_site(site, state, site_channels)
    
    save_state(state)
    logger.info("SSL Check cycle completed.")

if __name__ == "__main__":
    main()
