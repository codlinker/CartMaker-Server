/**
 * CartMaker Payments Dashboard - Core de Conciliación Bancaria y Facturación SENIAT
 * Maneja la validación asíncrona, previsualización de comprobantes, filtros y emisión de facturas.
 */

"use strict";

/**
 * Conmutador de vistas principales de tablas de control (Decks)
 */
function changeDeck(tabButton) {
    const selectedDeckId = tabButton.getAttribute('data-target');

    document.querySelectorAll('.deck-view').forEach(deck => {
        deck.classList.remove('active');
    });
    document.querySelectorAll('.matrix-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    const targetDeck = document.getElementById(selectedDeckId);
    if (targetDeck) {
        targetDeck.classList.add('active');
    }
    tabButton.classList.add('active');
    filterPaymentsTable();
}

/**
 * Copia el número de referencia bancaria al portapapeles en 1 toque
 */
async function copyReference(refText, btnEl) {
    try {
        await navigator.clipboard.writeText(refText);
        if (btnEl) {
            const icon = btnEl.querySelector('.material-symbols-rounded');
            const orig = icon ? icon.textContent : 'content_copy';
            if (icon) icon.textContent = 'check';
            btnEl.style.color = '#10B981';
            setTimeout(() => {
                if (icon) icon.textContent = orig;
                btnEl.style.color = '';
            }, 1400);
        }
    } catch (e) {
        console.warn('No se pudo copiar automáticamente:', e);
    }
}

/**
 * Filtra en tiempo real las filas del deck activo por texto (referencia, email, nombre, factura)
 */
function filterPaymentsTable() {
    const searchInput = document.getElementById('paymentsSearchInput');
    const query = (searchInput ? searchInput.value : '').trim().toLowerCase();

    const activeDeck = document.querySelector('.deck-view.active');
    if (!activeDeck) return;

    const activeHistBtn = activeDeck.querySelector('.hist-filter-btn.active');
    const statusFilter = activeHistBtn ? activeHistBtn.getAttribute('data-status') : 'all';

    activeDeck.querySelectorAll('.searchable-payment-row').forEach(row => {
        const textMatch = !query || row.textContent.toLowerCase().includes(query);
        const rowStatus = row.getAttribute('data-status');
        const statusMatch = !rowStatus || statusFilter === 'all' || rowStatus === statusFilter;
        row.style.display = (textMatch && statusMatch) ? '' : 'none';
    });
}

/**
 * Filtra la tabla de historial por estado (Todos / Aprobados / Rechazados)
 */
function setHistoryFilter(btn, deckType) {
    const parent = btn.closest('.history-filter-pills');
    if (parent) {
        parent.querySelectorAll('.hist-filter-btn').forEach(b => b.classList.remove('active'));
    }
    btn.classList.add('active');
    filterPaymentsTable();
}

/**
 * Previsualización de la captura de pantalla del pago reportado
 */
function displayProofModal(proofUrl, referenceNumber, amountBs = '', equivUsd = '') {
    const metaSubtitle = amountBs
        ? `<div style="margin-bottom:12px;font-size:0.88rem;color:#475569;">
               Monto reportado: <strong>${amountBs}</strong> ${equivUsd ? `(≈ <strong>${equivUsd}</strong>)` : ''}
               · <a href="${proofUrl}" target="_blank" rel="noopener" style="color:#6D49F2;font-weight:700;text-decoration:underline;">Abrir imagen original ↗</a>
           </div>`
        : '';

    Swal.fire({
        ...CartMakerModal.baseConfig,
        title: `Comprobante Ref: #${referenceNumber}`,
        html: metaSubtitle,
        imageUrl: proofUrl,
        imageAlt: 'Captura de pantalla de la transacción del cliente',
        confirmButtonText: 'Cerrar Vista'
    });
}

/**
 * Canaliza la resolución de estado del pago hacia Django y refresca el tablero
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
            await refreshActiveDeck();

            if (data.auto_credited_wallet) {
                await CartMakerModal.warning('Abono Parcial Acreditado a Billetera', data.message);
            } else if (data.invoice_url && data.invoice_number) {
                const docLabel = data.document_label || 'Comprobante Digital';
                await CartMakerModal.success('¡Pago Conciliado con Éxito!', '', {
                    html: `
                        <p style="font-size:0.94rem;color:#4B4660;line-height:1.55;margin-bottom:16px;">
                            ${data.message}
                        </p>
                        <div style="display:flex;justify-content:center;gap:10px;flex-wrap:wrap;">
                            <a href="${data.invoice_url}" target="_blank" rel="noopener"
                               style="display:inline-flex;align-items:center;gap:6px;padding:10px 16px;border-radius:11px;background:rgba(109,73,242,0.10);border:1px solid rgba(109,73,242,0.28);color:#6D49F2;font-weight:800;font-size:0.86rem;text-decoration:none;">
                                <span class="material-symbols-rounded" style="font-size:18px;">receipt_long</span>
                                Ver ${docLabel} ${data.invoice_number}
                            </a>
                            <a href="${data.invoice_url}&print=1" target="_blank" rel="noopener"
                               style="display:inline-flex;align-items:center;gap:6px;padding:10px 16px;border-radius:11px;background:#F1F5F9;border:1px solid #E2E8F0;color:#0F172A;font-weight:700;font-size:0.86rem;text-decoration:none;">
                                <span class="material-symbols-rounded" style="font-size:18px;">print</span>
                                Imprimir / PDF
                            </a>
                        </div>
                    `
                });
            } else {
                await CartMakerModal.success('Operación Completada', data.message);
            }
        } else {
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
    const activeTab = document.querySelector('.matrix-tab-btn.active');
    if (!activeTab) return;

    const targetDeckId = activeTab.getAttribute('data-target');
    const deckType = targetDeckId === 'merchant-deck' ? 'merchant' : 'atlas';
    const deckContainer = document.getElementById(targetDeckId);
    const syncIcon = document.getElementById('syncDeckIcon');

    if (deckContainer) {
        deckContainer.style.opacity = '0.55';
        deckContainer.style.pointerEvents = 'none';
    }
    if (syncIcon) {
        syncIcon.classList.add('spin-sync');
    }

    try {
        const response = await fetch(`${ENDPOINT_URI}?deck=${deckType}`, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        const data = await response.json();

        if (data.success && data.html && deckContainer) {
            deckContainer.innerHTML = data.html;

            const badge = document.getElementById(`badge-${deckType}`);
            if (badge) {
                badge.textContent = data.pending_count;
            }

            const atlasBadge = parseInt((document.getElementById('badge-atlas') || {}).textContent || '0', 10) || 0;
            const merchantBadge = parseInt((document.getElementById('badge-merchant') || {}).textContent || '0', 10) || 0;
            const kpiPending = document.getElementById('kpi-total-pending');
            if (kpiPending) {
                kpiPending.textContent = atlasBadge + merchantBadge;
            }

            filterPaymentsTable();
        }
    } catch (error) {
        CartMakerModal.error('Fallo de Sincronización', 'No se pudieron obtener los últimos pagos del servidor.');
    } finally {
        if (deckContainer) {
            deckContainer.style.opacity = '1';
            deckContainer.style.pointerEvents = 'auto';
        }
        if (syncIcon) {
            syncIcon.classList.remove('spin-sync');
        }
    }
}

/**
 * Despliega el modal de confirmación antes de aprobar un pago, mostrando resumen de montos
 */
async function triggerApprovalWorkflow(type, id, refNumber = '', amountBs = '', equivUsd = '', coversPlan = true) {
    let detailHtml = `
        <div style="text-align:left;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:14px;padding:14px 16px;margin-top:10px;font-size:0.88rem;color:#334155;">
            <div style="margin-bottom:6px;"><strong>Referencia Bancaria:</strong> <span style="font-family:monospace;">#${refNumber || id}</span></div>
            <div style="margin-bottom:6px;"><strong>Monto Reportado:</strong> ${amountBs} ${equivUsd ? `(≈ <strong>${equivUsd}</strong>)` : ''}</div>
            ${
                coversPlan
                    ? `<div style="color:#047857;font-weight:700;margin-top:8px;">✓ El monto cubre el plan. Se activará la suscripción y se emitirá el Comprobante Digital / Documento Fiscal correspondiente.</div>`
                    : `<div style="color:#B45309;font-weight:700;margin-top:8px;">⚠ El monto es parcial respecto al plan. El sistema acreditará automáticamente ${equivUsd} a la Billetera CartMaker del usuario.</div>`
            }
        </div>
    `;

    const result = await Swal.fire({
        ...CartMakerModal.baseConfig,
        icon: coversPlan ? 'question' : 'warning',
        iconColor: coversPlan ? '#10B981' : '#F59E0B',
        title: coversPlan ? '¿Validar y Aprobar Pago?' : '¿Procesar Abono Parcial?',
        html: detailHtml,
        showCancelButton: true,
        confirmButtonText: coversPlan ? 'Sí, Validar y Emitir' : 'Acreditar a Billetera',
        cancelButtonText: 'Cancelar',
        reverseButtons: true
    });

    if (result.isConfirmed) {
        executePaymentResolution(type, id, 1);
    }
}

/**
 * Despliega el formulario Swal parametrizado con los motivos de rechazo reales del backend
 */
async function triggerRejectionWorkflow(type, id, refNumber = '') {
    const rawOptions = JSON.parse(document.getElementById('rejection-reasons-source').textContent);

    let selectMarkup = `<select id="modal-rejection-selector" class="cm-rejection-select">`;
    rawOptions.forEach(opt => {
        selectMarkup += `<option value="${opt.id}">${opt.label}</option>`;
    });
    selectMarkup += `</select>`;

    const modalTemplateHTML = `
        <p style="text-align: left; font-size: 0.9rem; color: #475569; line-height: 1.55;">
            Indica la inconsistencia detectada en la referencia <strong>#${refNumber || id}</strong>. Esta acción rechazará la solicitud y notificará automáticamente al usuario.
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

    if (workflowResult.isConfirmed && workflowResult.value) {
        executePaymentResolution(type, id, 2, workflowResult.value);
    }
}