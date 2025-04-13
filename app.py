import os
import logging
import json
from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize Gemini API with key from environment
gemini_api_key = os.environ.get("GOOGLE_API_KEY")
if not gemini_api_key:
    logger.warning("Google API key not found in environment variables!")
else:
    # Initialize Gemini client
    genai.configure(api_key=gemini_api_key)

@app.route('/')
def index():
    """Render the main chat interface"""
    # Initialize session message history if it doesn't exist
    if 'messages' not in session:
        session['messages'] = []
    return render_template('index.html', messages=session['messages'], ai_provider="Hanumant Jadhav Bot")

@app.route('/send_message', methods=['POST'])
def send_message():
    """Process user message and get response from Gemini API"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400
        
        # Initialize message history if it doesn't exist
        if 'messages' not in session:
            session['messages'] = []
        
        # Add user message to history
        session['messages'].append({
            'role': 'user',
            'content': user_message
        })
        
        # Format messages for Gemini
        gemini_messages = []
        system_message = "You are a helpful assistant. Provide concise, accurate, and friendly responses."
        
        # Convert session messages to Gemini format
        for msg in session['messages']:
            role = msg['role']
            content = msg['content']
            
            if role == 'user':
                gemini_messages.append({"role": "user", "parts": [{"text": content}]})
            elif role == 'assistant':
                gemini_messages.append({"role": "model", "parts": [{"text": content}]})
        
        # Call Gemini API
        logger.debug(f"Sending request to Gemini API with messages: {gemini_messages}")
        
        # Create a Gemini chat instance
        model = genai.GenerativeModel('gemini-1.5-pro')
        chat = model.start_chat(history=gemini_messages[:-1])  # Exclude the latest user message
        
        # Generate a response with the latest user message
        response = chat.send_message(
            user_message,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 1000,
            }
        )
        
        # Extract response content
        assistant_message = response.text
        
        # Add assistant response to history
        session['messages'].append({
            'role': 'assistant',
            'content': assistant_message
        })
        
        # Save session
        session.modified = True
        
        return jsonify({
            'message': assistant_message
        })
    
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return jsonify({'error': f"An error occurred: {str(e)}"}), 500

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    """Clear the chat history"""
    session['messages'] = []
    session.modified = True
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
