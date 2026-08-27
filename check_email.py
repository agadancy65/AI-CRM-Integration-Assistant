import os
import imaplib
import email
from email.header import decode_header
import requests
from dotenv import load_dotenv

load_dotenv()

IMAP_SERVER = os.environ.get("IMAP_SERVER", "imap.gmail.com")
EMAIL_ADDRESS = os.environ["EMAIL_ADDRESS"]
EMAIL_APP_PASSWORD = os.environ["EMAIL_APP_PASSWORD"]
INTAKE_URL = "http://127.0.0.1:5000/intake"
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-me")


def decode_str(s):
    parts = decode_header(s)
    return "".join(
        p.decode(enc or "utf-8") if isinstance(p, bytes) else p
        for p, enc in parts
    )


def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")
    return msg.get_payload(decode=True).decode(errors="ignore")


def main():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
    mail.select("Leads")

    status, message_ids = mail.search(None, "UNSEEN")
    ids = message_ids[0].split()

    print(f"Found {len(ids)} unread email(s).")

    for msg_id in ids:
        status, data = mail.fetch(msg_id, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])

        subject = decode_str(msg.get("Subject", ""))
        sender = msg.get("From", "")
        body = get_body(msg)

        full_text = f"From: {sender}\nSubject: {subject}\n\n{body}"

        resp = requests.post(
            INTAKE_URL,
            headers={"X-Webhook-Secret": WEBHOOK_SECRET},
            json={"text": full_text, "source": "email"},
        )
        print(f"Processed '{subject}' -> {resp.status_code}: {resp.json()}")

        mail.store(msg_id, "+FLAGS", "\\Seen")

    mail.logout()


if __name__ == "__main__":
    main()