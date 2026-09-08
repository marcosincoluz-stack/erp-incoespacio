/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { collectFiles } from "./ocr_upload_utils";

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
        this.state.files.push(...(await collectFiles(fileList, this.notification)));
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
        this.state.files.push(...(await collectFiles(fileList, this.notification)));
    }

    removeFile(index) {
        this.state.files.splice(index, 1);
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
