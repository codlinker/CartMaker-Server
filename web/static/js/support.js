const socket = io("http://127.0.0.1:3000", {
    auth: { token: JWT_TOKEN },
    transports: ['websocket']
});

const messagesContainer = document.getElementById('chat-messages');
const input = document.getElementById('message-input');
const sendBtn = document.getElementById('send-button');
const typingIndicator = document.getElementById('typing-indicator');
const statusDot = document.getElementById('client-status-dot');
const statusText = document.getElementById('client-status-text');
const loader = document.getElementById('history-loader');

let typingTimeout;

async function loadHistory() {
    try {
        const response = await fetch(`/chat/support/history/?ticket_id=${TICKET_ID}`, {
            headers: { 'Authorization': `Bearer ${JWT_TOKEN}` }
        });
        const json = await response.json();
        loader.style.display = 'none';
        
        if (json.data) {
            json.data.forEach(msg => renderMessage(msg));
            scrollToBottom();
        }
    } catch (e) {
        loader.style.display = 'none';
    }
}

socket.on('connect', () => {
    socket.emit('join_support_chat', { ticket_id: TICKET_ID });
});

socket.on('new_support_message', (msg) => {
    renderMessage(msg);
    scrollToBottom();
});

socket.on('support_presence_change', (data) => {
    if (data.user_id !== AGENT_ID) {
        if (data.status === 'online') {
            statusDot.classList.add('online');
            statusText.textContent = 'Cliente en línea';
        } else {
            statusDot.classList.remove('online');
            statusText.textContent = 'Cliente desconectado';
        }
    }
});

socket.on('typing_status', (data) => {
    if (data.user_id !== AGENT_ID) {
        typingIndicator.textContent = data.isTyping ? "Escribiendo..." : "";
    }
});

socket.on('support_room_read_receipt', () => {
    document.querySelectorAll('.tick-icon').forEach(icon => {
        icon.textContent = 'done_all';
    });
});

input.addEventListener('input', () => {
    socket.emit('typing', { isTyping: input.value.trim().length > 0 });
    
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        socket.emit('typing', { isTyping: false });
    }, 2000);
});

input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

sendBtn.addEventListener('click', sendMessage);

function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    socket.emit('send_support_message', {
        ticket_id: TICKET_ID,
        text: text,
        message_type: 'text',
        media_url: null
    });

    input.value = '';
    socket.emit('typing', { isTyping: false });
}

function renderMessage(msg) {
    const div = document.createElement('div');
    const isAgent = msg.sender_id === AGENT_ID;
    div.className = `message ${isAgent ? 'agent' : 'client'}`;
    
    let content = msg.text;
    if (msg.message_type === 'image') {
        content = `<img src="${msg.media_url}" style="max-width:100%; border-radius:8px;">`;
    } else if (msg.message_type === 'audio') {
        content = `<audio controls src="${msg.media_url}" style="height:35px;"></audio>`;
    }

    const tickIcon = isAgent 
        ? `<span class="material-icons-rounded tick-icon" style="font-size:14px;">${msg.status >= 3 ? 'done_all' : 'check'}</span>` 
        : '';

    div.innerHTML = `
        ${content}
        <div class="message-time">
            ${msg.created_at.split(' ').slice(1).join(' ')}
            ${tickIcon}
        </div>
    `;
    
    messagesContainer.appendChild(div);
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

loadHistory();