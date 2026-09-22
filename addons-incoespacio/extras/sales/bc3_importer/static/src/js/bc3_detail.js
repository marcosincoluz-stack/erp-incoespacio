/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";

export function bc3Measures(data) {
    const raw = data?.bc3_measures;
    if (Array.isArray(raw)) {
        return raw;
    }
    if (typeof raw === "string" && raw) {
        try {
            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed : [];
        } catch {
            return [];
        }
    }
    return [];
}

export function bc3HasDetail(data) {
    if (!data || data.display_type) {
        return false;
    }
    const text = data.bc3_text;
    return Boolean((text && String(text).trim()) || bc3Measures(data).length);
}

export function bc3MeasureLabel(value) {
    if (value === null || value === undefined || value === false || value === "") {
        return "";
    }
    const num = Number(value);
    return Number.isNaN(num) ? "" : String(num);
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.bc3Detail = useState({ open: {} });
    },
    bc3Measures(record) {
        return bc3Measures(record.data);
    },
    bc3HasDetail(record) {
        return bc3HasDetail(record.data);
    },
    bc3MeasureLabel(value) {
        return bc3MeasureLabel(value);
    },
    bc3DetailOpen(record) {
        return Boolean(this.bc3Detail?.open[record.id]);
    },
    _bc3ChevronHit(record, column, ev) {
        if (!column || column.name !== "name" || !this.bc3HasDetail(record)) {
            return false;
        }
        const td = ev.target?.closest?.("td");
        if (!td) {
            return false;
        }
        const pad = parseFloat(getComputedStyle(td).paddingLeft) || 0;
        const x = ev.clientX - td.getBoundingClientRect().left;
        return x >= pad - 2 && x <= pad + 22;
    },
    getRowClass(record) {
        let cls = super.getRowClass(record);
        if (this.bc3HasDetail(record)) {
            cls += " o_bc3_has_detail";
            if (this.bc3Detail.open[record.id]) {
                cls += " o_bc3_detail_open";
            }
        }
        return cls;
    },
    onCellClicked(record, column, ev) {
        if (this._bc3ChevronHit(record, column, ev)) {
            ev.stopPropagation();
            ev.preventDefault();
            this.bc3Detail.open[record.id] = !this.bc3Detail.open[record.id];
            return;
        }
        return super.onCellClicked(record, column, ev);
    },
});
