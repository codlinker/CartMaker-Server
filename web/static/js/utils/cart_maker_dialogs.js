/**
 * CartMaker Dialogs - Wrapper modular para SweetAlert2
 * Mantiene la consistencia de UI/UX en toda la plataforma.
 */
class CartMakerModal {
    // Configuración base inyectando las clases CSS de CartMaker
    static get baseConfig() {
        return {
            background: 'rgba(20, 15, 30, 0.95)',
            color: '#ffffff',
            backdrop: 'rgba(0, 0, 0, 0.75)',
            buttonsStyling: false, // Desactivamos estilos por defecto para usar los nuestros
            customClass: {
                popup: 'cm-modal-popup',
                title: 'cm-modal-title',
                htmlContainer: 'cm-modal-text',
                confirmButton: 'btn-save-profile cm-modal-btn', // Reutilizamos tu clase de botón
                cancelButton: 'btn-action close-ticket cm-modal-btn cm-modal-cancel', 
                input: 'custom-select'
            },
            showClass: {
                popup: 'animate__animated animate__fadeInUp animate__faster'
            },
            hideClass: {
                popup: 'animate__animated animate__fadeOutDown animate__faster'
            }
        };
    }

    /**
     * Modal de Éxito genérico
     */
    static success(title, text = '') {
        return Swal.fire({
            ...this.baseConfig,
            icon: 'success',
            title: title,
            text: text,
            iconColor: 'var(--success-green)',
            confirmButtonText: 'Entendido'
        });
    }

    /**
     * Modal de Error genérico
     */
    static error(title, text = '') {
        return Swal.fire({
            ...this.baseConfig,
            icon: 'error',
            title: title,
            text: text,
            iconColor: 'var(--error-red)',
            confirmButtonText: 'Aceptar'
        });
    }

    /**
     * Modal de Confirmación (Retorna un Promise booleano)
     */
    static async confirm(title, text, confirmText = 'Confirmar', cancelText = 'Cancelar') {
        const result = await Swal.fire({
            ...this.baseConfig,
            icon: 'warning',
            title: title,
            text: text,
            iconColor: 'var(--warning-yellow)',
            showCancelButton: true,
            confirmButtonText: confirmText,
            cancelButtonText: cancelText,
            reverseButtons: true // Coloca el botón principal a la derecha
        });
        return result.isConfirmed;
    }

    /**
     * Modal de Formulario Personalizado (Retorna la data del form)
     */
    static async form({ title, html, confirmText = 'Guardar', preConfirm }) {
        const result = await Swal.fire({
            ...this.baseConfig,
            title: title,
            html: html,
            showCancelButton: true,
            confirmButtonText: confirmText,
            cancelButtonText: 'Cancelar',
            reverseButtons: true,
            focusConfirm: false,
            preConfirm: preConfirm // Callback inyectado para validar/extraer datos del DOM
        });
        
        return result; // Retorna { isConfirmed: true, value: ... }
    }
}