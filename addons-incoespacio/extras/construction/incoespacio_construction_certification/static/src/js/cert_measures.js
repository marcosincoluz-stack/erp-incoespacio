/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";
import { bc3MeasureNum, bc3MeasurePartial, bc3Measures } from "@bc3_importer/js/bc3_detail";

const QTY_EPS = 0.0005;

function certBudgetIdx(value) {
  if (value === null || value === undefined || value === false || value === "") {
    return null;
  }
  const num = Number(value);
  return Number.isInteger(num) ? num : null;
}

function certFmt(value) {
  const num = bc3MeasureNum(value);
  if (num === null) {
    return "";
  }
  return num.toLocaleString("es-ES", { maximumFractionDigits: 3 });
}

function matchesBudget(row, source, index) {
  if (row?.budget_key && source?.key) {
    return row.budget_key === source.key;
  }
  if (row?.budget_key) {
    return false;
  }
  return certBudgetIdx(row?.budget_idx) === index;
}

function certRowsToSave(rows) {
  return (rows || []).map((row) => {
    const partial = bc3MeasurePartial(row);
    return {
      comment: row?.comment || "",
      units: bc3MeasureNum(row?.units),
      length: bc3MeasureNum(row?.length),
      width: bc3MeasureNum(row?.width),
      height: bc3MeasureNum(row?.height),
      partial: partial === null ? 0 : partial,
      budget_idx: certBudgetIdx(row?.budget_idx),
      budget_key: row?.budget_key || null,
    };
  });
}

// Misma regla que ConstructionCertificationLine._measures_period_qty:
// suma solo si alguna fila tiene parcial; si no, no se toca Med. Periodo.
function certPeriodSum(rows) {
  let sum = 0;
  let any = false;
  for (const row of rows || []) {
    const qty = bc3MeasureNum(row?.partial);
    if (qty) {
      any = true;
      sum += qty;
    }
  }
  return any ? sum : null;
}

function certPartialSum(rows) {
  return certPeriodSum(rows) || 0;
}

patch(ListRenderer.prototype, {
  setup() {
    super.setup();
    this.certDetail = useState({ open: {} });
  },
  certList() {
    return this.props.list?.resModel === "construction.certification.line";
  },
  bc3ShowChevron(record) {
    if (this.certList()) {
      return false;
    }
    return super.bc3ShowChevron(record);
  },
  budgetRows(record) {
    return bc3Measures(record.data);
  },
  certRows(record) {
    return bc3Measures(record.data, "bc3_cert_measures");
  },
  prevRows(record) {
    return bc3Measures(record.data, "bc3_prev_measures");
  },
  certFmt(value) {
    return certFmt(value);
  },
  certNumber(record) {
    const parent = record._parentRecord || record.model?.root || this.props.list?._parent;
    const num = parent?.data?.number ?? parent?.evalContext?.number;
    return num || "";
  },
  certRowLabel(row, record) {
    const num = row?.cert || this.certNumber(record);
    return num ? `Cert. ${num}` : "";
  },
  certPrevSum(record) {
    return certPartialSum(this.prevRows(record));
  },
  certCurrentSum(record) {
    return certPartialSum(this.certRows(record));
  },
  certUndetailed(record) {
    const origin = bc3MeasureNum(record.data.qty_origin) || 0;
    const explained = this.certPrevSum(record) + this.certCurrentSum(record);
    const gap = origin - explained;
    return Math.abs(gap) > QTY_EPS ? gap : 0;
  },
  _budgetMatch(row, source, index) {
    return matchesBudget(row, source, index);
  },
  budgetPending(record, index) {
    const source = this.budgetRows(record)[index];
    if (!source) {
      return null;
    }
    const partial = bc3MeasureNum(source.partial);
    if (partial === null) {
      return null;
    }
    let used = 0;
    for (const row of [...this.prevRows(record), ...this.certRows(record)]) {
      if (this._budgetMatch(row, source, index)) {
        used += bc3MeasureNum(row.partial) || 0;
      }
    }
    return partial - used;
  },
  budgetTotal(record) {
    let sum = 0;
    for (const row of this.budgetRows(record)) {
      sum += bc3MeasureNum(row.partial) || 0;
    }
    return sum;
  },
  budgetPendingTotal(record) {
    let sum = 0;
    this.budgetRows(record).forEach((_, index) => {
      const pending = this.budgetPending(record, index);
      if (pending > QTY_EPS) {
        sum += pending;
      }
    });
    return sum;
  },
  budgetPendingClass(record, index) {
    const pending = this.budgetPending(record, index);
    if (pending === null) {
      return "";
    }
    if (pending < -QTY_EPS) {
      return "text-danger";
    }
    if (Math.abs(pending) <= QTY_EPS) {
      return "text-success";
    }
    return "";
  },
  budgetCertLabel(record, index) {
    const source = this.budgetRows(record)[index];
    const nums = [];
    const seen = new Set();
    const current = this.certNumber(record);
    for (const row of [...this.prevRows(record), ...this.certRows(record)]) {
      if (!this._budgetMatch(row, source, index)) {
        continue;
      }
      const num = row.cert || current;
      if (!num || seen.has(num)) {
        continue;
      }
      seen.add(num);
      nums.push(num);
    }
    return nums.map((num) => `Cert. ${num}`).join(", ");
  },
  certRowOver(record, measure) {
    const budget = this.budgetRows(record);
    for (let index = 0; index < budget.length; index++) {
      if (!this._budgetMatch(measure, budget[index], index)) {
        continue;
      }
      const pending = this.budgetPending(record, index);
      return pending !== null && pending < -QTY_EPS;
    }
    return false;
  },
  certShowChevron(record) {
    if (!this.certList() || !record.data || record.data.display_type) {
      return false;
    }
    const fields = this.props.list?.activeFields;
    if (!fields?.bc3_measures && !fields?.bc3_cert_measures && !fields?.bc3_prev_measures) {
      return false;
    }
    const text = record.data.bc3_text && String(record.data.bc3_text).trim();
    return Boolean(
      text ||
        this.budgetRows(record).length ||
        this.certRows(record).length ||
        this.prevRows(record).length ||
        this.props.editable
    );
  },
  certDetailOpen(record) {
    return Boolean(this.certDetail?.open[record.id]);
  },
  _certChevronHit(record, column, ev) {
    if (!this.certShowChevron(record) || !column || column.name !== "name") {
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
  async _certSave(record, rows) {
    const had = this.certRows(record).length;
    const measures = certRowsToSave(rows);
    const vals = { bc3_cert_measures: measures.length ? measures : false };
    const period = certPeriodSum(measures);
    if (period !== null) {
      vals.qty_period = period;
    } else if (had && !measures.length) {
      vals.qty_period = 0;
    }
    await record.update(vals);
  },
  certSetMeasure(record, index, field, ev) {
    const rows = this.certRows(record).map((row) => ({ ...row }));
    rows[index] = { ...rows[index], [field]: ev.target.value };
    return this._certSave(record, rows);
  },
  _certCloneBudget(source, index, units) {
    const pendingOnly = units !== undefined;
    return {
      comment: source.comment || "",
      units: pendingOnly ? units : source.units,
      length: pendingOnly ? null : source.length,
      width: pendingOnly ? null : source.width,
      height: pendingOnly ? null : source.height,
      partial: pendingOnly ? units : source.partial,
      budget_key: source.key || null,
      budget_idx: source.key ? null : index,
    };
  },
  certCopyMeasure(record, index) {
    if (!this.props.editable) {
      return;
    }
    const source = this.budgetRows(record)[index] || {};
    const rows = this.certRows(record).map((row) => ({ ...row }));
    rows.push(this._certCloneBudget(source, index));
    return this._certSave(record, rows);
  },
  certCopyPending(record) {
    if (!this.props.editable) {
      return;
    }
    const rows = this.certRows(record).map((row) => ({ ...row }));
    this.budgetRows(record).forEach((source, index) => {
      const pending = this.budgetPending(record, index);
      if (!(pending > QTY_EPS)) {
        return;
      }
      rows.push(this._certCloneBudget(source, index, pending));
    });
    return this._certSave(record, rows);
  },
  certAddMeasure(record) {
    if (!this.props.editable) {
      return;
    }
    const rows = this.certRows(record).map((row) => ({ ...row }));
    rows.push({
      comment: "",
      units: null,
      length: null,
      width: null,
      height: null,
      partial: null,
      budget_idx: null,
      budget_key: null,
    });
    return this._certSave(record, rows);
  },
  certRemoveMeasure(record, index) {
    const kept = this.certRows(record).filter((_, i) => i !== index);
    return this._certSave(record, kept);
  },
  getRowClass(record) {
    let cls = super.getRowClass(record);
    if (!this.certShowChevron(record)) {
      return cls;
    }
    cls += " o_bc3_has_detail";
    const text = record.data.bc3_text && String(record.data.bc3_text).trim();
    if (!text && !this.budgetRows(record).length && !this.certRows(record).length && !this.prevRows(record).length) {
      cls += " o_bc3_detail_empty";
    }
    if (this.certDetail.open[record.id]) {
      cls += " o_bc3_detail_open";
    }
    return cls;
  },
  onCellClicked(record, column, ev) {
    if (this._certChevronHit(record, column, ev)) {
      ev.stopPropagation();
      ev.preventDefault();
      this.certDetail.open[record.id] = !this.certDetail.open[record.id];
      return;
    }
    return super.onCellClicked(record, column, ev);
  },
});
