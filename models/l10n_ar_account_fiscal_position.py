from odoo.exceptions import UserError
from odoo import models

class AccountFiscalPositionL10nArTax(models.Model):
    _inherit = "account.fiscal.position.l10n_ar_tax"

    def _get_padron_data(self, partner, date, to_date):
        aliquot, ref = super()._get_padron_data(
            partner, date, to_date
        )

        if (
            self.webservice == "padron"
            and self.default_tax_id.l10n_ar_state_id.jurisdiction_code == "921"
            and aliquot is None
        ):
            raise UserError(
                _(
                    "El CUIT '%s' no fue encontrado en el padrón de Santa Fe "
                    "vigente para el período %s - %s.\n\n"
                    "Verifique el CUIT del proveedor o el archivo de padrón cargado."
                )
                % (partner.vat, date, to_date)
            )

        return aliquot, ref