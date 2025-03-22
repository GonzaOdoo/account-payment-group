# -*- coding: utf-8 -*-
{
    'name': "Account Payment with multiple methods",

    'summary': """
        Este modulo permite usar multiples metodos de pago en una sola orden""",

    'description': """
        Este modulo permite usar multiples metodos de pago en una sola orden
    """,

    'author': "OutsourceArg",
    'website': "http://www.outsourcearg.com",
    "license": "AGPL-3",
    'installable': True,
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Payment',
    'version': '17.0.0.1',

    # any module necessary for this one to work correctly
    "external_dependencies": {
        "python": [],
        "bin": [], 
    }, 
    "depends": [
        "account",
        "account_payment_pro",
        "l10n_ar_withholding_ux",
        "l10n_ar_account_withholding", 
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/account_payment_group_views.xml',
        'views/account_payment_register.xml',
        'views/account_move_views.xml',
        'reports/report_withholdings_template.xml',
        'reports/report_payment_with_withholdings.xml',
        'views/account_journal_views.xml',
        'views/account_existing_payment_wizard.xml',
        'data/accoun_move_actions.xml',
        'data/ir_sequence.xml'
    ],
    'post_init_hook': 'create_sequences',
}