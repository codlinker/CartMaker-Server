document.addEventListener('DOMContentLoaded', function() {
    const statusField = document.querySelector('#id_status');
    const rejectionReasonRow = document.querySelector('.field-rejection_reason');
    const rejectionReasonInput = document.querySelector('#id_rejection_reason');

    function toggleRejectionReason() {
        if (statusField && rejectionReasonRow) {
            // Valor 2 es REJECTED
            if (statusField.value === '2') {
                // 1. Mostramos el campo
                rejectionReasonRow.style.display = 'block'; 
                
                // 2. Hacemos el scroll suave hasta el final
                // 'behavior: smooth' hace que no sea un salto brusco
                rejectionReasonRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                rejectionReasonRow.style.display = 'none';
                if (rejectionReasonInput) {
                    rejectionReasonInput.value = '';
                }
            }
        }
    }

    if (statusField) {
        // Ejecutar al cargar por si ya viene rechazado
        toggleRejectionReason(); 
        
        statusField.addEventListener('change', toggleRejectionReason);
    }
});