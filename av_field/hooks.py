app_name = "av_field"
app_title = "AV Field"
app_publisher = "Aakvatech Limited"
app_description = "Offline field visits and order capture for ERPNext"
app_email = "info@aakvatech.com"
app_license = "AGPL-3.0-only"
required_apps = ["erpnext"]
after_install = "av_field.install.after_install"
after_migrate = "av_field.route_setup.ensure_route_fields"

app_logo_url = "/assets/av_field/pwa/icon-192.png"
app_home = "/desk/av-field"

add_to_apps_screen = [
    {
        "name": app_name,
        "logo": app_logo_url,
        "title": app_title,
        "route": app_home,
    }
]
