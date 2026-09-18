/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formatMonetary } from "@web/views/fields/formatters";
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

    _sumColumnNames() {
        return this.props.archInfo.columns
            .filter((col) => col.sum)
            .map((col) => col.name);
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
        if (
            record.data.display_type === "line_section" &&
            this._sumColumnNames().includes(column.name)
        ) {
            return `${super.getCellClass(column, record)} o_section_fold_total text-end`;
        }
        return super.getCellClass(column, record);
    }

    getFormattedValue(column, record) {
        if (record.data.display_type !== "line_section") {
            return super.getFormattedValue(column, record);
        }
        if (column.name === this.titleField || column.name === "bc3_code") {
            return super.getFormattedValue(column, record);
        }
        if (!this._sumColumnNames().includes(column.name)) {
            return "";
        }
        const records = this.props.list.records;
        const val = sectionColumnSums(records, records.indexOf(record), [column.name])[
            column.name
        ];
        const currency = record.data.currency_id;
        const currencyId = Array.isArray(currency) ? currency[0] : currency;
        return formatMonetary(val, { currencyId });
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
