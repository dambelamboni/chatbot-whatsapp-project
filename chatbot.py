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
    "sqlite:///murmures_final.db"
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

    main = db.Column(db.String(10))
    sub = db.Column(db.String(10))
    description = db.Column(db.Text)

    commune = db.Column(db.String(10))
    canton = db.Column(db.String(10))


class Signalement(db.Model):
    __tablename__ = "signalements"

    id = db.Column(db.Integer, primary_key=True)
    telephone = db.Column(db.String(50))

    categorie = db.Column(db.String(100))
    sous_categorie = db.Column(db.String(100))
    description = db.Column(db.Text)

    commune = db.Column(db.String(100))
    canton = db.Column(db.String(100))

    ambassadeur_nom = db.Column(db.String(100))
    ambassadeur_tel = db.Column(db.String(50))

    date_creation = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

# =========================================================
# RESET
# =========================================================

RESET_CMDS = {"menu", "0", "restart", "accueil", "home", "retour"}

# =========================================================
# MENU PRINCIPAL (HIÉRARCHIE EXACTE)
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
            "2": "Vulnérabilités",
            "3": "Tensions ou malentendus"
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
        "label": "SOS",
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
# AMBASSADEURS PAR COMMUNE + CATÉGORIE
# =========================================================

AMBASSADEURS = {
    "1": {  # Tandjouaré
        "Signalement": ("Jean K.", "+22890011234"),
        "Déclarer un fait": ("Sara T.", "+22890122345"),
        "Obtenir un conseil": ("Amina K.", "+22890233456"),
        "SOS": ("Police locale", "112")
    },
    "2": {  # Nano
        "Signalement": ("Lea S.", "+22890566789"),
        "Déclarer un fait": ("Yao I.", "+22890677890"),
        "Obtenir un conseil": ("Emma T.", "+22890788901"),
        "SOS": ("Sécurité nationale", "112")
    }
}

# =========================================================
# HELPERS
# =========================================================

def send(msg):
    resp = MessagingResponse()
    resp.message(msg)
    return str(resp)


def clean(text):
    return text.strip().lower() if text else ""


def reset(session):
    session.step = "menu"
    session.main = None
    session.sub = None
    session.description = None
    session.commune = None
    session.canton = None


def is_reset(text):
    return text in RESET_CMDS


def main_menu():
    return (
        "🕊️ *MURMURES DU QUARTIER*\n━━━━━━━━━━━━━━\n\n"
        "1️⃣ Signalement\n"
        "2️⃣ Déclarer un fait\n"
        "3️⃣ Obtenir un conseil\n"
        "4️⃣ SOS\n\n"
        "🔄 MENU pour revenir."
    )


def sub_menu(main):
    txt = f"📌 {MENU[main]['label']}\n\n"
    for k, v in MENU[main]["sub"].items():
        txt += f"{k}️⃣ {v}\n"
    txt += "\n🔄 MENU pour revenir."
    return txt


def commune_menu():
    return (
        "🏛️ Choisissez la commune :\n\n"
        "1️⃣ Tandjouaré\n"
        "2️⃣ Nano\n\n"
        "🔄 MENU pour revenir."
    )


def canton_menu(commune):
    txt = f"📍 {COMMUNES[commune]['nom']}\n\n"
    for k, v in COMMUNES[commune]["cantons"].items():
        txt += f"{k}️⃣ {v}\n"
    txt += "\n🔄 MENU pour revenir."
    return txt


def get_ambassadeur(commune, main_label):
    return AMBASSADEURS.get(commune, {}).get(
        main_label,
        ("Non assigné", "N/A")
    )

# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    user_id = request.form.get("From", "").replace("whatsapp:", "")
    body = clean(request.form.get("Body", ""))

    session = UserSession.query.get(user_id)

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
    # MENU
    # =====================================================

    if session.step == "menu":

        if body in MENU:
            session.main = body
            session.step = "sub"
            db.session.commit()
            return send(sub_menu(body))

        return send(main_menu())

    # =====================================================
    # SUB MENU
    # =====================================================

    if session.step == "sub":

        if body in MENU[session.main]["sub"]:
            session.sub = body
            session.step = "description"
            db.session.commit()
            return send("✍️ Décrivez la situation :\n\n🔄 MENU pour annuler.")

        return send(sub_menu(session.main))

    # =====================================================
    # DESCRIPTION
    # =====================================================

    if session.step == "description":

        session.description = body
        session.step = "commune"
        db.session.commit()

        return send(commune_menu())

    # =====================================================
    # COMMUNE
    # =====================================================

    if session.step == "commune":

        if body not in COMMUNES:
            return send(commune_menu())

        session.commune = body
        session.step = "canton"
        db.session.commit()

        return send(canton_menu(body))

    # =====================================================
    # CANTON + FINAL PROCESS
    # =====================================================

    if session.step == "canton":

        if body not in COMMUNES[session.commune]["cantons"]:
            return send(canton_menu(session.commune))

        canton_name = COMMUNES[session.commune]["cantons"][body]
        session.canton = canton_name

        main_label = MENU[session.main]["label"]
        sub_label = MENU[session.main]["sub"][session.sub]

        amb_name, amb_tel = get_ambassadeur(session.commune, main_label)

        signalement = Signalement(
            telephone=user_id,
            categorie=main_label,
            sous_categorie=sub_label,
            description=session.description,
            commune=COMMUNES[session.commune]["nom"],
            canton=canton_name,
            ambassadeur_nom=amb_name,
            ambassadeur_tel=amb_tel
        )

        try:
            db.session.add(signalement)
            db.session.commit()

        except Exception:
            db.session.rollback()
            reset(session)
            db.session.commit()
            return send("❌ Erreur serveur. Réessayez ou tapez MENU.")

        # RESET PROPRE
        reset(session)
        db.session.commit()

        # AFFICHAGE FINAL
        return send(
            "🟢 *DEMANDE ENREGISTRÉE*\n━━━━━━━━━━━━━━\n\n"
            f"📌 Catégorie : {main_label}\n"
            f"📎 Sous-catégorie : {sub_label}\n"
            f"🏛️ Commune : {COMMUNES[session.commune]['nom']}\n"
            f"📍 Canton : {canton_name}\n\n"
            "👤 Ambassadeur :\n"
            f"{amb_name} - {amb_tel}\n\n"
            "✅ Traitement en cours.\n\n"
            "🔄 MENU pour recommencer."
        )

    reset(session)
    db.session.commit()
    return send(main_menu())


if __name__ == "__main__":
    app.run(debug=True)
