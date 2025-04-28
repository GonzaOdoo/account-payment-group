from odoo import models,api,fields
from odoo.exceptions import UserError

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def create_payment_group_from_lines(self):
        """ Crea un pago en grupo a partir de las líneas de asiento seleccionadas. """
        context = self.env.context or {}
        active_ids = context.get("active_ids", [])
        
        if not active_ids:
            raise UserError("No se seleccionaron líneas de factura.")

        # Obtener las líneas seleccionadas
        lines = self.browse(active_ids)
        
        # Filtrar solo líneas válidas (facturas publicadas, no pagadas, cuenta reconciliable)
        valid_lines = lines.filtered(lambda l: 
            l.move_id.state == "posted" and 
            not l.reconciled and 
            l.account_id.reconcile and
            l.move_id.payment_state not in ["paid", "reversed"]
        )
        
        if not valid_lines:
            raise UserError("No hay líneas válidas para pagar (facturas publicadas, no reconciliadas y con cuentas reconciliables).")

        # Verificar que todas las líneas sean del mismo partner
        partners = valid_lines.mapped('partner_id')
        if len(partners) > 1:
            raise UserError("¡Error! Todas las líneas seleccionadas deben ser del mismo partner.")
        partner = partners[0] if partners else False
        if not partner:
            raise UserError("Algunas líneas no tienen partner asignado.")

        # Verificar que todas las líneas sean del mismo tipo (cliente/proveedor)
        move_types = valid_lines.mapped('move_id.move_type')
        if any(t not in ('out_invoice', 'out_refund') for t in move_types) and any(t not in ('in_invoice', 'in_refund') for t in move_types):
            raise UserError("No se pueden mezclar facturas de cliente y proveedor en un mismo pago.")

        # Determinar si es cliente o proveedor
        is_customer = valid_lines[0].move_id.move_type in ('out_invoice', 'out_refund')

        # Crear el grupo de pago
        payment_group = self.env["account.payment.group"].create({
            "partner_id": partner.id,
            "partner_type": "customer" if is_customer else "supplier",
            "company_id": valid_lines[0].company_id.id,
        })

        # Asignar las líneas al pago
        payment_group.to_pay_move_line_ids = [(6, 0, valid_lines.ids)]

        return {
            "type": "ir.actions.act_window",
            "name": "Pago en Grupo",
            "res_model": "account.payment.group",
            "view_mode": "form",
            "res_id": payment_group.id,
            "target": "current",
        }