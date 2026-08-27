import os
import json
from groq import Groq

MODEL = "openai/gpt-oss-120b"

_client_instance = None


class AIProcessingError(Exception):
    pass


def _client():
    global _client_instance
    if _client_instance is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise AIProcessingError("GROQ_API_KEY is not set")
        _client_instance = Groq(api_key=api_key)
    return _client_instance


def _call_json(system: str, user: str) -> dict:
    try:
        resp = _client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=600,
        )
        text = resp.choices[0].message.content.strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIProcessingError(f"Model did not return valid JSON: {e}")
    except Exception as e:
        raise AIProcessingError(f"Groq API error: {e}")


def extract_lead_fields(raw_text: str) -> dict:
    system = (
        "You extract structured CRM fields from raw customer/lead text such as "
        "emails, form submissions, or meeting notes. "
        "Respond with ONLY a JSON object, no other text, no markdown fences. "
        "Schema: {\"name\": string|null, \"email\": string|null, \"company\": string|null, "
        "\"need\": string|null (one sentence describing what they want), "
        "\"urgency\": \"low\"|\"medium\"|\"high\"}. "
        "Use null for any field you cannot confidently determine. Never invent information."
    )
    return _call_json(system, raw_text)


def summarize_interaction(raw_text: str, prior_summary: str | None = None) -> str:
    system = (
        "You write short, factual sales/customer-interaction summaries for a CRM. "
        "Respond with ONLY a JSON object, no other text: {\"summary\": string}. "
        "Keep it to 2-3 sentences. Do not speculate beyond what is stated."
    )
    user = raw_text if not prior_summary else (
        f"Prior summary of this customer:\n{prior_summary}\n\n"
        f"New interaction to incorporate:\n{raw_text}"
    )
    return _call_json(system, user)["summary"]


def recommend_next_action(customer_record: dict) -> dict:
    system = (
        "You are a sales-operations assistant. Given a CRM record as JSON, recommend "
        "the single best next action. "
        "Respond with ONLY a JSON object, no other text: "
        "{\"next_action\": string (one concise sentence), "
        "\"assigned_to\": \"sales\"|\"support\"|\"account_management\", "
        "\"priority\": \"low\"|\"medium\"|\"high\"}."
    )
    user = json.dumps({
        "name": customer_record.get("name"),
        "company": customer_record.get("company"),
        "need": customer_record.get("need"),
        "stage": customer_record.get("stage"),
        "summary": customer_record.get("summary"),
    })
    return _call_json(system, user)