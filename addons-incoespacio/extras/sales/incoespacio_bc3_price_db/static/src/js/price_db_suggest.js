/** @odoo-module **/

import { Component, useEffect, useRef, useState, onWillUnmount } from "@odoo/owl";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { useAutoresize } from "@web/core/utils/autoresize";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { ListSectionAndNoteText } from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";
import {
    SaleOrderLineProductField,
    saleOrderLineProductField,
} from "@sale/js/sale_product_field";

// ponytail: 8 hits in the menu. Buscar más opens the full list.

export function stripPartidaCode(text) {
    return (text || "").replace(/^\[[^\]]+\]\s*/, "");
}

export class PriceDbSuggest extends Component {
    static template = "incoespacio_bc3_price_db.PriceDbSuggest";
    static components = { ListSectionAndNoteText };
    static props = {
        ...standardFieldProps,
        multiline: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.addDialog = useOwnedDialogs();
        this.input = useRef("input");
        this.state = useState({
            text: this._shown(this.props.record.data[this.props.name]),
            choices: [],
            open: false,
            above: false,
            top: 0,
            bottom: 0,
            left: 0,
            width: 320,
            maxHeight: 320,
        });
        this.alive = true;
        this.dirty = false;
        this._seq = 0;
        this._timer = null;
        this._blur = null;
        onWillUnmount(() => {
            this.alive = false;
            clearTimeout(this._timer);
            clearTimeout(this._blur);
        });
        useAutoresize(this.input, { minimumHeight: 0 });
        useEffect(
            () => {
                if (this.dirty && this.input.el && document.activeElement === this.input.el) {
                    return;
                }
                this.state.text = this._shown(this.props.record.data[this.props.name]);
            },
            () => [this.props.record.data[this.props.name], this.props.record.data.bc3_code]
        );
    }

    get term() {
        return (this.state.text || "").trim();
    }

    get isSection() {
        const kind = this.props.record.data.display_type;
        return kind === "line_section" || kind === "line_note";
    }

    get sectionProps() {
        const { multiline, ...rest } = this.props;
        return rest;
    }

    get menuStyle() {
        const edge = this.state.above
            ? "bottom:" + this.state.bottom + "px;"
            : "top:" + this.state.top + "px;";
        return (
            edge + "left:" + this.state.left + "px;width:" +
            this.state.width + "px;max-height:" + this.state.maxHeight + "px;"
        );
    }

    _shown(value) {
        return value || "";
    }

    onInput(ev) {
        this.dirty = true;
        this.state.text = ev.target.value;
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.search(this.state.text), 200);
    }

    async search(term) {
        const seq = ++this._seq;
        const text = (term || "").trim();
        if (!text) {
            this.state.choices = [];
            this.state.open = false;
            return;
        }
        const rows = await this.orm.call("product.product", "name_search", [], {
            name: text,
            args: [],
            operator: "ilike",
            limit: 8,
            context: { price_db_only: true },
        });
        if (!this.alive || seq !== this._seq) {
            return;
        }
        this.state.choices = rows.map((row) => ({ id: row[0], label: row[1] }));
        this.state.open = true;
        this.place();
    }

    place() {
        const el = this.input.el;
        if (!el) {
            return;
        }
        const rect = el.getBoundingClientRect();
        const gap = 4;
        const below = window.innerHeight - rect.bottom - gap;
        const above = rect.top - gap;
        const upward = below < 240 && above > below;
        this.state.above = upward;
        this.state.maxHeight = Math.max(120, Math.min(320, upward ? above : below));
        this.state.left = rect.left;
        this.state.width = Math.max(rect.width, 320);
        if (upward) {
            this.state.bottom = window.innerHeight - rect.top + gap;
        } else {
            this.state.top = rect.bottom + gap;
        }
    }

    hold() {
        clearTimeout(this._blur);
        this.dirty = false;
        this.state.open = false;
    }

    priceDomain() {
        if (!this._priceDomain) {
            this._priceDomain = this.orm.call("product.product", "price_db_domain", []);
        }
        return this._priceDomain;
    }

    async priceContext(name) {
        const domain = await this.priceDomain();
        const categ = domain.find((item) => item[0] === "categ_id");
        return {
            default_name: name || false,
            default_categ_id: categ ? categ[2] : false,
            default_detailed_type: "service",
            default_sale_ok: true,
            default_purchase_ok: false,
        };
    }

    async pickId(id) {
        const [row] = await this.orm.read("product.product", [id], ["display_name"]);
        if (!this.alive || !row) {
            return;
        }
        await this.pick({ id, label: row.display_name });
    }

    async searchMore() {
        const term = this.term;
        this.hold();
        const domain = await this.priceDomain();
        const context = await this.priceContext(term);
        let dynamicFilters = [];
        if (term) {
            const rows = await this.orm.call("product.product", "name_search", [], {
                name: term,
                args: domain,
                operator: "ilike",
                limit: 80,
                context: { price_db_only: true },
            });
            if (rows.length) {
                dynamicFilters = [{
                    description: term,
                    domain: [["id", "in", rows.map((row) => row[0])]],
                }];
            }
        }
        if (!this.alive) {
            return;
        }
        this.addDialog(SelectCreateDialog, {
            title: "Buscar: Partida",
            noCreate: false,
            multiSelect: false,
            resModel: "product.product",
            context,
            domain,
            dynamicFilters,
            onSelected: async (resIds) => {
                if (resIds && resIds[0]) {
                    await this.pickId(resIds[0]);
                }
            },
        });
    }

    async quickCreate() {
        const name = this.term;
        this.hold();
        if (!name) {
            return;
        }
        const context = await this.priceContext(name);
        const [id] = await this.orm.call("product.product", "name_create", [name], { context });
        if (this.alive) {
            await this.pickId(id);
        }
    }

    async createEdit() {
        const name = this.term;
        this.hold();
        const context = await this.priceContext(name);
        this.addDialog(FormViewDialog, {
            resModel: "product.product",
            context,
            title: "Crear partida",
            onRecordSaved: async (record) => {
                await this.pickId(record.resId);
            },
            onRecordDiscarded: () => {
                this.state.text = this._shown(this.props.record.data[this.props.name]);
            },
        });
    }

    async pick(choice) {
        clearTimeout(this._blur);
        this.dirty = false;
        this.state.open = false;
        this.state.choices = [];
        await this.props.record.update({
            product_id: [choice.id, choice.label],
        });
        if (!this.alive) {
            return;
        }
        this.state.text = this._shown(this.props.record.data[this.props.name]);
        const el = this.input.el;
        if (el && this.props.multiline) {
            requestAnimationFrame(() => {
                el.style.height = "auto";
                el.style.height = el.scrollHeight + "px";
            });
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && this.state.open && this.state.choices.length) {
            ev.preventDefault();
            ev.stopPropagation();
            this.pick(this.state.choices[0]);
        } else if (ev.key === "Escape") {
            this.state.open = false;
        }
    }

    onBlur() {
        clearTimeout(this._blur);
        this._blur = setTimeout(() => this.commit(), 200);
    }

    async commit() {
        this.state.open = false;
        if (!this.dirty) {
            return;
        }
        this.dirty = false;
        const data = this.props.record.data;
        if (data.price_db_linked && !this.props.multiline) {
            this.state.text = data.price_product_code || "";
            return;
        }
        const stored = this._shown(data[this.props.name]);
        if ((this.state.text || "") === stored) {
            return;
        }
        await this.props.record.update({
            [this.props.name]: this.state.text || false,
        });
    }
}

const priceDbCodeField = {
    component: PriceDbSuggest,
    supportedTypes: ["char"],
    extractProps: () => ({ multiline: false }),
};

const priceDbTitleField = {
    component: PriceDbSuggest,
    supportedTypes: ["text", "char"],
    extractProps: () => ({ multiline: true }),
};

export class PriceDbPartidaField extends SaleOrderLineProductField {
    get displayName() {
        return stripPartidaCode(super.displayName);
    }
}

const priceDbPartidaField = {
    ...saleOrderLineProductField,
    component: PriceDbPartidaField,
};

registry.category("fields").add("price_db_code", priceDbCodeField);
registry.category("fields").add("list.price_db_code", priceDbCodeField);
registry.category("fields").add("price_db_title", priceDbTitleField);
registry.category("fields").add("list.price_db_title", priceDbTitleField);
registry.category("fields").add("price_db_partida", priceDbPartidaField);
registry.category("fields").add("list.price_db_partida", priceDbPartidaField);
