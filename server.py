from flask import Flask, redirect, request, jsonify, render_template
from stravalib.client import Client
from dotenv import load_dotenv
import os, json, time

# 🔧 Carica variabili da .env (solo in locale)
load_dotenv()

app = Flask(__name__, template_folder="templates")
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

# 🌐 Interfaccia HTML
@app.route("/attivita")
def attivita():
    return render_template("attivita.html")

# 🔐 OAuth2 redirect
@app.route("/authorize")
def authorize():
    try:
        url = client.authorization_url(
            client_id=os.getenv("STRAVA_CLIENT_ID"),
          redirect_uri="https://nrc-strava.onrender.com/callback",
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



# 📌 Attività dettagliate per frontend
@app.route("/activities")
def activities():
    try:
        enriched = []
        for summary in client.get_activities(limit=50):
            act = client.get_activity(summary.id)
            enriched.append({
                "id": act.id,
                "name": act.name,
                "type": act.type,
                "start_date": act.start_date.isoformat(),
                "elapsed_time_sec": float(act.elapsed_time) if act.elapsed_time else None,
                "distance_km": round(float(act.distance) / 1000, 2) if act.distance else None,
                "average_speed_kmh": round(float(act.average_speed) * 3.6, 2) if act.average_speed else None,
                "max_speed_kmh": round(float(act.max_speed) * 3.6, 2) if act.max_speed else None,
                "total_elevation_gain_m": act.total_elevation_gain,
                "calories": act.calories,
                "average_watts": act.average_watts,
                "max_watts": act.max_watts,
                "weighted_average_watts": act.weighted_average_watts,
                "average_heartrate": act.average_heartrate,
                "max_heartrate": act.max_heartrate,
                "kudos_count": act.kudos_count,
                "comment_count": act.comment_count,
                "photo_count": act.photo_count,
                "gear_id": act.gear_id,
                "device_name": getattr(act, "device_name", None),
                "location": {
                    "city": act.location_city,
                    "state": act.location_state,
                    "country": act.location_country
                },
                "map": act.map.summary_polyline if act.map else None
            })
        return jsonify(enriched)
    except Exception as e:
        return f"❌ Errore nel recupero attività: {str(e)}", 500

# 📊 Stream biomeccanici
@app.route("/streams/<int:activity_id>")
def streams(activity_id):
    try:
        data = client.get_activity_streams(
            activity_id,
            types=["time", "altitude", "velocity_smooth", "heartrate", "watts", "cadence"],
            resolution="medium"
        )
        return jsonify({k: v.data for k, v in data.items()})
    except Exception as e:
        return f"❌ Errore nel recupero stream: {str(e)}", 500

# 💾 Salvataggio attività dettagliate
@app.route("/save-detailed")
def save_detailed():
    try:
        detailed = []
        for summary in client.get_activities(limit=200):
            act = client.get_activity(summary.id)
            detailed.append({
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
                "average_heartrate": act.average_heartrate,
                "max_heartrate": act.max_heartrate,
                "average_watts": act.average_watts,
                "max_watts": act.max_watts,
                "weighted_average_watts": act.weighted_average_watts,
                "kudos_count": act.kudos_count,
                "comment_count": act.comment_count,
                "photo_count": act.photo_count,
                "gear_id": act.gear_id,
                "device_name": getattr(act, "device_name", None),
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
        with open("detailed_attivita.json", "w") as f:
            json.dump(detailed, f, indent=2)
        return f"✅ Salvate {len(detailed)} attività dettagliate in detailed_attivita.json"
    except Exception as e:
        return f"❌ Errore nel salvataggio dettagliato: {str(e)}", 500

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

@app.route("/cached-activities")
def cached_activities():
    try:
        with open("detailed_attivita.json") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return f"❌ Errore nel caricamento cache: {str(e)}", 500

@app.route("/trend-data")
def trend_data():
    try:
        trend = []
        for summary in client.get_activities(limit=100):
            act = client.get_activity(summary.id)
            trend.append({
                "date": act.start_date.date().isoformat(),
                "distance_km": round(float(act.distance) / 1000, 2) if act.distance else None,
                "elapsed_min": round(float(act.elapsed_time) / 60, 1) if act.elapsed_time else None,
                "average_speed_kmh": round(float(act.average_speed) * 3.6, 2) if act.average_speed else None,
                "average_watts": act.average_watts,
                "weighted_watts": act.weighted_average_watts,
                "calories": act.calories,
                "kilojoules": act.kilojoules,
                "average_heartrate": act.average_heartrate,
                "elevation_gain": act.total_elevation_gain,
                "kudos": act.kudos_count,
                "comments": act.comment_count
            })
        return jsonify(trend)
    except Exception as e:
        return f"❌ Errore nel recupero trend: {str(e)}", 500


# 🚀 Avvio compatibile con Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)






