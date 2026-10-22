/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";

// Odoo: monetary 104px / float 92px, y al encoger no baja de 92px.
const TIGHT_WIDTHS = {
    boolean: "40px",
    float: "56px",
    integer: "48px",
    monetary: "64px",
};

function isX2Many(renderer) {
    return Boolean(renderer.tableRef?.el?.closest(".o_field_x2many"));
}

patch(ListRenderer.prototype, {
    calculateColumnWidth(column) {
        const result = super.calculateColumnWidth(column);
        if (!isX2Many(this) || result.type !== "absolute" || column.attrs?.width) {
            return result;
        }
        const type = column.widget || this.fields[column.name]?.type;
        if (type in TIGHT_WIDTHS) {
            return { type: "absolute", value: TIGHT_WIDTHS[type] };
        }
        return result;
    },

    computeColumnWidthsFromContent() {
        if (!isX2Many(this)) {
            return super.computeColumnWidthsFromContent();
        }
        // No encoger al ancho del padre (suelo 92px): la tabla scrollea al contenido.
        const table = this.tableRef.el;
        table.classList.add("o_list_computing_widths");
        const widths = [...table.querySelectorAll("thead th")].map(
            (th) => th.getBoundingClientRect().width
        );
        table.classList.remove("o_list_computing_widths");
        return widths;
    },

    freezeColumnWidths() {
        super.freezeColumnWidths();
        if (!isX2Many(this)) {
            return;
        }
        const table = this.tableRef.el;
        if (table.closest(".o_sale_order")) {
            fitColumnsToText(table);
        }
        for (const th of table.querySelectorAll("thead th.o_handle_cell")) {
            th.style.width = "33px";
        }
        const total = [...table.querySelectorAll("thead th")].reduce(
            (sum, th) => sum + th.getBoundingClientRect().width,
            0
        );
        table.style.width = `${Math.floor(total)}px`;
    },
});

// The laid-out cell is already stretched, so its box is the white space.
// Measure the text and stop the column there.
function textWidth(el) {
    const prevWhite = el.style.whiteSpace;
    const prevWidth = el.style.width;
    el.style.whiteSpace = "nowrap";
    el.style.width = "max-content";
    const width = el.scrollWidth;
    el.style.whiteSpace = prevWhite;
    el.style.width = prevWidth;
    return width;
}

function fitColumnsToText(table) {
    const headers = [...table.querySelectorAll("thead th")];
    headers.forEach((th, index) => {
        if (
            th.classList.contains("o_handle_cell") ||
            th.classList.contains("o_list_button") ||
            th.classList.contains("o_list_record_selector")
        ) {
            return;
        }
        const label = th.querySelector(".text-truncate") || th;
        let width = textWidth(label);
        const thStyle = getComputedStyle(th);
        width += parseFloat(thStyle.paddingLeft) + parseFloat(thStyle.paddingRight);
        for (const row of table.querySelectorAll("tbody > tr.o_data_row")) {
            if (row.classList.contains("o_is_line_section") || row.classList.contains("o_is_line_note")) {
                continue;
            }
            const cell = row.children[index];
            if (!cell || cell.colSpan > 1) {
                continue;
            }
            const field = cell.querySelector(".o_field_widget");
            if (!field) {
                continue;
            }
            const cellStyle = getComputedStyle(cell);
            const need =
                textWidth(field) +
                parseFloat(cellStyle.paddingLeft) +
                parseFloat(cellStyle.paddingRight);
            width = Math.max(width, need);
        }
        const px = `${Math.ceil(width)}px`;
        th.style.width = px;
        th.style.minWidth = px;
        th.style.maxWidth = px;
    });
}
