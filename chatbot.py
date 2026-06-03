import os
import threading
from datetime import datetime

from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///murmures_secure.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
lock = threading.Lock()

# =========================================================
# TWILIO
# =========================================================

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_NUMBER = "whatsapp:+14155238886"

client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID and TWILIO_TOKEN else None


def send_whatsapp(to, message):
    if not client:
        return
    try:
        client.messages.create(
            from_=TWILIO_NUMBER,
            to=f"whatsapp:{to}",
            body=message
        )
    except Exception as e:
        print("Twilio error:", e)

# =========================================================
# MODELS
# =========================================================

class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.String(80), primary_key=True)
    step = db.Column(db.String(30), default="menu")
    main = db.Column(db.String(10))
    sub = db.Column(db.String(10))
    commune = db.Column(db.String(10))
    canton = db.Column(db.String(10))


class Signalement(db.Model):
    __tablename__ = "signalements"

    id = db.Column(db.Integer, primary_key=True)
    telephone = db.Column(db.String(50))
    categorie = db.Column(db.String(120))
    sous_categorie = db.Column(db.String(120))
    commune = db.Column(db.String(120))
    canton = db.Column(db.String(120))
    ambassadeur_nom = db.Column(db.String(120))
    ambassadeur_tel = db.Column(db.String(50))
    type_signal = db.Column(db.String(30), default="texte")
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

# =========================================================
# RESET
# =========================================================

RESET_CMDS = {"menu", "0", "restart", "accueil", "home"}

# =========================================================
# MENU
# =========================================================

MENU = {
    "1": {"label": "Signalement", "sub": {
        "1": "Conflits ou violence",
        "2": "Viol ou VBG",
        "3": "Rumeur du quartier",
        "4": "Groupe suspect ou personne suspecte"
    }},
    "2": {"label": "Déclarer un fait", "sub": {
        "1": "Injustice sociale",
        "2": "Vulnérabilités",
        "3": "Tensions naissantes ou malentendus"
    }},
    "3": {"label": "Obtenir un conseil", "sub": {
        "1": "Cas VBG",
        "2": "Viol",
        "3": "Litige foncier",
        "4": "Autres"
    }},
    "4": {"label": "SOS (Urgence)", "sub": {
        "1": "Braquage",
        "2": "Cambriolage",
        "3": "Agression ou attaque terroriste"
    }}
}

# =========================================================
# COMMUNES / CANTONS
# =========================================================

COMMUNES = {
    "1": {
        "nom": "Commune de Tandjouaré",
        "cantons": {
            "1": "Bogou", "2": "Bombouaka", "3": "Boulogou",
            "4": "Pligou", "5": "Tammongue", "6": "Loko",
            "7": "Nandoga", "8": "Goundoga"
        }
    },
    "2": {
        "nom": "Commune de Nano",
        "cantons": {
            "1": "Bagou", "2": "Sissiek", "3": "Sangou",
            "4": "Nano", "5": "Mamprougou", "6": "Lokpanou",
            "7": "Tampialim", "8": "Doukpergou"
        }
    }
}

# =========================================================
# AMBASSADEURS PAR COMMUNE (NORMAL FLOW)
# =========================================================

AMBASSADEURS = {
    "1": {
        "Signalement": ("Jean K.", "+22890011234"),
        "Déclarer un fait": ("Sara T.", "+22890122345"),
        "Obtenir un conseil": ("Amina K.", "+22890233456"),
        "SOS (Urgence)": ("Police nationale", "112")
    },
    "2": {
        "Signalement": ("Lea S.", "+22890566789"),
        "Déclarer un fait": ("Yao I.", "+22890677890"),
        "Obtenir un conseil": ("Emma T.", "+22890788901"),
        "SOS (Urgence)": ("Sécurité", "112")
    }
}

# =========================================================
# VERNACULAIRE (AUDIO ONLY)
# =========================================================

VERNACULAIRE = {
    "nom": "Banganaré Tikita",
    "tel": "+22892391868"
}

# =========================================================
# HELPERS
# =========================================================

def send(msg):
    resp = MessagingResponse()
    resp.message(msg)
    return str(resp)


def reset(session):
    session.step = "menu"
    session.main = None
    session.sub = None
    session.commune = None
    session.canton = None


def clean(text):
    return text.strip().lower() if text else ""


def is_audio(req):
    return int(req.form.get("NumMedia", 0)) > 0 and "audio" in req.form.get("MediaContentType0", "")

# =========================================================
# MENU DISPLAY
# =========================================================

def main_menu():
    return (
        "🕊️ *MURMURES DU QUARTIER*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Signalement\n"
        "2️⃣ Déclarer un fait\n"
        "3️⃣ Obtenir un conseil\n"
        "4️⃣ SOS (Urgence)\n\n"
        "🔄 MENU pour revenir"
    )

# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    with lock:

        user = request.form.get("From", "").replace("whatsapp:", "")
        body = clean(request.form.get("Body", ""))

        session = UserSession.query.get(user)

        # INIT
        if not session:
            session = UserSession(id=user)
            db.session.add(session)
            db.session.commit()
            return send(main_menu())

        # RESET
        if body in RESET_CMDS:
            reset(session)
            db.session.commit()
            return send(main_menu())

        # =====================================================
        # 🎤 AUDIO PRIORITY (NE BLOQUE PAS LE RESTE DU SYSTEME)
        # =====================================================
        if is_audio(request):

            try:
                db.session.add(Signalement(
                    telephone=user,
                    categorie="Audio / Vernaculaire",
                    sous_categorie="Message vocal Moba",
                    commune="N/A",
                    canton="N/A",
                    ambassadeur_nom=VERNACULAIRE["nom"],
                    ambassadeur_tel=VERNACULAIRE["tel"],
                    type_signal="audio"
                ))
                db.session.commit()

                # 🔔 NOTIFICATION VERNACULAIRE
                send_whatsapp(
                    VERNACULAIRE["tel"],
                    f"🎤 AUDIO REÇU\n📞 {user}\n⚠️ Traitement immédiat"
                )

                return send(
                    "🎤 AUDIO REÇU\n"
                    f"➡ Envoyé à {VERNACULAIRE['nom']}\n"
                    "🔄 MENU"
                )

            except Exception as e:
                print("Audio error:", e)
                return send("❌ Erreur traitement audio")

        # =====================================================
        # NORMAL FLOW (AMBASSADEURS PAR COMMUNE)
        # =====================================================

        if session.step == "menu":

            if body in MENU:
                session.main = body
                session.step = "sub"
                db.session.commit()
                return send(sub_menu(body))

            return send(main_menu())

        if session.step == "sub":

            if body in MENU[session.main]["sub"]:
                session.sub = body
                session.step = "commune"
                db.session.commit()
                return send(commune_menu())

            return send(sub_menu(session.main))

        if session.step == "commune":

            if body in COMMUNES:
                session.commune = body
                session.step = "canton"
                db.session.commit()
                return send(canton_menu(body))

            return send(commune_menu())

        if session.step == "canton":

            if body not in COMMUNES[session.commune]["cantons"]:
                return send(canton_menu(session.commune))

            canton = COMMUNES[session.commune]["cantons"][body]
            commune = COMMUNES[session.commune]["nom"]

            cat = MENU[session.main]["label"]
            sub = MENU[session.main]["sub"][session.sub]

            amb_nom, amb_tel = AMBASSADEURS[session.commune][cat]

            db.session.add(Signalement(
                telephone=user,
                categorie=cat,
                sous_categorie=sub,
                commune=commune,
                canton=canton,
                ambassadeur_nom=amb_nom,
                ambassadeur_tel=amb_tel,
                type_signal="texte"
            ))
            db.session.commit()

            reset(session)
            db.session.commit()

            return send(
                "🟢 *SIGNALEMENT ENREGISTRÉ*\n\n"
                f"📌 Catégorie : {cat}\n"
                f"📎 Sous-catégorie : {sub}\n"
                f"🏛️ Commune : {commune}\n"
                f"📍 Canton : {canton}\n\n"
                "👤 Ambassadeur :\n"
                f"{amb_nom} - {amb_tel}\n\n"
                "🔄 MENU"
            )

        reset(session)
        db.session.commit()
        return send(main_menu())


if __name__ == "__main__":
    app.run(debug=True)
