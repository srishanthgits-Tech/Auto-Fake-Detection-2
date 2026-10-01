import random
import smtplib
import qrcode
import os
import re

from base64 import b64encode

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    session,
    flash,
    send_file
)

from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_session import Session
from flask_migrate import Migrate

import wikipedia

from keras.models import load_model
from PIL import Image, ImageChops, ImageEnhance
import numpy as np


# ============================================================
# APPLICATION SETUP
# ============================================================

app = Flask(__name__)

app.config['SECRET_KEY'] = 'your_secret_key'

# ============================================================
# EMAIL CONFIGURATION
# ============================================================
# IMPORTANT:
# Do NOT put your real Gmail password directly in this file.
#
# Windows Anaconda Prompt:
#
# set MAIL_USERNAME=your_email@gmail.com
# set MAIL_PASSWORD=your_app_password
#
# Then run:
# python app.py
# ============================================================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True

app.config['MAIL_USERNAME'] = os.environ.get(
    'MAIL_USERNAME',
    'your_email@gmail.com'
)

app.config['MAIL_PASSWORD'] = os.environ.get(
    'MAIL_PASSWORD',
    ''
)

app.config['MAIL_DEFAULT_SENDER'] = os.environ.get(
    'MAIL_DEFAULT_SENDER',
    app.config['MAIL_USERNAME']
)


# ============================================================
# DATABASE
# ============================================================

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///user.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# ============================================================
# FLASK SESSION
# ============================================================

app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# ============================================================
# INITIALIZE EXTENSIONS
# ============================================================

mail = Mail(app)
bcrypt = Bcrypt(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)


# ============================================================
# LOAD IMAGE DETECTION MODEL
# ============================================================

try:
    fake_model = load_model('model.h5')
    print("✅ Image detection model loaded successfully.")
except Exception as e:
    fake_model = None
    print("⚠️ Could not load model.h5:", e)


# ============================================================
# UPLOAD FOLDER
# ============================================================

UPLOAD_FOLDER = "static/uploads/"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# USER MODEL
# ============================================================

class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    phone = db.Column(
        db.String(20),
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    city = db.Column(
        db.String(100),
        nullable=False
    )

    district = db.Column(
        db.String(100),
        nullable=False
    )

    is_admin = db.Column(
        db.Boolean,
        default=False
    )

    def __repr__(self):
        return f"<User {self.name}>"


# ============================================================
# OTP FUNCTIONS
# ============================================================

def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(recipient_email, otp):

    subject = "Your OTP Code"

    body = f"""
Hello,

Your OTP verification code is:

{otp}

Please use this code to complete your registration.

Regards,
Truth AI
"""

    msg = MIMEMultipart()

    msg['From'] = app.config['MAIL_USERNAME']
    msg['To'] = recipient_email
    msg['Subject'] = subject

    msg.attach(
        MIMEText(body, 'plain')
    )

    try:

        if not app.config['MAIL_PASSWORD']:
            print("⚠️ MAIL_PASSWORD is not configured.")
            print("⚠️ OTP for testing:", otp)
            return False

        server = smtplib.SMTP(
            app.config['MAIL_SERVER'],
            app.config['MAIL_PORT']
        )

        server.starttls()

        server.login(
            app.config['MAIL_USERNAME'],
            app.config['MAIL_PASSWORD']
        )

        server.sendmail(
            app.config['MAIL_USERNAME'],
            recipient_email,
            msg.as_string()
        )

        server.quit()

        print("✅ OTP sent successfully.")

        return True

    except Exception as e:

        print(
            f"❌ Error sending email: {e}"
        )

        return False


# ============================================================
# INDEX
# ============================================================

@app.route('/', methods=['GET', 'POST'])
def index():

    return render_template(
        'index.html'
    )


# ============================================================
# REGISTER
# ============================================================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name']

        email = request.form['email']

        phone = request.form['phone']

        password = bcrypt.generate_password_hash(
            request.form['password']
        ).decode('utf-8')

        city = request.form['city']

        district = request.form['district']


        session['user_details'] = {

            'name': name,

            'email': email,

            'phone': phone,

            'password': password,

            'city': city,

            'district': district
        }


        otp = generate_otp()

        session['otp'] = otp


        if send_otp_email(email, otp):

            return redirect(
                url_for('verify_otp')
            )

        else:

            flash(
                'Failed to send OTP. Check email configuration.',
                'danger'
            )

    return render_template(
        'register.html'
    )


# ============================================================
# OTP VERIFICATION
# ============================================================

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():

    if request.method == 'POST':

        user_otp = request.form['otp']


        if (
            'otp' in session
            and
            session['otp'] == user_otp
        ):

            user_details = session.pop(
                'user_details',
                None
            )


            if user_details:

                existing_user = User.query.filter_by(
                    email=user_details['email']
                ).first()


                if existing_user:

                    flash(
                        'User already registered. Please login.',
                        'warning'
                    )

                    return redirect(
                        url_for('login')
                    )


                new_user = User(

                    name=user_details['name'],

                    email=user_details['email'],

                    phone=user_details['phone'],

                    password=user_details['password'],

                    city=user_details['city'],

                    district=user_details['district']
                )


                db.session.add(new_user)

                db.session.commit()


                print(
                    f"✅ User saved: {new_user.email}"
                )


                flash(
                    'Registration successful! Please login.',
                    'success'
                )


                return redirect(
                    url_for('login')
                )

        else:

            flash(
                'Invalid OTP. Please try again.',
                'danger'
            )


    return render_template(
        'verify_otp.html'
    )


# ============================================================
# LOGIN
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']

        password = request.form['password']


        user = User.query.filter_by(
            email=email
        ).first()


        if (
            user
            and
            bcrypt.check_password_hash(
                user.password,
                password
            )
        ):

            session['user_id'] = user.id

            session['user_name'] = user.name


            print(
                f"✅ User logged in: {user.email}"
            )


            flash(
                'Login successful!',
                'success'
            )


            return redirect(
                url_for('home')
            )


        else:

            flash(
                'Invalid credentials',
                'danger'
            )


    return render_template(
        'login.html'
    )


# ============================================================
# HOME
# ============================================================

@app.route('/home', methods=['GET', 'POST'])
def home():

    return render_template(
        'home.html'
    )


# ============================================================
# NEWS ANALYSIS ENGINE
# ============================================================

def analyze_news(news_text):

    """
    Analyze submitted news text.

    IMPORTANT:
    This is a transparent heuristic/source-based analyzer.
    It is NOT a trained fact-checking ML model.

    Returns:
        verdict
        reason
        confidence
        evidence
    """


    text = news_text.strip()

    lower_text = text.lower()


    # --------------------------------------------------------
    # Empty input
    # --------------------------------------------------------

    if not text:

        return {

            "verdict": "UNCERTAIN",

            "reason": "No news content was provided for analysis.",

            "confidence": 0,

            "evidence": "Please enter a complete news claim."
        }


    # --------------------------------------------------------
    # Suspicious claim patterns
    # --------------------------------------------------------

    suspicious_patterns = [

        (
            r'\b(secret|hidden|hiding|suppressed)\b',
            "The claim uses secrecy or suppression language without providing supporting evidence."
        ),

        (
            r'\b(cure[s]?|cured|completely cure)\b',
            "The claim makes a strong medical cure statement that requires credible scientific evidence."
        ),

        (
            r'\b(within\s+\d+\s*(hours?|days?))\b',
            "The claim gives an unusually rapid medical or scientific result without evidence."
        ),

        (
            r'\b(150\s*years?|200\s*years?)\b',
            "The claim makes an extraordinary lifespan statement without supporting evidence."
        ),

        (
            r'\b(government[s]?|hospital[s]?|scientist[s]?)\b.*\b(hiding|hide|covering)\b',
            "The claim alleges a coordinated cover-up without providing verifiable evidence."
        ),

        (
            r'\b(miracle|miraculous)\b',
            "The wording uses an extraordinary claim that requires strong supporting evidence."
        ),

        (
            r'\b(cancer|diabetes|heart disease)\b.*\b(cure|cures|cured)\b',
            "The claim suggests a single treatment can cure multiple serious diseases."
        ),

        (
            r'\b(lifespan|live)\b.*\b(150|200)\b',
            "The claim makes an extraordinary human lifespan claim."
        )
    ]


    matched_reasons = []


    for pattern, reason in suspicious_patterns:

        try:

            if re.search(
                pattern,
                lower_text,
                re.IGNORECASE
            ):

                matched_reasons.append(
                    reason
                )

        except re.error:

            pass


    # --------------------------------------------------------
    # Strong suspicious language
    # --------------------------------------------------------

    strong_words = [

        "secret fruit",

        "secret cure",

        "hidden cure",

        "government hiding",

        "governments hiding",

        "pharmaceutical industry",

        "miracle cure",

        "instant cure",

        "100% cure",

        "guaranteed cure",

        "cure all diseases"
    ]


    matched_words = []


    for word in strong_words:

        if word in lower_text:

            matched_words.append(
                word
            )


    # --------------------------------------------------------
    # Check Wikipedia for a possible related topic
    # --------------------------------------------------------

    wiki_evidence = ""

    wiki_titles = []


    try:

        # Search only the first reasonable portion.
        # This prevents the old 300-character Wikipedia
        # request problem.

        search_text = re.sub(
            r'[^a-zA-Z0-9\s]',
            ' ',
            text
        )

        search_words = search_text.split()


        # Remove generic news words.

        ignored_words = {

            "breaking",

            "news",

            "scientists",

            "have",

            "has",

            "been",

            "the",

            "this",

            "that",

            "with",

            "from",

            "they",

            "their",

            "experts",

            "claim",

            "claims",

            "said"
        }


        useful_words = [

            word
            for word in search_words
            if (
                len(word) > 3
                and
                word.lower() not in ignored_words
            )
        ]


        search_query = " ".join(
            useful_words[:8]
        )


        if search_query:

            wiki_results = wikipedia.search(
                search_query,
                results=5
            )


            if wiki_results:

                wiki_titles = wiki_results[:5]


    except Exception as e:

        wiki_evidence = (
            f"Wikipedia source lookup was unavailable: {str(e)}"
        )


    # --------------------------------------------------------
    # Verdict calculation
    # --------------------------------------------------------

    suspicious_score = 0


    suspicious_score += (
        len(matched_reasons) * 2
    )


    suspicious_score += (
        len(matched_words) * 3
    )


    # --------------------------------------------------------
    # FALSE
    # --------------------------------------------------------

    if suspicious_score >= 5:

        verdict = "FALSE"

        confidence = min(
            95,
            70 + suspicious_score * 3
        )


        reason_parts = []


        reason_parts.extend(
            matched_reasons
        )


        if matched_words:

            reason_parts.append(
                "Suspicious phrases detected: "
                +
                ", ".join(matched_words)
                +
                "."
            )


        reason = " ".join(
            reason_parts
        )


        evidence = (
            "The submitted claim contains multiple "
            "extraordinary or unsupported statements. "
            "The system could not establish reliable "
            "evidence supporting those statements."
        )


        return {

            "verdict": verdict,

            "reason": reason,

            "confidence": confidence,

            "evidence": evidence,

            "wiki_titles": wiki_titles
        }


    # --------------------------------------------------------
    # POSSIBLY TRUE / SOURCE SUPPORTED
    # --------------------------------------------------------

    if len(wiki_titles) > 0 and suspicious_score == 0:

        verdict = "TRUE"

        confidence = 55


        reason = (
            "No major suspicious claim patterns were "
            "detected, and related information was found "
            "through the available Wikipedia search."
        )


        evidence = (
            "Related Wikipedia topics were found: "
            +
            ", ".join(wiki_titles[:5])
            +
            "."
        )


        return {

            "verdict": verdict,

            "reason": reason,

            "confidence": confidence,

            "evidence": evidence,

            "wiki_titles": wiki_titles
        }


    # --------------------------------------------------------
    # UNCERTAIN
    # --------------------------------------------------------

    verdict = "UNCERTAIN"

    confidence = 35


    reason = (
        "The system could not find enough reliable "
        "evidence to classify this claim confidently."
    )


    evidence = (
        "The claim does not contain enough information "
        "for a reliable source-based verification."
    )


    if wiki_titles:

        evidence += (
            " Related Wikipedia topics found: "
            +
            ", ".join(wiki_titles[:5])
            +
            "."
        )


    return {

        "verdict": verdict,

        "reason": reason,

        "confidence": confidence,

        "evidence": evidence,

        "wiki_titles": wiki_titles
    }


# ============================================================
# NEWS DASHBOARD
# ============================================================

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )


    # Default values

    topic = None

    content = None

    verdict = None

    reason = None

    confidence = None

    evidence = None

    wiki_titles = []


    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    if request.method == 'POST':

        topic = request.form.get(
            'topic',
            ''
        ).strip()


        # ----------------------------------------------------
        # Empty topic
        # ----------------------------------------------------

        if not topic:

            flash(
                'Please enter a news statement.',
                'warning'
            )

            return render_template(

                'dashboard.html',

                topic=None,

                content=None,

                verdict=None,

                reason=None,

                confidence=None,

                evidence=None,

                wiki_titles=[]
            )


        # ----------------------------------------------------
        # Maximum length
        # ----------------------------------------------------

        if len(topic) > 3000:

            verdict = "UNCERTAIN"

            reason = (
                "The submitted news statement is too long. "
                "Please enter the main claim or headline."
            )

            confidence = 0

            evidence = (
                "Maximum supported input is 3000 characters."
            )


            return render_template(

                'dashboard.html',

                topic=topic,

                content=None,

                verdict=verdict,

                reason=reason,

                confidence=confidence,

                evidence=evidence,

                wiki_titles=[]
            )


        # ----------------------------------------------------
        # Run News Analysis
        # ----------------------------------------------------

        try:

            analysis = analyze_news(
                topic
            )


            verdict = analysis.get(
                "verdict"
            )

            reason = analysis.get(
                "reason"
            )

            confidence = analysis.get(
                "confidence"
            )

            evidence = analysis.get(
                "evidence"
            )

            wiki_titles = analysis.get(
                "wiki_titles",
                []
            )


            # Content shown as supporting information,
            # NOT the full Wikipedia article.

            content = evidence


        except Exception as e:

            verdict = "UNCERTAIN"

            reason = (
                "The verification engine encountered "
                "an unexpected error."
            )

            confidence = 0

            evidence = str(e)

            content = evidence


    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    return render_template(

        'dashboard.html',

        topic=topic,

        content=content,

        verdict=verdict,

        reason=reason,

        confidence=confidence,

        evidence=evidence,

        wiki_titles=wiki_titles
    )


# ============================================================
# OLD COMPATIBILITY FUNCTION
# ============================================================

def check_fake_content(content):

    """
    Kept for compatibility with the existing summary page.
    """

    if not content:

        return "Unknown"


    result = analyze_news(
        content
    )


    verdict = result.get(
        "verdict"
    )


    if verdict == "FALSE":

        return "False"

    elif verdict == "TRUE":

        return "True"

    else:

        return "Unknown"


# ============================================================
# SUMMARY
# ============================================================

@app.route('/summarize', methods=['POST'])
def summarize():

    topic = request.form.get(
        'topic',
        ''
    ).strip()


    if not topic:

        return render_template(

            'summary.html',

            topic='',

            summary='No topic was provided.',

            status='Unknown'
        )


    try:

        summary = wikipedia.summary(
            topic,
            sentences=5
        )


        status = check_fake_content(
            summary
        )


    except wikipedia.exceptions.DisambiguationError as e:

        summary = (
            "Multiple results found: "
            +
            str(e.options[:5])
        )

        status = "Unknown"


    except wikipedia.exceptions.PageError:

        summary = (
            "Topic not found. Please try another one."
        )

        status = "Unknown"


    except Exception as e:

        summary = (
            f"An error occurred: {e}"
        )

        status = "Unknown"


    return render_template(

        'summary.html',

        topic=topic,

        summary=summary,

        status=status
    )


# ============================================================
# DOWNLOAD ARTICLE
# ============================================================

@app.route('/download/<path:topic>')
def download_article(topic):

    try:

        content = wikipedia.page(
            topic
        ).content


        safe_filename = re.sub(
            r'[\\/:*?"<>|]',
            '_',
            topic
        )


        file_path = (
            f"{safe_filename}.txt"
        )


        with open(
            file_path,
            'w',
            encoding='utf-8'
        ) as file:

            file.write(
                content
            )


        return send_file(
            file_path,
            as_attachment=True
        )


    except Exception as e:

        return (
            f"An error occurred: {e}"
        )


# ============================================================
# SHARE ARTICLE
# ============================================================

@app.route('/share/<path:topic>')
def share_article(topic):

    share_link = (
        request.url_root
        +
        f"download/{topic}"
    )


    return render_template(

        'share.html',

        topic=topic,

        share_link=share_link
    )


# ============================================================
# IMAGE ERROR LEVEL ANALYSIS
# ============================================================

def convert_to_ela_image(
    path,
    quality=90
):

    resaved_filename = (
        'static/tempresaved.jpg'
    )


    im = Image.open(
        path
    ).convert('RGB')


    im.save(
        resaved_filename,
        'JPEG',
        quality=quality
    )


    resaved_im = Image.open(
        resaved_filename
    )


    ela_im = ImageChops.difference(
        im,
        resaved_im
    )


    extrema = ela_im.getextrema()


    max_diff = max(
        [
            ex[1]
            for ex in extrema
        ]
    )


    if max_diff == 0:

        max_diff = 1


    scale = 255.0 / max_diff


    ela_im = ImageEnhance.Brightness(
        ela_im
    ).enhance(
        scale
    )


    return ela_im


# ============================================================
# IMAGE PREDICTION
# ============================================================

def predict_fake_image(
    file_path
):

    if fake_model is None:

        return (
            "Model unavailable ❌"
        )


    X = []


    ela_img = convert_to_ela_image(
        file_path,
        90
    ).resize(
        (128, 128)
    )


    X.append(
        np.array(
            ela_img
        ).flatten()
        /
        255.0
    )


    X = np.array(
        X
    )


    X = X.reshape(
        -1,
        128,
        128,
        3
    )


    pred = fake_model.predict(
        X,
        verbose=0
    )


    pred = np.argmax(
        pred,
        axis=1
    )[0]


    if pred == 0:

        return (
            "Real Image ✅"
        )

    else:

        return (
            "Fake Image ⚠️"
        )


# ============================================================
# FAKE IMAGE ROUTE
# ============================================================

@app.route(
    "/fake_image",
    methods=["GET", "POST"]
)
def fake_image():

    if request.method == "POST":

        file = request.files.get(
            "image"
        )


        if not file:

            return render_template(

                "fake_image.html",

                result="No image selected ❌"
            )


        if file.filename == "":

            return render_template(

                "fake_image.html",

                result="No file selected ❌"
            )


        try:

            filepath = os.path.join(
                UPLOAD_FOLDER,
                file.filename
            )


            file.save(
                filepath
            )


            result = predict_fake_image(
                filepath
            )


            return render_template(

                "fake_image.html",

                result=result,

                image=filepath
            )


        except Exception as e:

            return render_template(

                "fake_image.html",

                result=(
                    f"Image analysis error: {e}"
                )
            )


    return render_template(
        "fake_image.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route('/logout')
def logout():

    session.clear()


    flash(
        'You have been logged out.',
        'info'
    )


    return redirect(
        url_for('login')
    )


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    with app.app_context():

        db.create_all()


    print("")
    print("======================================")
    print("        TRUTH AI VERIFICATION")
    print("======================================")
    print("🚀 Flask server starting...")
    print("🌐 Open: http://127.0.0.1:5000")
    print("📰 News Scanner: /dashboard")
    print("🖼️ Image Scanner: /fake_image")
    print("======================================")
    print("")


    app.run(
        debug=True
    )