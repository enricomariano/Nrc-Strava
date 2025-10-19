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
        client.set_token(
            refreshed["access_token"],
            refresh_token=refreshed["refresh_token"],
            expires_at=refreshed["expires_at"]
        )
        with open("token.json", "w") as f:
            json.dump(refreshed, f)
    else:
        client.set_token(
            saved["access_token"],
            refresh_token=saved["refresh_token"],
            expires_at=saved["expires_at"]
        )


# 🌐 Interfaccia HTML
@app.route("/attivita")
def attivita():
    return render_template("attivita.html")

# 🔐 OAuth2 redirect
@app.route("/authorize")
def authorize():
    try:
        redirect_uri = os.getenv("STRAVA_REDIRECT_URI")
        if not redirect_uri:
            # fallback hardcoded URI (solo per test)
            redirect_uri = "https://nrc-strava.onrender.com/callback"

        url = client.authorization_url(
            client_id=os.getenv("STRAVA_CLIENT_ID"),
            redirect_uri=redirect_uri,
            scope=["activity:read_all"]
        )
        print("🔗 Redirect URI generato:", url)
        return redirect(url)
    except Exception as e:
        print("❌ Errore OAuth:", str(e))
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
        client.refresh_token = token["refresh_token"]

        with open("token.json", "w") as f:
            json.dump(token, f)

        print("✅ Access token salvato:", token["access_token"])
        return "✅ Token ricevuto e salvato"
    except Exception as e:
        print("❌ Errore nel callback:", str(e))
        return f"❌ Errore nel callback: {str(e)}", 500

# 📌 Attività dettagliate per frontend
# 📌 Attività dettagliate per frontend
@app.route("/activities")
def activities():
    try:
        activities = list(client.get_activities(limit=50))  # riduci il batch
        enriched = []
        for act in activities:
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
        summaries = list(client.get_activities(limit=50))  # batch ridotto per evitare rate limit

        for summary in summaries:
            act = client.get_activity(summary.id)  # ✅ ottieni DetailedActivity

            detailed.append({
                "id": act.id,
                "name": getattr(act, "name", None),
                "type": getattr(act, "type", None),
                "start_date": act.start_date.isoformat() if getattr(act, "start_date", None) else None,
                "elapsed_time_sec": float(act.elapsed_time) if getattr(act, "elapsed_time", None) else None,
                "distance_km": round(float(act.distance) / 1000, 2) if getattr(act, "distance", None) else None,
                "average_speed_kmh": round(float(act.average_speed) * 3.6, 2) if getattr(act, "average_speed", None) else None,
                "max_speed_kmh": round(float(act.max_speed) * 3.6, 2) if getattr(act, "max_speed", None) else None,
                "total_elevation_gain_m": getattr(act, "total_elevation_gain", None),
                "elev_high_m": getattr(act, "elev_high", None),
                "elev_low_m": getattr(act, "elev_low", None),
                "calories": getattr(act, "calories", None),
                "average_heartrate": getattr(act, "average_heartrate", None),
                "max_heartrate": getattr(act, "max_heartrate", None),
                "average_watts": getattr(act, "average_watts", None),
                "max_watts": getattr(act, "max_watts", None),
                "weighted_average_watts": getattr(act, "weighted_average_watts", None),
                "kudos_count": getattr(act, "kudos_count", None),
                "comment_count": getattr(act, "comment_count", None),
                "photo_count": getattr(act, "photo_count", None),
                "gear_id": getattr(act, "gear_id", None),
                "device_name": getattr(act, "device_name", None),
                "trainer": getattr(act, "trainer", None),
                "commute": getattr(act, "commute", None),
                "manual": getattr(act, "manual", None),
                "private": getattr(act, "private", None),
                "visibility": getattr(act, "visibility", None),
                "location_city": getattr(act, "location_city", None),
                "location_state": getattr(act, "location_state", None),
                "location_country": getattr(act, "location_country", None),
                "map_summary_polyline": act.map.summary_polyline if getattr(act, "map", None) else None
            })

        with open("detailed_attivita.json", "w") as f:
            json.dump(detailed, f, indent=2)

        print(f"✅ Salvate {len(detailed)} attività dettagliate")
        return f"✅ Salvate {len(detailed)} attività dettagliate in detailed_attivita.json"
    except Exception as e:
        print("❌ Errore nel salvataggio:", str(e))
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












