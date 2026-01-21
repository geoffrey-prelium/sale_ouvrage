from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError

class TestSaleOuvrage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Product = self.env['product.product']
        self.Bom = self.env['mrp.bom']
        self.SaleOrder = self.env['sale.order']
        self.SaleOrderLine = self.env['sale.order.line']

        # Create Products
        self.product_ouvrage = self.Product.create({
            'name': 'Ouvrage A',
            'type': 'product',
            'is_ouvrage': True,
            'list_price': 100.0,
        })
        self.component_b = self.Product.create({
            'name': 'Component B',
            'type': 'product',
            'list_price': 10.0,
        })
        self.component_c = self.Product.create({
            'name': 'Component C',
            'type': 'product',
            'list_price': 20.0,
        })

        # Create BoM
        self.bom_ouvrage = self.Bom.create({
            'product_tmpl_id': self.product_ouvrage.product_tmpl_id.id,
            'product_qty': 1.0,
            'hide_prices': True,
            'bom_line_ids': [
                (0, 0, {'product_id': self.component_b.id, 'product_qty': 2.0}),
                (0, 0, {'product_id': self.component_c.id, 'product_qty': 1.0}),
            ]
        })

        self.partner = self.env['res.partner'].create({'name': 'Test Partner'})

    def test_ouvrage_creation_and_explosion(self):
        """ Test that adding an Ouvrage adds its components """
        so = self.SaleOrder.create({'partner_id': self.partner.id})
        
        # Add Ouvrage Line
        ouvrage_line = self.SaleOrderLine.create({
            'order_id': so.id,
            'product_id': self.product_ouvrage.id,
            'product_uom_qty': 1.0,
        })

        # Check explosion triggers
        # Since we overrode create, it should explode immediately
        self.assertEqual(len(ouvrage_line.ouvrage_line_ids), 2, "Should have 2 components")
        
        comp_b = ouvrage_line.ouvrage_line_ids.filtered(lambda l: l.product_id == self.component_b)
        self.assertEqual(comp_b.product_uom_qty, 2.0, "Component B quantity should be 2.0")
        
        # Check defaults
        self.assertTrue(ouvrage_line.hide_prices, "Should inherit hide_prices from BoM")

    def test_scaling_logic(self):
        """ Test logic: updating Ouvrage Qty updates Component Qty """
        so = self.SaleOrder.create({'partner_id': self.partner.id})
        ouvrage_line = self.SaleOrderLine.create({
            'order_id': so.id,
            'product_id': self.product_ouvrage.id,
            'product_uom_qty': 1.0,
        })

        # Scale Up
        ouvrage_line.write({'product_uom_qty': 2.0})
        
        comp_b = ouvrage_line.ouvrage_line_ids.filtered(lambda l: l.product_id == self.component_b)
        self.assertEqual(comp_b.product_uom_qty, 4.0, "2 * 2 = 4.0")

        # Scale Down
        ouvrage_line.write({'product_uom_qty': 1.0})
        self.assertEqual(comp_b.product_uom_qty, 2.0, "4 / 2 = 2.0")

    def test_confirmation_new_bom(self):
        """ Test confirmation creates new BoM if modified """
        so = self.SaleOrder.create({'partner_id': self.partner.id})
        ouvrage_line = self.SaleOrderLine.create({
            'order_id': so.id,
            'product_id': self.product_ouvrage.id,
            'product_uom_qty': 1.0,
        })
        
        # Modify Component
        comp_b = ouvrage_line.ouvrage_line_ids.filtered(lambda l: l.product_id == self.component_b)
        comp_b.write({'product_uom_qty': 5.0}) # Was 2.0. Ratio is now 5:1 vs BoM 2:1

        # Confirm
        so.action_confirm()
        
        # Check BoM
        self.assertNotEqual(ouvrage_line.bom_id, self.bom_ouvrage, "Should refer to a new BoM")
        self.assertTrue("Test Partner" in ouvrage_line.bom_id.code, "BoM code should contain partner name")
        
        # Check New BoM structure
        new_bom_line_b = ouvrage_line.bom_id.bom_line_ids.filtered(lambda l: l.product_id == self.component_b)
        self.assertEqual(new_bom_line_b.product_qty, 5.0, "New BoM should have Qty 5.0 for Component B")

