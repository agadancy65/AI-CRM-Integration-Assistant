import os
import requests
from app.db import log_event

SLACK_TIMEOUT_SECONDS = 5

WEBHOOK_BY_TEAM = {
    "sales": "SLACK_WEBHOOK_SALES",
    "support": "SLACK_WEBHOOK_SUPPORT",
    "account_management": "SLACK_WEBHOOK_DEFAULT",
}


def _webhook_for(team: str | None) -> str:
    env_var = WEBHOOK_BY_TEAM.get(team, "SLACK_WEBHOOK_DEFAULT")
    return os.environ.get(env_var, "").strip() or os.environ.get("SLACK_WEBHOOK_DEFAULT", "").strip()


def send_notification(text: str, customer_id: int | None = None, team: str | None = None) -> bool:
    webhook_url = _webhook_for(team)

    if not webhook_url:
        log_event("notification", customer_id, {"channel": "none_configured", "team": team, "text": text}, status="skipped")
        return False

    try:
        resp = requests.post(webhook_url, json={"text": text}, timeout=SLACK_TIMEOUT_SECONDS)
        resp.raise_for_status()
        log_event("notification", customer_id, {"channel": "slack", "team": team, "text": text}, status="success")
        return True
    except requests.RequestException as e:
        log_event("notification", customer_id, {"channel": "slack", "team": team, "text": text, "error": str(e)}, status="failed")
        return False