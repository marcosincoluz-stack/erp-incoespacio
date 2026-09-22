/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { formatMonetary } from "@web/views/fields/formatters";
import { SectionAndNoteListRenderer } from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";

export function lineAmount(data) {
    if (!data || data.display_type) {
        return 0;
    }
    if ("price_subtotal" in data) {
        return Number(data.price_subtotal) || 0;
    }
    if ("amount_origin" in data) {
        return Number(data.amount_origin) || 0;
    }
    return (
        (Number(data.price_unit) || 0) *
        (Number(data.product_uom_qty) || Number(data.quantity) || 0)
    );
}

export function sectionLevel(data) {
    const lv = data?.bc3_level;
    return lv === false || lv === undefined || lv === null ? 0 : Number(lv) || 0;
}

function sectionWalkEnd(rec, parentLevel) {
    const dt = rec.data?.display_type;
    const lv = sectionLevel(rec.data);
    if (dt === "line_section") {
        return lv <= parentLevel;
    }
    // ponytail: 0/0 = pedido plano; la hermana del subcapítulo solo existe con bc3_level
    return lv <= parentLevel && (parentLevel > 0 || lv > 0);
}

export function sectionChildRecords(records, sectionIndex) {
    const level = sectionLevel(records[sectionIndex].data);
    const children = [];
    for (let i = sectionIndex + 1; i < records.length; i++) {
        if (sectionWalkEnd(records[i], level)) {
            break;
        }
        children.push(records[i]);
    }
    return children;
}

export function sectionTotal(records, sectionIndex) {
    return sectionChildRecords(records, sectionIndex).reduce(
        (sum, rec) => sum + lineAmount(rec.data || rec),
        0
    );
}

export function foldedHiddenIds(records, folded, searchActive) {
    if (searchActive) {
        return new Set();
    }
    const hidden = new Set();
    for (let i = 0; i < records.length; i++) {
        const rec = records[i];
        if (rec.data?.display_type !== "line_section" || !folded[rec.id]) {
            continue;
        }
        for (const child of sectionChildRecords(records, i)) {
            hidden.add(child.id);
        }
    }
    return hidden;
}

patch(SectionAndNoteListRenderer.prototype, {
    setup() {
        super.setup();
        this.sectionFold = useState({ folded: {} });
    },
    _foldSearchActive() {
        return Boolean(
            this.tableRef?.el
                ?.closest(".o_field_x2many")
                ?.querySelector(".o_certification_line_search input")
                ?.value?.trim()
        );
    },
    _foldedHiddenIds() {
        return foldedHiddenIds(
            this.props.list.records,
            this.sectionFold.folded,
            this._foldSearchActive()
        );
    },
    _sectionTotal(record) {
        const records = this.props.list.records;
        return sectionTotal(records, records.indexOf(record));
    },
    _toggleSection(record) {
        this.sectionFold.folded[record.id] = !this.sectionFold.folded[record.id];
    },
    getRowClass(record) {
        let cls = super.getRowClass(record);
        if (record.data.display_type === "line_section" && this.sectionFold.folded[record.id]) {
            cls += " o_section_folded";
        }
        if (this._foldedHiddenIds().has(record.id)) {
            cls += " o_section_folded_hidden";
        }
        const lv = sectionLevel(record.data);
        if (lv > 0) {
            cls += " o_bc3_level_" + Math.min(lv, 6);
        }
        return cls;
    },
    getColumns(record) {
        const columns = super.getColumns(record);
        if (record.data.display_type !== "line_section") {
            return columns;
        }
        return columns
            .map((col) =>
                col.name === this.titleField && col.colspan
                    ? { ...col, colspan: Math.max(1, col.colspan - 1) }
                    : col
            )
            .concat({
                id: "section_total",
                type: "field",
                name: "display_type",
            });
    },
    // Fake total has no field descriptor; Field() would throw in fieldVisualFeedback.
    canUseFormatter(column, record) {
        if (column.id === "section_total") {
            return true;
        }
        return super.canUseFormatter(column, record);
    },
    getCellClass(column, record) {
        if (column.id === "section_total") {
            return "o_data_cell o_section_fold_total text-end";
        }
        return super.getCellClass(column, record);
    },
    getFormattedValue(column, record) {
        if (column.id === "section_total") {
            const currency = record.data.currency_id;
            const currencyId = Array.isArray(currency) ? currency[0] : currency;
            return formatMonetary(this._sectionTotal(record), { currencyId });
        }
        return super.getFormattedValue(column, record);
    },
    onCellClicked(record, column, ev) {
        if (
            record.data.display_type === "line_section" &&
            !record.isInEdition &&
            column.widget !== "handle" &&
            !ev.target.closest(".o_row_handle")
        ) {
            ev.stopPropagation();
            this._toggleSection(record);
            return;
        }
        return super.onCellClicked(record, column, ev);
    },
});
