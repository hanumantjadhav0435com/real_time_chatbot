import os
import logging
from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
app.secret_key = "dev-secret-key"  # Replace with a secure key in production

# Set your Gemini API key
gemini_api_key = "AIzaSyBQmYo4RnWabu-x7XAz6e-fgJTIqRFpEo8"
genai.configure(api_key=gemini_api_key)

@app.route('/')
def index():
    """Render the main chat interface"""
    if 'messages' not in session:
        session['messages'] = []
    return render_template('index.html', messages=session['messages'], ai_provider="Hanumant Jadhav Bot")

@app.route('/send_message', methods=['POST'])
def send_message():
    """Process user message and get response from Gemini 1.5 Flash"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'error': 'Empty message'}), 400

        # Initialize message history if not present
        if 'messages' not in session:
            session['messages'] = []

        # Add user message to session
        session['messages'].append({
            'role': 'user',
            'content': user_message
        })

        # Convert session messages to Gemini-compatible format
        gemini_messages = []
        for msg in session['messages']:
            role = msg['role']
            content = msg['content']
            if role == 'user':
                gemini_messages.append({"role": "user", "parts": [{"text": content}]})
            elif role == 'assistant':
                gemini_messages.append({"role": "model", "parts": [{"text": content}]})

        logger.debug(f"Sending messages to Gemini API: {gemini_messages}")

        # ✅ Use the FREE Gemini 1.5 Flash model
        model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")

        # Start a new chat with prior history (excluding the latest message)
        chat = model.start_chat(history=gemini_messages[:-1])

        # Send the current user message
        response = chat.send_message(
            user_message,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 1000,
            }
        )

        assistant_message = response.text

        # Save assistant response in session
        session['messages'].append({
            'role': 'assistant',
            'content': assistant_message
        })
        session.modified = True

        return jsonify({'message': assistant_message})

    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return jsonify({'error': f"An error occurred: {str(e)}"}), 500

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    """Clear chat history"""
    session['messages'] = []
    session.modified = True
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
