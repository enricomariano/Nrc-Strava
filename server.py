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
        return jsonify({ "error": f"Errore nella generazione URL OAuth: {str(e)}" }), 500

# 🔑 Callback
@app.route("/callback")
def callback():
    try:
        code = request.args.get("code")
        if not code:
            return jsonify({ "error": "Nessun codice ricevuto" }), 400

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
        return jsonify({ "error": f"Errore nel callback: {str(e)}" }), 500


# 📌 Attività dettagliate per frontend
@app.route("/activities")
def activities():
    try:
        activities = list(client.get_activities(limit=50))
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
                "location": {
                    "city": act.location_city,
                    "state": act.location_state,
                    "country": act.location_country
                },
                "map": act.map.summary_polyline if act.map else None
            })
        return jsonify(enriched)
    except Exception as e:
        return jsonify({ "error": f"Errore nel recupero attività: {str(e)}" }), 500


# 📊 Stream biomeccanici
@app.route("/details/<int:activity_id>")
def details(activity_id):
    try:
        act = client.get_activity(activity_id)
        return jsonify({
            "total_elevation_gain_m": getattr(act, "total_elevation_gain", None),
            "elev_high_m": getattr(act, "elev_high", None),
            "elev_low_m": getattr(act, "elev_low", None),
            "calories": getattr(act, "calories", None),
            "average_heartrate": getattr(act, "average_heartrate", None),
            "average_watts": getattr(act, "average_watts", None)
        })
    except Exception as e:
        return jsonify({ "error": f"Errore dettagli attività: {str(e)}" }), 500

@app.route("/analyze/week")
def analyze_week():
    try:
        with open("detailed_attivita.json") as f:
            data = json.load(f)

        # Raggruppa per settimana
        from collections import defaultdict
        import datetime

        weekly = defaultdict(lambda: {"distance": 0, "calories": 0, "watts": [], "hr": []})
        for act in data:
            date = datetime.datetime.fromisoformat(act["start_date"]).date()
            week = date.isocalendar()[1]
            key = f"Settimana {week}"

            weekly[key]["distance"] += act.get("distance_km", 0)
            weekly[key]["calories"] += act.get("calories", 0) or 0
            if act.get("average_watts"): weekly[key]["watts"].append(act["average_watts"])
            if act.get("average_heartrate"): weekly[key]["hr"].append(act["average_heartrate"])

        labels = list(weekly.keys())
        chart = {
            "labels": labels,
            "datasets": [
                {"label": "Distanza (km)", "data": [round(weekly[w]["distance"], 1) for w in labels]},
                {"label": "Calorie", "data": [round(weekly[w]["calories"], 1) for w in labels]},
                {"label": "Potenza media", "data": [round(sum(weekly[w]["watts"]) / len(weekly[w]["watts"]), 1) if weekly[w]["watts"] else 0 for w in labels]},
                {"label": "HR media", "data": [round(sum(weekly[w]["hr"]) / len(weekly[w]["hr"]), 1) if weekly[w]["hr"] else 0 for w in labels]}
            ]
        }

        text = f"📊 Hai coperto {sum([weekly[w]['distance'] for w in labels]):.1f} km nelle ultime settimane, bruciando circa {sum([weekly[w]['calories'] for w in labels]):.0f} kcal. La potenza media è stata di {round(sum([sum(weekly[w]['watts']) for w in labels]) / max(1, sum([len(weekly[w]['watts']) for w in labels])), 1)} W."

        return jsonify({"text": text, "chart": chart})
    except Exception as e:
        return jsonify({ "error": f"Errore analisi settimanale: {str(e)}" }), 500

@app.route("/status")
def status():
    try:
        token_info = {}
        if os.path.exists("token.json"):
            with open("token.json") as f:
                t = json.load(f)
            token_info = {
                "access_token": t["access_token"],
                "expires_in_sec": int(t["expires_at"] - time.time()),
                "refresh_token": t["refresh_token"]
            }

        file_info = {
            "detailed_attivita.json": os.path.exists("detailed_attivita.json"),
            "valid_json": False
        }

        try:
            with open("detailed_attivita.json") as f:
                json.load(f)
            file_info["valid_json"] = True
        except:
            pass

        rate = getattr(client, "rate_limits", {})
        return jsonify({
            "token": token_info,
            "file_status": file_info,
            "rate_limits": rate
        })
    except Exception as e:
        return jsonify({ "error": f"Errore diagnostico: {str(e)}" }), 500

@app.route("/gear-usage")
def gear_usage():
    try:
        with open("detailed_attivita.json") as f:
            data = json.load(f)

        usage = {}
        for act in data:
            gear = act.get("gear_id", "Sconosciuto")
            usage.setdefault(gear, 0)
            usage[gear] += act.get("distance_km", 0)

        return jsonify({k: round(v, 1) for k, v in usage.items()})
    except Exception as e:
        return jsonify({ "error": f"Errore gear usage: {str(e)}" }), 500
        
# 💾 Salvataggio attività dettagliate
@app.route("/save-detailed")
def save_detailed():
    try:
        ensure_valid_token()
        detailed = []
        existing = []
        if os.path.exists("detailed_attivita.json"):
            with open("detailed_attivita.json") as f:
                existing = json.load(f)

        existing_ids = {a["id"] for a in existing}
        summaries = list(client.get_activities(limit=50))

        for summary in summaries:
            if summary.id in existing_ids:
                continue
            try:
                act = client.get_activity(summary.id)
            except Exception as e:
                print(f"⚠️ Skipping activity {summary.id} → {str(e)}")
                continue

            detailed.append({
                "id": act.id,
                "name": getattr(act, "name", None),
                "type": str(getattr(act, "type", "")).replace("root='", "").replace("'", ""),
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
                "gear_id": str(getattr(act, "gear_id", "")),
                "device_name": str(getattr(act, "device_name", "")),
                "trainer": getattr(act, "trainer", None),
                "commute": getattr(act, "commute", None),
                "manual": getattr(act, "manual", None),
                "private": getattr(act, "private", None),
                "visibility": str(getattr(act, "visibility", "")),
                "location_city": getattr(act, "location_city", None),
                "location_state": getattr(act, "location_state", None),
                "location_country": getattr(act, "location_country", None),
                "map_summary_polyline": act.map.summary_polyline if getattr(act, "map", None) else None
            })

        with open("detailed_attivita.json", "w") as f:
            json.dump(existing + detailed, f, indent=2)

        print(f"✅ Salvate {len(detailed)} nuove attività")
        return f"✅ Salvate {len(detailed)} nuove attività in detailed_attivita.json"
    except Exception as e:
        print("❌ Errore nel salvataggio:", str(e))
        return jsonify({ "error": f"Errore nel salvataggio dettagliato: {str(e)}" }), 500

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
            return jsonify({ "error": "Nessun token salvato" }), 404
    except Exception as e:
        return jsonify({ "error": f"Errore nel debug token: {str(e)}" }), 500


@app.route("/cached-activities")
def cached_activities():
    try:
        file_info = { "valid_json": False }

        try:
            with open("detailed_attivita.json") as f:
                data = json.load(f)
            file_info["valid_json"] = True
        except:
            return jsonify({ "error": "❌ detailed_attivita.json non valido o assente", "file_status": file_info }), 500

        return jsonify(data)
    except Exception as e:
        return jsonify({ "error": str(e) }), 500


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
        return jsonify({ "error": f"Errore nel caricamento cache: {str(e)}" }), 500


@app.route("/download-json")
def download_json():
    try:
        return app.send_static_file("detailed_attivita.json")
    except Exception as e:
        return jsonify({ "error": f"Errore nel download: {str(e)}" }), 500


# 🚀 Avvio compatibile con Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

































