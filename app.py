import os
import logging
import json
from flask import Flask, render_template, request, jsonify, session
from anthropic import Anthropic

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize Anthropic API with key from environment
anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not anthropic_api_key:
    logger.warning("Anthropic API key not found in environment variables!")

# Initialize Anthropic client
client = Anthropic(api_key=anthropic_api_key)

@app.route('/')
def index():
    """Render the main chat interface"""
    # Initialize session message history if it doesn't exist
    if 'messages' not in session:
        session['messages'] = []
    return render_template('index.html', messages=session['messages'], ai_provider="Claude")

@app.route('/send_message', methods=['POST'])
def send_message():
    """Process user message and get response from Claude API"""
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
        
        # Format messages for Anthropic
        messages = []
        # Add system message if it's the first message
        if len(session['messages']) <= 1:
            messages.append({
                "role": "system", 
                "content": "You are a helpful assistant. Provide concise, accurate, and friendly responses."
            })
            
        # Add conversation history
        for msg in session['messages']:
            messages.append(msg)
        
        # Call Anthropic API
        logger.debug(f"Sending request to Anthropic with messages: {messages}")
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",  # the newest Anthropic model is "claude-3-5-sonnet-20241022" which was released October 22, 2024
            max_tokens=1000,
            temperature=0.7,
            messages=messages
        )
        
        # Extract response content
        assistant_message = response.content[0].text
        
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
