from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReportPdf(TransactionCase):
    def test_sale_and_certification_pdf(self):
        partner = self.env["res.partner"].create({"name": "Cliente PDF"})
        product = self.env["product.product"].create(
            {"name": "Partida PDF", "detailed_type": "service", "list_price": 10}
        )
        order = self.env["sale.order"].create({"partner_id": partner.id})
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": product.id,
                "name": "Partida PDF",
                "product_uom_qty": 1,
                "price_unit": 10,
            }
        )
        report = self.env["ir.actions.report"].with_context(force_report_rendering=True)
        sale_pdf, _type = report._render_qweb_pdf("sale.report_saleorder", order.ids)
        self.assertTrue(sale_pdf.startswith(b"%PDF"))
        order.action_confirm()
        action = order.action_create_certification()
        cert = self.env["construction.certification"].browse(action["res_id"])
        cert_pdf, _type = report._render_qweb_pdf(
            "incoespacio_construction_certification.report_certification_document",
            cert.ids,
        )
        self.assertTrue(cert_pdf.startswith(b"%PDF"))
