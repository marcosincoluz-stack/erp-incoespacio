odoo.define('incoluz_invoice_ai_ocr.drawer', function (require) {
"use strict";

const { Component, useState, onWillStart, onWillUnmount } = owl;
const rpc = require('web.rpc');
const WebClient = require('web.WebClient');

class OcrBatchDrawer extends Component {
    constructor(parent, props) {
        super(parent, props);
        this.state = useState({ visible: false, minimized: false, items: [] });
        this.pollTimer = null;
        onWillStart(() => this.checkActiveBatch());
        onWillUnmount(() => {
            if (this.pollTimer) {
                clearInterval(this.pollTimer);
            }
        });
    }

    mounted() {
        // Polling ligero: solo consulta cuando el drawer está visible y queda trabajo
        this.pollTimer = setInterval(() => this.pollActiveItems(), 4000);
    }

    async checkActiveBatch() {
        try {
            const items = await rpc.query({
                model: 'account.move', method: 'get_active_ocr_batch', args: [],
            });
            if (!items || !items.length) {
                this.state.visible = false;
                return;
            }
            this.state.items = items;
            this.state.visible = true;
            this.state.minimized = this.isComplete;
        } catch (e) {
            // Silencioso: el polling reintenta
        }
    }

    async pollActiveItems() {
        if (!this.state.visible || this.isComplete || !this.state.items.length) {
            return;
        }
        try {
            const ids = this.state.items.map(i => i.id);
            const fresh = await rpc.query({
                model: 'account.move', method: 'get_active_ocr_batch', args: [ids],
            });
            for (const s of fresh || []) {
                const item = this.state.items.find(i => i.id === s.id);
                if (!item) {
                    continue;
                }
                item.status = s.status;
                item.filename = s.filename || item.filename;
                item.partner = s.partner || item.partner;
                item.amount_total = s.amount_total || item.amount_total;
                item.name = s.name || item.name;
                item.ref = s.ref || item.ref;
                item.error = s.error || item.error;
                item.mismatch_details = s.mismatch_details || item.mismatch_details;
                item.is_duplicate = s.is_duplicate || item.is_duplicate;
            }
            if (this.isComplete) {
                this.state.minimized = true;
            }
        } catch (e) {
            // Silencioso: el próximo tick reintenta
        }
    }

    get totalCount() {
        return this.state.items.length;
    }

    get doneCount() {
        return this.state.items.filter(i => i.status === 'done').length;
    }

    get isComplete() {
        return this.totalCount > 0 && this.state.items.every(
            i => ['done', 'failed', 'mismatch'].includes(i.status));
    }

    get progressPercent() {
        if (!this.totalCount) {
            return 0;
        }
        const completed = this.state.items.filter(
            i => ['done', 'failed', 'mismatch'].includes(i.status)).length;
        return Math.round((completed / this.totalCount) * 100);
    }

    toggleMinimize() {
        this.state.minimized = !this.state.minimized;
    }

    close() {
        this.state.visible = false;
    }

    openInvoice(moveId) {
        window.open('/web#id=' + moveId + '&model=account.move&view_type=form', '_blank');
    }

    formatCurrency(amount) {
        try {
            return (Number(amount) || 0).toLocaleString('es-ES', { style: 'currency', currency: 'EUR' });
        } catch (e) {
            return amount + ' €';
        }
    }
}

OcrBatchDrawer.template = 'incoluz_invoice_ai_ocr.OcrBatchDrawer';

WebClient.include({
    show_application: function () {
        const result = this._super.apply(this, arguments);
        const drawer = new OcrBatchDrawer(null, {});
        drawer.mount(document.body);
        return result;
    },
});

return OcrBatchDrawer;
});
