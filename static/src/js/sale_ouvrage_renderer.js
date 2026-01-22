/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SaleOrderLineListRenderer } from "@sale/static/src/js/sale_order_line_field/sale_order_line_field";
import { useSubEnv, useState } from "@odoo/owl";

patch(SaleOrderLineListRenderer.prototype, {
    setup() {
        super.setup();
        this.ouvrageState = useState({
            expandedOuvrages: new Set(),
        });
    },

    toggleOuvrage(recordId) {
        if (this.ouvrageState.expandedOuvrages.has(recordId)) {
            this.ouvrageState.expandedOuvrages.delete(recordId);
        } else {
            this.ouvrageState.expandedOuvrages.add(recordId);
        }
    },

    get rows() {
        const rows = super.rows;
        return rows.filter((row) => {
            const record = row.record;
            // ouvrage_parent_line_id: [id, name] or False
            const parentField = record.data.ouvrage_parent_line_id;
            // Handle both [id, name] and id (though usually array in m2o)
            const parentId = Array.isArray(parentField) ? parentField[0] : parentField;

            // If it has a parent, it is a component
            if (parentId) {
                // If the parent is NOT in the expanded set, hide this row
                if (!this.ouvrageState.expandedOuvrages.has(parentId)) {
                    return false;
                }
            }
            return true;
        });
    },
});
