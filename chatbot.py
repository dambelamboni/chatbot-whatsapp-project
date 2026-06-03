import os
from datetime import datetime
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from twilio.twiml.messaging_response import MessagingResponse

# =========================================================
# APP
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

    id = db.Column(db.String(50), primary_key=True)

    step = db.Column(db.String(30), default="menu")

    categorie = db.Column(db.String(100))
    sous_categorie = db.Column(db.String(100))

    commune = db.Column(db.String(100))
    canton = db.Column(db.String(100))


class Signalement(db.Model):
    __tablename__ = "signalements"

    id = db.Column(db.Integer, primary_key=True)

    telephone = db.Column(db.String(50))

    categorie = db.Column(db.String(100))
    sous_categorie = db.Column(db.String(100))

    commune = db.Column(db.String(100))
    canton = db.Column(db.String(100))

    statut = db.Column(db.String(20), default="Nouveau")

    date_creation = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

# =========================================================
# REFERENTIELS
# =========================================================

CATEGORIES = {
    "1": {
        "nom": "Signalement",
        "options": {
            "1": "Conflit ou violence",
            "2": "Viol ou VBG",
            "3": "Rumeur du quartier",
            "4": "Groupe ou personne suspecte"
        }
    },

    "2": {
        "nom": "Déclarer un fait",
        "options": {
            "1": "Injustice sociale",
            "2": "Vulnérabilité communautaire",
            "3": "Tension naissante ou malentendu"
        }
    },

    "3": {
        "nom": "Obtenir un conseil",
        "options": {
            "1": "Cas de VBG",
            "2": "Cas de viol",
            "3": "Litige foncier",
            "4": "Autre situation"
        }
    },

    "4": {
        "nom": "SOS (Urgence)",
        "options": {
            "1": "Agression en cours",
            "2": "Attaque terroriste",
            "3": "Braquage ou cambriolage",
            "4": "Autre urgence sécuritaire"
        }
    },

    "5": {
        "nom": "Autres",
        "options": {
            "1": "Poser une question",
            "2": "Faire une suggestion",
            "3": "Contacter l'équipe",
            "4": "Autre demande"
        }
    }
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

# =========================================================
# MENUS
# =========================================================

def send_reply(msg):
    resp = MessagingResponse()
    resp.message(msg)
    return str(resp)


def get_main_menu():
    return (
        "🕊️ *MURMURES DU QUARTIER*\n"
        "━━━━━━━━━━━━━━\n\n"
        "1️⃣ Signalement\n"
        "2️⃣ Déclarer un fait\n"
        "3️⃣ Obtenir un conseil\n"
        "4️⃣ SOS (Urgence)\n"
        "5️⃣ Autres\n\n"
        "Répondez par un numéro.\n"
        "MENU pour revenir."
    )


def get_sub_menu(cat):
    data = CATEGORIES[cat]

    text = f"📂 *{data['nom']}*\n━━━━━━━━━━━━━━\n\n"

    for k, v in data["options"].items():
        text += f"{k}️⃣ {v}\n"

    return text


def get_commune_menu():
    return (
        "🏛️ Choisissez votre commune :\n\n"
        "1️⃣ Commune de Tandjouaré\n"
        "2️⃣ Commune de Nano"
    )


def get_canton_menu(commune):
    data = COMMUNES[commune]

    text = f"📍 {data['nom']}\n\nChoisissez votre canton :\n\n"

    for k, v in data["cantons"].items():
        text += f"{k}️⃣ {v}\n"

    return text


# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    user_id = request.form.get("From")
    body = request.form.get("Body", "").strip().lower()

    if not user_id:
        abort(400)

    session = UserSession.query.get(user_id)

    # ---------------- INIT SESSION ----------------

    if not session:
        session = UserSession(id=user_id, step="menu")
        db.session.add(session)
        db.session.commit()
        return send_reply(get_main_menu())

    # ---------------- RESET ----------------

    if body in ["menu", "0", "restart", "accueil"]:
        session.step = "menu"
        session.categorie = None
        session.sous_categorie = None
        session.commune = None
        session.canton = None
        db.session.commit()
        return send_reply(get_main_menu())

    # =====================================================
    # MENU PRINCIPAL
    # =====================================================

    if session.step == "menu":

        if body in CATEGORIES:
            session.categorie = CATEGORIES[body]["nom"]
            session.step = "sous_menu"
            db.session.commit()
            return send_reply(get_sub_menu(body))

        return send_reply(get_main_menu())

    # =====================================================
    # SOUS CATEGORIE
    # =====================================================

    if session.step == "sous_menu":

        cat_key = None
        for k, v in CATEGORIES.items():
            if v["nom"] == session.categorie:
                cat_key = k
                break

        if not cat_key or body not in CATEGORIES[cat_key]["options"]:
            return send_reply(get_sub_menu(cat_key))

        session.sous_categorie = CATEGORIES[cat_key]["options"][body]
        session.step = "commune"
        db.session.commit()

        return send_reply(get_commune_menu())

    # =====================================================
    # COMMUNE
    # =====================================================

    if session.step == "commune":

        if body not in COMMUNES:
            return send_reply(get_commune_menu())

        session.commune = COMMUNES[body]["nom"]
        session.step = "canton"
        db.session.commit()

        return send_reply(get_canton_menu(body))

    # =====================================================
    # CANTON + SAVE
    # =====================================================

    if session.step == "canton":

        commune_key = None
        for k, v in COMMUNES.items():
            if v["nom"] == session.commune:
                commune_key = k
                break

        if not commune_key or body not in COMMUNES[commune_key]["cantons"]:
            return send_reply(get_canton_menu(commune_key))

        session.canton = COMMUNES[commune_key]["cantons"][body]

        # ---------------- SAVE ----------------

        signalement = Signalement(
            telephone=user_id,
            categorie=session.categorie,
            sous_categorie=session.sous_categorie,
            commune=session.commune,
            canton=session.canton
        )

        db.session.add(signalement)

        # reset session
        session.step = "menu"
        session.categorie = None
        session.sous_categorie = None
        session.commune = None
        session.canton = None

        db.session.commit()

        return send_reply(
            "✅ *SIGNALEMENT ENREGISTRÉ*\n"
            "━━━━━━━━━━━━━━\n\n"
            "Merci pour votre contribution.\n"
            "Un médiateur traitera votre demande.\n\n"
            "Tapez MENU pour recommencer."
        )

    return send_reply(get_main_menu())


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
