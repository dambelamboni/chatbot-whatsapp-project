import os
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from twilio.twiml.messaging_response import MessagingResponse

# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    "DATABASE_URL",
    "sqlite:///murmures_paix.db"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =========================================================
# DATABASE MODEL
# =========================================================

class UserSession(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    step = db.Column(db.String(20), default="menu")
    service = db.Column(db.String(20), nullable=True)

# =========================================================
# INIT DB
# =========================================================

with app.app_context():
    db.create_all()

# =========================================================
# DATA
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
        "-*- SÉCURITÉ ET COHÉSION SOCIALE -*-\n\n"
        "Bienvenue sur Murmures du Quartier.\n\n"
        "1. Signaler un incident\n"
        "2. Demander une assistance\n"
        "3. Demander un conseil\n\n"
        "Tapez MENU pour recommencer."
    )

def get_zone_menu():
    return (
        "--- UNITÉ DE MÉDIATION ---\n\n"
        "Choisissez votre zone :\n"
        "1. Dapaong\n"
        "2. Tandjouaré\n"
        "3. Oti\n"
        "4. Kpendjal"
    )

# =========================================================
# TWILIO RESPONSE
# =========================================================

def send_reply(text):
    resp = MessagingResponse()
    resp.message(text)
    return str(resp)

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

    # NEW USER
    if not session:
        session = UserSession(id=user_id)
        db.session.add(session)
        db.session.commit()
        return send_reply(get_main_menu())

    # RESET COMMAND
    if body in ["menu", "0", "restart", "accueil"]:
        session.step = "menu"
        db.session.commit()
        return send_reply(get_main_menu())

    # =====================================================
    # STEP 1: MENU
    # =====================================================

    if session.step == "menu":
        mapping = {"1": "incident", "2": "aide", "3": "conseil"}

        if body in mapping:
            session.service = mapping[body]
            session.step = "zone"
            db.session.commit()
            return send_reply(get_zone_menu())

        return send_reply("Option invalide.\n\n" + get_main_menu())

    # =====================================================
    # STEP 2: ZONE
    # =====================================================

    if session.step == "zone":

        if body not in PROFESSIONNELS:
            return send_reply("Zone invalide.\n\n" + get_zone_menu())

        zone = PROFESSIONNELS[body]
        pro = zone.get(session.service)

        session.step = "menu"
        db.session.commit()

        return send_reply(
            f"DOSSIER ENREGISTRÉ\n\n"
            f"Zone : {zone['label']}\n"
            f"Médiateur : {pro['nom']}\n"
            f"Contact : {pro['tel']}"
        )

    # fallback
    return send_reply(get_main_menu())

# =========================================================
# MAIN (RENDER SAFE)
# =========================================================

if __name__ == "__main__":
    app.run()
