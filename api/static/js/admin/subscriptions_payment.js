document.addEventListener('DOMContentLoaded', function() {
    const statusField = document.querySelector('#id_status');
    const rejectionReasonInput = document.querySelector('#id_rejection_reason');

    // 💡 1. Buscamos el contenedor PADRE real de Rejection Reason
    let rejectionReasonRow = null;
    if (rejectionReasonInput) {
        // Navegamos hacia arriba hasta encontrar el form-row principal
        rejectionReasonRow = rejectionReasonInput.closest('.field-row') || rejectionReasonInput.closest('.form-row');
    }

    // 💡 2. Buscamos la fila de Rejection Help buscando su <label> (A prueba de balas)
    let rejectionHelpRow = null;
    let readonlyDiv = null;

    const labels = document.querySelectorAll('label');
    labels.forEach(label => {
        // Comparamos el texto ignorando mayúsculas y espacios
        if (label.textContent.trim().toLowerCase() === 'rejection help') {
            rejectionHelpRow = label.closest('.field-row') || label.closest('.form-row');
            if (rejectionHelpRow) {
                readonlyDiv = rejectionHelpRow.querySelector('.readonly');
            }
        }
    });

    const helpTexts = {
        '1': 'El número de referencia ingresado no coincide con nuestros registros bancarios. Por favor, verifique los dígitos y vuelva a intentarlo.',
        '2': 'La fecha indicada en el formulario no coincide con la del comprobante. Por favor, seleccione la fecha exacta en la que realizó la operación.',
        '3': 'La imagen adjunta no es legible, está borrosa o no corresponde a un comprobante válido. Suba una captura de pantalla clara donde se vean todos los datos de la operación.',
        '4': 'Su pago ha sido rechazado por un motivo no listado. Por favor, póngase en contacto con soporte técnico para más detalles.',
        '5': 'Su pago ha sido abonado a su cuenta. Por favor, realice el reporte de pago del monto restante para continuar con la activación de su suscripción.'
    };

    function updateHelpText() {
        if (rejectionReasonInput && readonlyDiv) {
            const selectedValue = rejectionReasonInput.value;

            if (selectedValue && helpTexts[selectedValue]) {
                readonlyDiv.textContent = helpTexts[selectedValue];
                readonlyDiv.style.color = '#dedede';
                readonlyDiv.style.fontWeight = 'bold';
            } else {
                readonlyDiv.textContent = '-'; 
                readonlyDiv.style.color = '';
                readonlyDiv.style.fontWeight = 'normal';
            }
        }
    }

    function toggleRejectionReason() {
        if (statusField) {
            if (statusField.value === '2') { // 2 = REJECTED
                if (rejectionReasonRow) rejectionReasonRow.style.display = ''; 
                if (rejectionHelpRow) rejectionHelpRow.style.display = ''; 
                
                if (rejectionReasonRow) {
                    rejectionReasonRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            } else {
                if (rejectionReasonRow) rejectionReasonRow.style.display = 'none';
                if (rejectionHelpRow) rejectionHelpRow.style.display = 'none';
                
                if (rejectionReasonInput) {
                    rejectionReasonInput.value = '';
                    updateHelpText(); 
                }
            }
        }
    }

    // 💡 Listeners
    if (statusField) {
        toggleRejectionReason(); 
        statusField.addEventListener('change', toggleRejectionReason);
    }

    if (rejectionReasonInput) {
        updateHelpText();
        rejectionReasonInput.addEventListener('change', updateHelpText);
    }
});