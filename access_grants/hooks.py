app_name = "access_grants"
app_title = "Access Grants"
app_publisher = "Grayhat"
app_description = "Give roles access past their user permissions, managed centrally"
app_email = "info@grayhat.studio"
app_license = "mit"

required_apps = ["frappe"]

add_to_apps_screen = [
	{
		"name": "access_grants",
		"logo": "/assets/access_grants/images/logo.svg",
		"title": "Access Grants",
		"route": "/app/access-grant",
	}
]

# The flag on User Permission that marks the rows this app owns.
fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [["dt", "=", "User Permission"], ["fieldname", "=", "managed_by_access_grants"]],
	},
]

# Everything that can change which rows a grant should produce.
doc_events = {
	"User": {"on_update": "access_grants.sync.on_user_change"},
	"User Permission": {
		"on_update": "access_grants.sync.on_user_permission_change",
		"after_delete": "access_grants.sync.on_user_permission_change",
	},
	"*": {
		"after_insert": "access_grants.sync.on_record_insert",
		"on_trash": "access_grants.sync.on_record_trash",
	},
}

# Catches changes that bypass the document events, such as direct database writes.
scheduler_events = {"daily": ["access_grants.sync.sync"]}
