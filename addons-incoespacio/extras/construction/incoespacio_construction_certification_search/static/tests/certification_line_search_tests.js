/** @odoo-module **/

import {
    fold,
    rowMatches,
} from "@incoespacio_construction_certification_search/js/certification_line_search";

QUnit.module("construction certification line search");

QUnit.test("fold strips accents and unifies decimal comma", (assert) => {
    assert.strictEqual(fold("Tabiquería"), "tabiqueria");
    assert.strictEqual(fold("12,50"), "12.50");
});

QUnit.test("rowMatches name and price", (assert) => {
    const row = "C01\tTabiquería pladur\tm2\t12,50";
    assert.ok(rowMatches(row, "tabiqueria"));
    assert.ok(rowMatches(row, "12,5"));
    assert.ok(rowMatches(row, "12.5"));
    assert.notOk(rowMatches(row, "hormigon"));
    assert.notOk(rowMatches(row, ""));
});
