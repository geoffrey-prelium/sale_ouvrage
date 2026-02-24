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

    @api.depends('order_line.price_subtotal', 'currency_id', 'company_id', 'payment_term_id')
    def _compute_amounts(self):
        """
        Override to exclude Ouvrage lines from the total amount.
        We only want them to display a price locally but not impact the order total.
        """
        AccountTax = self.env['account.tax']
        for order in self:
            # Filter out Ouvrage lines from the total calculation
            order_lines = order.order_line.filtered(lambda x: not x.display_type and not x.is_ouvrage)
            
            base_lines = [line._prepare_base_line_for_taxes_computation() for line in order_lines]
            base_lines += order._add_base_lines_for_early_payment_discount()
            
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            
            tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )
            order.amount_untaxed = tax_totals['base_amount_currency']
            order.amount_tax = tax_totals['tax_amount_currency']
            order.amount_total = tax_totals['total_amount_currency']

    @api.depends('order_line.price_subtotal', 'currency_id', 'company_id', 'payment_term_id')
    def _compute_tax_totals(self):
        """
        Override to exclude Ouvrage lines from the tax totals computation.
        This fixes the display in the portal and reports.
        """
        AccountTax = self.env['account.tax']
        for order in self:
            # Filter out Ouvrage lines
            order_lines = order.order_line.filtered(lambda x: not x.display_type and not x.is_ouvrage)
            
            base_lines = [line._prepare_base_line_for_taxes_computation() for line in order_lines]
            base_lines += order._add_base_lines_for_early_payment_discount()
            
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            
            order.tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )

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
        if len(line.ouvrage_line_ids) != len(bom.bom_line_ids):
            is_modified = True
        else:
            # Check quantities ratio
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
            # Naming format: Order Name + Date + Customer
            date_str = line.order_id.date_order.strftime('%Y-%m-%d') if line.order_id.date_order else ''
            new_code = f"{line.order_id.name} - {date_str} - {line.order_id.partner_id.name}"
            
            new_bom = bom.copy({
                'code': new_code,
                'product_tmpl_id': line.product_id.product_tmpl_id.id,
                'bom_line_ids': False, # Clean lines to recreate them
                'sequence': 9999, # Push to bottom as requested
            })
            
            # Create new lines
            new_bom_lines = []
            for child in line.ouvrage_line_ids:
                new_bom_lines.append((0, 0, {
                    'product_id': child.product_id.id,
                    'product_qty': child.product_uom_qty / (line.product_uom_qty or 1.0),
                    'product_uom_id': child.product_uom.id if hasattr(child, 'product_uom') else child.product_uom_id.id if hasattr(child, 'product_uom_id') else False,
                }))
            
            new_bom.write({'bom_line_ids': new_bom_lines})
            
            # Link line to new BoM
            line.write({'bom_id': new_bom.id})
