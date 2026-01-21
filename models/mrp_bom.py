from odoo import models, fields, api, exceptions

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    hide_prices = fields.Boolean(string="Masquer les prix par défaut")
    hide_structure = fields.Boolean(string="Masquer la structure par défaut")

    @api.constrains('bom_line_ids')
    def _check_ouvrage_recursion(self):
        for bom in self:
            for line in bom.bom_line_ids:
                if line.product_id.is_ouvrage:
                    raise exceptions.ValidationError("Il n'est pas possible d'ajouter des produits qui sont cochés 'Ouvrage' au niveau des composants de la nomenclature.")
