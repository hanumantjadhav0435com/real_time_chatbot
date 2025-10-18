import os
import logging
import sqlite3
import re
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai

# -------------------------------------
# Configuration
# -------------------------------------
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

# ✅ Gemini API setup
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("❌ GEMINI_API_KEY is not set in environment variables.")

client = genai.Client(api_key=gemini_api_key)

DB_PATH = 'users.db'


# -------------------------------------
# Database setup
# -------------------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('DROP TABLE IF EXISTS users')
        c.execute('''CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
        )''')
        conn.commit()


init_db()


def get_user(username):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, password_hash, full_name, email FROM users WHERE username = ?', (username,))
        return c.fetchone()


def create_user(username, password, full_name, email):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('INSERT INTO users (username, password_hash, full_name, email) VALUES (?, ?, ?, ?)',
                      (username, generate_password_hash(password), full_name, email))
            conn.commit()
            return True, None
    except sqlite3.IntegrityError as e:
        if 'username' in str(e):
            return False, 'Username already exists.'
        if 'email' in str(e):
            return False, 'Email already exists.'
        return False, 'Database error.'


def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


# -------------------------------------
# Routes
# -------------------------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')

    data = request.get_json() or request.form
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    confirm_password = data.get('confirm_password', '').strip()

    if not all([full_name, email, username, password, confirm_password]):
        return jsonify({'success': False, 'error': 'All fields are required.'}), 400
    if not is_valid_email(email):
        return jsonify({'success': False, 'error': 'Invalid email address.'}), 400
    if password != confirm_password:
        return jsonify({'success': False, 'error': 'Passwords do not match.'}), 400

    success, error = create_user(username, password, full_name, email)
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': error}), 400


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    data = request.get_json() or request.form
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    user = get_user(username)

    if user and check_password_hash(user[2], password):
        session['user'] = username
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    session.pop('messages', None)
    return jsonify({'success': True})


@app.route('/')
def home():
    if 'user' in session:
        return redirect(url_for('chat'))
    return render_template('home.html')


@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect(url_for('login'))
    if 'messages' not in session:
        session['messages'] = []
    return render_template('index.html', messages=session['messages'], ai_provider="Hanumant Jadhav Bot")


# -------------------------------------
# Chat route with Gemini 1.5 Flash
# -------------------------------------
@app.route('/send_message', methods=['POST'])
def send_message():
    """Process user message and get response from Gemini 1.5 Flash"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'error': 'Empty message'}), 400

        if 'messages' not in session:
            session['messages'] = []

        session['messages'].append({'role': 'user', 'content': user_message})

        # Convert chat history to Gemini format
        gemini_messages = []
        for msg in session['messages']:
            gemini_messages.append({
                "role": "user" if msg['role'] == "user" else "model",
                "parts": [{"text": msg['content']}]
            })

        logger.debug(f"Sending messages to Gemini API: {gemini_messages}")

        # ✅ Correct generate_content usage for latest SDK
        response = client.models.generate_content(
            model="models/gemini-1.5-flash",
            contents=gemini_messages,
            temperature=0.7,
            max_output_tokens=1000,
        )

        # Extract text safely
        assistant_message = response.candidates[0].content.parts[0].text

        session['messages'].append({'role': 'assistant', 'content': assistant_message})
        session.modified = True

        return jsonify({'message': assistant_message})

    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return jsonify({'error': f"An error occurred: {str(e)}"}), 500


@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    session['messages'] = []
    session.modified = True
    return jsonify({'status': 'success'})


# -------------------------------------
# Run the Flask app
# -------------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
