from odoo.upgrade import util

def migrate(cr, version):
    util.rename_module(cr, 'account-payment-patch', 'account_payment_patch')
    util.rename_module(cr, 'account-payment-group', 'account_payment_group')