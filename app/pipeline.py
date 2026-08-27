from datetime import datetime
from app import db, ai, notify


class PipelineResult:
    def __init__(self, customer_id, is_new, record, warnings=None):
        self.customer_id = customer_id
        self.is_new = is_new
        self.record = record
        self.warnings = warnings or []

    def to_dict(self):
        return {
            "customer_id": self.customer_id,
            "is_new": self.is_new,
            "record": self.record,
            "warnings": self.warnings,
        }


def process_lead(raw_text: str, source: str = "unknown") -> PipelineResult:
    warnings = []

    # 1. Validate input
    if not raw_text or not raw_text.strip():
        db.log_event("intake", None, {"source": source, "error": "empty input"}, status="failed")
        raise ValueError("Received empty input — nothing to process")

    db.log_event("intake", None, {"source": source, "length": len(raw_text)})

    # 2. Extract structured fields (AI). If this fails, we stop — there's
    #    nothing useful to write to the CRM without it.
    try:
        fields = ai.extract_lead_fields(raw_text)
    except ai.AIProcessingError as e:
        db.log_event("extraction", None, {"error": str(e)}, status="failed")
        raise

    # 3. Dedupe check against existing records
    existing = db.find_duplicate(fields.get("email"), fields.get("name"))

    # 4. Summarize (AI). Non-fatal if it fails — we fall back to raw text.
    try:
        summary = ai.summarize_interaction(
            raw_text, prior_summary=existing.get("summary") if existing else None
        )
    except ai.AIProcessingError as e:
        warnings.append(f"summarization_failed: {e}")
        summary = (existing.get("summary") + " " if existing else "") + raw_text[:200]

    now = datetime.utcnow().isoformat()

    if existing:
        customer_id = existing["id"]
        update_fields = {
            "name": fields.get("name") or existing.get("name"),
            "email": fields.get("email") or existing.get("email"),
            "company": fields.get("company") or existing.get("company"),
            "need": fields.get("need") or existing.get("need"),
            "summary": summary,
            "last_contacted_at": now,
        }
        db.update_customer(customer_id, update_fields)
        db.log_event("crm_update", customer_id, {"source": source, "duplicate_of": existing["id"]})
        is_new = False
    else:
        customer_id = db.create_customer({
            "name": fields.get("name"),
            "email": fields.get("email"),
            "company": fields.get("company"),
            "need": fields.get("need"),
            "stage": "new",
            "summary": summary,
            "source": source,
        })
        db.log_event("crm_create", customer_id, {"source": source})
        is_new = True

    # 5. Recommend next action (AI). Non-fatal if it fails.
    record = db.get_customer(customer_id)
    try:
        recommendation = ai.recommend_next_action(record)
        db.update_customer(customer_id, {
            "next_action": recommendation["next_action"],
            "assigned_to": recommendation["assigned_to"],
        })
        db.log_event("recommendation", customer_id, recommendation)
    except ai.AIProcessingError as e:
        warnings.append(f"recommendation_failed: {e}")
        recommendation = None

    record = db.get_customer(customer_id)

    # 6. Notify
    urgency = fields.get("urgency", "medium")
    label = "NEW LEAD" if is_new else "LEAD UPDATED"
    priority = recommendation["priority"] if recommendation else urgency
    notify.send_notification(
        f":bell: *{label}* — {record.get('name') or 'Unknown'} "
        f"({record.get('company') or 'no company'})\n"
        f"Priority: {priority} | Next action: {record.get('next_action') or 'pending review'}",
        customer_id=customer_id,
        team=record.get("assigned_to"),
    )

    return PipelineResult(customer_id, is_new, record, warnings)


def run_reminder_sweep(threshold_days: int) -> list[dict]:
    """Check for stale leads and notify. Called by the reminder script/cron."""
    stale = db.overdue_customers(threshold_days)
    for customer in stale:
        notify.send_notification(
            f":alarm_clock: *No follow-up in {threshold_days}+ days* — "
            f"{customer.get('name') or 'Unknown'} ({customer.get('company') or 'no company'}). "
            f"Stage: {customer.get('stage')}",
            customer_id=customer["id"],
        )
        db.log_event("reminder", customer["id"], {"stage": customer.get("stage")})
    return stale
