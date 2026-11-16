frappe.listview_settings["Field Route Plan"] = {
  onload(listview) {
    if (!(frappe.user.has_role("Field Manager") || frappe.user.has_role("System Manager"))) return;
    listview.page.add_inner_button(__("Generate Optimized Route"), () => {
      const dialog = new frappe.ui.Dialog({
        title: __("Optimize Sales Visits — Geoapify"),
        fields: [
          {fieldname:"salesperson", label:__("Assigned Field Salesperson (User)"),
           fieldtype:"Link", options:"User", reqd:1},
          {fieldname:"route_date", label:__("Route Date"),
           fieldtype:"Date", default: frappe.datetime.get_today(), reqd:1},
          {fieldname:"publish", label:__("Publish Route to Salesperson"), fieldtype:"Check", default:0}
        ],
        primary_action_label: __("Optimize Route"),
        primary_action(values) {
          frappe.call({
            method:"av_field.route_optimizer.generate_optimized_route",
            args:values,
            freeze:true,
            freeze_message:__("Optimizing road travel and visit windows…"),
            callback(result) {
              if (!result.message) return;
              dialog.hide();
              frappe.show_alert({message:__("Optimized {0} customer visits", [result.message.count]),indicator:"green"});
              frappe.set_route("Form","Field Route Plan",result.message.name);
            }
          });
        }
      });
      dialog.show();
    });
  }
};
