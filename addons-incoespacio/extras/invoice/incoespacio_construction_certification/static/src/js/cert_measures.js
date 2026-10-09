/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";
import {
    bc3MeasureLabel,
    bc3MeasureNum,
    bc3MeasurePartial,
    bc3Measures,
} from "@bc3_importer/js/bc3_detail";

export function certRowsFrom(data) {
    return bc3Measures(data).map((row) => ({
        comment: row?.comment || "",
        units: row?.units,
        length: row?.length,
        width: row?.width,
        height: row?.height,
        partial: row?.partial,
        qty_period: row?.qty_period || 0,
        manual: Boolean(row?.manual),
    }));
}

export function certRowsToSave(rows) {
    return (rows || []).map((row) => {
        const partial = bc3MeasurePartial(row);
        const manual = Boolean(row?.manual);
        const qty = manual ? partial || 0 : bc3MeasureNum(row?.qty_period) || 0;
        return {
            comment: row?.comment || "",
            units: bc3MeasureNum(row?.units),
            length: bc3MeasureNum(row?.length),
            width: bc3MeasureNum(row?.width),
            height: bc3MeasureNum(row?.height),
            partial: partial === null ? 0 : partial,
            qty_period: qty,
            manual,
        };
    });
}

// Misma regla que ConstructionCertificationLine._measures_period_qty:
// suma solo si alguna fila tiene cantidad; si no, no se toca Med. Periodo.
export function certPeriodSum(rows) {
    let sum = 0;
    let any = false;
    for (const row of rows || []) {
        const qty = bc3MeasureNum(row?.qty_period);
        if (qty) {
            any = true;
            sum += qty;
        }
    }
    return any ? sum : null;
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.certDetail = useState({ open: {} });
    },
    certList() {
        return this.props.list?.resModel === "construction.certification.line";
    },
    bc3ShowChevron(record) {
        if (this.certList()) {
            return false;
        }
        return super.bc3ShowChevron(record);
    },
    certRows(record) {
        return certRowsFrom(record.data);
    },
    certMeasureLabel(value) {
        return bc3MeasureLabel(value);
    },
    certPeriodLabel(value) {
        const num = bc3MeasureNum(value);
        return num ? bc3MeasureLabel(value) : "";
    },
    certShowChevron(record) {
        if (!this.certList() || !record.data || record.data.display_type) {
            return false;
        }
        if (!this.props.list?.activeFields?.bc3_measures) {
            return false;
        }
        return this.certRows(record).length > 0 || Boolean(this.props.editable);
    },
    certDetailOpen(record) {
        return Boolean(this.certDetail?.open[record.id]);
    },
    certHasManual(record) {
        return this.certRows(record).some((row) => row.manual);
    },
    _certChevronHit(record, column, ev) {
        if (!this.certShowChevron(record) || !column || column.name !== "name") {
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
    async _certSave(record, rows) {
        const measures = certRowsToSave(rows);
        const vals = { bc3_measures: measures.length ? measures : false };
        const period = certPeriodSum(measures);
        if (period !== null) {
            vals.qty_period = period;
        }
        await record.update(vals);
    },
    certSetPeriod(record, index, ev) {
        const rows = this.certRows(record).map((row) => ({ ...row }));
        rows[index] = { ...rows[index], qty_period: ev.target.value };
        return this._certSave(record, rows);
    },
    certSetMeasure(record, index, field, ev) {
        const rows = this.certRows(record).map((row) => ({ ...row }));
        rows[index] = { ...rows[index], [field]: ev.target.value };
        return this._certSave(record, rows);
    },
    certAddMeasure(record) {
        if (!this.props.editable || this.certHasManual(record)) {
            return;
        }
        const rows = this.certRows(record).map((row) => ({ ...row }));
        rows.push({
            comment: "",
            units: null,
            length: null,
            width: null,
            height: null,
            partial: null,
            qty_period: 0,
            manual: true,
        });
        return this._certSave(record, rows);
    },
    certRemoveMeasure(record, index) {
        const kept = this.certRows(record).filter((_, i) => i !== index);
        return this._certSave(record, kept);
    },
    getRowClass(record) {
        let cls = super.getRowClass(record);
        if (!this.certShowChevron(record)) {
            return cls;
        }
        cls += " o_bc3_has_detail";
        if (!this.certRows(record).length) {
            cls += " o_bc3_detail_empty";
        }
        if (this.certDetail.open[record.id]) {
            cls += " o_bc3_detail_open";
        }
        return cls;
    },
    onCellClicked(record, column, ev) {
        if (this._certChevronHit(record, column, ev)) {
            ev.stopPropagation();
            ev.preventDefault();
            this.certDetail.open[record.id] = !this.certDetail.open[record.id];
            return;
        }
        return super.onCellClicked(record, column, ev);
    },
});
