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
    "sqlite:///murmures_paix.db"
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

    main_choice = db.Column(db.String(10))
    sub_choice = db.Column(db.String(10))


with app.app_context():
    db.create_all()

# =========================================================
# MENU (TON NOUVEAU MENU)
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
            "3": "Tensions naissantes ou malentendus"
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

# =========================================================
# AMBASSADEURS
# =========================================================

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
        "Tensions naissantes ou malentendus": {"nom": "Emma T.", "tel": "+22890788901"},
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

# =========================================================
# HELPERS
# =========================================================

RESET_CMDS = {"menu", "0", "restart", "accueil", "home", "retour"}


def send(msg):
    resp = MessagingResponse()
    resp.message(msg)
    return str(resp)


def clean(text):
    if not text:
        return ""
    return " ".join(text.lower().strip().split())


def reset(session):
    session.step = "menu"
    session.main_choice = None
    session.sub_choice = None


def is_reset(body):
    return body in RESET_CMDS


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
        "🔄 Tapez MENU pour revenir."
    )


def sub_menu(main):
    data = MENU.get(main)

    if not data:
        return main_menu()

    txt = f"📌 *{data['label']}*\n━━━━━━━━━━━━━━\n\n"

    for k, v in data["sub"].items():
        txt += f"{k}️⃣ {v}\n"

    txt += "\n🔄 Tapez MENU pour revenir."
    return txt

# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    user_id = request.form.get("From", "").replace("whatsapp:", "")
    body = clean(request.form.get("Body", ""))

    if not user_id:
        return "error", 400

    session = UserSession.query.filter_by(id=user_id).first()

    if not session:
        session = UserSession(id=user_id)
        db.session.add(session)
        db.session.commit()
        return send(main_menu())

    # =====================================================
    # RESET GLOBAL
    # =====================================================

    if is_reset(body):
        reset(session)
        db.session.commit()
        return send(main_menu())

    # =====================================================
    # MENU PRINCIPAL
    # =====================================================

    if session.step == "menu":

        if body in MENU:
            session.main_choice = body
            session.step = "sub_menu"
            db.session.commit()
            return send(sub_menu(body))

        return send(main_menu())

    # =====================================================
    # SOUS MENU
    # =====================================================

    if session.step == "sub_menu":

        main = session.main_choice

        if not main or main not in MENU:
            reset(session)
            db.session.commit()
            return send(main_menu())

        if body in MENU[main]["sub"]:
            session.sub_choice = body
            session.step = "done"
            db.session.commit()

            main_label = MENU[main]["label"]
            sub_label = MENU[main]["sub"][body]

            return send(
                "🟢 *DEMANDE ENREGISTRÉE*\n"
                "━━━━━━━━━━━━━━\n\n"
                f"📌 Catégorie : {main_label}\n"
                f"📍 Sous-catégorie : {sub_label}\n\n"
                "🕊️ Merci pour votre signalement.\n\n"
                "Tapez MENU pour revenir."
            )

        return send(sub_menu(main))

    # =====================================================
    # FINAL + AMBASSADEUR
    # =====================================================

    if session.step == "done":

        main_label = MENU[session.main_choice]["label"]
        sub_label = MENU[session.main_choice]["sub"][session.sub_choice]

        amb = get_ambassadeur(main_label, sub_label)

        reset(session)
        db.session.commit()

        return send(
            "✅ *SIGNALEMENT FINALISÉ*\n"
            "━━━━━━━━━━━━━━\n\n"
            f"📌 Catégorie : {main_label}\n"
            f"📍 Sous-catégorie : {sub_label}\n\n"
            f"👤 Ambassadeur : {amb['nom']}\n"
            f"📞 Contact : {amb['tel']}\n\n"
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
