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

                    if (response.ok && (json.path || json.url)) {
                        socket.emit('send_support_message', {
                            ticket_id: TICKET_ID,
                            text: '',
                            message_type: 'audio',
                            media_url: json.path || json.url
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

        if (response.ok && (json.path || json.url)) {
            socket.emit('send_support_message', {
                ticket_id: TICKET_ID,
                text: '',
                message_type: 'image',
                media_url: json.path || json.url
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
    if (msg.message_type === 'system' || msg.sender_role === 'system') {
        const sysDiv = document.createElement('div');
        sysDiv.style.cssText = 'align-self: center; background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1; border-radius: 999px; padding: 5px 14px; font-size: 0.76rem; font-weight: 700; margin: 6px auto; text-align: center; max-width: 88%;';
        sysDiv.textContent = msg.text || '';
        messagesContainer.appendChild(sysDiv);
        return;
    }

    const div = document.createElement('div');
    const isAgent = (msg.sender_id === AGENT_ID) || (msg.sender_role === 'support');
    div.className = `message ${isAgent ? 'agent' : 'client'}`;

    let roleBadgeHtml = '';
    if (!isAgent) {
        const isMerchantSender = msg.sender_role === 'merchant';
        const roleLabel = isMerchantSender ? '🏪 Comerciante' : '🛒 Comprador';
        const roleBg = isMerchantSender ? '#FEF3C7' : '#DBEAFE';
        const roleColor = isMerchantSender ? '#92400E' : '#1E40AF';
        const senderNameSafe = escapeHtml(msg.sender_name || '');
        roleBadgeHtml = `
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px; font-size: 0.72rem;">
                <span style="background: ${roleBg}; color: ${roleColor}; padding: 2px 7px; border-radius: 6px; font-weight: 800;">${roleLabel}</span>
                <strong style="color: #334155;">${senderNameSafe}</strong>
            </div>
        `;
    }

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
        ${roleBadgeHtml}
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
// 🔇 CONTROL DE SILENCIAMIENTO TRIPARTITO (COMPRADOR / COMERCIANTE)
// =========================================================================
function updateMuteButtonUI(role, isMuted) {
    const btn = document.getElementById(`btn-mute-${role}`);
    const icon = document.getElementById(`icon-mute-${role}`);
    const label = document.getElementById(`label-mute-${role}`);
    if (!btn) return;
    btn.setAttribute('data-muted', isMuted ? 'true' : 'false');
    btn.style.borderColor = isMuted ? '#EF4444' : '#CBD5E1';
    btn.style.background = isMuted ? '#FEF2F2' : '#FFFFFF';
    btn.style.color = isMuted ? '#DC2626' : '#334155';
    if (icon) icon.textContent = isMuted ? 'volume_off' : 'volume_up';
    if (label) {
        if (role === 'client') {
            label.textContent = isMuted ? 'Comprador Silenciado' : 'Silenciar Comprador';
        } else {
            label.textContent = isMuted ? 'Comercio Silenciado' : 'Silenciar Comercio';
        }
    }
}

async function toggleParticipantMute(role) {
    const btn = document.getElementById(`btn-mute-${role}`);
    if (!btn) return;
    const currentlyMuted = btn.getAttribute('data-muted') === 'true';
    const nextMuted = !currentlyMuted;
    const csrfTokenEl = document.getElementById('csrf_token');
    const csrfToken = csrfTokenEl ? csrfTokenEl.value : '';

    btn.disabled = true;
    try {
        const resp = await fetch(`/support/ticket/${TICKET_ID}/mute/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({
                target_role: role,
                muted: nextMuted,
            }),
        });
        const data = await resp.json();
        if (resp.ok && data.success) {
            updateMuteButtonUI('client', Boolean(data.muted_client));
            updateMuteButtonUI('merchant', Boolean(data.muted_merchant));
        } else {
            CartMakerModal.error('Error', data.error || 'No se pudo actualizar el estado de silenciamiento.');
        }
    } catch (e) {
        CartMakerModal.error('Error de red', 'No se pudo conectar con el servidor.');
    } finally {
        btn.disabled = false;
    }
}

const btnMuteClient = document.getElementById('btn-mute-client');
if (btnMuteClient) {
    btnMuteClient.addEventListener('click', () => toggleParticipantMute('client'));
}
const btnMuteMerchant = document.getElementById('btn-mute-merchant');
if (btnMuteMerchant) {
    btnMuteMerchant.addEventListener('click', () => toggleParticipantMute('merchant'));
}

socket.on('support_mute_status', (data) => {
    if (data && String(data.ticket_id) === String(TICKET_ID)) {
        updateMuteButtonUI('client', Boolean(data.muted_client));
        updateMuteButtonUI('merchant', Boolean(data.muted_merchant));
    }
});

// =========================================================================
// 🔒 LÓGICA DE CIERRE DE TICKET CON MODAL UNIFICADO CARTMAKER + CONCLUSIÓN
// =========================================================================
const btnTriggerClose = document.getElementById('btn-trigger-close');

if (btnTriggerClose) {
    btnTriggerClose.addEventListener('click', async () => {
        const result = await CartMakerModal.form({
            title: 'Resolver y Cerrar Ticket',
            html: `
                <div style="text-align: left; margin-top: 8px; display: flex; flex-direction: column; gap: 12px;">
                    <div>
                        <label style="font-size: 0.78rem; color: #475569; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; display: block;">
                            Selecciona el dictamen de resolución:
                        </label>
                        <select id="swal-close-reason" class="cm-modal-select">
                            <option value="0">Resuelto con éxito</option>
                            <option value="1">No se pudo resolver</option>
                            <option value="2">Spam / Solicitud inválida</option>
                            <option value="3">El cliente no responde</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 0.78rem; color: #475569; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; display: block;">
                            Conclusión / Dictamen para las partes (visible en la orden y ticket):
                        </label>
                        <textarea id="swal-resolution-note" rows="3" placeholder="Ej: Se verificó el comprobante bancario y se acordó la entrega inmediata del pedido..." style="width: 100%; border: 1px solid #CBD5E1; border-radius: 10px; padding: 10px; font-size: 0.88rem; font-family: inherit; resize: vertical;"></textarea>
                    </div>
                </div>
            `,
            confirmText: 'Confirmar Cierre',
            preConfirm: () => {
                return {
                    reasonId: document.getElementById('swal-close-reason').value,
                    resolutionNote: (document.getElementById('swal-resolution-note').value || '').trim(),
                };
            }
        });

        if (result.isConfirmed && result.value) {
            const { reasonId, resolutionNote } = result.value;
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

            const noteInput = document.createElement('input');
            noteInput.type = 'hidden';
            noteInput.name = 'resolution_note';
            noteInput.value = resolutionNote;

            form.appendChild(csrfInput);
            form.appendChild(reasonInput);
            form.appendChild(noteInput);
            document.body.appendChild(form);

            Swal.showLoading();
            form.submit();
        }
    });
}

loadHistory();