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

// 💡 NUEVO: Capturar elementos multimedia
const btnAttach = document.getElementById('btn-attach');
const mediaInput = document.getElementById('media-input');
const btnMic = document.getElementById('btn-mic');

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

socket.on('ticket_closed', (data) => {
    // 1. Bloquear inputs lógicamente
    input.disabled = true;
    input.placeholder = `Ticket Cerrado: ${data.reason}`;
    sendBtn.disabled = true;
    btnAttach.disabled = true;
    btnMic.disabled = true;
    
    // 2. Apagar el área de input visualmente
    const inputArea = document.querySelector('.chat-input-area');
    if (inputArea) {
        inputArea.style.opacity = '0.5';
        inputArea.style.pointerEvents = 'none';
        inputArea.style.filter = 'grayscale(100%)';
        inputArea.style.transition = 'all 0.4s ease';
    }
    
    // 3. Actualizar estado del cliente (Corrección de clase)
    statusDot.className = 'status-dot'; // Mantenemos la clase base
    statusDot.style.background = 'var(--error-red)';
    statusDot.style.boxShadow = '0 0 10px var(--error-red)'; // Brillo rojo
    
    statusText.textContent = `Cerrado: ${data.reason}`;
    statusText.style.color = 'var(--error-red)';
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
        // 1. Iniciar Grabación
        try {
            // Pedimos permiso al navegador para usar el micrófono
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            
            mediaRecorder.ondataavailable = event => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                // Creamos el archivo final en formato webm o mp4 (soportado por HTML5)
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                audioChunks = []; 
                
                // Apagamos la luz roja del micrófono en la pestaña del navegador
                stream.getTracks().forEach(track => track.stop());

                // Bloqueamos inputs mientras se sube
                const originalPlaceholder = input.placeholder;
                input.placeholder = "Subiendo audio...";
                input.disabled = true;
                btnAttach.disabled = true;
                sendBtn.disabled = true;
                btnMic.disabled = true;

                // Preparamos el FormData simulando un archivo
                const formData = new FormData();
                formData.append('file', audioBlob, `audio_agente_${Date.now()}.webm`);

                try {
                    // Usamos el MISMO endpoint que preparamos para las fotos de soporte
                    const response = await fetch('/chat/support/upload-media/', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${JWT_TOKEN}` },
                        body: formData
                    });

                    const json = await response.json();

                    if (response.ok && json.url) {
                        // Enviamos el mensaje por el socket
                        socket.emit('send_support_message', {
                            ticket_id: TICKET_ID,
                            text: '', 
                            message_type: 'audio',
                            media_url: json.url
                        });
                    } else {
                        CartMakerModal.error("Oops", "Error al subir el audio. Verifica tu conexión.");
                    }
                } catch (error) {
                    console.error("Error de red subiendo audio:", error);
                    alert("Fallo de conexión al enviar la nota de voz.");
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
            
            // 💡 Efectos visuales de grabación
            btnMic.style.color = 'white';
            btnMic.style.backgroundColor = 'var(--error-red)';
            btnMic.innerHTML = '<span class="material-symbols-rounded">stop</span>';
            input.placeholder = "Grabando... (Click en Stop para enviar)";
            input.disabled = true; 
            sendBtn.style.display = 'none';
            btnAttach.style.display = 'none';

        } catch (err) {
            console.error("Error accediendo al micrófono:", err);
            CartMakerModal.error("Permiso denegado", "No se pudo acceder al micrófono. Verifica los permisos del navegador.");
        }
    } else {
        // 2. Detener Grabación (dispara mediaRecorder.onstop automáticamente)
        mediaRecorder.stop();
        isRecording = false;
        
        // Restauramos los estilos del botón
        btnMic.style.color = 'var(--primary)';
        btnMic.style.backgroundColor = 'transparent';
        btnMic.innerHTML = '<span class="material-symbols-rounded">mic</span>';
        sendBtn.style.display = 'flex';
        btnAttach.style.display = 'flex';
    }
});

// =========================================================================
// 💡 NUEVO: LÓGICA DE SUBIDA DE IMÁGENES
// =========================================================================
btnAttach.addEventListener('click', () => {
    mediaInput.click();
});

mediaInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Bloqueamos inputs temporalmente
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
        mediaInput.value = ''; // Limpiamos el input
    }
});
// =========================================================================

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
        // Envolvemos la imagen en un contenedor para que mantenga un tamaño decente
        content = `<div style="max-width: 250px; overflow: hidden; border-radius: 8px;">
                       <img src="${msg.media_url}" style="width: 100%; height: auto; display: block; border-radius: 8px;">
                   </div>`;
    } else if (msg.message_type === 'audio') {
        content = `<audio controls src="${msg.media_url}" style="height:35px;"></audio>`;
    }

    const tickIcon = isAgent 
        ? `<span class="material-symbols-rounded tick-icon" style="font-size:14px;">${msg.status >= 3 ? 'done_all' : 'check'}</span>` 
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

// =========================================================================
// 🔒 LÓGICA DE CIERRE DE TICKET CON MODAL PERSONALIZADO
// =========================================================================
const btnTriggerClose = document.getElementById('btn-trigger-close');

if (btnTriggerClose) {
    btnTriggerClose.addEventListener('click', async () => {
        
        // 1. Invocamos el formulario modal usando la estructura limpia
        const result = await CartMakerModal.form({
            title: 'Cerrar Ticket',
            html: `
                <div style="text-align: left; margin-top: 10px;">
                    <label style="font-size: 0.85rem; color: var(--light-grey); font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; display: block;">
                        Selecciona el motivo de resolución:
                    </label>
                    <select id="swal-close-reason" class="custom-select" style="width: 100%; box-sizing: border-box; text-align: left;">
                        <option value="0">Resuelto con éxito</option>
                        <option value="1">No se pudo resolver</option>
                        <option value="2">Spam / Inválido</option>
                        <option value="3">El cliente no responde</option>
                    </select>
                </div>
            `,
            confirmText: 'Confirmar Cierre',
            preConfirm: () => {
                // Extraemos el valor del DOM dentro de Swal antes de que se cierre
                return document.getElementById('swal-close-reason').value;
            }
        });

        // 2. Si el agente confirmó (no canceló)
        if (result.isConfirmed) {
            const reasonId = result.value;
            const csrfToken = document.getElementById('csrf_token').value;

            // 3. Creamos un formulario dinámico para enviar el POST a Django 
            // (Mantenemos el patrón original que redirige al dashboard)
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/support/close-ticket/${TICKET_ID}/`; // Ajusta esta URL si tu urls.py es distinta
            
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

            // 4. Feedback visual opcional antes de redirigir
            Swal.showLoading();
            form.submit();
        }
    });
}

loadHistory();