/**
 * CartMaker Payments Dashboard - Core de Control de Transacciones
 * Maneja las interacciones asíncronas y cambios de interfaz del Tablero Administrativo.
 */

"use strict";

/**
 * Conmutador de vistas principales de tablas de control (Decks)
 */
function changeDeck(tabButton) {
    const selectedDeckId = tabButton.getAttribute('data-target');
    
    // Remover estados de activación vigentes
    document.querySelectorAll('.deck-view').forEach(deck => {
        deck.classList.remove('active');
    });
    document.querySelectorAll('.matrix-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Asignar visibilidad al elemento objetivo
    document.getElementById(selectedDeckId).classList.add('active');
    tabButton.classList.add('active');
}

/**
 * Renderizador de previsualización para el documento de soporte bancario reportado
 */
function displayProofModal(proofUrl, referenceNumber) {
    Swal.fire({
        background: 'rgba(20, 15, 30, 0.98)',
        color: '#ffffff',
        title: `Comprobante Ref: ${referenceNumber}`,
        imageUrl: proofUrl,
        imageAlt: 'Captura de pantalla de la transacción del cliente',
        confirmButtonText: 'Cerrar Vista',
        customClass: {
            popup: 'cm-modal-popup',
            title: 'cm-modal-title',
            confirmButton: 'btn-submit cm-modal-btn'
        }
    });
}

/**
 * Canaliza la resolución de estado del pago hacia la pasarela REST de Django
 * @param {string} type Contexto del pago ('merchant' o 'atlas')
 * @param {string} id Identificador primario UUID/Int del registro de pago
 * @param {number} status target status (1 = APPROVED, 2 = REJECTED)
 * @param {number|null} reasonId Clave del enum RejectionReason (requerido si status es 2)
 */
async function executePaymentResolution(type, id, status, reasonId = null) {
    try {
        const payload = {
            payment_type: type,
            payment_id: id,
            status: status,
            rejection_reason: reasonId
        };

        const response = await fetch(ENDPOINT_URI, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': APP_CSRF_TOKEN
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (data.success) {
            await CartMakerModal.success('Operación Completada', data.message);
            
            // Remoción fluida de la fila en la tabla dinámica
            const targetRow = document.getElementById(`row-${type}-${id}`);
            if (targetRow) {
                targetRow.remove();
                
                // Recalcular y decrementar contadores visuales del Tablero
                const badge = document.getElementById(`badge-${type}`);
                if (badge) {
                    let currentCount = parseInt(badge.textContent) || 0;
                    badge.textContent = Math.max(0, currentCount - 1);
                }
            }
        } else {
            // Manejo estructurado de fallas de validación de negocio devueltas por Django
            let parsedError = typeof data.error === 'object' ? JSON.stringify(data.error) : data.error;
            CartMakerModal.error('Error de Negocio', parsedError);
        }

    } catch (error) {
        CartMakerModal.error('Fallo del Ecosistema', 'No fue posible actualizar el estado del pago debido a una desconexión de red.');
    }
}

/**
 * Refresca el deck activo actual (Merchant o Atlas) extrayendo el HTML desde el servidor.
 */
async function refreshActiveDeck() {
    // 1. Identificar el contexto activo
    const activeTab = document.querySelector('.matrix-tab-btn.active');
    if (!activeTab) return;
    
    const targetDeckId = activeTab.getAttribute('data-target'); // 'merchant-deck' o 'atlas-deck'
    const deckType = targetDeckId === 'merchant-deck' ? 'merchant' : 'atlas';
    const deckContainer = document.getElementById(targetDeckId);
    
    // 2. Efecto visual de "Cargando"
    deckContainer.style.opacity = '0.5';
    deckContainer.style.pointerEvents = 'none';
    
    try {
        const response = await fetch(`${ENDPOINT_URI}?deck=${deckType}`, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest' // Header clave para que Django lo detecte
            }
        });
        
        const data = await response.json();
        
        if (data.success && data.html) {
            // 3. Inyectar el nuevo HTML parcial directamente
            deckContainer.innerHTML = data.html;
            
            // 4. Actualizar el contador del badge
            const badge = document.getElementById(`badge-${deckType}`);
            if (badge) {
                badge.textContent = data.pending_count;
            }
        }
    } catch (error) {
        CartMakerModal.error('Fallo de Sincronización', 'No se pudieron obtener los últimos pagos del servidor.');
    } finally {
        // Restaurar estado visual
        deckContainer.style.opacity = '1';
        deckContainer.style.pointerEvents = 'auto';
    }
}

/**
 * Despliega el modal de confirmación antes de aprobar un pago
 */
async function triggerApprovalWorkflow(type, id) {
    const isConfirmed = await CartMakerModal.confirm(
        '¿Validar y Aprobar Pago?',
        '¿Estás seguro de que deseas confirmar esta transacción? Los fondos serán acreditados inmediatamente a la cuenta.',
        'Sí, Validar Pago',
        'Cancelar'
    );

    if (isConfirmed) {
        executePaymentResolution(type, id, 1);
    }
}

/**
 * Despliega el formulario Swal parametrizado con los motivos de rechazo reales del backend
 */
async function triggerRejectionWorkflow(type, id) {
    // Extracción segura del nodo JSON incrustado en el DOM por Django
    const rawOptions = JSON.parse(document.getElementById('rejection-reasons-source').textContent);
    
    // Construcción limpia del select modular
    let selectMarkup = `<select id="modal-rejection-selector" class="cm-rejection-select">`;
    rawOptions.forEach(opt => {
        selectMarkup += `<option value="${opt.id}">${opt.label}</option>`;
    });
    selectMarkup += `</select>`;

    const modalTemplateHTML = `
        <p style="text-align: left; font-size: 0.9rem; color: var(--light-grey); line-height: 1.5;">
            Por favor, indica cuál es la inconsistencia detectada en el comprobante. Esta acción revocará la petición y notificará de inmediato al usuario enviándole los textos de asistencia correspondientes.
        </p>
        ${selectMarkup}
    `;

    const workflowResult = await CartMakerModal.form({
        title: 'Rechazar Reporte de Pago',
        html: modalTemplateHTML,
        confirmText: 'Confirmar Rechazo',
        preConfirm: () => {
            const selectElement = document.getElementById('modal-rejection-selector');
            return selectElement ? selectElement.value : null;
        }
    });

    // Si el operador confirma la acción y se captura el ID del Enum, despachamos el POST
    if (workflowResult.isConfirmed && workflowResult.value) {
        executePaymentResolution(type, id, 2, workflowResult.value);
    }
}