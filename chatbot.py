import os
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
    "sqlite:///murmures_pro.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================================================
# SESSION MODEL
# =========================================================

class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.String(80), primary_key=True)
    step = db.Column(db.String(30), default="menu")

    main = db.Column(db.String(10))
    sub = db.Column(db.String(10))

    commune = db.Column(db.String(10))
    canton = db.Column(db.String(10))


# =========================================================
# SIGNAL MODEL
# =========================================================

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
# RESET CONTROL
# =========================================================

RESET_CMDS = {"menu", "0", "restart", "accueil", "home"}

# =========================================================
# BUSINESS DATA
# =========================================================

MENU = {
    "1": {
        "label": "Signalement",
        "sub": {
            "1": "Conflits ou violence",
            "2": "Viol ou VBG",
            "3": "Rumeur du quartier",
            "4": "Personne suspecte"
        }
    },
    "2": {
        "label": "Déclarer un fait",
        "sub": {
            "1": "Injustice sociale",
            "2": "Vulnérabilité",
            "3": "Tensions / malentendus"
        }
    },
    "3": {
        "label": "Conseil",
        "sub": {
            "1": "Cas VBG",
            "2": "Viol",
            "3": "Litige foncier",
            "4": "Autres"
        }
    },
    "4": {
        "label": "SOS",
        "sub": {
            "1": "Braquage",
            "2": "Cambriolage",
            "3": "Agression"
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
            "4": "Pligou"
        }
    },
    "2": {
        "nom": "Commune de Nano",
        "cantons": {
            "1": "Bagou",
            "2": "Sissiek",
            "3": "Sangou",
            "4": "Nano"
        }
    }
}

AMBASSADEURS = {
    "1": {
        "Signalement": ("Jean K.", "+22890011234"),
        "Déclarer un fait": ("Sara T.", "+22890122345"),
        "Conseil": ("Amina K.", "+22890233456"),
        "SOS": ("Police nationale", "112")
    },
    "2": {
        "Signalement": ("Lea S.", "+22890566789"),
        "Déclarer un fait": ("Yao I.", "+22890677890"),
        "Conseil": ("Emma T.", "+22890788901"),
        "SOS": ("Sécurité", "112")
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


def main_menu():
    return (
        "🕊️ *MURMURES DU QUARTIER*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Signalement\n"
        "2️⃣ Déclarer un fait\n"
        "3️⃣ Conseil\n"
        "4️⃣ SOS\n\n"
        "ℹ️ Tapez MENU pour revenir à tout moment"
    )


def sub_menu(main):
    title = MENU[main]["label"]
    txt = f"📌 *{title}*\n\n"
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
    txt = "📍 *Choisissez le canton*\n\n"
    for k, v in COMMUNES[commune]["cantons"].items():
        txt += f"{k}️⃣ {v}\n"
    return txt


def get_ambassadeur(commune, category):
    return AMBASSADEURS.get(commune, {}).get(
        category,
        ("Non assigné", "N/A")
    )

# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    user = request.form.get("From", "").replace("whatsapp:", "")
    body = clean(request.form.get("Body", ""))

    session = UserSession.query.get(user)

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
    # 1. MENU
    # =====================================================

    if session.step == "menu":

        if body in MENU:
            session.main = body
            session.step = "sub"
            db.session.commit()
            return send(sub_menu(body))

        return send(main_menu())

    # =====================================================
    # 2. SUB MENU
    # =====================================================

    if session.step == "sub":

        if body in MENU[session.main]["sub"]:
            session.sub = body
            session.step = "commune"
            db.session.commit()
            return send(commune_menu())

        return send(sub_menu(session.main))

    # =====================================================
    # 3. COMMUNE
    # =====================================================

    if session.step == "commune":

        if body in COMMUNES:
            session.commune = body
            session.step = "canton"
            db.session.commit()
            return send(canton_menu(body))

        return send(commune_menu())

    # =====================================================
    # 4. CANTON + FINAL PROCESS
    # =====================================================

    if session.step == "canton":

        if body not in COMMUNES[session.commune]["cantons"]:
            return send(canton_menu(session.commune))

        canton = COMMUNES[session.commune]["cantons"][body]
        session.canton = canton

        category = MENU[session.main]["label"]
        subcategory = MENU[session.main]["sub"][session.sub]

        amb_name, amb_tel = get_ambassadeur(session.commune, category)

        # SAVE
        signal = Signalement(
            telephone=user,
            categorie=category,
            sous_categorie=subcategory,
            commune=COMMUNES[session.commune]["nom"],
            canton=canton,
            ambassadeur_nom=amb_name,
            ambassadeur_tel=amb_tel
        )

        db.session.add(signal)
        db.session.commit()

        # RESET CLEAN
        reset(session)
        db.session.commit()

        # FINAL OUTPUT
        return send(
            "🟢 *SIGNALEMENT ENREGISTRÉ AVEC SUCCÈS*\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 Catégorie : {category}\n"
            f"📎 Sous-catégorie : {subcategory}\n"
            f"🏛️ Commune : {COMMUNES[session.commune]['nom']}\n"
            f"📍 Canton : {canton}\n\n"
            "👤 *Ambassadeur assigné :*\n"
            f"{amb_name} - {amb_tel}\n\n"
            "✔ Transmission effectuée\n"
            "🔄 MENU pour recommencer"
        )

    reset(session)
    db.session.commit()
    return send(main_menu())


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)
