from odoo import models, fields, api

class OuvrageConfigurator(models.TransientModel):
    _name = 'sale.ouvrage.configurator'
    _description = 'Wizard to configure Ouvrage components'

    sale_line_id = fields.Many2one('sale.order.line', string="Ligne de vente", required=True)
    product_id = fields.Many2one('product.product', related='sale_line_id.product_id', readonly=True)
    bom_id = fields.Many2one('mrp.bom', string="Nomenclature")
    
    # Configuration fields
    hide_prices = fields.Boolean(string="Masquer les prix")
    hide_structure = fields.Boolean(string="Masquer la structure")

    # Metrics (Readonly for reference or editable?)
    qty = fields.Float(related='sale_line_id.product_uom_qty', readonly=False, string="Quantité Ouvrage")
    
    component_ids = fields.One2many('sale.ouvrage.component', 'wizard_id', string="Composants")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_sale_line_id'):
            line = self.env['sale.order.line'].browse(self.env.context['default_sale_line_id'])
            # Load components
            component_vals = []
            for child in line.ouvrage_line_ids:
                component_vals.append((0, 0, {
                    'product_id': child.product_id.id,
                    'quantity': child.product_uom_qty,
                    'price_unit': child.price_unit,
                    'cost': child.purchase_price,
                    'discount': child.discount,
                }))
            
            res.update({
                'bom_id': line.bom_id.id,
                'hide_prices': line.hide_prices,
                'hide_structure': line.hide_structure,
                'component_ids': component_vals,
            })
        return res

    @api.onchange('bom_id')
    def _onchange_bom_id(self):
        # User requirement: "A partie du moment ou j'ai sélectionné une nomenclature, les composants doivent être figés"
        # Implies we don't auto-reload unless initialized? 
        # But "Un champ 'nomenclature' ... J'ai la possibilité d'en sélectionner un autre, dans ce cas les composants sont recalculés par rapport à cette nomenclature."
        if self.bom_id:
             self.hide_prices = self.bom_id.hide_prices
             self.hide_structure = self.bom_id.hide_structure
             # Reload components from BoM
             lines = []
             factor = self.qty or 1.0
             for bom_line in self.bom_id.bom_line_ids:
                lines.append((0, 0, {
                    'product_id': bom_line.product_id.id,
                    'quantity': bom_line.product_qty * factor,
                    'price_unit': bom_line.product_id.list_price, # or standard calculation
                    'cost': bom_line.product_id.standard_price,
                    'discount': 0.0,
                }))
             self.component_ids = [(5, 0, 0)] + lines # Clear and add

    def action_initialize(self):
        self._onchange_bom_id()

    def action_save(self):
        self.ensure_one()
        line = self.sale_line_id
        
        # 1. Update Parent fields
        line.write({
            'hide_prices': self.hide_prices,
            'hide_structure': self.hide_structure,
            'product_uom_qty': self.qty,
            'bom_id': self.bom_id.id,
        })
        
        # 2. Sync Components
        # Strategy: Delete all existing children and recreate. 
        # This is destructive but ensures exact match with wizard.
        # Check if line is locked/confirmed? Assuming Draft/Sent state.
        line.ouvrage_line_ids.unlink()
        
        new_children = []
        for comp in self.component_ids:
            new_children.append({
                'order_id': line.order_id.id,
                'product_id': comp.product_id.id,
                'product_uom_qty': comp.quantity,
                'price_unit': comp.price_unit,
                'purchase_price': comp.cost,
                'discount': comp.discount,
                'ouvrage_parent_line_id': line.id,
                'sequence': line.sequence + 1,
            })
        
        if new_children:
            self.env['sale.order.line'].create(new_children)

        return {'type': 'ir.actions.act_window_close'}

class OuvrageComponent(models.TransientModel):
    _name = 'sale.ouvrage.component'
    _description = 'Temporary component line for wizard'

    wizard_id = fields.Many2one('sale.ouvrage.configurator', string="Wizard")
    product_id = fields.Many2one('product.product', string="Produit", required=True)
    quantity = fields.Float(string="Quantité", default=1.0)
    price_unit = fields.Float(string="Prix Unitaire")
    cost = fields.Float(string="Coût")
    discount = fields.Float(string="Remise (%)")
    
    margin = fields.Float(string="Marge", compute='_compute_margin')
    margin_percent = fields.Float(string="Marge %", compute='_compute_margin')

    @api.depends('price_unit', 'cost', 'quantity', 'discount')
    def _compute_margin(self):
        for line in self:
            price_effective = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.margin = (price_effective - line.cost) * line.quantity
            if price_effective:
                line.margin_percent = (price_effective - line.cost) / price_effective
            else:
                line.margin_percent = 0.0
