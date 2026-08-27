# AI CRM Integration Assistant

Built for AI BuildFest 2026, Track 5 — Case Study 2.

Turns unstructured lead/customer text (emails, form submissions, meeting
notes, chat messages) into structured, deduplicated CRM records — with an
AI-generated summary, a recommended next action, automatic assignment,
Slack notifications, and a full audit trail.

## What it does

1. Receives raw text from a webhook (simulating a form, inbox, or chatbot).
2. Uses Groq to extract structured fields: name, email, company, need, urgency.
3. Checks for an existing record (by email, then name) to avoid duplicates.
4. Creates or updates the CRM record (SQLite — stands in for a real CRM).
5. Uses Groq to summarize the interaction (merged with prior history if updating).
6. Uses Groq to recommend the next action and who it should be assigned to.
7. Sends a Slack notification (or logs it if Slack isn't configured).
8. Logs every step to an audit trail, viewable on the dashboard.
9. A separate reminder sweep flags leads with no follow-up in N days.

## Tools & stack

- **Python 3 / Flask** — webhook endpoint + dashboard
- **Groq API** — extraction, summarization, recommendation
- **SQLite** — simulated CRM database + audit log
- **Slack incoming webhook** — notifications (optional; degrades gracefully)
- **python-dotenv** — configuration

## Setup

```bash
cd crm-assistant
pip install -r requirements.txt
cp .env.example .env
# edit .env: add your GROQ_API_KEY, optionally SLACK_WEBHOOK_URL
```

## Running the demo

**Option A — batch test run (fastest, good for recording your demo video):**

```bash
python test_pipeline.py
```

This processes every sample in `data/sample_inputs.json` through the full
pipeline and prints a trace of what happened at each step, including one
input that's deliberately empty/junk to show validation working.

**Option B — live webhook + dashboard:**

```bash
python -m app.main
```

Then in another terminal:

```bash
curl -X POST http://localhost:5000/intake \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: change-me" \
  -d '{"text": "Hi, I'\''m Amaka from Brightline Retail, need help automating support tickets. amaka@brightline.com", "source": "contact_form"}'
```

Open `http://localhost:5000` to see the dashboard: live CRM records and the
full audit log.

**Reminder sweep** (run manually, or on a schedule):

```bash
python run_reminders.py
```

## Sample input → output

**Input** (raw text from `source: contact_form`):
> "Hi, I'm Amaka Obi from Brightline Retail. We're looking for a way to
> automate our customer support ticket routing... amaka.obi@brightlineretail.com"

**Output** (CRM record created):
```json
{
  "name": "Amaka Obi",
  "company": "Brightline Retail",
  "email": "amaka.obi@brightlineretail.com",
  "need": "Automate customer support ticket routing/triage",
  "stage": "new",
  "next_action": "Schedule a discovery call to scope the ticket-routing automation",
  "assigned_to": "sales"
}
```
Plus: a Slack notification, and two audit log entries (`crm_create`, `recommendation`).

When a later meeting note about the same person arrives, the pipeline finds
the existing record by name, updates it instead of duplicating it, and
merges the new summary with the old one.

## Error handling & reliability

- Empty/invalid input is rejected with a 400 before touching the CRM.
- Webhook is protected by a shared-secret header (`X-Webhook-Secret`).
- If extraction fails, the pipeline stops and logs the failure — nothing
  bad gets written to the CRM.
- If summarization or recommendation fails, the pipeline logs a warning and
  continues (non-fatal) rather than losing the record.
- If Slack isn't configured or the request fails, the notification is
  logged instead of crashing the pipeline.
- Every step — success or failure — is written to `audit_log`, visible on
  the dashboard.

## Privacy & security notes

- API keys and the webhook secret live in `.env`, which is git-ignored and
  never logged.
- The intake endpoint requires a shared secret so it isn't a fully open
  write endpoint.
- Customer data stays in a local SQLite file for this prototype; a
  production version would use a managed database with encryption at rest
  and role-based access control.
- No customer data is sent anywhere except to the Groq API (for field
  extraction/summarization) and, optionally, your own Slack workspace.

## Known limitations (stated up front, as required)

- Dedupe matching is exact-match on email/name only — no fuzzy matching.
- "CRM" is a local SQLite file, not a real CRM integration — swapping in a
  real CRM's API would replace `app/db.py` without touching the AI or
  webhook logic.
- Reminder sweep must be triggered manually or by an external scheduler;
  it isn't a background daemon in this prototype.
- Single-tenant, no authentication beyond the webhook shared secret.

## What we'd build next

- Real CRM connector (HubSpot/Airtable API) behind the same interface.
- Fuzzy/embedding-based dedupe instead of exact match.
- A scheduled worker (cron or a lightweight queue) for reminders.
- Multi-channel intake (real inbox polling via Gmail API, Slack DMs).
