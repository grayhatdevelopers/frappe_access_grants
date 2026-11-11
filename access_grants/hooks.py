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

# Everything that can change which rows a grant should produce, and the hook that keeps
# the roles of active Access Requests through a role profile reset.
doc_events = {
	"User": {
		"validate": "access_grants.access_requests.on_user_validate",
		"on_update": "access_grants.sync.on_user_change",
	},
	"User Permission": {
		"on_update": "access_grants.sync.on_user_permission_change",
		"after_delete": "access_grants.sync.on_user_permission_change",
	},
	"*": {
		"after_insert": "access_grants.sync.on_record_insert",
		"on_trash": "access_grants.sync.on_record_trash",
	},
}

scheduler_events = {
	# Starts and ends Access Requests; a request ends at most this late.
	"cron": {"*/5 * * * *": ["access_grants.access_requests.process_due"]},
	# Catches changes that bypass the document events, such as direct database writes.
	"daily": ["access_grants.sync.sync"],
}

# Requesters see their own Access Requests; approvers see all of them.
permission_query_conditions = {
	"Access Request": "access_grants.access_requests.get_permission_query_conditions",
}
has_permission = {"Access Request": "access_grants.access_requests.has_permission"}
