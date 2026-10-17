const socket = io(window.location.origin, {
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

const btnAttach = document.getElementById('btn-attach');
const mediaInput = document.getElementById('media-input');
const btnMic = document.getElementById('btn-mic');

let typingTimeout;

// =========================================================================
// ⚡ RESPUESTAS RÁPIDAS (MACROS DE 1 TOQUE)
// =========================================================================
document.querySelectorAll('.quick-reply-chip').forEach(chip => {
    chip.addEventListener('click', () => {
        if (!input || input.disabled) return;
        const replyText = chip.getAttribute('data-reply') || '';
        input.value = replyText;
        input.focus();
        socket.emit('typing', { isTyping: true });
    });
});

/**
 * Lightbox para ampliar imágenes enviadas en el chat de soporte
 */
function previewChatImage(imageUrl) {
    if (!imageUrl) return;
    Swal.fire({
        ...CartMakerModal.baseConfig,
        title: 'Imagen Adjunta en Soporte',
        imageUrl: imageUrl,
        imageAlt: 'Adjunto del chat',
        confirmButtonText: 'Cerrar Vista'
    });
}

async function loadHistory() {
    try {
        const response = await fetch(`/chat/support/history/?ticket_id=${TICKET_ID}`, {
            headers: { 'Authorization': `Bearer ${JWT_TOKEN}` }
        });
        const json = await response.json();
        if (loader) loader.style.display = 'none';

        if (json.data) {
            json.data.forEach(msg => renderMessage(msg));
            scrollToBottom();
        }
    } catch (e) {
        if (loader) loader.style.display = 'none';
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
            statusText.textContent = 'Cliente en línea ahora';
        } else {
            statusDot.classList.remove('online');
            statusText.textContent = 'Cliente desconectado';
        }
    }
});

socket.on('typing_status', (data) => {
    if (data.user_id !== AGENT_ID) {
        typingIndicator.textContent = data.isTyping ? "El cliente está escribiendo..." : "";
    }
});

socket.on('support_room_read_receipt', () => {
    document.querySelectorAll('.tick-icon').forEach(icon => {
        icon.textContent = 'done_all';
    });
});

socket.on('ticket_closed', (data) => {
    input.disabled = true;
    input.placeholder = `Ticket Cerrado: ${data.reason}`;
    sendBtn.disabled = true;
    btnAttach.disabled = true;
    btnMic.disabled = true;

    const inputArea = document.querySelector('.chat-input-area');
    if (inputArea) {
        inputArea.style.opacity = '0.55';
        inputArea.style.pointerEvents = 'none';
    }
    const quickBar = document.getElementById('quickRepliesBar');
    if (quickBar) {
        quickBar.style.display = 'none';
    }

    statusDot.className = 'status-dot';
    statusDot.style.background = '#EF4444';
    statusText.textContent = `Cerrado: ${data.reason}`;
    statusText.style.color = '#DC2626';
    statusText.style.fontWeight = '800';
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

// =========================================================================
// 🎙️ LÓGICA DE NOTAS DE VOZ (API MediaRecorder)
// =========================================================================
let mediaRecorder;
let audioChunks = [];
let isRecording = false;

btnMic.addEventListener('click', async () => {
    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = event => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                audioChunks = [];
                stream.getTracks().forEach(track => track.stop());

                const originalPlaceholder = input.placeholder;
                input.placeholder = "Subiendo nota de voz...";
                input.disabled = true;
                btnAttach.disabled = true;
                sendBtn.disabled = true;
                btnMic.disabled = true;

                const formData = new FormData();
                formData.append('file', audioBlob, `audio_agente_${Date.now()}.webm`);

                try {
                    const response = await fetch('/chat/support/upload-media/', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${JWT_TOKEN}` },
                        body: formData
                    });

                    const json = await response.json();

                    if (response.ok && json.url) {
                        socket.emit('send_support_message', {
                            ticket_id: TICKET_ID,
                            text: '',
                            message_type: 'audio',
                            media_url: json.url
                        });
                    } else {
                        CartMakerModal.error("Error de subida", "No se pudo subir la nota de voz. Verifica tu conexión.");
                    }
                } catch (error) {
                    console.error("Error de red subiendo audio:", error);
                    CartMakerModal.error("Fallo de conexión", "No fue posible enviar la nota de voz.");
                } finally {
                    input.placeholder = originalPlaceholder;
                    input.disabled = false;
                    btnAttach.disabled = false;
                    sendBtn.disabled = false;
                    btnMic.disabled = false;
                }
            };

            mediaRecorder.start();
            isRecording = true;

            btnMic.style.color = '#FFFFFF';
            btnMic.style.backgroundColor = '#EF4444';
            btnMic.style.borderColor = '#EF4444';
            btnMic.innerHTML = '<span class="material-symbols-rounded">stop</span>';
            input.placeholder = "Grabando nota de voz... (Pulsa Stop para enviar)";
            input.disabled = true;
            sendBtn.style.display = 'none';
            btnAttach.style.display = 'none';

        } catch (err) {
            console.error("Error accediendo al micrófono:", err);
            CartMakerModal.error("Permiso requerido", "No se pudo acceder al micrófono. Verifica los permisos del navegador.");
        }
    } else {
        mediaRecorder.stop();
        isRecording = false;

        btnMic.style.color = '';
        btnMic.style.backgroundColor = '';
        btnMic.style.borderColor = '';
        btnMic.innerHTML = '<span class="material-symbols-rounded">mic</span>';
        sendBtn.style.display = 'flex';
        btnAttach.style.display = 'flex';
    }
});

// =========================================================================
// 🖼️ LÓGICA DE SUBIDA DE IMÁGENES
// =========================================================================
btnAttach.addEventListener('click', () => {
    mediaInput.click();
});

mediaInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const originalPlaceholder = input.placeholder;
    input.placeholder = "Subiendo imagen...";
    input.disabled = true;
    btnAttach.disabled = true;
    sendBtn.disabled = true;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/chat/support/upload-media/', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${JWT_TOKEN}`
            },
            body: formData
        });

        const json = await response.json();

        if (response.ok && json.url) {
            socket.emit('send_support_message', {
                ticket_id: TICKET_ID,
                text: '',
                message_type: 'image',
                media_url: json.url
            });
        } else {
            CartMakerModal.error("Error de subida", "No se pudo subir la imagen. Verifica el formato o tamaño.");
        }
    } catch (error) {
        console.error("Error subiendo archivo:", error);
        CartMakerModal.error("Fallo de red", "Verifica tu conexión a internet e intenta de nuevo.");
    } finally {
        input.placeholder = originalPlaceholder;
        input.disabled = false;
        btnAttach.disabled = false;
        sendBtn.disabled = false;
        mediaInput.value = '';
    }
});

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

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function renderMessage(msg) {
    const div = document.createElement('div');
    const isAgent = msg.sender_id === AGENT_ID;
    div.className = `message ${isAgent ? 'agent' : 'client'}`;

    let content = escapeHtml(msg.text);
    const safeMediaUrl = escapeHtml(msg.media_url);
    if (msg.message_type === 'image') {
        content = `<div style="max-width: 260px; overflow: hidden; border-radius: 12px; cursor: pointer;" onclick="previewChatImage('${safeMediaUrl}')">
                       <img src="${safeMediaUrl}" style="width: 100%; height: auto; display: block; border-radius: 12px;" alt="Adjunto">
                   </div>`;
    } else if (msg.message_type === 'audio') {
        content = `<audio controls src="${safeMediaUrl}" style="height:36px; max-width:250px;"></audio>`;
    }

    const tickIcon = isAgent
        ? `<span class="material-symbols-rounded tick-icon" style="font-size:15px;">${msg.status >= 3 ? 'done_all' : 'check'}</span>`
        : '';

    const safeTime = escapeHtml((msg.created_at || '').split(' ').slice(1).join(' '));
    div.innerHTML = `
        ${content}
        <div class="message-time">
            ${safeTime}
            ${tickIcon}
        </div>
    `;

    messagesContainer.appendChild(div);
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// =========================================================================
// 🔒 LÓGICA DE CIERRE DE TICKET CON MODAL UNIFICADO CARTMAKER
// =========================================================================
const btnTriggerClose = document.getElementById('btn-trigger-close');

if (btnTriggerClose) {
    btnTriggerClose.addEventListener('click', async () => {
        const result = await CartMakerModal.form({
            title: 'Resolver y Cerrar Ticket',
            html: `
                <div style="text-align: left; margin-top: 8px;">
                    <label style="font-size: 0.78rem; color: #475569; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; display: block;">
                        Selecciona el dictamen de resolución:
                    </label>
                    <select id="swal-close-reason" class="cm-modal-select">
                        <option value="0">Resuelto con éxito</option>
                        <option value="1">No se pudo resolver</option>
                        <option value="2">Spam / Solicitud inválida</option>
                        <option value="3">El cliente no responde</option>
                    </select>
                </div>
            `,
            confirmText: 'Confirmar Cierre',
            preConfirm: () => {
                return document.getElementById('swal-close-reason').value;
            }
        });

        if (result.isConfirmed) {
            const reasonId = result.value;
            const csrfToken = document.getElementById('csrf_token').value;

            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/support/ticket/${TICKET_ID}/close/`;

            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrfmiddlewaretoken';
            csrfInput.value = csrfToken;

            const reasonInput = document.createElement('input');
            reasonInput.type = 'hidden';
            reasonInput.name = 'close_reason';
            reasonInput.value = reasonId;

            form.appendChild(csrfInput);
            form.appendChild(reasonInput);
            document.body.appendChild(form);

            Swal.showLoading();
            form.submit();
        }
    });
}

loadHistory();