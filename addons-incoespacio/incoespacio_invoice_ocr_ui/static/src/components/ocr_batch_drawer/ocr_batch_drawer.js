/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class OcrBatchDrawer extends Component {
    static template = "incoespacio_invoice_ocr.OcrBatchDrawer";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.busService = this.env.services.bus_service;
        this.notification = useService("notification");
        this.fileInputRef = useRef("fileInput");
        this.pollTimer = null;

        this.state = useState({
            visible: false,
            minimized: false,
            items: [],
        });

        onWillStart(async () => {
            await this.checkActiveBatch();
        });

        onWillUnmount(() => {
            if (this.pollTimer) {
                clearInterval(this.pollTimer);
            }
        });

        // Escuchar eventos en vivo desde el servidor mediante WebSockets (ambos tipos de notificación)
        if (this.busService) {
            this.busService.subscribe("incoespacio_ocr_batch_event", this.onOcrEvent.bind(this));
            this.busService.subscribe("ocr_batch_status", this.onOcrEvent.bind(this));
        }

        // Escuchar creación inmediata desde el popup wizard
        if (this.env.bus) {
            this.env.bus.addEventListener(
                "INCOESPACIO_OCR_BATCH_CREATED",
                ({ detail }) => this.onBatchCreated(detail)
            );
        }

        // Polling ligero de respaldo (aquí no hay websocket gevent): solo dispara
        // consultas cuando el drawer está visible y aún queda trabajo por procesar
        this.pollTimer = setInterval(() => this.pollActiveItems(), 4000);
    }

    onBatchCreated(createdMoves) {
        if (!createdMoves || !Array.isArray(createdMoves)) {
            return;
        }

        // Si se inicia una nueva subida, limpiar el estado de descartado de la sesión
        sessionStorage.removeItem("incoespacio_ocr_dismissed_ids");

        for (const m of createdMoves) {
            if (!this.state.items.find((i) => i.id === m.id)) {
                this.state.items.push({
                    id: m.id,
                    filename: m.filename || "factura.pdf",
                    status: "processing",
                    partner_name: "",
                    total: 0,
                    ref: "",
                    move_name: m.name || "",
                    error: "",
                });
            }
        }
        this.state.visible = true;
        this.state.minimized = false;
    }

    mapServerItem(s) {
        return {
            id: s.id,
            filename: s.filename || "factura.pdf",
            status: s.status === "error" ? "failed" : s.status || "pending",
            partner_name: s.partner || "",
            total: s.amount_total || 0,
            ref: s.ref || "",
            move_name: s.name || "",
            error: s.error || "",
            mismatch_details: s.mismatch_details || "",
            is_duplicate: s.is_duplicate || false,
            iban_status: s.iban_status || "none",
        };
    }

    async checkActiveBatch() {
        try {
            const activeItems = await this.orm.call("account.move", "get_active_ocr_batch", []);
            const dismissedRaw = sessionStorage.getItem("incoespacio_ocr_dismissed_ids");
            const dismissedIds = dismissedRaw ? JSON.parse(dismissedRaw) : [];

            // Estilo Google Drive: el lote (activos Y terminados recientes) sobrevive a F5
            // y solo desaparece cuando el usuario pulsa la X (descartados en sessionStorage)
            const items = (activeItems || [])
                .filter((i) => !dismissedIds.includes(i.id))
                .map((i) => this.mapServerItem(i));

            if (items.length === 0) {
                this.state.visible = false;
                return;
            }

            this.state.items = items;
            this.state.visible = true;
            // Si ya terminó todo durante la recarga, arrancar colapsado en la píldora
            this.state.minimized = this.isComplete;
        } catch (e) {
            console.warn("No se pudo comprobar la cola activa de OCR:", e);
        }
    }

    async pollActiveItems() {
        if (!this.state.visible || this.isComplete) {
            return;
        }
        try {
            const ids = this.state.items.map((i) => i.id);
            const serverItems = await this.orm.call("account.move", "get_active_ocr_batch", [ids]);
            for (const s of serverItems || []) {
                const item = this.state.items.find((i) => i.id === s.id);
                if (!item) {
                    continue;
                }
                const fresh = this.mapServerItem(s);
                item.status = fresh.status;
                item.filename = fresh.filename || item.filename;
                item.partner_name = fresh.partner_name || item.partner_name;
                item.total = fresh.total || item.total;
                item.move_name = fresh.move_name || item.move_name;
                item.error = fresh.error || item.error;
                item.mismatch_details = fresh.mismatch_details || item.mismatch_details;
                item.is_duplicate = fresh.is_duplicate || item.is_duplicate;
            }
            if (this.isComplete) {
                this.state.minimized = true;
            }
        } catch (e) {
            // Silencioso: el próximo tick reintenta
        }
    }

    onOcrEvent(payload) {
        if (!payload) return;
        const moveId = payload.move_id || payload.id;
        if (!moveId) return;

        const rawEvent = payload.event || payload.status; // 'started', 'processing', 'done', 'failed', 'error', 'mismatch'
        const isDone = rawEvent === "done";
        const isMismatch = rawEvent === "mismatch" || payload.mismatch;
        const isFailed = (rawEvent === "failed" || rawEvent === "error") && !isMismatch;
        const isProcessing = rawEvent === "started" || rawEvent === "processing";

        let item = this.state.items.find((i) => i.id === moveId);

        if (!item) {
            item = {
                id: moveId,
                filename: payload.filename || "factura.pdf",
                status: isProcessing ? "processing" : (isDone ? "done" : (isMismatch ? "mismatch" : "failed")),
                partner_name: payload.partner_name || payload.partner || "",
                total: payload.total || payload.amount_total || 0,
                ref: payload.ref || "",
                move_name: payload.move_name || "",
                error: payload.error || "",
                mismatch_details: payload.mismatch_details || "",
                is_duplicate: payload.is_duplicate || false,
                iban_status: payload.iban_status || "none",
            };
            this.state.items.push(item);
        } else {
            if (isProcessing) {
                item.status = "processing";
            } else if (isDone) {
                item.status = "done";
                item.partner_name = payload.partner_name || payload.partner || item.partner_name;
                item.total = payload.total || payload.amount_total || item.total;
                item.ref = payload.ref || item.ref;
                item.move_name = payload.move_name || item.move_name;
                item.is_duplicate = payload.is_duplicate || false;
                item.iban_status = payload.iban_status || item.iban_status || "none";
            } else if (isMismatch) {
                item.status = "mismatch";
                item.mismatch_details = payload.mismatch_details || "Discrepancia de empresa";
            } else if (isFailed) {
                item.status = "failed";
                item.error = payload.error || "Error en la extracción";
            }
        }

        // Si llega un nuevo evento y no estaba descartado, asegurar visibilidad
        const dismissedRaw = sessionStorage.getItem("incoespacio_ocr_dismissed_ids");
        const dismissedIds = dismissedRaw ? JSON.parse(dismissedRaw) : [];
        if (!dismissedIds.includes(moveId)) {
            this.state.visible = true;
        }

        // Si se han completado todas las facturas del lote, colapsar a la píldora
        if (this.isComplete) {
            this.state.minimized = true;
        }
    }

    close() {
        this.state.visible = false;
        // Guardar los IDs descartados en la sesión para que NUNCA reaparezcan en un F5
        const ids = this.state.items.map((i) => i.id);
        sessionStorage.setItem("incoespacio_ocr_dismissed_ids", JSON.stringify(ids));
    }

    get totalCount() {
        return this.state.items.length;
    }

    get doneCount() {
        return this.state.items.filter((i) => i.status === "done").length;
    }

    get isComplete() {
        return (
            this.totalCount > 0 &&
            this.state.items.every((i) => i.status === "done" || i.status === "failed" || i.status === "mismatch")
        );
    }

    get progressPercent() {
        if (this.totalCount === 0) {
            return 0;
        }
        const completed = this.state.items.filter(
            (i) => i.status === "done" || i.status === "failed" || i.status === "mismatch"
        ).length;
        return Math.round((completed / this.totalCount) * 100);
    }

    toggleMinimize() {
        this.state.minimized = !this.state.minimized;
    }

    openInvoice(moveId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: moveId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    triggerFileInput() {
        if (this.fileInputRef.el) {
            this.fileInputRef.el.click();
        }
    }

    async onFilesSelected(ev) {
        const fileList = ev.target.files;
        if (!fileList || fileList.length === 0) {
            return;
        }

        sessionStorage.removeItem("incoespacio_ocr_dismissed_ids");

        const MAX_FILE_SIZE = 25 * 1024 * 1024;
        const filesData = [];
        for (let i = 0; i < fileList.length; i++) {
            const file = fileList[i];
            if (file.size > MAX_FILE_SIZE) {
                this.notification.add(`El archivo ${file.name} supera el tamaño máximo permitido de 25 MB y ha sido omitido.`, {
                    type: "danger",
                });
                continue;
            }
            const base64Data = await this.readFileAsBase64(file);
            filesData.push({
                name: file.name,
                data: base64Data,
                mimetype: file.type || "application/pdf",
            });
        }

        ev.target.value = "";

        try {
            const createdMoves = await this.orm.call(
                "account.move",
                "upload_bills_batch",
                [filesData],
                { context: this.env.searchModel ? this.env.searchModel.context : {} }
            );

            if (createdMoves && createdMoves.length > 0) {
                for (const m of createdMoves) {
                    if (!this.state.items.find((i) => i.id === m.id)) {
                        this.state.items.push(m);
                    }
                }
                this.state.visible = true;
                this.state.minimized = false;
            }
        } catch (error) {
            this.notification.add("Error al añadir facturas a la cola de procesamiento", {
                type: "danger",
            });
            console.error(error);
        }
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

    formatCurrency(amount) {
        try {
            return (Number(amount) || 0).toLocaleString("es-ES", {
                style: "currency",
                currency: "EUR",
            });
        } catch {
            return `${amount} €`;
        }
    }
}

registry.category("main_components").add("OcrBatchDrawer", { Component: OcrBatchDrawer });
