/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formatFloat, formatMonetary } from "@web/views/fields/formatters";
import { MonetaryField, monetaryField } from "@web/views/fields/monetary/monetary_field";
import {
    SectionAndNoteFieldOne2Many,
    SectionAndNoteListRenderer,
    sectionAndNoteFieldOne2Many,
} from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";
import { sectionChildRecords } from "@incoespacio_section_fold/js/section_fold";

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

    getColumns(record) {
        if (record.data.display_type === "line_section") {
            const product = this.props.list.records.find((r) => !r.data.display_type);
            const source = product || record;
            return super.getColumns(source).filter((col) => col.id !== "section_total");
        }
        return super.getColumns(record).filter((col) => col.id !== "section_total");
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
