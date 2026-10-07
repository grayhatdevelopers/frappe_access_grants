"""Turn Access Grants into User Permission rows and keep them current.

Frappe has no way to exempt a role from a user permission. A user restricted to their own
Employee sees another employee's Timesheet only if they hold a User Permission row for that
employee. This module writes those rows for every user a grant covers and removes them when the
grant, the role or the record goes away.

Only rows flagged `managed_by_access_grants` are ever created, changed or deleted here.
"""

import frappe

MANAGED = "managed_by_access_grants"
ALLOW_DOCTYPES_KEY = "access_grants:allow_doctypes"
SYNC_REQUESTED_KEY = "access_grants:sync_requested"


def sync(user: str | None = None) -> None:
	"""Make the managed rows match the enabled grants, for one user or for everyone."""
	if not frappe.get_meta("User Permission").has_field(MANAGED):
		# The flag arrives with the app's fixtures, after its hooks are already live.
		return

	desired = get_desired_rows(user)
	filters = {MANAGED: 1}
	if user:
		filters["user"] = user
	existing = {
		(row.user, row.allow, row.for_value, row.applicable_for): row.name
		for row in frappe.get_all(
			"User Permission",
			filters=filters,
			fields=["name", "user", "allow", "for_value", "applicable_for"],
		)
	}

	frappe.flags.access_grants_syncing = True
	try:
		for key in existing.keys() - desired:
			frappe.delete_doc("User Permission", existing[key], force=True, ignore_permissions=True)
		for row_user, allow, for_value, applicable_for in desired - existing.keys():
			frappe.get_doc(
				{
					"doctype": "User Permission",
					"user": row_user,
					"allow": allow,
					"for_value": for_value,
					"apply_to_all_doctypes": 0,
					"applicable_for": applicable_for,
					MANAGED: 1,
				}
			).insert(ignore_permissions=True)
	finally:
		frappe.flags.access_grants_syncing = False


def get_desired_rows(user: str | None = None) -> set[tuple[str, str, str, str]]:
	"""Return the (user, allow, for_value, applicable_for) rows the enabled grants call for."""
	desired = set()
	for name in frappe.get_all("Access Grant", filters={"enabled": 1}, pluck="name"):
		grant = frappe.get_doc("Access Grant", name)
		if not frappe.db.table_exists(grant.allow):
			continue
		users = get_users_with_roles([row.role for row in grant.roles], user)
		if not users:
			continue
		targets = {row.document_type for row in grant.applicable_for}
		values = frappe.get_all(grant.allow, pluck="name")

		# The values each user already reaches through rows this app does not own.
		own = {}
		for row in frappe.get_all(
			"User Permission",
			filters={"allow": grant.allow, "user": ["in", users], MANAGED: ["!=", 1]},
			fields=["user", "for_value", "apply_to_all_doctypes", "applicable_for"],
		):
			for target in targets:
				if row.apply_to_all_doctypes or row.applicable_for == target:
					own.setdefault((row.user, target), set()).add(row.for_value)

		# A user with no restriction of their own already sees every record, and rows
		# for other records would hide the ones they see now.
		for (row_user, target), reachable in own.items():
			desired.update(
				(row_user, grant.allow, value, target) for value in values if value not in reachable
			)
	return desired


def get_users_with_roles(roles: list[str], user: str | None = None) -> list[str]:
	filters = {"parenttype": "User", "role": ["in", roles]}
	if user:
		filters["parent"] = user
	holders = set(frappe.get_all("Has Role", filters=filters, pluck="parent")) - {"Administrator"}
	if not holders:
		return []
	return frappe.get_all("User", filters={"name": ["in", list(holders)], "enabled": 1}, pluck="name")


def request_sync(user: str | None = None) -> None:
	"""Sync in the background once the change that asked for it is committed."""
	if frappe.in_test:
		# Tests roll back instead of committing, so nothing would ever be queued.
		sync(user)
		return
	frappe.db.after_commit.add(lambda: enqueue_sync(user))


def enqueue_sync(user: str | None = None) -> None:
	# One queued job covers every request made before it starts.
	key = f"{SYNC_REQUESTED_KEY}:{user or '*'}"
	if frappe.cache.get_value(key):
		return
	frappe.cache.set_value(key, 1, expires_in_sec=3600)
	frappe.enqueue(
		"access_grants.sync.run_requested_sync",
		queue="default" if user else "long",
		for_user=user,
	)


def run_requested_sync(for_user: str | None = None) -> None:
	# Cleared before reading, so a change made while this runs queues another job.
	frappe.cache.delete_value(f"{SYNC_REQUESTED_KEY}:{for_user or '*'}")
	sync(for_user)


def get_allow_doctypes() -> list[str]:
	"""Return the document types whose records the enabled grants hand out."""

	def load():
		if not frappe.db.table_exists("Access Grant"):
			return []
		return frappe.get_all("Access Grant", filters={"enabled": 1}, pluck="allow", distinct=True)

	return frappe.cache.get_value(ALLOW_DOCTYPES_KEY, load)


def clear_allow_doctypes() -> None:
	frappe.cache.delete_value(ALLOW_DOCTYPES_KEY)


def on_user_change(doc, method=None):
	request_sync(doc.name)


def on_user_permission_change(doc, method=None):
	if not frappe.flags.access_grants_syncing:
		request_sync(doc.user)


def on_record_insert(doc, method=None):
	if doc.doctype in get_allow_doctypes():
		request_sync()


def on_record_trash(doc, method=None):
	"""Remove the managed rows for a record being deleted, which would otherwise block it."""
	if doc.doctype not in get_allow_doctypes():
		return
	frappe.flags.access_grants_syncing = True
	try:
		for name in frappe.get_all(
			"User Permission",
			filters={"allow": doc.doctype, "for_value": doc.name, MANAGED: 1},
			pluck="name",
		):
			frappe.delete_doc("User Permission", name, force=True, ignore_permissions=True)
	finally:
		frappe.flags.access_grants_syncing = False
