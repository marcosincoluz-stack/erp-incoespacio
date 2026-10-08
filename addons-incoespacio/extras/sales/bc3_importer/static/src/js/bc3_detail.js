/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";

const MEASURE_NUMS = ["units", "length", "width", "height"];

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

export function bc3MeasureNum(raw) {
    if (raw === null || raw === undefined || raw === false || raw === "") {
        return null;
    }
    const num = Number(String(raw).replace(",", "."));
    return Number.isNaN(num) ? null : num;
}

export function bc3MeasurePartial(row) {
    const nums = MEASURE_NUMS.map((key) => bc3MeasureNum(row?.[key])).filter((num) => num !== null);
    if (!nums.length) {
        return null;
    }
    return nums.reduce((product, num) => product * num, 1);
}

// null = no numbered row, caller must leave product_uom_qty alone
export function bc3MeasuresQty(rows) {
    const parcials = (rows || []).map(bc3MeasurePartial).filter((num) => num !== null);
    if (!parcials.length) {
        return null;
    }
    return parcials.reduce((sum, num) => sum + num, 0);
}

export function bc3EditorRows(data) {
    const stored = bc3Measures(data);
    if (stored.length) {
        return stored;
    }
    const qty = bc3MeasureNum(data?.product_uom_qty);
    if (qty) {
        return [{ comment: "", units: qty, length: null, width: null, height: null, partial: qty }];
    }
    return [{ comment: "", units: null, length: null, width: null, height: null, partial: null }];
}

export function bc3RowsToSave(rows) {
    const measures = (rows || []).map(bc3NormalizeRow);
    const filled = measures.filter((row) => row.comment || bc3MeasurePartial(row) !== null);
    const blank = measures.find((row) => !row.comment && bc3MeasurePartial(row) === null);
    return filled.length && blank ? filled.concat([blank]) : filled;
}

export function bc3MeasureLabel(value) {
    const num = bc3MeasureNum(value);
    return num === null ? "" : String(num);
}

function bc3NormalizeRow(row) {
    const partial = bc3MeasurePartial(row);
    return {
        comment: row?.comment || "",
        units: bc3MeasureNum(row?.units),
        length: bc3MeasureNum(row?.length),
        width: bc3MeasureNum(row?.width),
        height: bc3MeasureNum(row?.height),
        partial: partial === null ? 0 : partial,
    };
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.bc3Detail = useState({ open: {} });
    },
    bc3Measures(record) {
        return bc3Measures(record.data);
    },
    bc3EditorRows(record) {
        return bc3EditorRows(record.data);
    },
    bc3MeasureLabel(value) {
        return bc3MeasureLabel(value);
    },
    bc3DetailOpen(record) {
        return Boolean(this.bc3Detail?.open[record.id]);
    },
    _bc3Order(record) {
        const parent = record._parentRecord || record.model?.root || this.props.list?._parent;
        const flag = parent?.data?.bc3 ?? parent?.evalContext?.bc3;
        return Boolean(flag);
    },
    bc3ShowChevron(record) {
        const data = record.data;
        const hasField = data && ("bc3_text" in data || this.props.list?.activeFields?.bc3_text);
        if (!data || data.display_type || !hasField) {
            return false;
        }
        if (bc3HasDetail(data)) {
            return true;
        }
        return Boolean(this.props.editable && this._bc3Order(record));
    },
    bc3DetailEmpty(record) {
        return !bc3HasDetail(record.data);
    },
    _bc3ChevronHit(record, column, ev) {
        if (!column || column.name !== "name" || !this.bc3ShowChevron(record)) {
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
    async _bc3Save(record, text, rows) {
        const measures = bc3RowsToSave(rows);
        const vals = {
            bc3_text: text && String(text).trim() ? text : false,
            bc3_measures: measures.length ? measures : false,
        };
        const qty = bc3MeasuresQty(measures);
        if (qty !== null) {
            vals.product_uom_qty = qty;
        }
        await record.update(vals);
    },
    bc3SetText(record, ev) {
        return this._bc3Save(record, ev.target.value, bc3Measures(record.data));
    },
    bc3SetMeasure(record, index, field, ev) {
        const rows = bc3EditorRows(record.data).map((row) => ({ ...row }));
        rows[index] = { ...rows[index], [field]: ev.target.value };
        return this._bc3Save(record, record.data.bc3_text, rows);
    },
    bc3AddMeasure(record) {
        const rows = bc3EditorRows(record.data).map((row) => ({ ...row }));
        rows.push({ comment: "", units: null, length: null, width: null, height: null, partial: null });
        return this._bc3Save(record, record.data.bc3_text, rows);
    },
    bc3RemoveMeasure(record, index) {
        const rows = bc3EditorRows(record.data).filter((_, i) => i !== index);
        return this._bc3Save(record, record.data.bc3_text, rows);
    },
    getRowClass(record) {
        let cls = super.getRowClass(record);
        if (this.bc3ShowChevron(record)) {
            cls += " o_bc3_has_detail";
            if (this.bc3DetailEmpty(record)) {
                cls += " o_bc3_detail_empty";
            }
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
