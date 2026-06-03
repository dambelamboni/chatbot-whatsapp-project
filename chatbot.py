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
# TWILIO CONFIG
# =========================================================

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"

client = Client(TWILIO_SID, TWILIO_TOKEN)


def send_whatsapp(to, message):
    """Envoi sécurisé WhatsApp via Twilio"""
    try:
        client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            body=message,
            to=f"whatsapp:{to}"
        )
    except Exception as e:
        print("Twilio Error:", e)


# =========================================================
# MODELES
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
        "3": "Tensions naissantes"
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
# AMBASSADEUR VERNACULAIRE (AUDIO)
# =========================================================

VERNACULAIRE = {
    "nom": "Banganaré Tikita",
    "tel": "+33780261877"
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
    return req.form.get("NumMedia", "0") != "0"


# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    with lock:

        user = request.form.get("From", "").replace("whatsapp:", "")
        body = clean(request.form.get("Body", ""))

        session = UserSession.query.get(user)

        # INIT SESSION
        if not session:
            session = UserSession(id=user)
            db.session.add(session)
            db.session.commit()
            return send("🕊️ MENU\n1- Signalement\n2- Déclarer\n3- Conseil\n4- SOS\n\nTape MENU pour revenir")

        # RESET GLOBAL
        if body in RESET_CMDS:
            reset(session)
            db.session.commit()
            return send("🕊️ MENU PRINCIPAL\n1- Signalement\n2- Déclarer\n3- Conseil\n4- SOS")

        # =====================================================
        # AUDIO PRIORITAIRE (VERNACULAIRE)
        # =====================================================
        if is_audio(request):

            signal = Signalement(
                telephone=user,
                categorie="Audio / Vernaculaire",
                sous_categorie="Message vocal Moba",
                commune="N/A",
                canton="N/A",
                ambassadeur_nom=VERNACULAIRE["nom"],
                ambassadeur_tel=VERNACULAIRE["tel"],
                type_signal="audio"
            )

            db.session.add(signal)
            db.session.commit()

            # ENVOI WHATSAPP À L'AMBASSADEUR
            msg_amb = (
                "🔔 NOUVELLE ALERTE AUDIO\n\n"
                f"📞 Demandeur : {user}\n"
                "📌 Type : Message vocal (Moba)\n\n"
                "⚠️ Traitement immédiat requis"
            )

            send_whatsapp(VERNACULAIRE["tel"], msg_amb)

            return send(
                "🎤 AUDIO REÇU\n\n"
                f"✔ Envoyé à {VERNACULAIRE['nom']}\n"
                f"📞 {VERNACULAIRE['tel']}\n\n"
                "🔄 MENU"
            )

        # =====================================================
        # FLOW NORMAL SIMPLIFIÉ (STABLE)
        # =====================================================

        if session.step == "menu":
            if body in MENU:
                session.main = body
                session.step = "sub"
                db.session.commit()

                txt = f"📌 {MENU[body]['label']}\n\n"
                for k, v in MENU[body]["sub"].items():
                    txt += f"{k}️⃣ {v}\n"
                return send(txt)

            return send("🕊️ MENU\n1- Signalement\n2- Déclarer\n3- Conseil\n4- SOS")

        # fallback sécurité
        reset(session)
        db.session.commit()
        return send("🕊️ MENU")


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
