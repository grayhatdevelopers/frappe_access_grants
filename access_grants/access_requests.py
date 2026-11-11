"""Keep the roles of active Access Requests on their users, and start and end requests on time.

An Access Request adds roles to a user for a window. It records the roles it added, and only
those are removed when it ends, so a role the user held anyway survives.
"""

import frappe
from frappe.utils import now_datetime

APPROVER = "Access Approver"
SYSTEM_MANAGER = "System Manager"


def is_approver(user: str | None = None) -> bool:
	return bool({APPROVER, SYSTEM_MANAGER} & set(frappe.get_roles(user)))


def get_active_roles(user: str, exclude: str | None = None) -> set[str]:
	"""Return the roles the user's active requests added, leaving out one request."""
	filters = {"user": user, "status": "Active"}
	if exclude:
		filters["name"] = ["!=", exclude]
	requests = frappe.get_all("Access Request", filters=filters, pluck="name")
	if not requests:
		return set()
	return set(
		frappe.get_all(
			"Has Role",
			filters={
				"parenttype": "Access Request",
				"parentfield": "added_roles",
				"parent": ["in", requests],
			},
			pluck="role",
		)
	)


def on_user_validate(doc, method=None):
	"""Put back the roles of the user's active requests.

	Saving a user with a role profile resets their roles to the profile's, which would end a
	temporary role early.
	"""
	if doc.is_new() or not frappe.db.table_exists("Access Request"):
		return
	roles = get_active_roles(doc.name)
	if roles - {row.role for row in doc.roles}:
		doc.append_roles(*roles)
		doc.set_system_user()


def process_due(now=None) -> None:
	"""Start approved requests whose window has opened and end active ones whose window has closed."""
	now = now or now_datetime()
	due = [
		(name, "start")
		for name in frappe.get_all(
			"Access Request", filters={"status": "Approved", "from_time": ["<=", now]}, pluck="name"
		)
	] + [
		(name, "expire")
		for name in frappe.get_all(
			"Access Request", filters={"status": "Active", "until": ["<=", now]}, pluck="name"
		)
	]
	for name, action in due:
		# One request failing must not hold up the others.
		frappe.db.savepoint("access_request")
		try:
			getattr(frappe.get_doc("Access Request", name), action)()
		except Exception:
			frappe.db.rollback(save_point="access_request")
			frappe.log_error(f"Access Request {name} could not {action}", reference_doctype="Access Request")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_role_profiles(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | list | None
):
	"""Role profile names for the Access Request picker.

	Frappe lets only System Managers look up role profiles, but anyone who may ask for access
	may ask for a profile. Like Frappe's own Role lookup for desk users, this shows names only.
	"""
	frappe.has_permission("Access Request", "create", throw=True)
	return frappe.get_all(
		"Role Profile",
		filters={"name": ["like", f"%{txt}%"]},
		offset=start,
		limit=page_len,
		fields=["name"],
		order_by="name",
		as_list=True,
	)


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if is_approver(user):
		return ""
	user = frappe.db.escape(user)
	return f"(`tabAccess Request`.`owner` = {user} or `tabAccess Request`.`user` = {user})"


def has_permission(doc, ptype=None, user=None, debug=False) -> bool:
	user = user or frappe.session.user
	return is_approver(user) or user in (doc.owner, doc.user)
