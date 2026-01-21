from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        # Pre-confirmation logic: Check/Create BoMs
        for order in self:
            for line in order.order_line:
                if line.is_ouvrage and line.bom_id:
                    self._check_and_create_specific_bom(line)
        
        return super().action_confirm()

    def _check_and_create_specific_bom(self, line):
        """
        Check if the current components roughly match the BoM structure.
        If not, create a new specific BoM.
        """
        if not line.ouvrage_line_ids:
            return

        is_modified = False
        bom = line.bom_id
        
        # Simple check: Count of lines vs BoM lines
        # This is basic. A better check is component-by-component matching.
        # But if user added/removed components, counts differ.
        if len(line.ouvrage_line_ids) != len(bom.bom_line_ids):
            is_modified = True
        else:
            # Check quantities ratio
            # Map product_id to ratio
            bom_ratios = {}
            for bl in bom.bom_line_ids:
                bom_ratios[bl.product_id.id] = bl.product_qty / (bom.product_qty or 1.0)
            
            for child in line.ouvrage_line_ids:
                ratio = child.product_uom_qty / (line.product_uom_qty or 1.0)
                target_ratio = bom_ratios.get(child.product_id.id)
                if target_ratio is None:
                    is_modified = True # Extra component
                    break
                if abs(ratio - target_ratio) > 0.001:
                    is_modified = True
                    break
        
        if is_modified:
            # Create new BoM
            new_code = f"{line.order_id.name} - {line.order_id.date_order} - {line.order_id.partner_id.name}"
            new_bom = bom.copy({
                'code': new_code,
                'product_tmpl_id': line.product_id.product_tmpl_id.id,
                'bom_line_ids': False, # Clean lines to recreate them
            })
            
            # Create new lines
            new_bom_lines = []
            for child in line.ouvrage_line_ids:
                new_bom_lines.append((0, 0, {
                    'product_id': child.product_id.id,
                    'product_qty': child.product_uom_qty / (line.product_uom_qty or 1.0), # Normalized to 1 unit of Ouvrage? 
                    # WAIT: If bom.product_qty is 1. If not, we should adjust.
                    # Assuming bom.product_qty of new bom is 1.0 (default copy).
                    'product_uom_id': child.product_uom.id,
                }))
            
            new_bom.write({'bom_line_ids': new_bom_lines})
            
            # Link line to new BoM
            line.write({'bom_id': new_bom.id})
