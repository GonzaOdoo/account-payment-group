from odoo import api, fields, models, _, Command, SUPERUSER_ID, modules, tools
from odoo.exceptions import UserError
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.payment"

    multiple_payment_id = fields.Many2one(
        comodel_name='account.payment.group',  # Apunta al modelo 'account.payment.multiplemethods'
        string='Payment group',
    #    ondelete='restrict',  # Puedes cambiar esto según tus necesidades: 'cascade', 'restrict', etc.
        help='Selecciona el registro de pago múltiple relacionado.'
    )
    
    amount_company_currency = fields.Monetary(
        string='Amount on Company Currency',
        compute='_compute_amount_company_currency',
        inverse='_inverse_amount_company_currency',  # Método inverso
        currency_field='company_currency_id',
    )
    manual_company_currency = fields.Boolean(
        string="Ajuste manual de cambio",
        default=False,
        help="Enable manual editing of Amount on Company Currency and automatic recalculation of Exchange Rate."
)
    exchange_rate = fields.Float('Tasa de cambio')

    other_currency = fields.Boolean('Divisa extranjera')
    @api.depends('amount', 'to_pay_move_line_ids')
    def _compute_exchange_rate(self):
        for rec in self:
            if rec.other_currency:
                if rec.manual_company_currency:
                    if rec.other_currency:
                        rec.exchange_rate = rec.amount and (
                            rec.amount_company_currency / rec.amount) or 0.0
                    else:
                        rec.exchange_rate = False
                    continue
                if rec.state != 'posted' and len(rec.to_pay_move_line_ids) > 0:
                    first_move_line = rec.to_pay_move_line_ids[0]
                    if first_move_line.move_id.l10n_ar_currency_rate:
                        rec.exchange_rate = first_move_line.move_id.l10n_ar_currency_rate
                        _logger.info(rec.exchange_rate)
                    else:
                        rec.exchange_rate = rec.amount and (
                            rec.amount_company_currency / rec.amount) or 0.0
                
                else:
                    if rec.matched_move_line_ids:
                        first_move_line = rec.matched_move_line_ids[0] if rec.matched_move_line_ids else False
                        if first_move_line.move_id.l10n_ar_currency_rate:
                            rec.exchange_rate = first_move_line.move_id.l10n_ar_currency_rate
                            _logger.info(rec.exchange_rate)
                        else:
                            rec.exchange_rate = rec.amount and (
                                rec.amount_company_currency / rec.amount) or 0.0
                    else:
                        rec.exchange_rate = rec.amount and (
                                rec.amount_company_currency / rec.amount) or 0.0
            else:
                rec.exchange_rate = 0.0

    
    @api.depends('amount')
    def _compute_amount_company_currency(self):
        """
        * Si las monedas son iguales devuelve 1
        * si no, si hay force_amount_company_currency, devuelve ese valor
        * sino, devuelve el amount convertido a la moneda de la cia
        """
        for rec in self:
            if rec.manual_company_currency:
                if not rec.other_currency:
                    amount_company_currency = rec.amount
                elif rec.force_amount_company_currency:
                    amount_company_currency = rec.force_amount_company_currency
                else:
                    amount_company_currency = rec.currency_id._convert(
                        rec.amount, rec.company_id.currency_id,
                        rec.company_id, rec.date)
                rec.amount_company_currency = amount_company_currency
                continue
            amount_company_currency = rec.amount
            if not rec.other_currency:
                amount_company_currency = rec.amount
            else:
                amount_company_currency = rec.amount * rec.exchange_rate
            rec.amount_company_currency = amount_company_currency
            
    def _inverse_amount_company_currency(self):
        for rec in self:
            if rec.amount and rec.other_currency:
                rec.exchange_rate = rec.amount_company_currency / rec.amount
                _logger.info(f"Exchange rate updated from manual company currency: {rec.exchange_rate}")
    
    @api.depends('amount_company_currency','exchange_rate')
    def _compute_amount_from_dollar(self):
        for rec in self:
            rec.amount = rec.amount_company_currency * rec.exchange_rate

    def delete_payment(self):
        self.ensure_one()
        self.unlink()


    ###WITHHOLDINGS USD
    @api.depends(
        'selected_debt', 'unreconciled_amount')
    def _compute_to_pay_amount(self):
        for rec in self:
            rec.to_pay_amount = rec.selected_debt
            
    def _get_payment_difference(self):
        wth_amount = sum(self.l10n_ar_withholding_line_ids.mapped('amount'))
        if self.currency_id != self.company_currency_id:
            wth_amount = wth_amount * self.exchange_rate
        #_logger.info(f'wth_amount: {wth_amount}')
        #_logger.info(f'difference inherited: {super()._get_payment_difference()}')
        payment_difference = super()._get_payment_difference() - wth_amount
        #_logger.info(f'payment_difference: {payment_difference}')
        return payment_difference
    
    #Se está repitiendo la suma de retenciones, por ahora no lo necesito.Revisar cuando necesite retenciones en otra moneda
    #@api.depends('l10n_ar_withholding_line_ids.amount')
    #def _compute_payment_total(self):
     #   super()._compute_payment_total()
      #  for rec in self:
       #     wth_amount = sum(self.l10n_ar_withholding_line_ids.mapped('amount'))
        #    if self.currency_id != self.company_currency_id:
         #       wth_amount = wth_amount * rec.exchange_rate
          #  rec.payment_total += wth_amount
            


    #@api.depends('l10n_ar_withholding_line_ids.amount')
    #def _compute_withholdings_amount(self):
    #    for rec in self:
    #        total_withholdings = sum(rec.l10n_ar_withholding_line_ids.mapped('amount'))
    #        if rec.currency_id == rec.company_currency_id: 
    #            rec.withholdings_amount = total_withholdings
    #        else:
    #            rec.withholdings_amount = total_withholdings * rec.exchange_rate
    #        rec.withholdings_amount = total_withholdings
            
 
    @api.depends("l10n_ar_fiscal_position_id", "partner_id", "company_id", "date")
    def _compute_l10n_ar_withholding_line_ids(self):
        _logger.info("Override!")
        if self.env.context.get('skip_ar_withholdings'):
            for wizard in self:
                wizard.l10n_ar_withholding_ids = [Command.clear()]
            return
        earnings_tax = self.env["account.tax"].search([
            ("l10n_ar_tax_type", "=", "earnings")
        ], limit=1)
    
        for rec in self.filtered(lambda x: x.partner_type == "supplier"):
    
            date = rec.date or fields.Date.context_today(rec)
    
            withholdings = [Command.clear()]
    
            taxes = self.env["account.tax"]
    
            # -------------------------------------------------
            # Taxes desde posición fiscal
            # -------------------------------------------------
            if rec.l10n_ar_fiscal_position_id.l10n_ar_tax_ids:
                taxes |= rec.l10n_ar_fiscal_position_id._l10n_ar_add_taxes(
                    rec.partner_id,
                    rec.company_id,
                    date,
                    "withholding",
                    rec,
                )
    
            # -------------------------------------------------
            # Agregar ganancias automáticamente
            # -------------------------------------------------
            partner = rec.partner_id
    
            if (
                partner.default_regimen_ganancias_id
                and partner.imp_ganancias_padron in ["AC", "NI", "EX"]
            ):
                taxes |= earnings_tax
    
            # evitar duplicados
            taxes = taxes.sorted(key=lambda x: x.id)
    
            # crear líneas
            withholdings += [
                Command.create({
                    "tax_id": tax.id,
                })
                for tax in taxes
            ]
    
            rec.l10n_ar_withholding_line_ids = withholdings