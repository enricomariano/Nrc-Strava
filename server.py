from flask import Flask, redirect, request, jsonify
from stravalib.client import Client
import os

app = Flask(__name__)
client = Client()

# 🔐 OAuth2 redirect
@app.route("/authorize")
def authorize():
    try:
        url = client.authorization_url(
            client_id=os.getenv("STRAVA_CLIENT_ID"),
            redirect_uri=os.getenv("STRAVA_REDIRECT_URI"),
            scope=["activity:read_all"]
        )
        return redirect(url)
    except Exception as e:
        return f"❌ Errore nella generazione URL OAuth: {str(e)}", 500

# 🔑 Callback
@app.route("/callback")
def callback():
    try:
        code = request.args.get("code")
        if not code:
            return "❌ Nessun codice ricevuto", 400

        token = client.exchange_code_for_token(
            client_id=os.getenv("STRAVA_CLIENT_ID"),
            client_secret=os.getenv("STRAVA_CLIENT_SECRET"),
            code=code
        )
        client.access_token = token
        print("✅ Access token ricevuto:", token)
        return "✅ Token ricevuto e salvato"
    except Exception as e:
        return f"❌ Errore nel callback: {str(e)}", 500

# 📌 Attività
@app.route("/activities")
def activities():
    try:
        acts = list(client.get_activities(limit=10))
        return jsonify([{
            "id": a.id,
            "name": a.name,
            "distance": a.distance.num,
            "start_date": a.start_date.isoformat()
        } for a in acts])
    except Exception as e:
        return f"❌ Errore nel recupero attività: {str(e)}", 500

# 📊 Stream biomeccanici
@app.route("/streams/<int:activity_id>")
def streams(activity_id):
    try:
        data = client.get_activity_streams(
            activity_id,
            types=["time", "altitude", "velocity_smooth", "heartrate"],
            resolution="medium"
        )
        return jsonify({k: v.data for k, v in data.items()})
    except Exception as e:
        return f"❌ Errore nel recupero stream: {str(e)}", 500

# 🚀 Avvio compatibile con Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


