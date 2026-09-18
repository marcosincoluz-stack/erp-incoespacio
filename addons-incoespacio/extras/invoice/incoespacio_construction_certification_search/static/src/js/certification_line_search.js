/** @odoo-module **/

import { unaccent } from "@web/core/utils/strings";
import { registry } from "@web/core/registry";
import { useState, useRef, onWillUnmount } from "@odoo/owl";
import {
    SectionAndNoteFieldOne2Many,
    sectionAndNoteFieldOne2Many,
} from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";

export function fold(s) {
    return unaccent(s || "").replace(/,/g, ".");
}

export function rowMatches(text, query) {
    const q = fold(query).trim();
    return Boolean(q) && fold(text).includes(q);
}

export class CertificationLinesField extends SectionAndNoteFieldOne2Many {
    static template = "incoespacio_construction_certification_search.X2ManyField";
    static components = {
        ...SectionAndNoteFieldOne2Many.components,
    };

    setup() {
        super.setup();
        this.state = useState({ query: "", current: 0, total: 0 });
        this.searchRef = useRef("search");
        this._timer = null;
        onWillUnmount(() => clearTimeout(this._timer));
    }

    onSearchInput(ev) {
        this.state.query = ev.target.value;
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this._jump(0, true), 150);
    }

    onSearchKeydown(ev) {
        if (ev.key !== "Enter" && ev.key !== "F3") {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this._jump(ev.shiftKey ? -1 : 1);
    }

    _listRoot() {
        return this.searchRef.el?.closest(".o_field_x2many")?.querySelector(".o_list_renderer");
    }

    _matchRows() {
        const root = this._listRoot();
        if (!root) {
            return [];
        }
        return [...root.querySelectorAll("tbody tr.o_data_row")].filter((tr) =>
            rowMatches(tr.innerText, this.state.query)
        );
    }

    _clearHighlights() {
        this._listRoot()
            ?.querySelectorAll(".o_certification_line_match")
            .forEach((el) => {
                el.classList.remove("o_certification_line_match", "o_certification_line_match_current");
            });
    }

    _jump(delta, reset = false) {
        this._clearHighlights();
        const rows = this._matchRows();
        this.state.total = rows.length;
        if (!rows.length) {
            this.state.current = 0;
            return;
        }
        if (reset) {
            this.state.current = 1;
        } else {
            const n = rows.length;
            this.state.current = ((this.state.current - 1 + delta + n) % n) + 1;
        }
        rows.forEach((tr, i) => {
            tr.classList.add("o_certification_line_match");
            if (i === this.state.current - 1) {
                tr.classList.add("o_certification_line_match_current");
                tr.scrollIntoView({ block: "center", inline: "nearest" });
            }
        });
    }
}

registry.category("fields").add("certification_lines", {
    ...sectionAndNoteFieldOne2Many,
    component: CertificationLinesField,
});
