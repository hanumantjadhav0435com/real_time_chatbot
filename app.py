import os
import logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from google import genai   # ✅ Correct new import
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import re

# -------------------------------------------------------------
# Logging Configuration
# -------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# Flask App Configuration
# -------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

# -------------------------------------------------------------
# Gemini API Configuration
# -------------------------------------------------------------
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("❌ GEMINI_API_KEY environment variable is not set.")

client = genai.Client(api_key=gemini_api_key)  # ✅ Use the new Client class

# -------------------------------------------------------------
# Database Setup
# -------------------------------------------------------------
DB_PATH = 'users.db'

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

# -------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------
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

# -------------------------------------------------------------
# Routes
# -------------------------------------------------------------
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

# -------------------------------------------------------------
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

# -------------------------------------------------------------
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    session.pop('messages', None)
    return jsonify({'success': True})

# -------------------------------------------------------------
@app.route('/')
def home():
    if 'user' in session:
        return redirect(url_for('chat'))
    return render_template('home.html')

# -------------------------------------------------------------
@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect(url_for('login'))
    if 'messages' not in session:
        session['messages'] = []
    return render_template('index.html', messages=session['messages'], ai_provider="Hanumant Jadhav Bot")

# -------------------------------------------------------------
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

        # Add user message
        session['messages'].append({'role': 'user', 'content': user_message})

        # Convert to Gemini format
        gemini_messages = []
        for msg in session['messages']:
            role = msg['role']
            content = msg['content']
            gemini_messages.append({
                "role": "user" if role == "user" else "model",
                "parts": [{"text": content}]
            })

        logger.debug(f"Sending messages to Gemini API: {gemini_messages}")

        # ✅ Using the free Gemini 1.5 Flash model
        response = client.models.generate_content(
            model="models/gemini-1.5-flash",
            contents=gemini_messages,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 1000,
            },
        )

        assistant_message = response.candidates[0].content.parts[0].text

        # Save assistant message
        session['messages'].append({'role': 'assistant', 'content': assistant_message})
        session.modified = True

        return jsonify({'message': assistant_message})

    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return jsonify({'error': f"An error occurred: {str(e)}"}), 500

# -------------------------------------------------------------
@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    """Clear chat history"""
    session['messages'] = []
    session.modified = True
    return jsonify({'status': 'success'})

# -------------------------------------------------------------
# Flask app runs from your deployment environment (Render, etc.)
# -------------------------------------------------------------
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000)
