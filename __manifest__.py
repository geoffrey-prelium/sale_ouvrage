{
    'name': 'Sale Ouvrage (Construction Works)',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Manage Construction Works (Ouvrages) in Sales',
    'description': """
        This module allows defining "Ouvrages" (Works) which are products composed of other products (BoM).
        It adds features to hide prices or structure of the ouvrage in sales orders and reports.
    """,
    'depends': ['sale_management', 'mrp', 'sale_margin'],
    'data': [
        'views/product_template_views.xml',
        'views/mrp_bom_views.xml',
        'views/sale_order_views.xml',
        'wizard/ouvrage_configurator_views.xml',
        'reports/sale_report_templates.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
