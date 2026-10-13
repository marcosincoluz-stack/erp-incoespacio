import datetime
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase


class TestOcrCron(TransactionCase):
    def setUp(self):
        super().setUp()
        # La cola es global. En el test no deben colarse facturas ya pendientes;
        # el rollback de TransactionCase las deja como estaban.
        queued = self.env["account.move"].search([
            ("ocr_status", "in", ("pending", "processing")),
        ])
        if queued:
            queued.write({"ocr_status": "done"})

    def _bill(self, status):
        return self.env["account.move"].create({
            "move_type": "in_invoice",
            "ocr_status": status,
        })

    def _scan(self, seen):
        def _run(move):
            seen.append(move.id)
            move.write({"ocr_status": "done"})
        return _run

    def test_pending_is_processed(self):
        move = self._bill("pending")
        seen = []
        with patch.object(type(move), "action_scan_with_ai", self._scan(seen)):
            self.env["account.move"]._cron_process_pending_ocr()
        self.assertEqual(move.ocr_status, "done")
        self.assertIn(move.id, seen)

    def test_stale_processing_is_reprocessed(self):
        move = self._bill("processing")
        self.env.cr.execute(
            "UPDATE account_move SET write_date = %s WHERE id = %s",
            [fields.Datetime.now() - datetime.timedelta(minutes=20), move.id],
        )
        move.invalidate_recordset()
        seen = []
        with patch.object(type(move), "action_scan_with_ai", self._scan(seen)):
            self.env["account.move"]._cron_process_pending_ocr()
        self.assertEqual(move.ocr_status, "done")
        self.assertIn(move.id, seen)

    def test_done_is_left_alone(self):
        move = self._bill("done")
        seen = []
        with patch.object(type(move), "action_scan_with_ai", self._scan(seen)):
            self.env["account.move"]._cron_process_pending_ocr()
        self.assertEqual(move.ocr_status, "done")
        self.assertNotIn(move.id, seen)
