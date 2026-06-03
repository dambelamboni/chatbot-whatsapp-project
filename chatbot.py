import os
from datetime import datetime
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from twilio.twiml.messaging_response import MessagingResponse

# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///murmures_quartier.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================================================
# MODELES
# =========================================================

class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.String(60), primary_key=True)
    step = db.Column(db.String(30), default="menu")

    categorie = db.Column(db.String(100))
    description = db.Column(db.Text)

    commune = db.Column(db.String(100))
    canton = db.Column(db.String(100))


class Signalement(db.Model):
    __tablename__ = "signalements"

    id = db.Column(db.Integer, primary_key=True)
    telephone = db.Column(db.String(50))

    categorie = db.Column(db.String(100))
    description = db.Column(db.Text)

    commune = db.Column(db.String(100))
    canton = db.Column(db.String(100))

    ambassadeur_nom = db.Column(db.String(100))
    ambassadeur_tel = db.Column(db.String(50))

    statut = db.Column(db.String(20), default="Nouveau")
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

# =========================================================
# REFERENTIELS
# =========================================================

CATEGORIES = {
    "1": "Signalement",
    "2": "Déclarer un fait",
    "3": "Obtenir un conseil",
    "4": "SOS (Urgence)",
    "5": "Autres"
}

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

AMBASSADEURS = {
    "Commune de Tandjouaré": {
        "Signalement": {"nom": "Jean K.", "tel": "+22890011234"},
        "Déclarer un fait": {"nom": "Sara T.", "tel": "+22890122345"},
        "Obtenir un conseil": {"nom": "Amina K.", "tel": "+22890233456"},
        "SOS (Urgence)": {"nom": "Paul A.", "tel": "+22890344567"},
        "Autres": {"nom": "Luc M.", "tel": "+22890455678"}
    },
    "Commune de Nano": {
        "Signalement": {"nom": "Lea S.", "tel": "+22890566789"},
        "Déclarer un fait": {"nom": "Yao I.", "tel": "+22890677890"},
        "Obtenir un conseil": {"nom": "Emma T.", "tel": "+22890788901"},
        "SOS (Urgence)": {"nom": "Ali B.", "tel": "+22890899012"},
        "Autres": {"nom": "Sara M.", "tel": "+22890910123"}
    }
}

# =========================================================
# HELPERS
# =========================================================

def send_reply(msg):
    resp = MessagingResponse()
    resp.message(msg)
    return str(resp)


# 🔥 NORMALISATION ULTRA ROBUSTE
def normalize(text):
    if not text:
        return ""
    return " ".join(text.lower().strip().split())


# 🔥 RESET ROBUSTE (FIX FINAL TON BUG)
RESET_CMDS = {"menu", "0", "restart", "accueil", "home", "retour"}

def is_reset(body):
    clean = body.replace(".", "").replace("!", "").replace(",", "")
    return clean in RESET_CMDS


def reset_session(session):
    session.step = "menu"
    session.categorie = None
    session.description = None
    session.commune = None
    session.canton = None


def is_valid_number(value, keys):
    return value.isdigit() and value in keys


def get_ambassadeur(commune, categorie):
    return AMBASSADEURS.get(commune, {}).get(
        categorie,
        {"nom": "Non assigné", "tel": "Non disponible"}
    )

# =========================================================
# MENUS
# =========================================================

def get_main_menu():
    text = "\n━━━━━━━━━ 🕊️ MURMURES DU QUARTIER ━━━━━━━━━\n"
    for k, v in CATEGORIES.items():
        text += f"{k}️⃣ {v}\n"
    text += "\n🔄 MENU pour revenir à tout moment."
    return text


def get_commune_menu():
    return (
        "🏛️ Choisissez votre commune :\n\n"
        "1️⃣ Commune de Tandjouaré\n"
        "2️⃣ Commune de Nano\n\n"
        "🔄 MENU pour revenir."
    )


def get_canton_menu(commune):
    data = COMMUNES[commune]
    text = f"📍 {data['nom']}\n\nChoisissez votre canton :\n\n"

    for k, v in data["cantons"].items():
        text += f"{k}️⃣ {v}\n"

    text += "\n🔄 MENU pour revenir."
    return text

# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    try:
        user_id_raw = request.form.get("From")
        user_id = user_id_raw.replace("whatsapp:", "").strip()

        body_raw = request.form.get("Body", "")
        body = normalize(body_raw)

        if not user_id:
            return "Missing user", 400

        session = UserSession.query.filter_by(id=user_id).first()

        if not session:
            session = UserSession(id=user_id, step="menu")
            db.session.add(session)
            db.session.commit()
            return send_reply(get_main_menu())

        # =====================================================
        # RESET GLOBAL (FIX DEFINITIF)
        # =====================================================

        if is_reset(body):
            reset_session(session)
            db.session.commit()
            return send_reply(get_main_menu())

        # =====================================================
        # MENU
        # =====================================================

        if session.step == "menu":

            if is_valid_number(body, CATEGORIES.keys()):
                session.categorie = CATEGORIES[body]
                session.step = "description"
                db.session.commit()

                return send_reply(
                    "✍️ Décrivez la situation :\n\n"
                    "Ex: incident, problème, urgence...\n\n"
                    "🔄 MENU pour annuler."
                )

            return send_reply(get_main_menu())

        # =====================================================
        # DESCRIPTION
        # =====================================================

        if session.step == "description":

            if len(body_raw.strip()) < 3:
                return send_reply("⚠️ Description trop courte.\n🔄 MENU pour annuler.")

            session.description = body_raw.strip()
            session.step = "commune"
            db.session.commit()

            return send_reply(get_commune_menu())

        # =====================================================
        # COMMUNE
        # =====================================================

        if session.step == "commune":

            if not is_valid_number(body, COMMUNES.keys()):
                return send_reply(get_commune_menu())

            session.commune = COMMUNES[body]["nom"]
            session.step = "canton"
            db.session.commit()

            return send_reply(get_canton_menu(body))

        # =====================================================
        # CANTON + SAVE
        # =====================================================

        if session.step == "canton":

            commune_key = next(
                (k for k, v in COMMUNES.items() if v["nom"] == session.commune),
                None
            )

            if not commune_key:
                reset_session(session)
                db.session.commit()
                return send_reply(get_main_menu())

            if not is_valid_number(body, COMMUNES[commune_key]["cantons"].keys()):
                return send_reply(get_canton_menu(commune_key))

            session.canton = COMMUNES[commune_key]["cantons"][body]

            amb = get_ambassadeur(session.commune, session.categorie)

            signalement = Signalement(
                telephone=user_id,
                categorie=session.categorie,
                description=session.description,
                commune=session.commune,
                canton=session.canton,
                ambassadeur_nom=amb["nom"],
                ambassadeur_tel=amb["tel"]
            )

            db.session.add(signalement)

            reset_session(session)
            db.session.commit()

            return send_reply(
                "✅ *SIGNALEMENT ENREGISTRÉ*\n"
                "━━━━━━━━━━━━━━\n\n"
                f"📂 Catégorie : {signalement.categorie}\n"
                f"📝 Description : {signalement.description}\n"
                f"🏛️ Commune : {signalement.commune}\n"
                f"📍 Canton : {signalement.canton}\n\n"
                "👤 Ambassadeur :\n"
                f"{amb['nom']} - {amb['tel']}\n\n"
                "🕊️ Merci pour votre contribution.\n\n"
                "MENU pour recommencer."
            )

        return send_reply(get_main_menu())

    except Exception as e:
        print("ERROR:", e)
        return send_reply("⚠️ Erreur. Tapez MENU pour recommencer.")


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
