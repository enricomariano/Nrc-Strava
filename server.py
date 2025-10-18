from flask import Flask, redirect, request, jsonify
from stravalib.client import Client
import os

app = Flask(__name__)
client = Client()

# 🔐 OAuth2 redirect
@app.route("/authorize")
def authorize():
    url = client.authorization_url(
        client_id=os.getenv("STRAVA_CLIENT_ID"),
        redirect_uri=os.getenv("STRAVA_REDIRECT_URI"),
        scope=["activity:read_all"]
    )
    return redirect(url)

# 🔑 Callback
@app.route("/callback")
def callback():
    code = request.args.get("code")
    token = client.exchange_code_for_token(
        client_id=os.getenv("STRAVA_CLIENT_ID"),
        client_secret=os.getenv("STRAVA_CLIENT_SECRET"),
        code=code
    )
    client.access_token = token
    return "✅ Token ricevuto"

# 📌 Attività
@app.route("/activities")
def activities():
    acts = list(client.get_activities(limit=10))
    return jsonify([{
        "id": a.id,
        "name": a.name,
        "distance": a.distance.num,
        "start_date": a.start_date.isoformat()
    } for a in acts])

# 📊 Stream biomeccanici
@app.route("/streams/<int:activity_id>")
def streams(activity_id):
    data = client.get_activity_streams(activity_id, types=["time", "altitude", "velocity_smooth", "heartrate"], resolution="medium")
    return jsonify({k: v.data for k, v in data.items()})

if __name__ == "__main__":
    app.run()
