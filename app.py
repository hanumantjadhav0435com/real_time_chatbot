import os
import logging
import json
from flask import Flask, render_template, request, jsonify, session
import openai

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize OpenAI API with key from environment
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    logger.warning("OpenAI API key not found in environment variables!")

client = openai.OpenAI(api_key=openai_api_key)

@app.route('/')
def index():
    """Render the main chat interface"""
    # Initialize session message history if it doesn't exist
    if 'messages' not in session:
        session['messages'] = []
    return render_template('index.html', messages=session['messages'])

@app.route('/send_message', methods=['POST'])
def send_message():
    """Process user message and get response from ChatGPT API"""
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
        
        # Create messages array for API call, including conversation history
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Provide concise, accurate, and friendly responses."}
        ]
        messages.extend(session['messages'])
        
        # Call OpenAI API
        logger.debug(f"Sending request to OpenAI with messages: {messages}")
        
        response = client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            messages=messages
        )
        
        # Extract response content
        assistant_message = response.choices[0].message.content
        
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
    
    except openai.APIError as e:
        logger.error(f"OpenAI API Error: {str(e)}")
        return jsonify({'error': f"OpenAI API Error: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    """Clear the chat history"""
    session['messages'] = []
    session.modified = True
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
