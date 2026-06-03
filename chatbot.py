import os
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from twilio.twiml.messaging_response import MessagingResponse

# =========================================================
# APP
# =========================================================

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///murmures_full.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================================================
# SESSION
# =========================================================

class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.String(60), primary_key=True)
    step = db.Column(db.String(30), default="menu")

    commune_choice = db.Column(db.String(10))
    canton_choice = db.Column(db.String(10))
    main_choice = db.Column(db.String(10))
    sub_choice = db.Column(db.String(10))


with app.app_context():
    db.create_all()

# =========================================================
# RESET COMMANDS
# =========================================================

RESET_CMDS = {"menu", "0", "restart", "accueil", "home", "retour"}

# =========================================================
# STRUCTURE COMMUNES / CANTONS
# =========================================================

COMMUNES = {
    "1": "Tandjouaré",
    "2": "Nano"
}

CANTONS = {
    "1": {"commune": "1", "label": "Bogou"},
    "2": {"commune": "1", "label": "Bombouaka"},
    "3": {"commune": "1", "label": "Boulogou"},
    "4": {"commune": "1", "label": "Pligou"},
    "5": {"commune": "1", "label": "Tammongue"},
    "6": {"commune": "1", "label": "Loko"},
    "7": {"commune": "1", "label": "Nandoga"},
    "8": {"commune": "1", "label": "Goundoga"},

    "9": {"commune": "2", "label": "Bagou"},
    "10": {"commune": "2", "label": "Sissiek"},
    "11": {"commune": "2", "label": "Sangou"},
    "12": {"commune": "2", "label": "Nano"},
    "13": {"commune": "2", "label": "Mamprougou"},
    "14": {"commune": "2", "label": "Lokpanou"},
    "15": {"commune": "2", "label": "Tampialim"},
    "16": {"commune": "2", "label": "Doukpergou"},
}

# =========================================================
# MENU PRINCIPAL
# =========================================================

MENU = {
    "1": {
        "label": "Signalement",
        "sub": {
            "1": "Conflits ou violence",
            "2": "Viol ou VBG",
            "3": "Rumeur du quartier",
            "4": "Personne ou groupe suspect"
        }
    },
    "2": {
        "label": "Déclarer un fait",
        "sub": {
            "1": "Injustice sociale",
            "2": "Vulnérabilité communautaire",
            "3": "Tension ou malentendu"
        }
    },
    "3": {
        "label": "Obtenir un conseil",
        "sub": {
            "1": "Cas de VBG",
            "2": "Viol",
            "3": "Litige foncier",
            "4": "Autre"
        }
    },
    "4": {
        "label": "SOS Urgence",
        "sub": {
            "1": "Braquage",
            "2": "Cambriolage",
            "3": "Attaque ou agression"
        }
    }
}

# =========================================================
# AMBASSADEURS
# =========================================================

AMBASSADEURS = {
    "Signalement": {"default": {"nom": "Jean K.", "tel": "+22890011234"}},
    "Déclarer un fait": {"default": {"nom": "Sara T.", "tel": "+22890122345"}},
    "Obtenir un conseil": {"default": {"nom": "Ali B.", "tel": "+22890233456"}},
    "SOS Urgence": {"default": {"nom": "Police Urgence", "tel": "112"}},
}

# =========================================================
# HELPERS
# =========================================================

def send(msg):
    resp = MessagingResponse()
    resp.message(msg)
    return str(resp)


def clean(text):
    return " ".join(text.lower().strip().split()) if text else ""


def reset(session):
    session.step = "menu"
    session.commune_choice = None
    session.canton_choice = None
    session.main_choice = None
    session.sub_choice = None


def is_reset(msg):
    return msg in RESET_CMDS


def get_ambassadeur(main_label):
    return AMBASSADEURS.get(main_label, {}).get(
        "default",
        {"nom": "Non assigné", "tel": "Non disponible"}
    )

# =========================================================
# MENUS TEXTES
# =========================================================

def main_menu():
    return (
        "🕊️ *MURMURES DU QUARTIER*\n━━━━━━━━━━━━━━\n\n"
        "1️⃣ Signalement\n"
        "2️⃣ Déclarer un fait\n"
        "3️⃣ Obtenir un conseil\n"
        "4️⃣ SOS Urgence\n\n"
        "🔄 MENU pour revenir."
    )


def commune_menu():
    return (
        "🏘️ *Choisissez la commune*\n━━━━━━━━━━━━━━\n\n"
        "1️⃣ Tandjouaré\n"
        "2️⃣ Nano\n\n"
        "🔄 MENU pour revenir."
    )


def canton_menu(commune_id):
    txt = "📍 *Choisissez le canton*\n━━━━━━━━━━━━━━\n\n"
    for k, v in CANTONS.items():
        if v["commune"] == commune_id:
            txt += f"{k}️⃣ {v['label']}\n"
    txt += "\n🔄 MENU pour revenir."
    return txt


def sub_menu(main):
    txt = f"📌 *{MENU[main]['label']}*\n━━━━━━━━━━━━━━\n\n"
    for k, v in MENU[main]["sub"].items():
        txt += f"{k}️⃣ {v}\n"
    txt += "\n🔄 MENU pour revenir."
    return txt

# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    user_id = request.form.get("From", "").replace("whatsapp:", "")
    body = clean(request.form.get("Body", ""))

    session = UserSession.query.filter_by(id=user_id).first()

    if not session:
        session = UserSession(id=user_id)
        db.session.add(session)
        db.session.commit()
        return send(main_menu())

    # RESET GLOBAL
    if is_reset(body):
        reset(session)
        db.session.commit()
        return send(main_menu())

    # =====================================================
    # STEP 1 : MENU
    # =====================================================

    if session.step == "menu":

        if body in MENU:
            session.main_choice = body
            session.step = "commune"
            db.session.commit()
            return send(commune_menu())

        return send(main_menu())

    # =====================================================
    # STEP 2 : COMMUNE
    # =====================================================

    if session.step == "commune":

        if body in COMMUNES:
            session.commune_choice = body
            session.step = "canton"
            db.session.commit()
            return send(canton_menu(body))

        return send(commune_menu())

    # =====================================================
    # STEP 3 : CANTON
    # =====================================================

    if session.step == "canton":

        if body in CANTONS and CANTONS[body]["commune"] == session.commune_choice:
            session.canton_choice = body
            session.step = "sub_menu"
            db.session.commit()
            return send(sub_menu(session.main_choice))

        return send(canton_menu(session.commune_choice))

    # =====================================================
    # STEP 4 : SOUS MENU + FINAL
    # =====================================================

    if session.step == "sub_menu":

        if body in MENU[session.main_choice]["sub"]:

            main_label = MENU[session.main_choice]["label"]
            sub_label = MENU[session.main_choice]["sub"][body]
            canton_label = CANTONS[session.canton_choice]["label"]
            commune_label = COMMUNES[session.commune_choice]

            amb = get_ambassadeur(main_label)

            reset(session)
            db.session.commit()

            return send(
                "🟢 *DEMANDE ENREGISTRÉE*\n━━━━━━━━━━━━━━\n\n"
                f"🏘️ Commune : {commune_label}\n"
                f"📍 Canton : {canton_label}\n"
                f"📌 Catégorie : {main_label}\n"
                f"📎 Sous-catégorie : {sub_label}\n\n"
                "👤 *Ambassadeur :*\n"
                f"{amb['nom']}\n"
                f"{amb['tel']}\n\n"
                "🕊️ Merci pour votre signalement.\n\n"
                "MENU pour recommencer."
            )

        return send(sub_menu(session.main_choice))

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
