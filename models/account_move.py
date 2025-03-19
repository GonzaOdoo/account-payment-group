from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    def create_payment_group_from_invoice(self):
            """ Crea un pago en grupo a partir de las facturas seleccionadas. """
            context = self.env.context or {}
            active_ids = context.get("active_ids", [])
            
            if not active_ids:
                return
    
            # Filtrar solo las facturas publicadas y no pagadas
            invoices = self.env["account.move"].browse(active_ids).filtered(lambda m: m.state == "posted" and not m.payment_state in ["paid", "reversed"])
            
            if not invoices:
                return
    
            partner = invoices[0].partner_id  # Tomamos el primer partner de las facturas seleccionadas
    
            # Crear un pago en grupo
            payment_group = self.env["account.payment.group"].create({
                "partner_id": partner.id,
                "partner_type": "customer" if invoices[0].move_type in ["out_invoice", "out_refund"] else "supplier",
                "company_id": invoices[0].company_id.id,
            })
    
            # Asociar las facturas al pago en grupo
            payment_group.to_pay_move_line_ids = [(6, 0, invoices.mapped("line_ids").filtered(lambda l: l.account_id.reconcile and not l.reconciled).ids)]
    
            return {
                "type": "ir.actions.act_window",
                "name": "Pago en Grupo",
                "res_model": "account.payment.group",
                "view_mode": "form",
                "res_id": payment_group.id,
                "target": "current",
            }

    def create_payment_group_from_invoice_form(self):
        """ Crea un pago en grupo a partir de una factura seleccionada en el formulario. """

        self.ensure_one()  # Solo permite una factura a la vez en el formulario

        if self.state != "posted" or self.payment_state in ["paid", "reversed"]:
            return

        partner = self.partner_id

        # Crear un pago en grupo
        payment_group = self.env["account.payment.group"].create({
            "partner_id": partner.id,
            "partner_type": "customer" if self.move_type in ["out_invoice", "out_refund"] else "supplier",
            "company_id": self.company_id.id,
        })

        # Asociar las facturas al pago en grupo
        payment_group.to_pay_move_line_ids = [(6, 0, self.line_ids.filtered(lambda l: l.account_id.reconcile and not l.reconciled).ids)]

        return {
            "type": "ir.actions.act_window",
            "name": "Pago en Grupo",
            "res_model": "account.payment.group",
            "view_mode": "form",
            "res_id": payment_group.id,
            "target": "current",
        }
   

