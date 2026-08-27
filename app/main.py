import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

from app import db, pipeline

app = Flask(__name__, template_folder="../templates")
db.init_db()


@app.route("/intake", methods=["POST"])
def intake():
    expected_secret = os.environ.get("WEBHOOK_SECRET", "")
    provided_secret = request.headers.get("X-Webhook-Secret", "")
    if expected_secret and provided_secret != expected_secret:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    raw_text = payload.get("text", "")
    source = payload.get("source", "webhook")

    try:
        result = pipeline.process_lead(raw_text, source=source)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"processing failed: {e}"}), 500

    return jsonify(result.to_dict()), 200


@app.route("/reminders/run", methods=["POST"])
def run_reminders():
    threshold = int(os.environ.get("REMINDER_THRESHOLD_DAYS", 3))
    stale = pipeline.run_reminder_sweep(threshold)
    return jsonify({"flagged": len(stale), "customers": stale}), 200


@app.route("/")
def dashboard():
    customers = db.list_customers()
    logs = db.list_audit_log(limit=50)
    return render_template("dashboard.html", customers=customers, logs=logs)


@app.route("/api/customers")
def api_customers():
    return jsonify(db.list_customers())


@app.route("/api/logs")
def api_logs():
    return jsonify(db.list_audit_log())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
