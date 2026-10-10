frappe.ui.form.on("Field Order Request", {
    refresh(frm) {
        frm.disable_save();
        if (!frm.is_new() && !frm.doc.sales_order &&
            ["Field Manager", "System Manager"].some(role => frappe.user_roles.includes(role))) {
            frm.add_custom_button(__("Create Draft Sales Order"), () => {
                const dialog = new frappe.ui.Dialog({
                    title: __("Review Order Request"),
                    fields: [
                        {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1},
                        {fieldname: "delivery_date", label: __("Delivery Date"), fieldtype: "Date", reqd: 1, default: frappe.datetime.get_today()},
                        {fieldtype: "HTML", options: __("ERPNext will calculate current prices and taxes. Review the resulting draft before submission.")}
                    ],
                    primary_action_label: __("Create Draft"),
                    async primary_action(values) {
                        dialog.get_primary_btn().prop("disabled", true);
                        try {
                            const result = await frappe.call({method: "av_field.api.make_sales_order", args: {request_name: frm.doc.name, ...values}});
                            dialog.hide();
                            frappe.set_route("Form", "Sales Order", result.message);
                        } finally { dialog.get_primary_btn().prop("disabled", false); }
                    }
                });
                dialog.show();
            });
        }
    }
});
