/** @odoo-module **/

import { bc3EditorRows, bc3MeasurePartial, bc3MeasuresQty, bc3RowsToSave } from "@bc3_importer/js/bc3_detail";

QUnit.module("bc3 detail");

QUnit.test("numbered measure sets qty; empty rows do not", (assert) => {
    const row = { units: 2, length: 5, width: null, height: null };
    assert.strictEqual(bc3MeasurePartial(row), 10);
    assert.strictEqual(bc3MeasuresQty([row]), 10);
    assert.strictEqual(bc3MeasuresQty([{ comment: "vacia" }]), null);
    assert.strictEqual(bc3MeasuresQty([]), null);
});

QUnit.test("total qty prefills the only measurement row", (assert) => {
    const rows = bc3EditorRows({ product_uom_qty: 10, bc3_measures: false });
    assert.strictEqual(rows.length, 1);
    assert.strictEqual(rows[0].units, 10);
    assert.strictEqual(bc3MeasuresQty(rows), 10);
});

QUnit.test("an added blank row stays after the filled ones", (assert) => {
    const saved = bc3RowsToSave([
        { comment: "Impulsion", units: 4 },
        { comment: "Extraccion", units: 4 },
        { comment: "" },
    ]);
    assert.strictEqual(saved.length, 3);
    assert.strictEqual(bc3MeasuresQty(saved), 8);
});
