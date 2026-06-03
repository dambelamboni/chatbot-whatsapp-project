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

    date_creation = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

# =========================================================
# RESET COMMANDS
# =========================================================

RESET_CMDS = {"menu", "0", "restart", "accueil", "home"}

# =========================================================
# MENU STRUCTURE (MIS À JOUR)
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
# COMMUNES / CANTONS
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
# AMBASSADEURS
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


def get_ambassadeur(commune_key, category):
    return AMBASSADEURS.get(commune_key, {}).get(category, ("Non assigné", "N/A"))

# =========================================================
# MENUS
# =========================================================

def main_menu():
    return (
        "🕊️ *MURMURES DU QUARTIER*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"    
        "1️⃣ Signalement\n"
        "2️⃣ Déclarer un fait\n"
        "3️⃣ Obtenir un conseil\n"
        "4️⃣ SOS (Urgence)\n\n"
        "🔄 MENU pour revenir à tout moment"
    )


def sub_menu(main):
    txt = f"📌 *{MENU[main]['label']}*\n\n"
    for k, v in MENU[main]["sub"].items():
        txt += f"{k}️⃣ {v}\n"
    return txt


def commune_menu():
    return (
        "🏛️ *Choisissez la commune*\n\n"
        "1️⃣ Commune de Tandjouaré\n"
        "2️⃣ Commune de Nano\n"
    )


def canton_menu(commune):
    txt = f"📍 *{COMMUNES[commune]['nom']}*\n\n"
    for k, v in COMMUNES[commune]["cantons"].items():
        txt += f"{k}️⃣ {v}\n"
    txt += "\n🔄 MENU pour revenir"
    return txt

# =========================================================
# WEBHOOK CORE
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

        # RESET GLOBAL
        if body in RESET_CMDS:
            reset(session)
            db.session.commit()
            return send(main_menu())

        # =====================================================
        # STEP 1: MENU
        # =====================================================
        if session.step == "menu":

            if body in MENU:
                session.main = body
                session.step = "sub"
                db.session.commit()
                return send(sub_menu(body))

            return send(main_menu())

        # =====================================================
        # STEP 2: SUB MENU
        # =====================================================
        if session.step == "sub":

            if body in MENU[session.main]["sub"]:
                session.sub = body
                session.step = "commune"
                db.session.commit()
                return send(commune_menu())

            return send(sub_menu(session.main))

        # =====================================================
        # STEP 3: COMMUNE
        # =====================================================
        if session.step == "commune":

            if body in COMMUNES:
                session.commune = body
                session.step = "canton"
                db.session.commit()
                return send(canton_menu(body))

            return send(commune_menu())

        # =====================================================
        # STEP 4: FINAL (CANTON + SAVE)
        # =====================================================
        if session.step == "canton":

            if body not in COMMUNES[session.commune]["cantons"]:
                return send(canton_menu(session.commune))

            canton_label = COMMUNES[session.commune]["cantons"][body]
            commune_label = COMMUNES[session.commune]["nom"]

            categorie = MENU[session.main]["label"]
            sous_categorie = MENU[session.main]["sub"][session.sub]

            amb_nom, amb_tel = get_ambassadeur(session.commune, categorie)

            # SAVE
            signal = Signalement(
                telephone=user,
                categorie=categorie,
                sous_categorie=sous_categorie,
                commune=commune_label,
                canton=canton_label,
                ambassadeur_nom=amb_nom,
                ambassadeur_tel=amb_tel
            )

            db.session.add(signal)
            db.session.commit()

            # BUILD MESSAGE
            message = (
                "🟢 *SIGNALEMENT ENREGISTRÉ*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📌 Catégorie : {categorie}\n"
                f"📎 Sous-catégorie : {sous_categorie}\n"
                f"🏛️ Commune : {commune_label}\n"
                f"📍 Canton : {canton_label}\n\n"
                "👤 Ambassadeur assigné :\n"
                f"Nom : {amb_nom}\n"
                f"Téléphone : {amb_tel}\n\n"
                "✔ Transmission réussie\n\n"
                "🔄 MENU pour recommencer"
            )

            # RESET SAFE AFTER SAVE
            reset(session)
            db.session.commit()

            return send(message)

        reset(session)
        db.session.commit()
        return send(main_menu())


if __name__ == "__main__":
    app.run(debug=True)
