let currentConversationId = null;
let messageInput = document.getElementById('messageInput');
let sendBtn = document.getElementById('sendBtn');
let messagesContainer = document.getElementById('messagesContainer');
let typingIndicator = document.getElementById('typingIndicator');
let newChatBtn = document.getElementById('newChatBtn');
let clearChatBtn = document.getElementById('clearChatBtn');
let exportChatBtn = document.getElementById('exportChatBtn');

document.addEventListener('DOMContentLoaded', function() {
    // Load conversations
    loadConversations();
    
    // Check URL for conversation ID
    const urlParams = new URLSearchParams(window.location.search);
    const convId = urlParams.get('conv_id');
    if (convId) {
        loadConversation(convId);
    }
    
    // Event listeners
    if (messageInput) {
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
            sendBtn.disabled = !this.value.trim();
        });
        
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (this.value.trim()) {
                    sendMessage();
                }
            }
        });
    }
    
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
    
    if (newChatBtn) {
        newChatBtn.addEventListener('click', startNewChat);
    }
    
    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', clearCurrentChat);
    }
    
    if (exportChatBtn) {
        exportChatBtn.addEventListener('click', exportChat);
    }
    
    // Topic buttons
    document.querySelectorAll('.topic-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            messageInput.value = this.textContent;
            messageInput.style.height = 'auto';
            messageInput.style.height = (messageInput.scrollHeight) + 'px';
            sendBtn.disabled = false;
            messageInput.focus();
        });
    });
});

function loadConversations() {
    fetch('/api/conversations')
        .then(response => response.json())
        .then(conversations => {
            const list = document.getElementById('conversationsList');
            if (!list) return;
            
            if (conversations.length === 0) {
                list.innerHTML += '<p class="no-conv">No conversations yet</p>';
                return;
            }
            
            let html = '<h3>Recent Conversations</h3>';
            conversations.forEach(conv => {
                const date = new Date(conv.updated_at);
                const timeStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
                
                html += `
                    <div class="conversation-item ${conv.id === currentConversationId ? 'active' : ''}" 
                         onclick="loadConversation(${conv.id})">
                        <div class="conv-icon-small">
                            <i class="fas fa-comment"></i>
                        </div>
                        <div class="conv-details">
                            <div class="conv-title">${escapeHtml(conv.title)}</div>
                            <div class="conv-time">${timeStr}</div>
                        </div>
                    </div>
                `;
            });
            
            list.innerHTML = html;
        })
        .catch(error => {
            console.error('Error loading conversations:', error);
        });
}

function loadConversation(conversationId) {
    currentConversationId = conversationId;
    
    // Update URL without reload
    const url = new URL(window.location);
    url.searchParams.set('conv_id', conversationId);
    window.history.pushState({}, '', url);
    
    // Update active state in sidebar
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('onclick')?.includes(conversationId)) {
            item.classList.add('active');
        }
    });
    
    // Load messages
    fetch(`/api/conversations/${conversationId}/messages`)
        .then(response => response.json())
        .then(messages => {
            displayMessages(messages);
        })
        .catch(error => {
            console.error('Error loading messages:', error);
        });
}

function displayMessages(messages) {
    if (!messagesContainer) return;
    
    if (messages.length === 0) {
        showWelcomeMessage();
        return;
    }
    
    let html = '';
    messages.forEach(msg => {
        const time = new Date(msg.timestamp);
        const timeStr = time.toLocaleTimeString();
        
        if (msg.role === 'user') {
            html += `
                <div class="message user">
                    <div class="message-avatar">
                        <i class="fas fa-user"></i>
                    </div>
                    <div class="message-content">
                        <p>${escapeHtml(msg.content)}</p>
                        <div class="message-time">${timeStr}</div>
                    </div>
                </div>
            `;
        } else {
            html += `
                <div class="message assistant">
                    <div class="message-avatar">
                        <i class="fas fa-user-md"></i>
                    </div>
                    <div class="message-content">
                        <p>${escapeHtml(msg.content)}</p>
                        <div class="message-time">${timeStr}</div>
                        <div class="message-disclaimer">⚠️ AI-generated medical information</div>
                    </div>
                </div>
            `;
        }
    });
    
    messagesContainer.innerHTML = html;
    scrollToBottom();
}

function showWelcomeMessage() {
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">
                <i class="fas fa-user-md"></i>
            </div>
            <h3>Welcome to DoctorAI Consultation</h3>
            <p>I'm your AI medical assistant. Please describe your symptoms or ask any health-related questions.</p>
            <p class="disclaimer">Remember: I'm an AI assistant and not a replacement for professional medical advice.</p>
            
            <div class="suggested-topics">
                <h4>Common Questions:</h4>
                <div class="topic-buttons">
                    <button class="topic-btn">What are symptoms of flu?</button>
                    <button class="topic-btn">How to lower blood pressure?</button>
                    <button class="topic-btn">First aid for burns</button>
                    <button class="topic-btn">When to see a doctor?</button>
                </div>
            </div>
        </div>
    `;
    
    // Reattach topic button listeners
    document.querySelectorAll('.topic-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            messageInput.value = this.textContent;
            messageInput.style.height = 'auto';
            messageInput.style.height = (messageInput.scrollHeight) + 'px';
            sendBtn.disabled = false;
            messageInput.focus();
        });
    });
}

function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;
    
    // Disable input
    messageInput.disabled = true;
    sendBtn.disabled = true;
    
    // Add user message to UI
    addMessageToUI('user', message);
    
    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    // Show typing indicator
    typingIndicator.classList.add('active');
    
    // Send to server
    fetch('/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message: message,
            conversation_id: currentConversationId
        })
    })
    .then(response => response.json())
    .then(data => {
        // Hide typing indicator
        typingIndicator.classList.remove('active');
        
        // Add assistant response
        addMessageToUI('assistant', data.response);
        
        // Update conversation ID if new
        if (!currentConversationId) {
            currentConversationId = data.conversation_id;
            loadConversations();
        }
        
        // Re-enable input
        messageInput.disabled = false;
        messageInput.focus();
        sendBtn.disabled = false;
    })
    .catch(error => {
        console.error('Error sending message:', error);
        typingIndicator.classList.remove('active');
        messageInput.disabled = false;
        sendBtn.disabled = false;
        
        // Show error message
        addMessageToUI('assistant', 'Sorry, an error occurred. Please try again.');
    });
}

function addMessageToUI(role, content) {
    // Remove welcome message if present
    const welcomeMsg = messagesContainer.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }
    
    const time = new Date();
    const timeStr = time.toLocaleTimeString();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.style.opacity = '0';
    
    if (role === 'user') {
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-user"></i>
            </div>
            <div class="message-content">
                <p>${escapeHtml(content)}</p>
                <div class="message-time">${timeStr}</div>
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-user-md"></i>
            </div>
            <div class="message-content">
                <p>${escapeHtml(content)}</p>
                <div class="message-time">${timeStr}</div>
                <div class="message-disclaimer">⚠️ AI-generated medical information</div>
            </div>
        `;
    }
    
    messagesContainer.appendChild(messageDiv);
    
    // Fade in animation
    setTimeout(() => {
        messageDiv.style.opacity = '1';
    }, 10);
    
    scrollToBottom();
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function startNewChat() {
    currentConversationId = null;
    
    // Remove conversation ID from URL
    const url = new URL(window.location);
    url.searchParams.delete('conv_id');
    window.history.pushState({}, '', url);
    
    // Show welcome message
    showWelcomeMessage();
    
    // Clear active state in sidebar
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.remove('active');
    });
}

function clearCurrentChat() {
    if (currentConversationId) {
        if (confirm('Are you sure you want to clear this conversation?')) {
            messagesContainer.innerHTML = '';
            startNewChat();
        }
    } else {
        messagesContainer.innerHTML = '';
        showWelcomeMessage();
    }
}

function exportChat() {
    const messages = messagesContainer.querySelectorAll('.message');
    if (messages.length === 0) {
        alert('No messages to export');
        return;
    }
    
    let exportText = 'DoctorAI Chat Export\n';
    exportText += '='.repeat(50) + '\n\n';
    
    messages.forEach(msg => {
        const role = msg.classList.contains('user') ? 'You' : 'DoctorAI';
        const content = msg.querySelector('.message-content p').textContent;
        const time = msg.querySelector('.message-time')?.textContent || '';
        
        exportText += `[${role}] ${time}\n${content}\n\n`;
    });
    
    exportText += '='.repeat(50) + '\n';
    exportText += 'This is AI-generated information. Always consult a real doctor.\n';
    
    // Create download link
    const blob = new Blob([exportText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `doctorai-chat-${new Date().toISOString().slice(0,10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}