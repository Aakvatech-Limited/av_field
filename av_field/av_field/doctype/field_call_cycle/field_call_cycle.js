frappe.ui.form.on("Field Call Cycle", {
  refresh(frm) {
    if (frm.is_new() || !frm.doc.active) return;
    if (!(frappe.user.has_role("Field Manager") || frappe.user.has_role("System Manager"))) return;
    frm.add_custom_button(__("Generate Daily Route"), () => {
      const dialog = new frappe.ui.Dialog({
        title: __("Generate Daily Sales Route"),
        fields: [
          {fieldname: "route_date", label: __("Route Date"), fieldtype: "Date",
           reqd: 1, default: frappe.datetime.get_today()},
          {fieldname: "publish", label: __("Publish to Salesperson"), fieldtype: "Check", default: 1}
        ],
        primary_action_label: __("Generate"),
        primary_action(values) {
          frappe.call({
            method: "av_field.routes.generate_route",
            args: {call_cycle: frm.doc.name, route_date: values.route_date, publish: values.publish},
            freeze: true,
            callback(result) {
              if (!result.message) return;
              dialog.hide();
              frappe.show_alert({message: __("Created route with {0} stops", [result.message.count]), indicator: "green"});
              frappe.set_route("Form", "Field Route Plan", result.message.name);
            }
          });
        }
      });
      dialog.show();
    });
  }
});
