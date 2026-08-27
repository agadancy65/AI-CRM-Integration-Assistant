import os
import sys
from dotenv import load_dotenv

load_dotenv()

from app import db, pipeline


def main():
    db.init_db()
    threshold = int(os.environ.get("REMINDER_THRESHOLD_DAYS", 2))
    stale = pipeline.run_reminder_sweep(threshold)
    print(f"Reminder sweep complete: {len(stale)} lead(s) flagged (threshold={threshold} days).")
    for c in stale:
        print(f"  #{c['id']} {c['name']} @ {c['company']} — stage={c['stage']}")


if __name__ == "__main__":
    sys.exit(main())
