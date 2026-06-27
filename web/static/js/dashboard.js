document.addEventListener('DOMContentLoaded', () => {
    // =========================================================================
    // 🔄 LÓGICA DE PAGINACIÓN ASÍNCRONA (AJAX)
    // =========================================================================
    const loadMoreButtons = document.querySelectorAll('.btn-load-more');

    loadMoreButtons.forEach(button => {
        button.addEventListener('click', async function() {
            const tab = this.getAttribute('data-tab');
            const page = this.getAttribute('data-page');
            const gridId = tab === 'active' ? 'dashboard-tickets-grid' : 'dashboard-closed-tickets-grid';
            const grid = document.getElementById(gridId);
            
            // Estado de carga (UX)
            const originalText = this.textContent;
            this.innerHTML = '<span class="material-symbols-rounded spinner" style="font-size: 18px; vertical-align: middle;">sync</span> Cargando...';
            this.disabled = true;

            try {
                // Petición al mismo dashboard_view pero como AJAX
                const response = await fetch(`?tab=${tab}&page=${page}`, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest', // Crítico para que Django lo detecte
                        'Accept': 'application/json'
                    }
                });

                if (!response.ok) throw new Error('Error en red');
                
                const data = await response.json();

                // Insertamos el nuevo HTML al final del grid
                grid.insertAdjacentHTML('beforeend', data.html);

                // Actualizamos el botón
                if (data.has_next) {
                    this.setAttribute('data-page', parseInt(page) + 1);
                    this.textContent = originalText;
                    this.disabled = false;
                } else {
                    // Si no hay más páginas, desaparecemos el botón suavemente
                    this.parentElement.style.opacity = '0';
                    setTimeout(() => this.parentElement.remove(), 300);
                }

            } catch (error) {
                console.error("Error paginando:", error);
                CartMakerModal.error("Error de conexión", "No se pudieron cargar más tickets.");
                this.textContent = originalText;
                this.disabled = false;
            }
        });
    });
    // 1. Navegación principal (Paneles)
    const navButtons = document.querySelectorAll('.nav-btn');
    const panels = document.querySelectorAll('.dash-panel');

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            navButtons.forEach(b => b.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetId = btn.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');
        });
    });

    // 2. Navegación secundaria (Pestañas de Tickets)
    const ticketTabs = document.querySelectorAll('.ticket-tab-toggle');
    const ticketPanels = document.querySelectorAll('.ticket-view-tab');
    let activeSubTab = 'tab-active-content';

    ticketTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            ticketTabs.forEach(t => {
                t.classList.remove('active');
                t.style.color = '#757575';
                t.style.fontWeight = '700';
            });
            ticketPanels.forEach(p => p.style.display = 'none');

            tab.classList.add('active');
            tab.style.color = '#6D49F2';
            tab.style.fontWeight = '800';

            const targetPanel = document.getElementById(tab.getAttribute('data-tab'));
            targetPanel.style.display = 'block';
            activeSubTab = tab.getAttribute('data-tab');

            // Si vuelve a "Activos", limpiamos el badge rojo
            if (activeSubTab === 'tab-active-content') {
                const alertBadge = document.getElementById('new-tickets-alert-badge');
                if (alertBadge) {
                    alertBadge.textContent = '0';
                    alertBadge.style.display = 'none';
                }
            }
        });
    });

    // 3. Previsualización de Imagen
    const imgInput = document.getElementById('profileImageInput');
    if (imgInput) {
        imgInput.addEventListener('change', function(e) {
            if (e.target.files && e.target.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const preview = document.querySelector('.avatar-preview');
                    preview.innerHTML = '<img src="' + e.target.result + '" alt="Profile Preview" id="avatarPreviewImg" style="width:100%; height:100%; object-fit:cover; border-radius:50%;">';
                }
                reader.readAsDataURL(e.target.files[0]);
            }
        });
    }

    // 4. Inicialización de Chart.js
    const dataElement = document.getElementById('analytics-data');
    if (dataElement) {
        try {
            const rawData = dataElement.textContent;
            const analytics = JSON.parse(rawData);

            Chart.defaults.color = '#D7D7D7';
            Chart.defaults.font.family = "'Inter', sans-serif";

            const canvasTopics = document.getElementById('topicsChart');
            if (canvasTopics) {
                const ctxTopics = canvasTopics.getContext('2d');
                new Chart(ctxTopics, {
                    type: 'doughnut',
                    data: {
                        labels: analytics.topics.labels,
                        datasets: [{
                            data: analytics.topics.data,
                            backgroundColor: ['#6D49F2', '#E65100', '#D32F2F', '#757575'],
                            borderWidth: 0,
                            hoverOffset: 10
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom', labels: { padding: 20 } }
                        },
                        cutout: '70%'
                    }
                });
            }

            const canvasReasons = document.getElementById('reasonsChart');
            if (canvasReasons) {
                const ctxReasons = canvasReasons.getContext('2d');
                new Chart(ctxReasons, {
                    type: 'bar',
                    data: {
                        labels: analytics.reasons.labels,
                        datasets: [{
                            label: 'Tickets',
                            data: analytics.reasons.data,
                            backgroundColor: '#6D49F2',
                            borderRadius: 8,
                            barPercentage: 0.6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                            x: { grid: { display: false } }
                        }
                    }
                });
            }
        } catch (error) {
            console.error("Error inicializando las gráficas:", error);
        }
    }

    // 5. WebSockets y UI en tiempo real
    if (typeof io !== 'undefined' && typeof JWT_TOKEN !== 'undefined') {
        const socket = io("http://127.0.0.1:3000", {
            auth: { token: JWT_TOKEN },
            transports: ['websocket']
        });

        socket.on('connect', () => {
            socket.emit('join_dashboard');
            console.log("Conectado al monitoreo en tiempo real");
        });

        socket.on('global_new_support_message', (msg) => {
            const badge = document.getElementById('badge-' + msg.ticket_id);
            if (badge) {
                const current = parseInt(badge.textContent) || 0;
                badge.textContent = current + 1;
                badge.style.display = 'inline-block';
                badge.style.transform = 'scale(1.3)';
                setTimeout(() => badge.style.transform = 'scale(1)', 200);
            }

            const labelPreview = document.getElementById('label-preview-' + msg.ticket_id);
            const msgPreview = document.getElementById('msg-preview-' + msg.ticket_id);

            if (labelPreview) {
                labelPreview.textContent = "Último mensaje:";
            }

            if (msgPreview) {
                let previewContent = "";
                if (msg.message_type === 'text') {
                    previewContent = msg.text.length > 65 ? msg.text.substring(0, 65) + "..." : msg.text;
                } else if (msg.message_type === 'image') {
                    previewContent = '<span class="material-symbols-rounded preview-icon" style="font-size: 14px; vertical-align: middle;">image</span> Imagen enviada';
                } else if (msg.message_type === 'audio') {
                    previewContent = '<span class="material-symbols-rounded preview-icon" style="font-size: 14px; vertical-align: middle;">mic</span> Nota de voz';
                }
                msgPreview.innerHTML = previewContent;
            }

            const card = document.getElementById('ticket-card-' + msg.ticket_id);
            const grid = document.getElementById('dashboard-tickets-grid');
            if (card && grid) {
                grid.prepend(card);
            }
        });

        socket.on('new_ticket_assigned', (ticket) => {
            const emptyState = document.querySelector('#tab-active-content .empty-tickets');
            if(emptyState) emptyState.remove();

            // Incrementar contador global
            const totalCounter = document.getElementById('total-active-counter');
            if(totalCounter) {
                const currentCount = parseInt(totalCounter.textContent) || 0;
                totalCounter.textContent = currentCount + 1;
            }

            // Si está en la pestaña de cerrados, mostrar notificación
            if (activeSubTab === 'tab-closed-content') {
                const alertBadge = document.getElementById('new-tickets-alert-badge');
                if (alertBadge) {
                    const currentAlerts = parseInt(alertBadge.textContent) || 0;
                    alertBadge.textContent = currentAlerts + 1;
                    alertBadge.style.display = 'inline-block';
                }
            }

            const grid = document.getElementById('dashboard-tickets-grid');
            const card = document.createElement('a');
            card.href = '/support/ticket/' + ticket.id + '/';
            card.className = "ticket-card-link";
            card.id = 'ticket-card-' + ticket.id;
            
            card.innerHTML = `
                <div class="ticket-card" style="animation: slideIn 0.5s ease; border-color: var(--success-green);">
                    <div class="ticket-header" style="display: flex; align-items: center;">
                        <span class="ticket-id">#${String(ticket.id).padStart(5, '0')}</span>
                        <span class="ticket-topic topic-${ticket.topic_id}">${ticket.topic}</span>
                        <span class="badge-unread" id="badge-${ticket.id}" style="margin-left: auto; background-color: var(--error-red); color: white; border-radius: 50%; padding: 2px 8px; font-size: 12px; font-weight: bold; display: none;">0</span>
                    </div>
                    <h4 class="ticket-title">${ticket.title}</h4>
                    <div class="ticket-message-preview">
                        <span class="preview-label" id="label-preview-${ticket.id}">Motivo de contacto:</span>
                        <p class="ticket-desc" id="msg-preview-${ticket.id}">${ticket.description.substring(0, 65)}...</p>
                    </div>
                    <div class="ticket-footer">
                        <div class="ticket-client">
                            <span class="material-symbols-rounded">person</span>
                            Nuevo Cliente
                        </div>
                        <div class="ticket-time">
                            <span class="material-symbols-rounded">schedule</span>
                            Justo ahora
                        </div>
                    </div>
                    <div class="ticket-status-badge pending-agent" style="background: var(--success-green)">¡Nuevo Asignado!</div>
                </div>
            `;
            grid.prepend(card);
        });

        // 💡 NUEVO: Escuchar cuando un ticket se cierra en tiempo real
        socket.on('ticket_closed', (data) => {
            // Buscamos la tarjeta en el panel de activos
            const activeCard = document.getElementById('ticket-card-' + data.ticket_id);
            
            if (activeCard) {
                // 1. Animación de salida (opcional, le da un gran toque UX)
                activeCard.style.transform = 'scale(0.9)';
                activeCard.style.opacity = '0';
                activeCard.style.transition = 'all 0.3s ease';
                
                // 2. Remover del DOM después de la animación
                setTimeout(() => {
                    activeCard.remove();
                    
                    // 3. Actualizar el contador global de activos
                    const totalCounter = document.getElementById('total-active-counter');
                    if (totalCounter) {
                        const currentCount = parseInt(totalCounter.textContent) || 0;
                        totalCounter.textContent = Math.max(0, currentCount - 1);
                    }

                    // 4. Si la cuadrícula quedó vacía, mostrar el mensaje de "¡Todo al día!"
                    const activeGrid = document.getElementById('dashboard-tickets-grid');
                    if (activeGrid && activeGrid.children.length === 0) {
                        activeGrid.innerHTML = `
                            <div class="empty-tickets" style="animation: fadeIn 0.5s ease;">
                                <span class="material-symbols-rounded">task_alt</span>
                                <h3>¡Todo al día!</h3>
                                <p>No tienes tickets asignados en este momento.</p>
                            </div>
                        `;
                    }
                }, 300);
            }
        });
    }
});