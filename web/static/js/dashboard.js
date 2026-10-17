document.addEventListener('DOMContentLoaded', () => {
    // =========================================================================
    // 🔍 FILTRADO EN TIEMPO REAL DE TICKETS (BUSCADOR + ESTADO + TEMA)
    // =========================================================================
    const searchInput = document.getElementById('ticketSearchInput');
    const stateFilter = document.getElementById('ticketStateFilter');
    const topicFilter = document.getElementById('ticketTopicFilter');

    function applyTicketFilters() {
        const query = (searchInput ? searchInput.value : '').trim().toLowerCase();
        const stateVal = stateFilter ? stateFilter.value : 'all';
        const topicVal = topicFilter ? topicFilter.value : 'all';

        document.querySelectorAll('.searchable-ticket-card').forEach(card => {
            const textMatch = !query || card.textContent.toLowerCase().includes(query);
            const cardWaiting = card.getAttribute('data-waiting') || 'all';
            const cardTopic = card.getAttribute('data-topic') || 'all';

            const stateMatch = stateVal === 'all' || cardWaiting === 'closed' || cardWaiting === stateVal;
            const topicMatch = topicVal === 'all' || cardTopic === topicVal;

            card.style.display = (textMatch && stateMatch && topicMatch) ? '' : 'none';
        });
    }

    if (searchInput) searchInput.addEventListener('input', applyTicketFilters);
    if (stateFilter) stateFilter.addEventListener('change', applyTicketFilters);
    if (topicFilter) topicFilter.addEventListener('change', applyTicketFilters);

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

            const originalHTML = this.innerHTML;
            this.innerHTML = '<span class="material-symbols-rounded spinner" style="font-size: 18px;">sync</span> Cargando...';
            this.disabled = true;

            try {
                const response = await fetch(`?tab=${tab}&page=${page}`, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }
                });

                if (!response.ok) throw new Error('Error en red');

                const data = await response.json();
                grid.insertAdjacentHTML('beforeend', data.html);
                applyTicketFilters();

                if (data.has_next) {
                    this.setAttribute('data-page', parseInt(page, 10) + 1);
                    this.innerHTML = originalHTML;
                    this.disabled = false;
                } else {
                    this.parentElement.style.opacity = '0';
                    setTimeout(() => this.parentElement.remove(), 300);
                }
            } catch (error) {
                console.error("Error paginando:", error);
                CartMakerModal.error("Error de conexión", "No se pudieron cargar más tickets.");
                this.innerHTML = originalHTML;
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
            const targetEl = document.getElementById(targetId);
            if (targetEl) targetEl.classList.add('active');
        });
    });

    // 2. Navegación secundaria (Pestañas de Tickets)
    const ticketTabs = document.querySelectorAll('.ticket-tab-toggle');
    const ticketPanels = document.querySelectorAll('.ticket-view-tab');
    let activeSubTab = 'tab-active-content';

    ticketTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            ticketTabs.forEach(t => t.classList.remove('active'));
            ticketPanels.forEach(p => p.style.display = 'none');

            tab.classList.add('active');
            const targetPanel = document.getElementById(tab.getAttribute('data-tab'));
            if (targetPanel) targetPanel.style.display = 'block';
            activeSubTab = tab.getAttribute('data-tab');

            if (activeSubTab === 'tab-active-content') {
                const alertBadge = document.getElementById('new-tickets-alert-badge');
                if (alertBadge) {
                    alertBadge.textContent = '0';
                    alertBadge.style.display = 'none';
                }
            }
        });
    });

    // 3. Previsualización de Imagen de Perfil
    const imgInput = document.getElementById('profileImageInput');
    if (imgInput) {
        imgInput.addEventListener('change', function(e) {
            if (e.target.files && e.target.files[0]) {
                const reader = new FileReader();
                reader.onload = function(ev) {
                    const preview = document.querySelector('.avatar-preview');
                    if (preview) {
                        preview.innerHTML = '<img src="' + ev.target.result + '" alt="Profile Preview" id="avatarPreviewImg">';
                    }
                };
                reader.readAsDataURL(e.target.files[0]);
            }
        });
    }

    // 4. Inicialización de Chart.js (Paleta CartMaker Light Design System)
    const dataElement = document.getElementById('analytics-data');
    if (dataElement) {
        try {
            const rawData = dataElement.textContent;
            const analytics = JSON.parse(rawData);

            Chart.defaults.color = '#475569';
            Chart.defaults.font.family = "'Inter', sans-serif";

            const canvasTopics = document.getElementById('topicsChart');
            if (canvasTopics) {
                const ctxTopics = canvasTopics.getContext('2d');
                new Chart(ctxTopics, {
                    type: 'doughnut',
                    data: {
                        labels: analytics.topics.labels.length ? analytics.topics.labels : ['Sin datos'],
                        datasets: [{
                            data: analytics.topics.data.length ? analytics.topics.data : [1],
                            backgroundColor: ['#6D49F2', '#EC4899', '#06B6D4', '#10B981', '#F59E0B'],
                            borderWidth: 2,
                            borderColor: '#FFFFFF',
                            hoverOffset: 8
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom', labels: { padding: 18, font: { weight: '600' } } }
                        },
                        cutout: '68%'
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
                            label: 'Tickets Cerrados',
                            data: analytics.reasons.data,
                            backgroundColor: '#6D49F2',
                            borderRadius: 10,
                            barPercentage: 0.55
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            y: { beginAtZero: true, grid: { color: '#F1F5F9' }, ticks: { stepSize: 1 } },
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
        const socket = io(window.location.origin, {
            auth: { token: JWT_TOKEN },
            transports: ['websocket']
        });

        socket.on('connect', () => {
            socket.emit('join_dashboard');
        });

        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        socket.on('global_new_support_message', (msg) => {
            const badge = document.getElementById('badge-' + msg.ticket_id);
            if (badge) {
                const current = parseInt(badge.textContent, 10) || 0;
                badge.textContent = current + 1;
                badge.style.display = 'inline-block';
                badge.style.transform = 'scale(1.25)';
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
                    const rawText = msg.text || '';
                    const clipped = rawText.length > 70 ? rawText.substring(0, 70) + "..." : rawText;
                    previewContent = escapeHtml(clipped);
                } else if (msg.message_type === 'image') {
                    previewContent = '<span class="material-symbols-rounded preview-icon">image</span> Imagen adjunta';
                } else if (msg.message_type === 'audio') {
                    previewContent = '<span class="material-symbols-rounded preview-icon">mic</span> Nota de voz';
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
            if (emptyState) emptyState.remove();

            const totalCounter = document.getElementById('total-active-counter');
            if (totalCounter) {
                const currentCount = parseInt(totalCounter.textContent, 10) || 0;
                totalCounter.textContent = currentCount + 1;
            }
            const kpiOpen = document.getElementById('kpi-open-count');
            if (kpiOpen) {
                kpiOpen.textContent = (parseInt(kpiOpen.textContent, 10) || 0) + 1;
            }
            const sidebarPill = document.getElementById('sidebar-active-pill');
            if (sidebarPill) {
                sidebarPill.textContent = (parseInt(sidebarPill.textContent, 10) || 0) + 1;
            }

            if (activeSubTab === 'tab-closed-content') {
                const alertBadge = document.getElementById('new-tickets-alert-badge');
                if (alertBadge) {
                    const currentAlerts = parseInt(alertBadge.textContent, 10) || 0;
                    alertBadge.textContent = currentAlerts + 1;
                    alertBadge.style.display = 'inline-block';
                }
            }

            const safeTicketId = parseInt(ticket.id, 10) || 0;
            const safeTopicId = parseInt(ticket.topic_id, 10) || 0;
            const safeTopic = escapeHtml(ticket.topic || '');
            const safeTitle = escapeHtml(ticket.title || '');
            const rawDesc = ticket.description || '';
            const safeDesc = escapeHtml(rawDesc.substring(0, 70));

            const grid = document.getElementById('dashboard-tickets-grid');
            const card = document.createElement('a');
            card.href = '/support/ticket/' + safeTicketId + '/';
            card.className = "ticket-card-link searchable-ticket-card";
            card.id = 'ticket-card-' + safeTicketId;
            card.setAttribute('data-waiting', 'agent');
            card.setAttribute('data-topic', String(safeTopicId));

            card.innerHTML = `
                <div class="ticket-card card-needs-agent">
                    <div class="ticket-header">
                        <span class="ticket-id">#${String(safeTicketId).padStart(5, '0')}</span>
                        <span class="ticket-topic topic-${safeTopicId}">${safeTopic}</span>
                        <span class="badge-unread" id="badge-${safeTicketId}" style="display: none;">0</span>
                    </div>
                    <h4 class="ticket-title">${safeTitle}</h4>
                    <div class="ticket-message-preview">
                        <span class="preview-label" id="label-preview-${safeTicketId}">Motivo de contacto:</span>
                        <p class="ticket-desc" id="msg-preview-${safeTicketId}">${safeDesc}...</p>
                    </div>
                    <div class="ticket-footer">
                        <div class="ticket-client">
                            <span class="material-symbols-rounded">person</span>
                            <span>Nuevo Cliente</span>
                        </div>
                        <div class="ticket-time">
                            <span class="material-symbols-rounded">schedule</span>
                            <span>Justo ahora</span>
                        </div>
                    </div>
                    <div class="ticket-status-badge pending-agent">
                        <span class="material-symbols-rounded">bolt</span>
                        ¡Nuevo Caso Asignado!
                    </div>
                </div>
            `;
            if (grid) grid.prepend(card);
            applyTicketFilters();
        });

        socket.on('ticket_closed', (data) => {
            const activeCard = document.getElementById('ticket-card-' + data.ticket_id);

            if (activeCard) {
                activeCard.style.transform = 'scale(0.95)';
                activeCard.style.opacity = '0';
                activeCard.style.transition = 'all 0.25s ease';

                setTimeout(() => {
                    activeCard.remove();

                    const totalCounter = document.getElementById('total-active-counter');
                    if (totalCounter) {
                        const currentCount = parseInt(totalCounter.textContent, 10) || 0;
                        totalCounter.textContent = Math.max(0, currentCount - 1);
                    }

                    const activeGrid = document.getElementById('dashboard-tickets-grid');
                    if (activeGrid && activeGrid.children.length === 0) {
                        activeGrid.innerHTML = `
                            <div class="empty-tickets">
                                <span class="material-symbols-rounded">task_alt</span>
                                <h3>¡Todo al día!</h3>
                                <p>No tienes tickets activos asignados en este momento.</p>
                            </div>
                        `;
                    }
                }, 260);
            }
        });
    }
});