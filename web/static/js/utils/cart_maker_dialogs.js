/**
 * CartMaker Dialogs - Wrapper modular para SweetAlert2
 * Mantiene la consistencia de UI/UX del Design System de CartMaker en toda la plataforma.
 */
class CartMakerModal {
    static get baseConfig() {
        return {
            background: '#FFFFFF',
            color: '#0F0B1D',
            backdrop: 'rgba(15, 11, 29, 0.55)',
            buttonsStyling: false,
            customClass: {
                popup: 'cm-modal-popup',
                title: 'cm-modal-title',
                htmlContainer: 'cm-modal-text',
                actions: 'cm-modal-actions',
                confirmButton: 'cm-modal-btn cm-modal-confirm',
                cancelButton: 'cm-modal-btn cm-modal-cancel',
                input: 'cm-modal-select'
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
     * Modal de Éxito genérico (soporta texto o HTML enriquecido como enlaces de Factura Digital)
     */
    static success(title, text = '', options = {}) {
        const config = {
            ...this.baseConfig,
            icon: 'success',
            title: title,
            iconColor: '#10B981',
            confirmButtonText: options.confirmButtonText || 'Entendido',
        };
        if (options.html) {
            config.html = options.html;
        } else {
            config.text = text;
        }
        return Swal.fire(config);
    }

    /**
     * Modal de Advertencia / Información operativa
     */
    static warning(title, text = '') {
        return Swal.fire({
            ...this.baseConfig,
            icon: 'warning',
            title: title,
            text: text,
            iconColor: '#F59E0B',
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
            iconColor: '#EF4444',
            confirmButtonText: 'Aceptar'
        });
    }

    /**
     * Modal de Confirmación (Retorna un Promise booleano)
     */
    static async confirm(title, text, confirmText = 'Confirmar', cancelText = 'Cancelar') {
        const result = await Swal.fire({
            ...this.baseConfig,
            icon: 'question',
            title: title,
            text: text,
            iconColor: '#6D49F2',
            showCancelButton: true,
            confirmButtonText: confirmText,
            cancelButtonText: cancelText,
            reverseButtons: true
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
            preConfirm: preConfirm
        });

        return result;
    }
}