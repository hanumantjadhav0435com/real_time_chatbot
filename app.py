import os
import logging
import sqlite3
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# Flask config
# ---------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.environ.get("SECRET_KEY", "dev-secret-key"))

# ---------------------------
# Gemini API config
# ---------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set. Add it on Render or locally.")

client = genai.Client(api_key=GEMINI_API_KEY)

# ---------------------------
# Database config
# ---------------------------
DB_PATH = os.environ.get("DB_PATH", "app_data.db")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Messages table to persist chat history per user
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------------------
# Helpers
# ---------------------------
EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")

def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))

def create_user(username, password, full_name, email):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password_hash, full_name, email) VALUES (?, ?, ?, ?)",
                  (username, generate_password_hash(password), full_name, email))
        conn.commit()
        conn.close()
        return True, None
    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if 'username' in msg:
            return False, "Username already exists."
        if 'email' in msg:
            return False, "Email already exists."
        return False, "Database error."

def get_user(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, password_hash, full_name, email FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row

def save_message(username, role, content):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO messages (username, role, content, created_at) VALUES (?, ?, ?, ?)",
              (username, role, content, datetime.utcnow()))
    conn.commit()
    conn.close()

def get_messages_for_user(username, limit=40):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT role, content, created_at FROM messages WHERE username = ? ORDER BY id ASC LIMIT ?",
              (username, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ---------------------------
# Robust generate wrapper
# ---------------------------
def _extract_text_from_response(resp):
    # Try several common response shapes
    try:
        # newer shape: response.candidates[0].content.parts[0].text
        return resp.candidates[0].content.parts[0].text
    except Exception:
        pass
    try:
        # older shape: resp.text
        return resp.text
    except Exception:
        pass
    try:
        # fallback: resp.candidates[0].text
        return resp.candidates[0].text
    except Exception:
        pass
    # Last fallback: stringify
    return str(resp)

def generate_content_with_fallback(model, contents, **gen_kwargs):
    """
    Try a few calling conventions for client.models.generate_content to handle SDK variations.
    - Try config=...
    - Then try flat kwargs
    - Then try generation_config=...
    - If all fail, raise the last exception
    """
    last_exc = None

    # Attempt 1: config param (recent SDK)
    try:
        return client.models.generate_content(model=model, contents=contents, config=gen_kwargs)
    except TypeError as ex:
        last_exc = ex
    except Exception as ex:
        # other runtime issues - rethrow
        raise

    # Attempt 2: flat kwargs (older SDKs)
    try:
        return client.models.generate_content(model=model, contents=contents, **gen_kwargs)
    except TypeError as ex:
        last_exc = ex
    except Exception as ex:
        raise

    # Attempt 3: generation_config param (older name)
    try:
        return client.models.generate_content(model=model, contents=contents, generation_config=gen_kwargs)
    except Exception as ex:
        last_exc = ex

    # All attempts failed
    raise last_exc

# ---------------------------
# Routes
# ---------------------------
@app.route('/')
def home():
    if 'user' in session:
        return redirect(url_for('chat'))
    return render_template('home.html')

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
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required.'}), 400
    user = get_user(username)
    if user and check_password_hash(user['password_hash'], password):
        session['user'] = username
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'success': True})

@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect(url_for('login'))
    messages = get_messages_for_user(session['user'], limit=200)
    return render_template('index.html', messages=messages, ai_provider="Hanumant Jadhav Bot")

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json() or request.form
    user_message = (data.get('message') or '').strip()
    if not user_message:
        return jsonify({'error': 'Empty message'}), 400

    username = session['user']
    # Save user message to DB
    save_message(username, 'user', user_message)

    # Build message history for the model (convert to Gemini message format)
    history = get_messages_for_user(username, limit=60)
    gemini_messages = []
    for m in history:
        # roles: 'user' -> user, 'assistant' -> model
        role = "user" if m['role'] == 'user' else "model"
        gemini_messages.append({"role": role, "parts": [{"text": m['content']}]})

    logger.info("Sending to Gemini; messages length=%d", len(gemini_messages))

    try:
        # Try the free Gemini 1.5 Flash model.
        model_name = "models/gemini-1.5-flash"

        # generation parameters
        gen_opts = {
            "temperature": 0.7,
            "max_output_tokens": 800,
        }

        resp = generate_content_with_fallback(model=model_name, contents=gemini_messages, **gen_opts)
        assistant_text = _extract_text_from_response(resp)

        # Save assistant message
        save_message(username, 'assistant', assistant_text)

        return jsonify({'message': assistant_text})
    except Exception as e:
        logger.exception("Error from Gemini API")
        # helpful error for logs, but short message to client
        return jsonify({'error': 'AI API error: ' + str(e)}), 500

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    username = session['user']
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# ---------------------------
# Run
# ---------------------------
if __name__ == '__main__':
    # Bind to PORT if provided by Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
