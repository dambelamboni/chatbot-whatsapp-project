import os
import threading
from datetime import datetime

from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from twilio.twiml.messaging_response import MessagingResponse

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
# MENU (ORIGINAL + CLEAN)
# =========================================================

MENU = {
    "1": {
        "label": "Signalement",
        "sub": {
            "1": "Conflits ou violence",
            "2": "Viol ou VBG",
            "3": "Rumeur du quartier",
            "4": "Groupe suspect ou personne suspecte"
        }
    },
    "2": {
        "label": "Déclarer un fait",
        "sub": {
            "1": "Injustice sociale",
            "2": "Vulnérabilités",
            "3": "Tensions naissantes ou malentendus"
        }
    },
    "3": {
        "label": "Obtenir un conseil",
        "sub": {
            "1": "Cas de VBG",
            "2": "Viol",
            "3": "Litige foncier",
            "4": "Autres"
        }
    },
    "4": {
        "label": "SOS (Urgence)",
        "sub": {
            "1": "Braquage",
            "2": "Cambriolage",
            "3": "Agression ou attaque terroriste"
        }
    }
}

# =========================================================
# COMMUNES + CANTONS (ORIGINAL COMPLET)
# =========================================================

COMMUNES = {
    "1": {
        "nom": "Commune de Tandjouaré",
        "cantons": {
            "1": "Bogou",
            "2": "Bombouaka",
            "3": "Boulogou",
            "4": "Pligou",
            "5": "Tammongue",
            "6": "Loko",
            "7": "Nandoga",
            "8": "Goundoga"
        }
    },
    "2": {
        "nom": "Commune de Nano",
        "cantons": {
            "1": "Bagou",
            "2": "Sissiek",
            "3": "Sangou",
            "4": "Nano",
            "5": "Mamprougou",
            "6": "Lokpanou",
            "7": "Tampialim",
            "8": "Doukpergou"
        }
    }
}

# =========================================================
# AMBASSADEURS (ORIGINAL EXACT)
# =========================================================

AMBASSADEURS = {
    "Commune de Tandjouaré": {
        "Signalement": {"nom": "Jean K.", "tel": "+22890011234"},
        "Déclarer un fait": {"nom": "Sara T.", "tel": "+22890122345"},
        "Obtenir un conseil": {"nom": "Amina K.", "tel": "+22890233456"},
        "SOS (Urgence)": {"nom": "Police nationale", "tel": "112"}
    },
    "Commune de Nano": {
        "Signalement": {"nom": "Lea S.", "tel": "+22890566789"},
        "Déclarer un fait": {"nom": "Yao I.", "tel": "+22890677890"},
        "Obtenir un conseil": {"nom": "Emma T.", "tel": "+22890788901"},
        "SOS (Urgence)": {"nom": "Sécurité", "tel": "112"}
    }
}

# =========================================================
# VERNACULAIRE AUDIO
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


# =========================================================
# AUDIO FIX (IMPORTANT)
# =========================================================

def is_audio(req):
    media_url = req.form.get("MediaUrl0")
    media_type = req.form.get("MediaContentType0", "")

    return media_url is not None and "audio" in media_type


# =========================================================
# AMBASSADEUR SELECT
# =========================================================

def get_ambassadeur(commune_label, category_label):
    return AMBASSADEURS.get(commune_label, {}).get(
        category_label,
        {"nom": "Non assigné", "tel": "N/A"}
    )

# =========================================================
# MENUS
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


def sub_menu(main):
    txt = f"📌 *{MENU[main]['label']}*\n\n"
    for k, v in MENU[main]["sub"].items():
        txt += f"{k}️⃣ {v}\n"
    return txt


def commune_menu():
    return (
        "🏛️ *Choisissez la commune*\n\n"
        "1️⃣ Tandjouaré\n"
        "2️⃣ Nano\n"
    )


def canton_menu(commune):
    txt = f"📍 *{COMMUNES[commune]['nom']}*\n\n"
    for k, v in COMMUNES[commune]["cantons"].items():
        txt += f"{k}️⃣ {v}\n"
    return txt

# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    with lock:

        user = request.form.get("From", "").replace("whatsapp:", "")
        body = clean(request.form.get("Body", ""))

        session = UserSession.query.get(user)

        if not session:
            session = UserSession(id=user)
            db.session.add(session)
            db.session.commit()
            return send(main_menu())

        if body in RESET_CMDS:
            reset(session)
            db.session.commit()
            return send(main_menu())

        # =====================================================
        # AUDIO PRIORITAIRE (CORRIGÉ)
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

            return send(
                "🎤 *AUDIO REÇU*\n\n"
                "✔ Transmis immédiatement\n\n"
                f"👤 {VERNACULAIRE['nom']}\n"
                f"📞 {VERNACULAIRE['tel']}\n\n"
                "🔄 MENU"
            )

        # =====================================================
        # FLOW NORMAL
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

            category = MENU[session.main]["label"]
            sub = MENU[session.main]["sub"][session.sub]

            amb = get_ambassadeur(commune, category)

            signal = Signalement(
                telephone=user,
                categorie=category,
                sous_categorie=sub,
                commune=commune,
                canton=canton,
                ambassadeur_nom=amb["nom"],
                ambassadeur_tel=amb["tel"],
                type_signal="texte"
            )

            db.session.add(signal)
            db.session.commit()

            reset(session)
            db.session.commit()

            return send(
                "🟢 *SIGNALEMENT ENREGISTRÉ*\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"📌 Catégorie : {category}\n"
                f"📎 Type : {sub}\n"
                f"🏛️ Commune : {commune}\n"
                f"📍 Canton : {canton}\n\n"
                "👤 Ambassadeur :\n"
                f"{amb['nom']} - {amb['tel']}\n\n"
                "🔄 MENU"
            )

        reset(session)
        db.session.commit()
        return send(main_menu())


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
