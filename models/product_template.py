from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_ouvrage = fields.Boolean(string="Est un ouvrage", help="Check this box if this product is a construction work (Ouvrage).")
