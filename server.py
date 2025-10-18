
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
        acts = list(client.get_activities(limit=200))
        return jsonify([{
            "id": a.id,
            "name": a.name,
            "type": a.type,
            "start_date": a.start_date.isoformat(),
            "elapsed_time_sec": float(a.elapsed_time) if a.elapsed_time else None,
            "distance_km": round(float(a.distance) / 1000, 2) if a.distance else None,
            "average_speed_kmh": round(float(a.average_speed) * 3.6, 2) if a.average_speed else None,
            "max_speed_kmh": round(float(a.max_speed) * 3.6, 2) if a.max_speed else None,
            "total_elevation_gain_m": a.total_elevation_gain,
            "elev_high_m": a.elev_high,
            "elev_low_m": a.elev_low,
            "gear_id": a.gear_id,
            "device_name": a.device_name,
            "trainer": a.trainer,
            "commute": a.commute,
            "manual": a.manual,
            "private": a.private,
            "visibility": a.visibility,
            "location_city": a.location_city,
            "location_state": a.location_state,
            "location_country": a.location_country,
            "map_summary_polyline": a.map.summary_polyline if a.map else None
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

# 💾 Salvataggio attività
@app.route("/save-json")
def save_json():
    try:
        all_acts = []
        for a in client.get_activities(limit=200):
            all_acts.append({
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "start_date": a.start_date.isoformat(),
                "elapsed_time_sec": float(a.elapsed_time) if a.elapsed_time else None,
                "distance_km": round(float(a.distance) / 1000, 2) if a.distance else None,
                "average_speed_kmh": round(float(a.average_speed) * 3.6, 2) if a.average_speed else None,
                "max_speed_kmh": round(float(a.max_speed) * 3.6, 2) if a.max_speed else None,
                "total_elevation_gain_m": a.total_elevation_gain,
                "elev_high_m": a.elev_high,
                "elev_low_m": a.elev_low,
                "gear_id": a.gear_id,
                "device_name": a.device_name,
                "trainer": a.trainer,
                "commute": a.commute,
                "manual": a.manual,
                "private": a.private,
                "visibility": a.visibility,
                "location_city": a.location_city,
                "location_state": a.location_state,
                "location_country": a.location_country,
                "map_summary_polyline": a.map.summary_polyline if a.map else None
            })
        with open("attivita.json", "w") as f:
            json.dump(all_acts, f, indent=2)
        return f"✅ Salvate {len(all_acts)} attività in attivita.json"
    except Exception as e:
        return f"❌ Errore nel salvataggio attività: {str(e)}", 500

# 🔍 Debug token
@app.route("/debug/token")
def debug_token():
    try:
        if os.path.exists("token.json"):
            with open("token.json") as f:
                t = json.load(f)
            return jsonify({
                "access_token": t["access_token"],
                "expires_at": t["expires_at"],
                "expires_in_sec": int(t["expires_at"] - time.time()),
                "refresh_token": t["refresh_token"]
            })
        else:
            return "❌ Nessun token salvato", 404
    except Exception as e:
        return f"❌ Errore nel debug token: {str(e)}", 500

# 🚀 Avvio compatibile con Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
