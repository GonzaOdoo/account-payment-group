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
        ondelete='restrict',  # Puedes cambiar esto según tus necesidades: 'cascade', 'restrict', etc.
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
    @api.depends('amount', 'other_currency', 'to_pay_move_line_ids')
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

    
    @api.depends('amount', 'other_currency', 'force_amount_company_currency','exchange_rate')
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
            
    #def _inverse_amount_company_currency(self):
     #   for rec in self:
      #      if rec.amount and rec.other_currency:
       #         rec.exchange_rate = rec.amount_company_currency / rec.amount
        #        _logger.info(f"Exchange rate updated from manual company currency: {rec.exchange_rate}")
    
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
            
    def _prepare_witholding_write_off_vals(self):
        self.ensure_one()
        write_off_line_vals = []
        conversion_rate = self.exchange_rate or 1.0
        sign = 1
        if self.partner_type == 'supplier':
            sign = -1
        for line in self.l10n_ar_withholding_line_ids:
            _logger.info(f"Line: {str(line)}")
            # nuestro approach esta quedando distinto al del wizard. En nuestras lineas tenemos los importes en moneda
            # de la cia, por lo cual el line.amount aca representa eso y tenemos que convertirlo para el amount_currency
            account_id, tax_repartition_line_id = line._tax_compute_all_helper()
            amount_currency = self.currency_id.round(line.amount / conversion_rate)
            line_amount = line.amount
            if self.currency_id != self.company_currency_id:
                amount_currency = line.amount
                line_amount = line.amount * conversion_rate
            write_off_line_vals.append({
                    **self._get_withholding_move_line_default_values(),
                    'name': line.name,
                    'account_id': account_id,
                    'amount_currency': sign * amount_currency,
                    'balance': sign * line_amount,
                    # este campo no existe mas
                    # 'tax_base_amount': sign * line.base_amount,
                    'tax_repartition_line_id': tax_repartition_line_id,
            })
            _logger.info(write_off_line_vals)
        for base_amount in list(set(self.l10n_ar_withholding_line_ids.mapped('base_amount'))):
            withholding_lines = self.l10n_ar_withholding_line_ids.filtered(lambda x: x.base_amount == base_amount)
            nice_base_label = ','.join(withholding_lines.filtered('name').mapped('name'))
            account_id = self.company_id.l10n_ar_tax_base_account_id.id
            base_amount = sign * base_amount
            base_amount_currency = self.currency_id.round(base_amount / conversion_rate)
            if self.currency_id != self.company_currency_id:
                base = base_amount
                base_amount = base * conversion_rate
                base_amount_currency = base
            write_off_line_vals.append({
                **self._get_withholding_move_line_default_values(),
                'name': _('Base Ret: ') + nice_base_label,
                'tax_ids': [Command.set(withholding_lines.mapped('tax_id').ids)],
                'account_id': account_id,
                'balance': base_amount,
                'amount_currency': base_amount_currency,
            })
            write_off_line_vals.append({
                **self._get_withholding_move_line_default_values(),  # Counterpart 0 operation
                'name': _('Base Ret Cont: ') + nice_base_label,
                'account_id': account_id,
                'balance': -base_amount,
                'amount_currency': -base_amount_currency,
            })
            _logger.info(write_off_line_vals)

        return write_off_line_vals
    

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):

        res = super()._prepare_move_line_default_vals(write_off_line_vals, force_balance=force_balance)
    
        wth_amount = sum(self.l10n_ar_withholding_line_ids.mapped('amount'))
        wth_amount_currency = wth_amount
        if self.currency_id != self.company_currency_id:
            wth_amount = wth_amount * self.exchange_rate
    
        valid_account_types = self._get_valid_payment_account_types()
        _logger.info(f'Preparing withholdings: {wth_amount},{wth_amount_currency}')

        # 🔹 Obtener el `amount_currency` correcto de la primera línea
        if res:
            first_line = res[0]  # Primera línea que tiene el valor correcto
            correct_amount_currency = first_line.get('amount_currency', 0.0)
            correct_debit = first_line.get('debit', 0.0)
            correct_credit = first_line.get('credit', 0.0)
            _logger.info(f"Using amount_currency from first line: {correct_amount_currency}")
    
        # 🔹 Aplicar el valor correcto a todas las líneas antes de sumar la retención
        for line in res:
            account_id = self.env['account.account'].browse(line['account_id'])
            if account_id.account_type in valid_account_types:
                _logger.info(f"Corrigiendo amount_currency de {line['amount_currency']} a {correct_amount_currency}")
                
    
                # 🔹 Ajustar también `debit` o `credit` con base en la línea correcta
                _logger.info(f"Payment_type: {self.payment_type}")
                if self.payment_type == 'inbound':
                    line['amount_currency'] = -correct_amount_currency
                    line['credit'] = correct_debit
                elif self.payment_type == 'outbound':
                    line['amount_currency'] = -correct_amount_currency
                    line['debit'] = correct_credit
        # Obtener líneas de retención existentes
        withholding_vals = self._prepare_witholding_write_off_vals()
        existing_accounts = {line['account_id']: line for line in res}

        # Actualizar líneas en res sin duplicar
        for line in withholding_vals:
            if line['account_id'] in existing_accounts:
                existing_accounts[line['account_id']]['balance'] = line['balance']
                existing_accounts[line['account_id']]['amount_currency'] = line['amount_currency']
            else:
                res.append(line)  # Solo agrega si no existe ya
    
        # Ajustar montos en las líneas de pago existentes para que cuadren con las retenciones
        for line in res:
            account_id = self.env['account.account'].browse(line['account_id'])
            
            if account_id.account_type in valid_account_types:
                _logger.info(f'Line to add: {str(line)}')
                if self.payment_type == 'inbound':
                    line['credit'] += wth_amount
                    line['amount_currency'] -= wth_amount_currency
                elif self.payment_type == 'outbound':
                    line['debit'] += wth_amount
                    line['amount_currency'] += wth_amount_currency
                
            _logger.info(f'Final line: {str(line)}')
        return res
        
    @api.depends('l10n_ar_withholding_line_ids.amount')
    def _compute_withholdings_amount(self):
        for rec in self:
            total_withholdings = sum(rec.l10n_ar_withholding_line_ids.mapped('amount'))
            if rec.currency_id == rec.company_currency_id: 
                rec.withholdings_amount = total_withholdings
            else:
                rec.withholdings_amount = total_withholdings * rec.exchange_rate
            rec.withholdings_amount = total_withholdings
            
 
        