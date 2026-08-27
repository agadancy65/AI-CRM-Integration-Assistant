import json
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from app import db, pipeline

SAMPLES_PATH = Path(__file__).parent / "data" / "sample_inputs.json"

PAUSE_BETWEEN_LEADS_SECONDS = 25


def main():
    db.init_db()
    samples = json.loads(SAMPLES_PATH.read_text())

    print(f"Running {len(samples)} sample leads through the pipeline...\n")

    for i, sample in enumerate(samples, start=1):
        print(f"--- [{i}/{len(samples)}] source={sample['source']} ---")
        print(f"input: {sample['text'][:100]}{'...' if len(sample['text']) > 100 else ''}")
        try:
            result = pipeline.process_lead(sample["text"], source=sample["source"])
            action = "CREATED" if result.is_new else "UPDATED"
            print(f"-> {action} customer #{result.customer_id}: {result.record.get('name')} "
                  f"({result.record.get('company')})")
            print(f"   next_action: {result.record.get('next_action')}")
            print(f"   assigned_to: {result.record.get('assigned_to')}")
            if result.warnings:
                print(f"   warnings: {result.warnings}")
        except ValueError as e:
            print(f"-> REJECTED (validation): {e}")
        except Exception as e:
            print(f"-> FAILED: {e}")
        print()

        if i < len(samples):
            time.sleep(PAUSE_BETWEEN_LEADS_SECONDS)

    print("Done. Records now in CRM:")
    for c in db.list_customers():
        print(f"  #{c['id']} {c['name']} @ {c['company']} — stage={c['stage']} "
              f"next_action={c['next_action']}")

    print(f"\nStart the dashboard with: python -m app.main")


if __name__ == "__main__":
    sys.exit(main())