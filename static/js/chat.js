document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const messageForm = document.getElementById('messageForm');
    const userInput = document.getElementById('userInput');
    const chatHistory = document.getElementById('chatHistory');
    const typingIndicator = document.getElementById('typingIndicator');
    const clearChatBtn = document.getElementById('clearChat');

    // Scroll to the bottom of chat history
    function scrollToBottom() {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
    
    // Scroll to bottom on page load
    scrollToBottom();

    // Auto-resize the textarea
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        // Reset if empty
        if (this.value === '') {
            this.style.height = 'auto';
        }
    });

    // Submit form on Shift+Enter
    userInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            messageForm.dispatchEvent(new Event('submit'));
        }
    });

    // Handle message submission
    messageForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const message = userInput.value.trim();
        if (!message) return;
        
        // Clear input and reset height
        userInput.value = '';
        userInput.style.height = 'auto';
        
        // Add user message to chat
        addMessageToChat('user', message);
        
        // Show typing indicator
        typingIndicator.classList.remove('d-none');
        scrollToBottom();
        
        try {
            // Send message to server
            const response = await fetch('/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message }),
            });
            
            const data = await response.json();
            
            // Hide typing indicator
            typingIndicator.classList.add('d-none');
            
            if (response.ok) {
                // Add assistant response to chat
                addMessageToChat('assistant', data.message);
            } else {
                // Handle error
                const errorMessage = data.error || 'An error occurred. Please try again.';
                addErrorMessage(errorMessage);
            }
        } catch (error) {
            console.error('Error:', error);
            typingIndicator.classList.add('d-none');
            addErrorMessage('Network error. Please check your connection and try again.');
        }
        
        scrollToBottom();
    });

    // Add message to chat history
    function addMessageToChat(role, content) {
        // Remove welcome message if it exists
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
        
        const messageContainer = document.createElement('div');
        messageContainer.className = `message-container ${role}-message`;
        
        // Format the message content
        const formattedContent = formatMessageContent(content);
        
        messageContainer.innerHTML = `
            <div class="message-bubble">
                <div class="message-header">
                    <strong>${role === 'user' ? 'You' : 'ChatGPT'}</strong>
                </div>
                <div class="message-content">${formattedContent}</div>
            </div>
        `;
        
        chatHistory.appendChild(messageContainer);
    }

    // Add error message to chat
    function addErrorMessage(errorText) {
        const errorContainer = document.createElement('div');
        errorContainer.className = 'alert alert-danger mx-3 my-2';
        errorContainer.textContent = errorText;
        chatHistory.appendChild(errorContainer);
    }

    // Format message with markdown-like syntax
    function formatMessageContent(content) {
        // Replace code blocks
        content = content.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        
        // Replace inline code
        content = content.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Replace line breaks with <br>
        content = content.replace(/\n/g, '<br>');
        
        return content;
    }

    // Clear chat history
    clearChatBtn.addEventListener('click', async function() {
        if (confirm('Are you sure you want to clear the chat history?')) {
            try {
                const response = await fetch('/clear_chat', {
                    method: 'POST',
                });
                
                if (response.ok) {
                    // Clear chat UI
                    chatHistory.innerHTML = `
                        <div class="welcome-message text-center">
                            <div class="p-4">
                                <i class="fas fa-comment-dots fs-1 mb-3 text-info"></i>
                                <h4>Welcome to ChatGPT Chatbot!</h4>
                                <p class="text-muted">Start a conversation by typing a message below.</p>
                            </div>
                        </div>
                    `;
                } else {
                    const data = await response.json();
                    console.error('Error clearing chat:', data.error);
                    alert('Failed to clear chat history.');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Network error. Please check your connection and try again.');
            }
        }
    });
});
