from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import RedirectWarning, UserError
import logging

_logger = logging.getLogger(__name__)
class l10nArPaymentRegisterWithholding(models.Model):
    _inherit = 'l10n_ar.payment.withholding'
    

    multiple_payment_id = fields.Many2one('account.payment.group', required=False, ondelete='cascade')
    payment_id = fields.Many2one('account.payment', required=False, ondelete='cascade')
    partner_type = fields.Selection(
        compute='_compute_payment_related_fields',
        store=True,
    )
    
    company_id = fields.Many2one(
        'res.company',
        compute='_compute_payment_related_fields',
        store=True,
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_payment_related_fields',
        store=True,
    )
    
    @api.depends(
        'payment_id',
        'multiple_payment_id',
    )
    def _compute_payment_related_fields(self):
        for rec in self:
            pay = rec._get_payment_source()
            _logger.info(pay)
            rec.company_id = pay.company_id
            rec.partner_type = pay.partner_type
            rec.currency_id = pay.company_currency_id

    def _get_payment_source(self):
        return self.payment_id or self.multiple_payment_id


    def _compute_base_amount(self):
        """practicamente mismo codigo que en l10n_ar.payment.register.withholding pero usamos campos "selected_debt_"""
        _logger.info("Compute base amount!")
        for wth in self:
            pay = wth._get_payment_source()
            pay._compute_to_pay_amount()
        for wth in self.filtered(lambda x: x._get_payment_source().partner_type == "supplier"):
            pay = wth._get_payment_source()
            _logger.info("Source detectada")
            _logger.info(pay)
            # calculamos advance_amount
            # si el adelanto es negativo estamos pagando parcialmente una
            # factura y ocultamos el campo sin impuesto y el metodo _get_withholdable_advanced_amount nos devuelve
            # el proporcional descontando de el iva a lo que se esta pagando
            advance_amount = pay.withholdable_advanced_amount
            tax = wth._get_withholding_tax()
            if advance_amount < 0.0 and pay.to_pay_move_line_ids:
                sorted_to_pay_lines = sorted(pay.to_pay_move_line_ids, key=lambda a: a.date_maturity or a.date)
    
                # last line to be reconciled
                partial_line = sorted_to_pay_lines[-1]
    
                # Comparar en moneda B (ambos lados)
                if pay.destination_currency_id and pay.destination_currency_id != pay.company_currency_id:
                    line_residual = abs(partial_line.amount_residual_currency)
                else:
                    line_residual = abs(partial_line.amount_residual)
    
                if line_residual < abs(pay.withholdable_advanced_amount):
                    raise UserError(
                        _(
                            "Seleccionó deuda por %s pero aparentemente desea pagar %s. En la deuda seleccionada hay algunos comprobantes de mas que no van a poder ser pagados (%s). Deberá quitar dichos comprobantes de la deuda seleccionada para poder hacer el correcto cálculo de las retenciones."
                        )
                        % (
                            pay.selected_debt,
                            pay.to_pay_amount,
                            partial_line.move_id.display_name,
                        )
                    )
                advance_amount = pay.unreconciled_amount
                if tax.l10n_ar_tax_type != "iibb_total":
                    advance_amount = advance_amount * (pay.selected_debt_untaxed / pay.selected_debt)
    
            if tax.l10n_ar_tax_type == "iibb_total":
                base_in_b = pay.selected_debt + advance_amount
            else:
                base_in_b = pay.selected_debt_untaxed + advance_amount
    
            # base_amount siempre en C (ARS): convertir de B a C usando la tasa del pago
            wth.base_amount = pay.company_currency_id.round(base_in_b * pay._get_withholding_rate())
            _logger.info(wth.base_amount)
        # esto lo hicimos así para soportar el caso de una posición fiscal que tenga más de un impuesto con ratio,
        # pero actualmente una misma posicion fiscal no puedo agregar 2 impuestos del mismo grupo (ej VAT Withholding)
        # Lo dejamos por el momento con la aclaración por si en un futuro sacamos la constraint de los grupos de impuestos.
        for wth in self.filtered(lambda x: x.tax_id.amount_type == "percent" and x.tax_id.ratio != 100):
            wth.base_amount *= wth.tax_id.ratio / 100

    def _tax_compute_all_helper(self):
        """practicamente mismo codigo que en l10n_ar.payment.register.withholding"""
        self.ensure_one()
        # Computes the withholding tax amount provided a base and a tax
        # It is equivalent to: amount = self.base * self.tax_id.amount / 100
        tax = self._get_withholding_tax()
        if not tax.amount_type:
            raise UserError(
                _(
                    "El impuesto de retención %s no tiene un tipo de cálculo definido. Por favor, defina el tipo de cálculo en la configuración del impuesto."
                )
                % tax.name
            )

        pay = self._get_payment_source()
        company_currency = pay.company_currency_id

        # base_amount ya está en C (ARS) — no se necesita conversión
        # Para ganancias: sumar acumulados del período (ya en C)
        if tax.l10n_ar_tax_type in ["earnings", "earnings_scale"]:
            same_period_withholdings = self._get_same_period_withholdings_amount()
            same_period_base = self._get_same_period_base_amount()
            net_amount = self.base_amount + same_period_base  # C + C = C
            # por ahora l10n_ar_non_taxable_amount lo estamos usando solo en ganancias (ligado al acumulado)
            # si llega a ser necesario para otros taxes, ademas de mostrarlo en UI tenemos que mover este código
            net_amount = max(0, net_amount - tax.l10n_ar_non_taxable_amount)
        else:
            net_amount = self.base_amount

        # compute_all SIEMPRE en ARS (C)
        taxes_res = tax.compute_all(
            net_amount,
            currency=company_currency,
            quantity=1.0,
            product=False,
            partner=False,
            is_refund=False,
            rounding_method="round_per_line",
        )
        _logger.info(taxes_res)
        tax_amount = taxes_res["taxes"][0]["amount"]
        tax_account_id = taxes_res["taxes"][0]["account_id"]
        tax_repartition_line_id = taxes_res["taxes"][0]["tax_repartition_line_id"]

        # Ref: usar company_currency para formatear (montos en ARS)
        ref = False
        if tax.l10n_ar_tax_type in ["earnings", "earnings_scale"]:
            f = company_currency.format
            if net_amount <= 0:
                ref = f"{f(self.base_amount)} + {f(same_period_base)} - {f(tax.l10n_ar_non_taxable_amount)} = {f(self.base_amount + same_period_base - tax.l10n_ar_non_taxable_amount)} (no corresponde aplicar)"
            # if it is earnings scale we calculate according to the scale.
            if tax.l10n_ar_tax_type == "earnings_scale":
                if not tax.l10n_ar_scale_id:
                    raise RedirectWarning(
                        _(
                            "El impuesto de retención '%s' (id: %s) es de tipo escala de ganancias y no tiene definida una escala (campo l10n_ar_scale_id). Por favor, defina una escala en la configuración del impuesto."
                        )
                        % (tax.name, tax.id),
                        {
                            "view_mode": "form",
                            "res_model": "account.tax",
                            "type": "ir.actions.act_window",
                            "res_id": tax.id,
                            "views": [[False, "form"]],
                        },
                        _("Configurar impuesto"),
                    )
                escala = self.env["l10n_ar.earnings.scale.line"].search(
                    [
                        ("scale_id", "=", tax.l10n_ar_scale_id.id),
                        ("excess_amount", "<=", net_amount),
                        ("to_amount", ">", net_amount),
                    ],
                    limit=1,
                )
                tax_amount = ((net_amount - escala.excess_amount) * escala.percentage / 100) + escala.fixed_amount
                ref = (
                    ref
                    or f"({f(self.base_amount)} + {f(same_period_base)} - {f(tax.l10n_ar_non_taxable_amount)} - {f(escala.excess_amount)}) * {escala.percentage}% + {f(escala.fixed_amount)} - {f(same_period_withholdings)}"
                )
            else:
                ref = f"({f(self.base_amount)} + {f(same_period_base)} - {f(tax.l10n_ar_non_taxable_amount)}) * {tax.amount}% - {f(same_period_withholdings)}"
            # deduct withholdings from the same period
            tax_amount -= same_period_withholdings

        # Gates para no-ganancias (IIBB y otros reg.): orden normativo definido en spec.
        if tax.l10n_ar_tax_type not in ["earnings", "earnings_scale"]:
            # 1) Gate por pago: si el total del pago no supera el mínimo, no se practica.
            if tax.l10n_ar_payment_minimum_threshold:
                if self._get_payment_source().to_pay_amount <= tax.l10n_ar_payment_minimum_threshold:
                    return 0.0, tax_account_id, tax_repartition_line_id, False
            # 2) Gate por base: si la base calculada no supera el mínimo, no se practica.
            if tax.l10n_ar_base_minimum_threshold:
                if self.base_amount <= tax.l10n_ar_base_minimum_threshold:
                    return 0.0, tax_account_id, tax_repartition_line_id, False

        # 3) Mínimo de importe: si el importe calculado es menor al umbral, se anula.
        l10n_ar_minimum_threshold = tax.l10n_ar_minimum_threshold
        if l10n_ar_minimum_threshold > tax_amount:
            tax_amount = 0.0
        return tax_amount, tax_account_id, tax_repartition_line_id, ref

    @api.depends("base_amount", "tax_id")
    def _compute_amount(self):
        _logger.info("Compute amount!")
        for line in self.filtered(lambda r: r._get_payment_source().partner_type == "supplier"):
            # TODO: usar _get_withholding_tax no deberia ser necesario
            # si al pasar a draft modificamos la linea
            tax_id = line._get_withholding_tax()
            _logger.info(tax_id)
            if not tax_id:
                line.amount = 0.0
                line.ref = False
            if line.tax_id.l10n_ar_tax_type == "earnings":
                _logger.info("Earnings")
                amount, ref = line._earnings_compute_helper()
                line.amount = amount
                line.ref = ref
                _logger.info(line.amount,line.ref)
                continue
            else:
                tax_amount, __, __, ref = line._tax_compute_all_helper()
                line.amount = tax_amount
                line.ref = ref

    ########################
    # EARNING COMPUTE HELPERS
    ########################

    def _get_same_period_dates(self):
        self.ensure_one()
        to_date = self._get_payment_source().date or fields.Date.context_today(self)
        from_date = to_date + relativedelta(day=1)
        _logger.info(f"{from_date},{to_date}")
        return to_date, from_date

    def _get_same_period_withholdings_domain(self):
        """Returns a heritable domain of earnings withholdings that
        belong to the same regime, same commercial partner,
        and from the month of payment between the 1st and the day of payment.
        """
        self.ensure_one()
        to_date, from_date = self._get_same_period_dates()
        tax_id = self._get_withholding_tax()
        return [
            *self.env["account.move.line"]._check_company_domain(tax_id.company_id),
            ("parent_state", "=", "posted"),
            ("tax_line_id.l10n_ar_code", "=", tax_id.l10n_ar_code),
            ("tax_line_id.l10n_ar_tax_type", "in", ["earnings", "earnings_scale"]),
            ("partner_id", "=", self._get_payment_source().partner_id.commercial_partner_id.id),
            ("date", "<=", to_date),
            ("date", ">=", from_date),
        ]

    def _get_same_period_withholdings_amount(self):
        """Return Cummulated withholding amount"""
        self.ensure_one()
        # We search for the payments in the same month of the same regimen and the same code.
        domain_same_period_withholdings = self._get_same_period_withholdings_domain()
        _logger.info(domain_same_period_withholdings)
        if same_period_partner_withholdings := self.env["account.move.line"]._read_group(
            domain_same_period_withholdings, ["partner_id"], ["balance:sum"]
        ):
            return abs(same_period_partner_withholdings[0][1])
        return 0.0

    def _get_same_period_base_domain(self):
        """Returns a heritable domain of earnings bases that
        belong to the same regime, same commercial partner,
        and from the month of payment between the 1st and the day of payment.
        """
        self.ensure_one()
        to_date, from_date = self._get_same_period_dates()
        tax_id = self._get_withholding_tax()
        return [
            *self.env["account.move.line"]._check_company_domain(tax_id.company_id),
            ("parent_state", "=", "posted"),
            ("tax_ids.l10n_ar_code", "=", tax_id.l10n_ar_code),
            ("tax_ids.l10n_ar_tax_type", "in", ["earnings", "earnings_scale"]),
            ("partner_id", "=", self._get_payment_source().partner_id.commercial_partner_id.id),
            ("date", "<=", to_date),
            ("date", ">=", from_date),
        ]

    def _get_same_period_base_amount(self):
        """Return Cummulated withholding base"""
        self.ensure_one()
        domain_same_period_base = self._get_same_period_base_domain()
        _logger.info(domain_same_period_base)
        if same_period_partner_base := self.env["account.move.line"]._read_group(
            domain_same_period_base, ["partner_id"], ["balance:sum"]
        ):
            return abs(same_period_partner_base[0][1])
        return 0.0

    def _get_withholding_tax(self):
        _logger.warning("GET WITHHOLDING TAX CALLED")
        self.ensure_one()
    
        pay = self._get_payment_source()
        partner = pay.partner_id
        date = pay.date
    
        fp = partner.property_account_position_id
    
        if not fp:
            return self.tax_id
    
        fp_tax = self.env["account.fiscal.position.l10n_ar_tax"].search([
            ("fiscal_position_id", "=", fp.id),
            ("tax_type", "=", "withholding"),
            ("default_tax_id", "=", self.tax_id.id),
        ], limit=1)
        _logger.info(f"Fiscal position tax? {fp_tax}")
        if fp_tax:
            taxes = fp_tax._get_missing_taxes(partner, date)
            _logger.info(taxes)
            if taxes:
                return taxes[0]
        
        return self.tax_id
    
    #def _get_withholding_tax(self):
    #    """Return the applicable withheld tax"""
    #    self.ensure_one()
    #    return self.tax_id


    def _earnings_compute_helper(self):
        self.ensure_one()
    
        tax = self.tax_id
        partner = self._get_payment_source().partner_id
        company_currency = self._get_payment_source().company_currency_id
    
        regimen = partner.default_regimen_ganancias_id
    
        if not regimen:
            return 0.0, False
    
        same_period_withholdings = self._get_same_period_withholdings_amount()
        same_period_base = self._get_same_period_base_amount()
    
        non_taxable_amount = regimen.montos_no_sujetos_a_retencion
    
        net_amount = self.base_amount + same_period_base
        taxable_amount = max(0.0, net_amount - non_taxable_amount)
    
        f = company_currency.format
    
        if taxable_amount <= 0:
            ref = (
                f"{f(self.base_amount)} + "
                f"{f(same_period_base)} - "
                f"{f(non_taxable_amount)} = "
                f"{f(net_amount - non_taxable_amount)} "
                f"(no corresponde aplicar)"
            )
            return 0.0, ref
    
        aliquot = (
            regimen.porcentaje_inscripto
            if partner.imp_ganancias_padron == "AC"
            else regimen.porcentaje_no_inscripto
        )
    
        tax_amount = (taxable_amount * aliquot / 100.0) - same_period_withholdings
    
        tax_amount = max(0.0, tax_amount)
    
        ref = (
            f"({f(self.base_amount)} + "
            f"{f(same_period_base)} - "
            f"{f(non_taxable_amount)}) "
            f"* {aliquot}% - "
            f"{f(same_period_withholdings)}"
        )
    
        return tax_amount, ref