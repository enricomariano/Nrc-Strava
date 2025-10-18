from flask import Flask, redirect, request, jsonify
from stravalib.client import Client
import os, json, time

app = Flask(__name__)
client = Client()

# 🔁 Ricarica e refresh token se esiste
if os.path.exists("token.json"):
    with open("token.json") as f:
        saved = json.load(f)
        if time.time() > saved["expires_at"]:
            refreshed = client.refresh_access_token(
                client_id=os.getenv("STRAVA_CLIENT_ID"),
                client_secret=os.getenv("STRAVA_CLIENT_SECRET"),
                refresh_token=saved["refresh_token"]
            )
            client.access_token = refreshed["access_token"]
            with open("token.json", "w") as f:
                json.dump(refreshed, f)
        else:
            client.access_token = saved["access_token"]

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
        client.access_token = token["access_token"]

        with open("token.json", "w") as f:
            json.dump(token, f)

        print("✅ Access token salvato:", token["access_token"])
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
            "distance_km": round(float(a.distance) / 1000, 2),
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

@app.route("/save-json")
def save_json():
    try:
        all_acts = []
        for act in client.get_activities(limit=200):
            all_acts.append({
                "id": act.id,
                "name": act.name,
                "type": act.type,
                "start_date": act.start_date.isoformat(),
                "elapsed_time_sec": float(act.elapsed_time) if act.elapsed_time else None,
                "distance_km": round(float(act.distance) / 1000, 2) if act.distance else None,
                "average_speed_kmh": round(float(act.average_speed) * 3.6, 2) if act.average_speed else None,
                "max_speed_kmh": round(float(act.max_speed) * 3.6, 2) if act.max_speed else None,
                "total_elevation_gain_m": act.total_elevation_gain,
                "elev_high_m": act.elev_high,
                "elev_low_m": act.elev_low,
                "calories": act.calories,
                "gear_id": act.gear_id,
                "device_name": act.device_name,
                "trainer": act.trainer,
                "commute": act.commute,
                "manual": act.manual,
                "private": act.private,
                "visibility": act.visibility,
                "location_city": act.location_city,
                "location_state": act.location_state,
                "location_country": act.location_country,
                "map_summary_polyline": act.map.summary_polyline if act.map else None
            })
        with open("attivita.json", "w") as f:
            json.dump(all_acts, f, indent=2)
        return f"✅ Salvate {len(all_acts)} attività in attivita.json"
    except Exception as e:
        return f"❌ Errore nel salvataggio attività: {str(e)}", 500


# 🚀 Avvio compatibile con Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)







