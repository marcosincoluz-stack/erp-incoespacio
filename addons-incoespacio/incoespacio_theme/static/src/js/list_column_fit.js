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
        const total = [...table.querySelectorAll("thead th")].reduce(
            (sum, th) => sum + th.getBoundingClientRect().width,
            0
        );
        table.style.width = `${Math.floor(total)}px`;
    },
});
