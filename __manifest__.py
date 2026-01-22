{
    'name': 'Sale Ouvrage (Construction Works)',
    'version': '1.2',
    'author': 'Prelium',
    'category': 'Sales',
    'summary': 'Manage Construction Works (Ouvrages) in Sales',
    'description': """
        This module allows defining "Ouvrages" (Works) which are products composed of other products (BoM).
        It adds features to hide prices or structure of the ouvrage in sales orders and reports.
    """,
    'depends': ['sale_management', 'mrp', 'sale_margin'],
    'data': [
        'security/ir.model.access.csv',
        'reports/sale_report_templates.xml',
        'views/product_template_views.xml',
        'views/mrp_bom_views.xml',
        'views/sale_order_views.xml',
        'views/sale_portal_templates.xml',
        'wizard/ouvrage_configurator_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sale_ouvrage/static/src/js/sale_ouvrage_renderer.js',
            'sale_ouvrage/static/src/xml/sale_ouvrage_renderer.xml',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
