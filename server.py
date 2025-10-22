from flask import Flask, redirect, request, jsonify, render_template
from stravalib.client import Client
from dotenv import load_dotenv
import os, json, time, datetime
from collections import defaultdict
from itertools import islice

# 🔧 Carica variabili da .env (solo in locale)
load_dotenv()

app = Flask(__name__, template_folder="templates")
client = Client()

# --------------------------------------
# 🛠️ Gestione token
# --------------------------------------
def ensure_valid_token():
    """Controlla e rinnova il token se necessario"""
    if not os.path.exists("token.json"):
        raise Exception("Token mancante: esegui /authorize")

    with open("token.json") as f:
        saved = json.load(f)

    expires_at = saved.get("expires_at", 0)
    access_token = saved.get("access_token")
    refresh_token = saved.get("refresh_token")

    if not access_token or not refresh_token:
        raise Exception("Token incompleto: esegui /authorize")

    if time.time() > expires_at:
        refreshed = client.refresh_access_token(
            client_id=os.getenv("STRAVA_CLIENT_ID"),
            client_secret=os.getenv("STRAVA_CLIENT_SECRET"),
            refresh_token=refresh_token
        )
        client.access_token = refreshed["access_token"]
        client.refresh_token = refreshed["refresh_token"]
        client.token_expires_at = refreshed["expires_at"]

        with open("token.json", "w") as f:
            json.dump(refreshed, f)
        print("🔁 Token aggiornato")
    else:
        client.access_token = access_token
        client.refresh_token = refresh_token
        client.token_expires_at = expires_at


# --------------------------------------
# 🌐 Rotte principali
# --------------------------------------

@app.route("/debug/token")
def debug_token():
    try:
        if not os.path.exists("token.json"):
            return jsonify({ "error": "Nessun token salvato" }), 404

        with open("token.json") as f:
            t = json.load(f)

        expires_in = int(t["expires_at"] - time.time()) if "expires_at" in t else -1

        return jsonify({
            "access_token": t.get("access_token"),
            "refresh_token": t.get("refresh_token"),
            "expires_at": t.get("expires_at"),
            "expires_in_sec": expires_in
        })
    except Exception as e:
        return jsonify({ "error": f"Errore nel debug token: {str(e)}" }), 500

@app.route("/attivita")
def attivita():
    try:
        if not os.path.exists("token.json"):
            return redirect("/authorize")

        with open("token.json") as f:
            t = json.load(f)
        if time.time() > t["expires_at"]:
            return redirect("/authorize")

        return render_template("attivita.html")
    except Exception as e:
        return jsonify({ "error": f"Errore attivita: {str(e)}" }), 500



@app.route("/authorize")
def authorize():
    try:
        redirect_uri = os.getenv("STRAVA_REDIRECT_URI") or "https://nrc-strava.onrender.com/callback"
        url = client.authorization_url(
            client_id=os.getenv("STRAVA_CLIENT_ID"),
            redirect_uri=redirect_uri,
            scope=["activity:read_all"]
        )
        print("🔗 Redirect URI:", url)
        return redirect(url)
    except Exception as e:
        return jsonify({"error": f"Errore OAuth: {str(e)}"}), 500

@app.route("/callback")
def callback():
    try:
        code = request.args.get("code")
        if not code:
            return jsonify({"error": "Nessun codice ricevuto"}), 400

        token = client.exchange_code_for_token(
            client_id=os.getenv("STRAVA_CLIENT_ID"),
            client_secret=os.getenv("STRAVA_CLIENT_SECRET"),
            code=code
        )
        with open("token.json", "w") as f:
            json.dump(token, f)

        print("✅ Token salvato correttamente")
        return redirect("/attivita")
    except Exception as e:
        return jsonify({"error": f"Errore nel callback: {str(e)}"}), 500


@app.route("/activities")
def activities():
    try:
        ensure_valid_token()
        activities = list(client.get_activities(limit=50))
        data = []
        for act in activities:
            data.append({
                "id": act.id,
                "name": act.name,
                "type": act.type,
                "start_date": act.start_date.isoformat(),
                "distance_km": round(float(act.distance) / 1000, 2) if act.distance else None,
                "average_speed_kmh": round(float(act.average_speed) * 3.6, 2) if act.average_speed else None,
                "average_heartrate": getattr(act, "average_heartrate", None),
                "location": {
                    "city": act.location_city,
                    "country": act.location_country
                }
            })
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Errore nel recupero attività: {str(e)}"}), 500


@app.route("/details/<int:activity_id>")
def details(activity_id):
    try:
        ensure_valid_token()
        act = client.get_activity(activity_id)
        return jsonify({
            "elevation_gain": getattr(act, "total_elevation_gain", None),
            "elev_high": getattr(act, "elev_high", None),
            "elev_low": getattr(act, "elev_low", None),
            "average_watts": getattr(act, "average_watts", None),
            "average_heartrate": getattr(act, "average_heartrate", None),
        })
    except Exception as e:
        return jsonify({"error": f"Errore dettagli attività: {str(e)}"}), 500


# --------------------------------------
# 💾 Salvataggio attività dettagliate
# --------------------------------------
@app.route("/save-detailed")
def save_detailed():
    try:
        ensure_valid_token()
        detailed = []
        existing = []

        # Carica attività già salvate, protezione da file vuoto o corrotto
        if os.path.exists("attivita.json") and os.path.getsize("attivita.json") > 0:
            with open("attivita.json") as f:
                try:
                    existing = json.load(f)
                except json.JSONDecodeError:
                    print("⚠️ File attivita.json corrotto, inizializzo vuoto")
                    existing = []
        else:
            existing = []

        existing_ids = {a["id"] for a in existing}
        summaries = islice(client.get_activities(), 50)

        for summary in summaries:
            if summary.id in existing_ids:
                continue
            try:
                act = client.get_activity(summary.id)
            except Exception as e:
                print(f"⚠️ Skipping {summary.id}: {e}")
                continue

            detailed.append({
                "id": act.id,
                "name": getattr(act, "name", None),
                "type": str(getattr(act, "type", "")),
                "start_date": act.start_date.isoformat() if act.start_date else None,
                "distance_km": round(float(act.distance) / 1000, 2) if act.distance else None,
                "average_speed_kmh": round(float(act.average_speed) * 3.6, 2) if act.average_speed else None,
                "average_watts": getattr(act, "average_watts", None),
                "average_heartrate": getattr(act, "average_heartrate", None),
                "calories": getattr(act, "calories", None),
                "device_name": getattr(act, "device_name", None),
                "gear_id": getattr(act, "gear_id", None)
            })

        updated = existing + detailed
        updated.sort(key=lambda a: a["start_date"] or "", reverse=True)

        with open("attivita.json", "w") as f:
            json.dump(updated, f, indent=2)

        print(f"✅ Salvate {len(detailed)} nuove attività")
        return jsonify({
            "message": f"✅ Salvate {len(detailed)} nuove attività",
            "new_count": len(detailed),
            "total_count": len(updated)
        })
    except Exception as e:
        print(f"❌ Errore nel salvataggio: {str(e)}")
        return jsonify({ "error": f"Errore nel salvataggio: {str(e)}" }), 500
        


@app.route("/download-json")
def download_json():
    try:
        with open("attivita.json") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({ "error": f"Errore nel download: {str(e)}" }), 500



@app.route("/attivita.json")
def serve_attivita_json():
    try:
        if not os.path.exists("attivita.json") or os.path.getsize("attivita.json") == 0:
            print("⚠️ File attivita.json assente o vuoto, restituisco array vuoto")
            return jsonify([])

        with open("attivita.json") as f:
            content = f.read().strip()
            if not content or content == "null":
                print("⚠️ Contenuto non valido, restituisco array vuoto")
                return jsonify([])
            return jsonify(json.loads(content))
    except Exception as e:
        print(f"❌ Errore nel caricamento attivita.json: {e}")
        return jsonify({ "error": f"Errore nel caricamento attività: {str(e)}" }), 500


# --------------------------------------
# 📊 Analisi settimanale
# --------------------------------------
@app.route("/analyze/week")
def analyze_week():
    try:
        with open("detailed_attivita.json") as f:
            data = json.load(f)

        weekly = defaultdict(lambda: {"distance": 0, "calories": 0, "hr": []})
        for act in data:
            if not act.get("start_date"):
                continue
            date = datetime.datetime.fromisoformat(act["start_date"]).date()
            week = date.isocalendar()[1]
            key = f"Settimana {week}"
            weekly[key]["distance"] += act.get("distance_km", 0) or 0
            weekly[key]["calories"] += act.get("calories", 0) or 0
            if act.get("average_heartrate"):
                weekly[key]["hr"].append(act["average_heartrate"])

        labels = list(weekly.keys())
        chart = {
            "labels": labels,
            "datasets": [
                {"label": "Distanza (km)", "data": [weekly[w]["distance"] for w in labels]},
                {"label": "Calorie", "data": [weekly[w]["calories"] for w in labels]},
                {"label": "HR media", "data": [round(sum(weekly[w]["hr"]) / len(weekly[w]["hr"]), 1) if weekly[w]["hr"] else 0 for w in labels]}
            ]
        }

        summary = f"Hai percorso {sum(w['distance'] for w in weekly.values()):.1f} km nelle ultime settimane, bruciando circa {sum(w['calories'] for w in weekly.values()):.0f} kcal."
        return jsonify({"text": summary, "chart": chart})
    except Exception as e:
        return jsonify({"error": f"Errore analisi settimanale: {str(e)}"}), 500


# --------------------------------------
# 🚀 Avvio
# --------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)





























