/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { onWillRender, useState } from "@odoo/owl";
import { evaluateExpr } from "@web/core/py_js/py";
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
  return (Number(data.price_unit) || 0) * (Number(data.product_uom_qty) || Number(data.quantity) || 0);
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
  return sectionChildRecords(records, sectionIndex).reduce((sum, rec) => sum + lineAmount(rec.data || rec), 0);
}

const CHAPTER_SUMS = ["price_subtotal", "amount_cert_origin", "amount_origin", "amount_period"];

export function sectionFieldTotal(records, sectionIndex, field) {
  if (!field || field === "price_subtotal") {
    return sectionTotal(records, sectionIndex);
  }
  return sectionChildRecords(records, sectionIndex).reduce((sum, rec) => {
    const data = rec.data || rec;
    if (!data || data.display_type) {
      return sum;
    }
    return sum + (Number(data[field]) || 0);
  }, 0);
}

// Chapter row keeps the title colspan, then one cell per sum column so the
// figures sit under Venta sin IVA / Total facturado. Columns after them stay
// as empty pads so the row still matches the header.
export function sectionDisplayColumns(active, titleField) {
  const sums = CHAPTER_SUMS.filter((name) => active.some((col) => col.name === name));
  const firstSum = active.findIndex((col) => sums.includes(col.name));
  const titleIdx = active.findIndex((col) => col.type === "field" && col.name === titleField);
  if (!sums.length || titleIdx < 0 || firstSum <= titleIdx) {
    return null;
  }
  const out = [];
  let consumed = 0;
  for (let i = 0; i < firstSum; i++) {
    if (active[i].widget === "handle") {
      out.push(active[i]);
      consumed++;
    }
  }
  out.push({ ...active[titleIdx], colspan: firstSum - consumed });
  for (let i = firstSum; i < active.length; i++) {
    if (active[i].id === "sale_share") {
      out.push(active[i]);
      continue;
    }
    const name = active[i].name;
    out.push(
      sums.includes(name)
        ? {
            id: "section_total_" + name,
            type: "field",
            name: "display_type",
            sumField: name,
          }
        : { id: "section_pad_" + i, type: "field", name: "display_type" }
    );
  }
  return out;
}

export function isSectionFoldColumn(column) {
  const id = column && column.id;
  return (
    id === "section_total" ||
    (typeof id === "string" && (id.startsWith("section_total_") || id.startsWith("section_pad_")))
  );
}

// The list passes the arch context as a Python string. Spreading that string
// drops default_display_type and the subchapter is created as a partida.
export function createContext(raw) {
  if (!raw) {
    return {};
  }
  if (typeof raw === "string") {
    return evaluateExpr(raw);
  }
  return { ...raw };
}

// Partida under the open section (chapter 0 -> 1, subchapter 1 -> 2).
// A section button keeps its own level. null = leave the field default.
export function addedLineLevel(records, context) {
  const ctx = context || {};
  if (ctx.default_display_type === "line_section") {
    return ctx.default_bc3_level ? Number(ctx.default_bc3_level) : 0;
  }
  if (ctx.default_display_type) {
    return null;
  }
  for (let i = records.length - 1; i >= 0; i--) {
    const data = records[i].data || records[i];
    if (data.display_type === "line_section") {
      return sectionLevel(data) + 1;
    }
  }
  return null;
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
    onWillRender(() => {
      const cols = this.getActiveColumns(this.props.list);
      const cur = this.state.columns;
      if (cols.length !== cur.length || cols.some((col, i) => col.id !== cur[i].id)) {
        this.state.columns = cols;
      }
    });
  },
  _foldSearchActive() {
    return Boolean(
      this.tableRef?.el?.closest(".o_field_x2many")?.querySelector(".o_certification_line_search input")?.value?.trim()
    );
  },
  _foldedHiddenIds() {
    return foldedHiddenIds(this.props.list.records, this.sectionFold.folded, this._foldSearchActive());
  },
  _toggleSection(record) {
    this.sectionFold.folded[record.id] = !this.sectionFold.folded[record.id];
  },
  add(params) {
    const context = createContext(params && params.context);
    const level = addedLineLevel(this.props.list.records, context);
    if (!context.default_display_type && level) {
      context.default_bc3_level = level;
    }
    return super.add({ ...params, context });
  },
  async sortDrop(dataRowId, params) {
    await super.sortDrop(dataRowId, params);
    const records = this.props.list.records;
    const rec = records.find((r) => r.id === dataRowId);
    if (!rec || rec.data.display_type || !("bc3_level" in rec.data)) {
      return;
    }
    const idx = records.indexOf(rec);
    let level = null;
    for (let i = idx - 1; i >= 0; i--) {
      if (records[i].data.display_type === "line_section") {
        level = sectionLevel(records[i].data) + 1;
        break;
      }
    }
    if (level && (Number(rec.data.bc3_level) || 0) !== level) {
      await rec.update({ bc3_level: level });
    }
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
    if (record.data.display_type !== "line_section") {
      return super.getColumns(record);
    }
    const built = sectionDisplayColumns(this.state.columns, this.titleField);
    if (built) {
      return built;
    }
    const columns = super.getColumns(record);
    return columns
      .map((col) =>
        col.name === this.titleField && col.colspan ? { ...col, colspan: Math.max(1, col.colspan - 1) } : col
      )
      .concat({
        id: "section_total",
        type: "field",
        name: "display_type",
      });
  },
  // Fake total has no field descriptor; Field() would throw in fieldVisualFeedback.
  canUseFormatter(column, record) {
    if (this._foldCell(column)) {
      return true;
    }
    return super.canUseFormatter(column, record);
  },
  _foldCell(column) {
    const id = column && column.id;
    if (id === "section_total" || (typeof id === "string" && id.startsWith("section_total_"))) {
      return "total";
    }
    if (typeof id === "string" && id.startsWith("section_pad_")) {
      return "pad";
    }
    return null;
  },
  getCellClass(column, record) {
    if (this._foldCell(column) === "total") {
      return "o_data_cell o_section_fold_total text-end";
    }
    if (this._foldCell(column) === "pad") {
      return "o_data_cell";
    }
    return super.getCellClass(column, record);
  },
  getFormattedValue(column, record) {
    if (this._foldCell(column) === "pad") {
      return "";
    }
    if (this._foldCell(column) === "total") {
      const currency = record.data.currency_id;
      const currencyId = Array.isArray(currency) ? currency[0] : currency;
      const records = this.props.list.records;
      const amount = sectionFieldTotal(records, records.indexOf(record), column.sumField);
      return formatMonetary(amount, { currencyId });
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
