from odoo import models
import re


class ResCompanyJurisdictionPadron(models.Model):
    _inherit = "res.company.jurisdiction.padron"

    def _read_parp_lines(self, lines, cuit):
        aliquot_ret = False
        aliquot_per = False
        is_in_padron = False

        normalized_cuit = re.sub(r"\D", "", str(cuit or ""))

        for line in lines:
            if not line:
                continue

            values = [value.strip() for value in line.split(";")]

            if len(values) <= 8:
                continue

            padron_cuit = re.sub(r"\D", "", values[3])

            if padron_cuit == normalized_cuit:
                aliquot_per = float(values[7].replace(",", "."))
                aliquot_ret = float(values[8].replace(",", "."))
                is_in_padron = True
                break

        return is_in_padron, aliquot_ret, aliquot_per