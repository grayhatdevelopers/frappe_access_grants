# Copyright (c) 2026, Grayhat and contributors
# For license information, please see license.txt

from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.permissions import AUTOMATIC_ROLES
from frappe.utils import get_datetime, now_datetime

from access_grants.access_requests import SYSTEM_MANAGER, get_active_roles, is_approver

# Longest window an Access Approver can approve; a System Manager can approve any.
APPROVER_MAX_WINDOW = timedelta(days=7)
DECISION_FIELDS = ("status", "decided_by", "decided_on", "revoked_by", "revoked_on", "requested_until")


class AccessRequest(Document):
	def validate(self):
		if self.is_new():
			self.status = "Requested"
			for field in DECISION_FIELDS[1:]:
				self.set(field, None)
			self.set("added_roles", [])
			if self.user != frappe.session.user and not is_approver():
				frappe.throw(_("You can only ask for access for yourself."), frappe.PermissionError)
		elif not self.flags.from_action:
			self.validate_still_editable()

		if not self.roles and not self.role_profiles:
			frappe.throw(_("Name at least one role or role profile."))
		for row in self.roles:
			if row.role in AUTOMATIC_ROLES:
				frappe.throw(_("{0} is assigned automatically and cannot be requested.").format(row.role))
		if get_datetime(self.until) <= get_datetime(self.from_time):
			frappe.throw(_("Until must be after From."))
		# Decides who is notified and who may approve.
		self.needs_system_manager = self.check_needs_system_manager(self.requested_until)

	def validate_still_editable(self):
		# Decisions only change through the actions below.
		before = self.get_doc_before_save()
		if before.status != "Requested":
			frappe.throw(_("This request has been decided and can no longer be edited."))
		changed = [field for field in DECISION_FIELDS if self.get(field) != before.get(field)]
		if changed or [row.role for row in self.added_roles] != [row.role for row in before.added_roles]:
			frappe.throw(_("Use the request's buttons to approve, reject or end it."))

	def get_roles_to_grant(self) -> set[str]:
		roles = {row.role for row in self.roles}
		profiles = [row.role_profile for row in self.role_profiles]
		if profiles:
			roles.update(
				frappe.get_all(
					"Has Role",
					filters={"parenttype": "Role Profile", "parent": ["in", profiles]},
					pluck="role",
				)
			)
		return roles

	def check_needs_system_manager(self, until=None) -> bool:
		window = get_datetime(until or self.until) - get_datetime(self.from_time)
		return SYSTEM_MANAGER in self.get_roles_to_grant() or window > APPROVER_MAX_WINDOW

	def check_can_decide(self, until=None):
		if not is_approver():
			frappe.throw(
				_("Only an Access Approver or a System Manager can decide access requests."),
				frappe.PermissionError,
			)
		if self.user == frappe.session.user:
			frappe.throw(_("You cannot approve access for yourself."), frappe.PermissionError)
		if self.check_needs_system_manager(until) and SYSTEM_MANAGER not in frappe.get_roles():
			frappe.throw(
				_("Only a System Manager can grant System Manager or more than {0} days.").format(
					APPROVER_MAX_WINDOW.days
				),
				frappe.PermissionError,
			)

	def check_is_requester(self):
		if frappe.session.user not in (self.user, self.owner):
			frappe.throw(_("Only the requester can do this."), frappe.PermissionError)

	def check_status(self, *statuses):
		if self.status not in statuses:
			frappe.throw(_("This request is {0}.").format(_(self.status)))

	def save_action(self):
		self.flags.from_action = True
		self.save(ignore_permissions=True)
		self.flags.from_action = False

	def decide(self, status):
		self.status = status
		self.decided_by = frappe.session.user
		self.decided_on = now_datetime()
		self.save_action()

	@frappe.whitelist()
	def approve(self):
		self.check_status("Requested")
		self.check_can_decide()
		self.decide("Approved")
		if get_datetime(self.from_time) <= now_datetime():
			self.start()

	@frappe.whitelist()
	def reject(self):
		self.check_status("Requested")
		self.check_can_decide()
		self.decide("Rejected")

	@frappe.whitelist()
	def withdraw(self):
		self.check_status("Requested", "Approved")
		self.check_is_requester()
		self.status = "Withdrawn"
		self.save_action()

	@frappe.whitelist()
	def revoke(self):
		"""End the access early; an approver can, and so can the user giving it back."""
		self.check_status("Approved", "Active")
		if frappe.session.user != self.user and not is_approver():
			frappe.throw(_("Only an approver or the user can revoke this access."), frappe.PermissionError)
		self.revoked_by = frappe.session.user
		self.revoked_on = now_datetime()
		self.end("Revoked")

	@frappe.whitelist()
	def ask_for_more_time(self, until: str):
		self.check_status("Active")
		self.check_is_requester()
		if get_datetime(until) <= get_datetime(self.until):
			frappe.throw(_("Ask for a time after the current Until."))
		self.requested_until = until
		self.save_action()

	@frappe.whitelist()
	def approve_more_time(self):
		self.check_status("Active")
		if not self.requested_until:
			frappe.throw(_("No more time was asked for."))
		self.check_can_decide(self.requested_until)
		self.until = self.requested_until
		self.requested_until = None
		self.save_action()

	@frappe.whitelist()
	def reject_more_time(self):
		self.check_status("Active")
		self.check_can_decide()
		self.requested_until = None
		self.save_action()

	def start(self):
		"""Add the roles the user lacks, and remember which ones they were."""
		held = set(
			frappe.get_all("Has Role", filters={"parenttype": "User", "parent": self.user}, pluck="role")
		)
		# A role another active request added still counts as added, so it stays until both end.
		held -= get_active_roles(self.user, exclude=self.name)
		self.set("added_roles", [{"role": role} for role in sorted(self.get_roles_to_grant() - held)])
		self.status = "Active"
		self.save_action()
		# The user's validate hook adds the roles of active requests.
		frappe.get_doc("User", self.user).save(ignore_permissions=True)

	def expire(self):
		self.end("Expired")

	def end(self, status):
		was_active = self.status == "Active"
		self.status = status
		self.requested_until = None
		self.save_action()
		if not was_active:
			return
		remove = {row.role for row in self.added_roles} - get_active_roles(self.user)
		user = frappe.get_doc("User", self.user)
		user.set("roles", [row for row in user.roles if row.role not in remove])
		user.save(ignore_permissions=True)
