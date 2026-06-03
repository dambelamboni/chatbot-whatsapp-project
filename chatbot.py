import os
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from twilio.twiml.messaging_response import MessagingResponse

# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///murmures_pro.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================================================
# ANTI DUPLICATION TWILIO
# =========================================================

LAST_MESSAGE = {}

# =========================================================
# SESSION MODEL
# =========================================================

class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.String(60), primary_key=True)
    step = db.Column(db.String(30), default="menu")

    main_choice = db.Column(db.String(10))
    sub_choice = db.Column(db.String(10))
    canton_choice = db.Column(db.String(10))


with app.app_context():
    db.create_all()

# =========================================================
# MENU STRUCTURE
# =========================================================

MENU = {
    "1": {
        "label": "Signalement",
        "sub": {
            "1": "Conflits ou violence",
            "2": "Viol ou VBG",
            "3": "Rumeur du quartier",
            "4": "Groupe ou personne suspecte"
        }
    },
    "2": {
        "label": "Déclarer un fait",
        "sub": {
            "1": "Injustice sociale",
            "2": "Vulnérabilités communautaires",
            "3": "Tensions ou malentendus"
        }
    },
    "3": {
        "label": "Obtenir un conseil",
        "sub": {
            "1": "Cas de VBG",
            "2": "Viol",
            "3": "Litige foncier",
            "4": "Autre situation"
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

CANTONS = {
    "1": "Bogou",
    "2": "Bombouaka",
    "3": "Boulogou",
    "4": "Pligou",
    "5": "Tammongue",
    "6": "Loko",
    "7": "Nandoga",
    "8": "Goundoga"
}

AMBASSADEURS = {
    "Signalement": {
        "Conflits ou violence": {"nom": "Jean K.", "tel": "+22890011234"},
        "Viol ou VBG": {"nom": "Sara T.", "tel": "+22890122345"},
        "Rumeur du quartier": {"nom": "Amina K.", "tel": "+22890233456"},
        "Groupe ou personne suspecte": {"nom": "Paul A.", "tel": "+22890344567"},
    },
    "Déclarer un fait": {
        "Injustice sociale": {"nom": "Lea S.", "tel": "+22890566789"},
        "Vulnérabilités communautaires": {"nom": "Yao I.", "tel": "+22890677890"},
        "Tensions ou malentendus": {"nom": "Emma T.", "tel": "+22890788901"},
    },
    "Obtenir un conseil": {
        "Cas de VBG": {"nom": "Ali B.", "tel": "+22890899012"},
        "Viol": {"nom": "Sara M.", "tel": "+22890910123"},
        "Litige foncier": {"nom": "Jean F.", "tel": "+22891021234"},
        "Autre situation": {"nom": "Paul Y.", "tel": "+22891132345"},
    },
    "SOS (Urgence)": {
        "Braquage": {"nom": "Equipe Sécurité", "tel": "112"},
        "Cambriolage": {"nom": "Equipe Sécurité", "tel": "112"},
        "Agression ou attaque terroriste": {"nom": "Police Urgence", "tel": "112"},
    }
}

RESET_CMDS = {"menu", "0", "restart", "accueil", "home", "retour"}

# =========================================================
# HELPERS
# =========================================================

def send(msg):
    resp = MessagingResponse()
    resp.message(msg)
    return str(resp)


def normalize(text):
    if not text:
        return ""
    return " ".join(text.lower().strip().split())


def is_reset(msg):
    msg = msg.replace(".", "").replace("!", "").replace(",", "")
    return msg in RESET_CMDS


def reset(session):
    session.step = "menu"
    session.main_choice = None
    session.sub_choice = None
    session.canton_choice = None


def valid_main(x):
    return x in MENU


def valid_sub(main, sub):
    return main in MENU and sub in MENU[main]["sub"]


def get_ambassadeur(main_label, sub_label):
    return AMBASSADEURS.get(main_label, {}).get(
        sub_label,
        {"nom": "Non assigné", "tel": "Non disponible"}
    )

# =========================================================
# MENUS
# =========================================================

def main_menu():
    return (
        "🕊️ *MURMURES DU QUARTIER*\n━━━━━━━━━━━━━━\n\n"
        "1️⃣ Signalement\n"
        "2️⃣ Déclarer un fait\n"
        "3️⃣ Obtenir un conseil\n"
        "4️⃣ SOS (Urgence)\n\n"
        "🔄 MENU pour revenir à tout moment."
    )


def sub_menu(main):
    data = MENU[main]
    txt = f"📌 *{data['label']}*\n━━━━━━━━━━━━━━\n\n"

    for k, v in data["sub"].items():
        txt += f"{k}️⃣ {v}\n"

    txt += "\n🔄 MENU pour revenir."
    return txt


def canton_menu():
    txt = "📍 *Choisissez votre canton*\n━━━━━━━━━━━━━━\n\n"
    for k, v in CANTONS.items():
        txt += f"{k}️⃣ {v}\n"
    txt += "\n🔄 MENU pour revenir."
    return txt

# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    user_id = request.form.get("From", "").replace("whatsapp:", "")
    body_raw = request.form.get("Body", "")
    body = normalize(body_raw)
    message_sid = request.form.get("MessageSid")

    if not user_id:
        return "error", 400

    # =====================================================
    # ANTI DUPLICATION TWILIO
    # =====================================================

    if message_sid:
        if LAST_MESSAGE.get(user_id) == message_sid:
            return send(main_menu())
        LAST_MESSAGE[user_id] = message_sid

    # =====================================================
    # SESSION
    # =====================================================

    session = UserSession.query.filter_by(id=user_id).first()

    if not session:
        session = UserSession(id=user_id)
        db.session.add(session)
        db.session.commit()
        return send(main_menu())

    # =====================================================
    # RESET GLOBAL ULTRA ROBUSTE
    # =====================================================

    if is_reset(body):
        reset(session)
        db.session.commit()
        return send(main_menu())

    # =====================================================
    # MENU PRINCIPAL
    # =====================================================

    if session.step == "menu":

        if valid_main(body):
            session.main_choice = body
            session.step = "sub_menu"
            db.session.commit()
            return send(sub_menu(body))

        return send(main_menu())

    # =====================================================
    # SOUS MENU
    # =====================================================

    if session.step == "sub_menu":

        if not valid_main(session.main_choice):
            reset(session)
            db.session.commit()
            return send(main_menu())

        if valid_sub(session.main_choice, body):
            session.sub_choice = body
            session.step = "canton"
            db.session.commit()
            return send(canton_menu())

        return send(sub_menu(session.main_choice))

    # =====================================================
    # CANTON + FINAL (ENREGISTREMENT + AFFICHAGE)
    # =====================================================

    if session.step == "canton":

        if body not in CANTONS:
            return send(canton_menu())

        session.canton_choice = body

        main_label = MENU[session.main_choice]["label"]
        sub_label = MENU[session.main_choice]["sub"][session.sub_choice]
        canton_label = CANTONS[body]

        amb = get_ambassadeur(main_label, sub_label)

        reset(session)
        db.session.commit()

        return send(
            "🟢 *SIGNALEMENT ENREGISTRÉ*\n━━━━━━━━━━━━━━\n\n"
            f"📌 Catégorie : {main_label}\n"
            f"📍 Sous-catégorie : {sub_label}\n"
            f"🏘️ Canton : {canton_label}\n\n"
            "👤 *Ambassadeur affecté :*\n"
            f"{amb['nom']}\n"
            f"{amb['tel']}\n\n"
            "🕊️ Merci pour votre contribution.\n\n"
            "MENU pour recommencer."
        )

    # =====================================================
    # FALLBACK SAFE
    # =====================================================

    reset(session)
    db.session.commit()
    return send(main_menu())


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
