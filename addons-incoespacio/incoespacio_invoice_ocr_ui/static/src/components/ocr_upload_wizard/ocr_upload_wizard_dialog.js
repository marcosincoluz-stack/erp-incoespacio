/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class OcrUploadWizardDialog extends Component {
    static template = "incoespacio_invoice_ocr.OcrUploadWizardDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        initialFiles: { type: Array, optional: true },
        context: { type: Object, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fileInputRef = useRef("fileInput");

        this.state = useState({
            files: [...(this.props.initialFiles || [])],
            isProcessing: false,
            isDragging: false,
        });
    }

    formatFileSize(bytes) {
        if (!bytes || bytes === 0) {
            return "0 B";
        }
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    }

    triggerAddFiles() {
        if (this.fileInputRef.el) {
            this.fileInputRef.el.click();
        }
    }

    async onFilesSelected(ev) {
        const fileList = ev.target.files;
        if (!fileList || fileList.length === 0) {
            return;
        }

        const maxSizeBytes = 25 * 1024 * 1024; // 25 MB
        for (let i = 0; i < fileList.length; i++) {
            const file = fileList[i];
            if (file.size > maxSizeBytes) {
                this.notification.add(
                    _t("El archivo '%s' (%s) supera el límite máximo permitido de 25 MB y ha sido omitido.", file.name, this.formatFileSize(file.size)),
                    { type: "danger" }
                );
                continue;
            }
            const base64Data = await this.readFileAsBase64(file);
            this.state.files.push({
                name: file.name,
                size: file.size,
                mimetype: file.type || "application/pdf",
                data: base64Data,
            });
        }

        // Limpiar input para permitir seleccionar de nuevo
        ev.target.value = "";
    }

    onDragOver(ev) {
        ev.preventDefault();
        this.state.isDragging = true;
    }

    onDragLeave(ev) {
        ev.preventDefault();
        this.state.isDragging = false;
    }

    async onDrop(ev) {
        ev.preventDefault();
        this.state.isDragging = false;
        const fileList = ev.dataTransfer ? ev.dataTransfer.files : null;
        if (!fileList || fileList.length === 0) {
            return;
        }

        const maxSizeBytes = 25 * 1024 * 1024; // 25 MB
        for (let i = 0; i < fileList.length; i++) {
            const file = fileList[i];
            if (file.size > maxSizeBytes) {
                this.notification.add(
                    _t("El archivo '%s' (%s) supera el límite máximo permitido de 25 MB y ha sido omitido.", file.name, this.formatFileSize(file.size)),
                    { type: "danger" }
                );
                continue;
            }
            const base64Data = await this.readFileAsBase64(file);
            this.state.files.push({
                name: file.name,
                size: file.size,
                mimetype: file.type || "application/pdf",
                data: base64Data,
            });
        }
    }

    removeFile(index) {
        this.state.files.splice(index, 1);
    }

    readFileAsBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const result = reader.result;
                const base64 = result.includes(",") ? result.split(",")[1] : result;
                resolve(base64);
            };
            reader.onerror = (error) => reject(error);
            reader.readAsDataURL(file);
        });
    }

    async processFiles() {
        if (this.state.files.length === 0 || this.state.isProcessing) {
            return;
        }

        this.state.isProcessing = true;

        try {
            const filesPayload = this.state.files.map((f) => ({
                name: f.name,
                data: f.data,
                mimetype: f.mimetype,
            }));

            const createdMoves = await this.orm.call(
                "account.move",
                "upload_bills_batch",
                [filesPayload],
                { context: this.props.context || {} }
            );

            // Notificar al drawer inferior para que muestre el progreso de inmediato
            if (this.env.bus && createdMoves) {
                this.env.bus.trigger("INCOESPACIO_OCR_BATCH_CREATED", createdMoves);
            }

            this.notification.add(
                _t("Se han enviado %s factura(s) a la cola de digitalización con IA.", this.state.files.length),
                { type: "success" }
            );

            this.props.close();
        } catch (error) {
            this.state.isProcessing = false;
            this.notification.add(
                _t("Error al enviar las facturas a digitalizar: %s", error.message || error),
                { type: "danger" }
            );
            console.error(error);
        }
    }
}
