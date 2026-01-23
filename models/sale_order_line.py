from odoo import models, fields, api, _

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_ouvrage = fields.Boolean(related='product_id.is_ouvrage', string="Est un ouvrage", readonly=True)
    ouvrage_parent_line_id = fields.Many2one('sale.order.line', string="Ligne Ouvrage Parente", ondelete='cascade')
    ouvrage_line_ids = fields.One2many('sale.order.line', 'ouvrage_parent_line_id', string="Composants de l'ouvrage")
    
    # Fields from BoM
    hide_prices = fields.Boolean(string="Masquer les prix")
    hide_structure = fields.Boolean(string="Masquer la structure")
    bom_id = fields.Many2one('mrp.bom', string="Nomenclature")

    # Metrics for Ouvrage/Components
    ouvrage_margin = fields.Monetary(string="Marge", compute='_compute_ouvrage_margin', store=True)
    ouvrage_margin_pct = fields.Float(string="Marge %", compute='_compute_ouvrage_margin', store=True)

    @api.depends('price_subtotal', 'purchase_price', 'ouvrage_line_ids.price_subtotal', 'ouvrage_line_ids.purchase_price')
    def _compute_ouvrage_margin(self):
        for line in self:
            if line.is_ouvrage:
                # Margin for Ouvrage is sum of margins (or Price - Cost)
                # But typically margin is Price - Cost.
                # Cost of Ouvrage = Sum(Cost of components)
                # Price of Ouvrage = Sum(Price of components)
                current_cost = sum(child.purchase_price * child.product_uom_qty for child in line.ouvrage_line_ids)
                current_price = line.price_subtotal 
                # Note: price_subtotal is Unit Price * Qty usually, but for Ouvrage, Unit Price is sum of components unit prices.
                
                line.ouvrage_margin = current_price - current_cost
                if current_price:
                    line.ouvrage_margin_pct = (line.ouvrage_margin / current_price) * 100
                else:
                    line.ouvrage_margin_pct = 0.0
            else:
                line.ouvrage_margin = line.margin
                line.ouvrage_margin_pct = line.margin_percent

    @api.onchange('product_id')
    def _onchange_product_id_ouvrage(self):
        if self.product_id and self.product_id.is_ouvrage:
            # Find BoM
            bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', self.product_id.product_tmpl_id.id)], limit=1)
            if bom:
                self.bom_id = bom.id
                self.hide_prices = bom.hide_prices
                self.hide_structure = bom.hide_structure
                
                # Calculate initial price from BoM
                price = 0.0
                for bom_line in bom.bom_line_ids:
                    price += bom_line.product_id.list_price * bom_line.product_qty
                self.price_unit = price

    def action_configure_ouvrage(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Configuration Ouvrage',
            'res_model': 'sale.ouvrage.configurator',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_line_id': self.id,
                'default_qty': self.product_uom_qty,
            }
        }

    def write(self, values):
        # Handle Scaling
        if 'product_uom_qty' in values and len(self) == 1 and self.is_ouvrage:
            old_qty = self.product_uom_qty
            new_qty = values['product_uom_qty']
            if old_qty != 0 and new_qty != old_qty:
                ratio = new_qty / old_qty
                # Scale components
                for child in self.ouvrage_line_ids:
                    new_child_qty = child.product_uom_qty * ratio
                    child.write({'product_uom_qty': new_child_qty})
        
        res = super().write(values)
        
        # Trigger price recompute if components changed
        # This is a fallback if onchanges didn't catch it
        if self.is_ouvrage and not self.env.context.get('skip_ouvrage_price_update'):
             self._recompute_ouvrage_price()
             
        return res

    def _recompute_ouvrage_price(self):
        for line in self:
            if not line.ouvrage_line_ids:
                continue
            total_price = sum(child.price_subtotal for child in line.ouvrage_line_ids)
            # price_unit should be total / line.qty
            if line.product_uom_qty:
                new_unit_price = total_price / line.product_uom_qty
                if abs(line.price_unit - new_unit_price) > 0.01:
                    line.with_context(skip_ouvrage_price_update=True).write({'price_unit': new_unit_price})

    @api.model_create_multi
    def create(self, vals_list):
        # 1. Ensure BoM is found for Ouvrage lines if not set
        for vals in vals_list:
            if vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                if product.is_ouvrage and not vals.get('bom_id'):
                    bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', product.product_tmpl_id.id)], limit=1)
                    if bom:
                        vals['bom_id'] = bom.id
                        vals['hide_prices'] = bom.hide_prices
                        vals['hide_structure'] = bom.hide_structure
                        # Calculate price from BoM if not set
                        if 'price_unit' not in vals:
                            price = 0.0
                            for bom_line in bom.bom_line_ids:
                                price += bom_line.product_id.list_price * bom_line.product_qty
                            vals['price_unit'] = price

        lines = super().create(vals_list)
        
        # 2. Explode
        for line in lines:
            if line.is_ouvrage and line.bom_id:
                line._explode_ouvrage()
                
        return lines

    def _explode_ouvrage(self):
        """
        Creates component lines from the BoM using the current Ouvrage Quantity.
        Does NOT remove existing lines.
        """
        self.ensure_one()
        if not self.is_ouvrage or not self.bom_id:
            return

        lines_values = []
        factor = self.product_uom_qty or 1.0
        
        for bom_line in self.bom_id.bom_line_ids:
            qty = bom_line.product_qty * factor
            name_indented = f"    > {bom_line.product_id.display_name}"
            
            vals = {
                'order_id': self.order_id.id,
                'product_id': bom_line.product_id.id,
                'name': name_indented, # Visual Indentation
                'product_uom_qty': qty,
                'product_uom_id': bom_line.product_uom_id.id,
                'ouvrage_parent_line_id': self.id,
                'sequence': self.sequence + 1, 
            }
            lines_values.append(vals)

        for val in lines_values:
            self.env['sale.order.line'].create(val)
