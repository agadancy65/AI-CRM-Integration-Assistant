import requests

resp = requests.post(
    "http://127.0.0.1:5000/intake",
    headers={"X-Webhook-Secret": "change-me"},
    json={
        "text": "Hi, I'm Chidi from Vantage Foods. We need help automating our supplier invoice approvals. chidi@vantagefoods.com",
        "source": "contact_form",
    },
)
print(resp.status_code)
print(resp.json())