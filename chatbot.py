import os
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from twilio.twiml.messaging_response import MessagingResponse

# =========================================================
# APPLICATION
# =========================================================

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///murmures_paix.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================================================
# BASE DE DONNÉES
# =========================================================

class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.String(50), primary_key=True)
    step = db.Column(db.String(20), default="menu")
    service = db.Column(db.String(20), nullable=True)


with app.app_context():
    db.create_all()

# =========================================================
# RÉFÉRENTIEL DES PROFESSIONNELS
# =========================================================

PROFESSIONNELS = {
    "1": {
        "label": "Dapaong",
        "incident": {"nom": "Jean K.", "tel": "+22890011234"},
        "aide": {"nom": "Sara T.", "tel": "+22890122345"},
        "conseil": {"nom": "Amina K.", "tel": "+22890233456"},
    },
    "2": {
        "label": "Tandjouaré",
        "incident": {"nom": "Paul A.", "tel": "+22890344567"},
        "aide": {"nom": "Lea S.", "tel": "+22890455678"},
        "conseil": {"nom": "Yao I.", "tel": "+22890566789"},
    },
    "3": {
        "label": "Oti",
        "incident": {"nom": "Luc A.", "tel": "+22890677890"},
        "aide": {"nom": "Emma T.", "tel": "+22890788901"},
        "conseil": {"nom": "Ali B.", "tel": "+22890899012"},
    },
    "4": {
        "label": "Kpendjal",
        "incident": {"nom": "Paul Y.", "tel": "+22890910123"},
        "aide": {"nom": "Sara M.", "tel": "+22891021234"},
        "conseil": {"nom": "Jean F.", "tel": "+22891132345"},
    }
}

# =========================================================
# MENUS
# =========================================================

def get_main_menu():
    return (
        "🕊️ *MURMURES DU QUARTIER*\n"
        "━━━━━━━━━━━━━━\n\n"
        "Bienvenue sur la plateforme de médiation et de cohésion sociale.\n\n"
        "*Comment pouvons-nous vous aider ?*\n\n"
        "1️⃣ Signaler un incident ou un conflit\n"
        "2️⃣ Demander une assistance (Urgence / VBG)\n"
        "3️⃣ Obtenir un conseil juridique ou social\n\n"
        "ℹ️ Répondez simplement par *1*, *2* ou *3*.\n\n"
        "🔄 Tapez *MENU* à tout moment pour revenir à l'accueil."
    )

def get_zone_menu():
    return (
        "📍 *UNITÉ DE MÉDIATION*\n"
        "━━━━━━━━━━━━━━\n\n"
        "Veuillez sélectionner votre zone :\n\n"
        "1️⃣ Dapaong\n"
        "2️⃣ Tandjouaré\n"
        "3️⃣ Oti\n"
        "4️⃣ Kpendjal\n\n"
        "ℹ️ Répondez par le numéro correspondant."
    )

def send_reply(message):
    resp = MessagingResponse()
    resp.message(message)
    return str(resp)

# =========================================================
# WEBHOOK WHATSAPP
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    user_id = request.form.get("From")
    body = request.form.get("Body", "").strip().lower()

    if not user_id:
        abort(400)

    # -----------------------------------------------------
    # Création de session
    # -----------------------------------------------------

    session = UserSession.query.get(user_id)

    if not session:
        session = UserSession(
            id=user_id,
            step="menu"
        )

        db.session.add(session)
        db.session.commit()

        return send_reply(get_main_menu())

    # -----------------------------------------------------
    # Réinitialisation
    # -----------------------------------------------------

    if body in ["menu", "0", "restart", "accueil"]:
        session.step = "menu"
        session.service = None

        db.session.commit()

        return send_reply(get_main_menu())

    # -----------------------------------------------------
    # MENU PRINCIPAL
    # -----------------------------------------------------

    if session.step == "menu":

        services_map = {
            "1": "incident",
            "2": "aide",
            "3": "conseil"
        }

        if body in services_map:

            session.service = services_map[body]
            session.step = "zone"

            db.session.commit()

            return send_reply(get_zone_menu())

        # UX améliorée :
        # peu importe le texte envoyé, on réaffiche le menu
        return send_reply(get_main_menu())

    # -----------------------------------------------------
    # CHOIX DE LA ZONE
    # -----------------------------------------------------

    if session.step == "zone":

        if body not in PROFESSIONNELS:
            return send_reply(
                "⚠️ Zone non reconnue.\n\n"
                + get_zone_menu()
            )

        zone_data = PROFESSIONNELS[body]

        pro = zone_data.get(session.service)

        service_labels = {
            "incident": "Signalement d'incident",
            "aide": "Demande d'assistance",
            "conseil": "Conseil juridique ou social"
        }

        service_nom = service_labels.get(
            session.service,
            "Demande"
        )

        response = (
            "✅ *DOSSIER ENREGISTRÉ*\n"
            "━━━━━━━━━━━━━━\n\n"
            f"📌 *Type :* {service_nom}\n"
            f"📍 *Zone :* {zone_data['label']}\n\n"
            f"👤 *Médiateur assigné :* {pro['nom']}\n"
            f"📞 *Contact :* {pro['tel']}\n\n"
            "🕊️ Votre demande a été transmise avec succès.\n"
            "Un ambassadeur de paix local vous contactera prochainement.\n\n"
            "🔄 Tapez *MENU* pour effectuer une nouvelle demande."
        )

        session.step = "menu"
        session.service = None

        db.session.commit()

        return send_reply(response)

    # -----------------------------------------------------
    # Sécurité
    # -----------------------------------------------------

    return send_reply(get_main_menu())


# =========================================================
# LANCEMENT LOCAL
# =========================================================

if __name__ == "__main__":
    app.run()
