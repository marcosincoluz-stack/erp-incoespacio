/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formatFloat, formatMonetary } from "@web/views/fields/formatters";
import { MonetaryField, monetaryField } from "@web/views/fields/monetary/monetary_field";
import {
    SectionAndNoteFieldOne2Many,
    SectionAndNoteListRenderer,
    sectionAndNoteFieldOne2Many,
} from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";
import { patch } from "@web/core/utils/patch";
import { isSectionFoldColumn, sectionChildRecords, sectionFieldTotal, sectionLevel } from "@incoespacio_section_fold/js/section_fold";

export function sectionColumnSums(records, sectionIndex, fieldNames) {
    const children = sectionChildRecords(records, sectionIndex);
    const sums = Object.fromEntries(fieldNames.map((name) => [name, 0]));
    for (const rec of children) {
        const data = rec.data || rec;
        if (data.display_type) {
            continue;
        }
        for (const name of fieldNames) {
            sums[name] += Number(data[name]) || 0;
        }
    }
    return sums;
}

// % de capítulo: importe contra importe. Sumar los % de cada partida mezcla unidades.
export const SECTION_RATIOS = {
    margin_percent_planned: ["amount_margin_planned", "price_subtotal"],
    progress_percent: ["amount_cert_origin", "price_subtotal"],
    margin_percent: ["amount_margin", "amount_cert_origin"],
    margin_percent_forecast: ["amount_margin_forecast", "price_subtotal"],
};

const BAD_UNDER = new Set([
    "amount_margin",
    "margin_percent",
    "amount_margin_planned",
    "margin_percent_planned",
    "amount_margin_forecast",
    "margin_percent_forecast",
]);

export function formatShare(pct) {
    if (pct == null || Number.isNaN(pct)) return "";
    const rounded = Math.round(pct * 10) / 10;
    return (Math.abs(rounded - Math.round(rounded)) < 0.05 ? String(Math.round(rounded)) : rounded.toFixed(1)) + "%";
}

function sharePct(run, total) {
    return !total ? 0 : Math.abs(run - total) <= 0.0001 ? 100 : (run / total) * 100;
}

// ponytail: página cargada; subir el límite de líneas si un presupuesto se corta.
export function cumulativeSalePercent(records) {
    const ordered = records.slice().sort((a, b) => (Number((a.data || a).sequence) || 0) - (Number((b.data || b).sequence) || 0));
    let total = 0;
    const chapterAmt = new Map();
    ordered.forEach((rec, i) => {
        const data = rec.data || rec;
        if (data.display_type === "line_section") chapterAmt.set(rec.id, sectionFieldTotal(ordered, i, "price_subtotal"));
        else if (!data.display_type) total += Number(data.price_subtotal) || 0;
    });
    const out = new Map();
    let run = 0;
    let chapterRun = 0;
    for (const rec of records) {
        const data = rec.data || rec;
        if (!data || data.display_type === "line_note") continue;
        if (data.display_type === "line_section") {
            const amt = chapterAmt.get(rec.id) || 0;
            if (sectionLevel(data) === 0) chapterRun += amt;
            out.set(rec.id, sharePct(sectionLevel(data) === 0 ? chapterRun : amt, total));
        } else {
            run += Number(data.price_subtotal) || 0;
            out.set(rec.id, sharePct(run, total));
        }
    }
    return out;
}

const SALE_SHARE = {
    id: "sale_share", type: "field", name: "display_type", label: "Acum. %",
    hasLabel: true, attrs: {}, options: {}, invisible: "0",
};

patch(SectionAndNoteListRenderer.prototype, {
    getActiveColumns(list) {
        const columns = super.getActiveColumns(list);
        const order = (list.orderBy || [])[0];
        const idx = columns.findIndex((col) => col.name === "amount_cert_origin");
        const on = list.resModel === "sale.order.line" && order && order.name === "price_subtotal" && idx >= 0
            && (this.allColumns || []).some((col) => col.name === "amount_cert_origin")
            && !columns.some((col) => col.id === "sale_share");
        if (!on) return columns;
        const out = columns.slice();
        out.splice(idx + 1, 0, SALE_SHARE);
        return out;
    },
    isSortable(column) { return column.id === "sale_share" ? false : super.isSortable(column); },
    isNumericColumn(column) { return column.id === "sale_share" ? true : super.isNumericColumn(column); },
    getCellClass(column, record) { return column.id === "sale_share" ? "o_data_cell text-end" : super.getCellClass(column, record); },
    canUseFormatter(column, record) { return column.id === "sale_share" ? true : super.canUseFormatter(column, record); },
    getFormattedValue(column, record) {
        if (column.id !== "sale_share") return super.getFormattedValue(column, record);
        const records = this.props.list.records;
        if (this._saleShareRecords !== records) this._saleShareMap = cumulativeSalePercent(this._saleShareRecords = records);
        return formatShare(this._saleShareMap.get(record.id));
    },
});

export function withExplicitPlus(value, text) {
    if (Number(value) > 0 && text && !String(text).trim().startsWith("+")) {
        return `+${text}`;
    }
    return text;
}

export function formatSignedMonetary(value, options) {
    return withExplicitPlus(value, formatMonetary(value, options));
}

export function sectionFigure(records, sectionIndex, columnName) {
    const ratio = SECTION_RATIOS[columnName];
    const sums = sectionColumnSums(records, sectionIndex, ratio || [columnName]);
    if (!ratio) {
        return sums[columnName];
    }
    const den = sums[ratio[1]];
    return den ? (sums[ratio[0]] / den) * 100 : 0;
}

export class ConstructionMarginListRenderer extends SectionAndNoteListRenderer {
    setup() {
        super.setup();
        this._foldNewSections();
    }

    _foldNewSections() {
        for (const rec of this.props.list.records) {
            if (
                rec.data.display_type === "line_section" &&
                this.sectionFold.folded[rec.id] === undefined
            ) {
                this.sectionFold.folded[rec.id] = true;
            }
        }
    }

    getRowClass(record) {
        this._foldNewSections();
        return super.getRowClass(record);
    }

    _isChapterFigure(column) {
        return Boolean((column.attrs && column.attrs.sum) || SECTION_RATIOS[column.name]);
    }

    // widget="monetary" no usa getFormattedValue y pintaría el 0 de la fila de capítulo.
    canUseFormatter(column, record) {
        if (record.data.display_type === "line_section") {
            return true;
        }
        return super.canUseFormatter(column, record);
    }

    getActiveColumns(list) {
        return super.getActiveColumns(list).filter((col) => col.id !== "sale_share");
    }

    getColumns(record) {
        if (record.data.display_type === "line_section") {
            const product = this.props.list.records.find((r) => !r.data.display_type);
            const source = product || record;
            return super.getColumns(source).filter((col) => !isSectionFoldColumn(col));
        }
        return super.getColumns(record).filter((col) => !isSectionFoldColumn(col));
    }

    getCellClass(column, record) {
        if (record.data.display_type !== "line_section") {
            return super.getCellClass(column, record);
        }
        // El renderer de secciones pone o_hidden en todo lo que no es el título y la fila se descuadra.
        let cls = super.getCellClass(column, record).replace(/\bo_hidden\b/g, "");
        if (!this._isChapterFigure(column)) {
            return cls;
        }
        cls += " o_section_fold_total text-end";
        const records = this.props.list.records;
        const val = sectionFigure(records, records.indexOf(record), column.name);
        if (column.name === "amount_cost_deviation") {
            if (val > 0) {
                return `${cls} text-success`;
            }
            if (val < 0) {
                return `${cls} text-danger`;
            }
            return cls;
        }
        return BAD_UNDER.has(column.name) && val < 0 ? `${cls} text-danger` : cls;
    }

    getFormattedValue(column, record) {
        if (record.data.display_type !== "line_section") {
            return super.getFormattedValue(column, record);
        }
        if (column.name === this.titleField || column.name === "bc3_code") {
            return super.getFormattedValue(column, record);
        }
        if (!this._isChapterFigure(column)) {
            return "";
        }
        const records = this.props.list.records;
        const val = sectionFigure(records, records.indexOf(record), column.name);
        if (SECTION_RATIOS[column.name]) {
            return formatFloat(val, { digits: [16, 1] });
        }
        const currency = record.data.currency_id;
        const currencyId = Array.isArray(currency) ? currency[0] : currency;
        const options = { currencyId };
        if (column.name === "amount_cost_deviation") {
            return formatSignedMonetary(val, options);
        }
        return formatMonetary(val, options);
    }
}

export class ConstructionMarginLinesField extends SectionAndNoteFieldOne2Many {}
ConstructionMarginLinesField.components = {
    ...SectionAndNoteFieldOne2Many.components,
    ListRenderer: ConstructionMarginListRenderer,
};

registry.category("fields").add("construction_margin_lines", {
    ...sectionAndNoteFieldOne2Many,
    component: ConstructionMarginLinesField,
});

export class DeviationMonetaryField extends MonetaryField {
    get formattedValue() {
        const text = super.formattedValue;
        if (this.props.inputType === "number" && !this.props.readonly && this.value) {
            return text;
        }
        return withExplicitPlus(this.value, text);
    }
}

registry.category("fields").add("deviation_monetary", {
    ...monetaryField,
    component: DeviationMonetaryField,
});

registry.category("formatters").add("deviation_monetary", formatSignedMonetary);
