# Copyright (c) 2026, Grayhat and Contributors
# See LICENSE

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user
from frappe.utils import add_to_date, now_datetime

from access_grants.access_requests import APPROVER, process_due

# Roles the tests create, so they do not depend on what another app has set up.
BASE_ROLE = "Access Request Test Base"
ROLE = "Access Request Test"
OTHER_ROLE = "Access Request Test Other"

# The tests make their own users; Frappe's User test records pull in every linked doctype.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


def make_user(*roles):
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": f"{frappe.generate_hash(length=8)}@example.com",
			"first_name": "Test",
			"send_welcome_email": 0,
		}
	).insert()
	user.add_roles(BASE_ROLE, *roles)
	return user.name


def make_role_profile(*roles):
	return frappe.get_doc(
		{
			"doctype": "Role Profile",
			"role_profile": frappe.generate_hash(length=8),
			"roles": [{"role": role} for role in roles],
		}
	).insert()


def set_role_profiles(user, *profiles):
	user = frappe.get_doc("User", user)
	user.set("role_profiles", [{"role_profile": profile} for profile in profiles])
	user.save()


def roles_of(user):
	return set(frappe.get_all("Has Role", filters={"parenttype": "User", "parent": user}, pluck="role"))


def later(hours):
	return add_to_date(now_datetime(), hours=hours)


def ask(user, roles=(ROLE,), role_profiles=(), starts=0, hours=1):
	with set_user(user):
		return frappe.get_doc(
			{
				"doctype": "Access Request",
				"user": user,
				"roles": [{"role": role} for role in roles],
				"role_profiles": [{"role_profile": profile} for profile in role_profiles],
				"from_time": later(starts),
				"until": later(starts + hours),
				"reason": "Year-end close",
			}
		).insert()


def act(user, request, action, *args):
	with set_user(user):
		doc = frappe.get_doc("Access Request", request.name)
		getattr(doc, action)(*args)
		return doc


class IntegrationTestAccessRequest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for role in (APPROVER, BASE_ROLE, ROLE, OTHER_ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_if_duplicate=True
			)
		# Shared, since Frappe refuses more than 60 new users an hour.
		cls.approver = make_user(APPROVER)
		cls.system_manager = make_user("System Manager")

	def setUp(self):
		self.requester = make_user()

	def test_approval_adds_the_roles_and_expiry_removes_them(self):
		request = ask(self.requester)
		self.assertNotIn(ROLE, roles_of(self.requester))

		act(self.approver, request, "approve")
		self.assertIn(ROLE, roles_of(self.requester))
		self.assertEqual(frappe.db.get_value("Access Request", request.name, "status"), "Active")

		process_due(later(2))
		self.assertNotIn(ROLE, roles_of(self.requester))
		self.assertEqual(frappe.db.get_value("Access Request", request.name, "status"), "Expired")

	def test_roles_the_user_already_had_survive_the_expiry(self):
		frappe.get_doc("User", self.requester).add_roles(OTHER_ROLE)
		request = ask(self.requester, roles=(ROLE, OTHER_ROLE))

		request = act(self.approver, request, "approve")
		self.assertEqual([row.role for row in request.added_roles], [ROLE])

		process_due(later(2))
		self.assertIn(OTHER_ROLE, roles_of(self.requester))
		self.assertNotIn(ROLE, roles_of(self.requester))

	def test_roles_last_through_a_role_profile_reset(self):
		profile = make_role_profile(BASE_ROLE).name
		set_role_profiles(self.requester, profile)
		act(self.approver, ask(self.requester), "approve")

		# Saving a user with a profile resets their roles to the profile's.
		frappe.get_doc("User", self.requester).save()
		self.assertIn(ROLE, roles_of(self.requester))

		process_due(later(2))
		self.assertEqual(roles_of(self.requester), {BASE_ROLE})

	def test_a_role_two_requests_share_stays_until_both_end(self):
		act(self.approver, ask(self.requester, hours=1), "approve")
		act(self.approver, ask(self.requester, hours=3), "approve")

		process_due(later(2))
		self.assertIn(ROLE, roles_of(self.requester))

		process_due(later(4))
		self.assertNotIn(ROLE, roles_of(self.requester))

	def test_a_role_profile_grants_its_roles_not_the_profile(self):
		profile = make_role_profile(ROLE).name

		act(self.approver, ask(self.requester, roles=(), role_profiles=(profile,)), "approve")

		self.assertIn(ROLE, roles_of(self.requester))
		self.assertEqual(frappe.get_doc("User", self.requester).role_profiles, [])

	def test_access_waits_for_its_window(self):
		request = act(self.approver, ask(self.requester, starts=1), "approve")
		self.assertEqual(request.status, "Approved")
		self.assertNotIn(ROLE, roles_of(self.requester))

		process_due(later(1.5))
		self.assertIn(ROLE, roles_of(self.requester))

	def test_revoking_removes_the_roles_early(self):
		request = act(self.approver, ask(self.requester), "approve")

		act(self.approver, request, "revoke")

		self.assertNotIn(ROLE, roles_of(self.requester))
		self.assertEqual(frappe.db.get_value("Access Request", request.name, "revoked_by"), self.approver)

	def test_more_time_moves_the_end(self):
		request = act(self.approver, ask(self.requester), "approve")

		act(self.requester, request, "ask_for_more_time", str(later(3)))
		act(self.approver, request, "approve_more_time")

		process_due(later(2))
		self.assertIn(ROLE, roles_of(self.requester))
		process_due(later(4))
		self.assertNotIn(ROLE, roles_of(self.requester))

	def test_nobody_approves_their_own_access(self):
		request = ask(self.approver)
		self.assertRaises(frappe.PermissionError, act, self.approver, request, "approve")

	def test_only_a_system_manager_grants_system_manager(self):
		request = ask(self.requester, roles=("System Manager",))
		self.assertRaises(frappe.PermissionError, act, self.approver, request, "approve")

		act(self.system_manager, request, "approve")
		self.assertIn("System Manager", roles_of(self.requester))

	def test_only_a_system_manager_approves_more_than_seven_days(self):
		request = ask(self.requester, hours=8 * 24)
		self.assertRaises(frappe.PermissionError, act, self.approver, request, "approve")

		act(self.system_manager, request, "approve")
		self.assertIn(ROLE, roles_of(self.requester))

	def test_a_decision_only_changes_through_the_buttons(self):
		with set_user(self.requester):
			request = frappe.get_doc(
				{
					"doctype": "Access Request",
					"user": self.requester,
					"status": "Active",
					"roles": [{"role": ROLE}],
					"until": later(1),
					"reason": "Year-end close",
				}
			).insert()
			self.assertEqual(request.status, "Requested")

			request.status = "Approved"
			self.assertRaises(frappe.ValidationError, request.save)

		act(self.approver, request, "approve")
		with set_user(self.requester):
			request = frappe.get_doc("Access Request", request.name)
			request.reason = "Something else"
			self.assertRaises(frappe.ValidationError, request.save)

	def test_requesters_ask_only_for_themselves_and_see_only_their_own(self):
		with set_user(self.requester):
			request = frappe.get_doc(
				{
					"doctype": "Access Request",
					"user": self.approver,
					"roles": [{"role": ROLE}],
					"until": later(1),
					"reason": "Year-end close",
				}
			)
			self.assertRaises(frappe.PermissionError, request.insert)

		mine = ask(self.requester)
		theirs = ask(make_user())
		with set_user(self.requester):
			visible = frappe.get_list("Access Request", pluck="name")
		self.assertIn(mine.name, visible)
		self.assertNotIn(theirs.name, visible)

	def test_rejects_a_request_for_nothing(self):
		self.assertRaises(frappe.ValidationError, ask, self.requester, roles=())

	def test_approvers_and_the_requester_are_notified(self):
		# The test site has no outgoing email account, which would stop the bell as well.
		with patch("frappe.sendmail") as sendmail:
			request = ask(self.requester)
			act(self.approver, request, "approve")

		for user in (self.approver, self.requester):
			self.assertTrue(
				frappe.db.exists("Notification Log", {"for_user": user, "document_name": request.name})
			)
		emailed = set().union(*(call.kwargs["recipients"] for call in sendmail.call_args_list))
		self.assertTrue({self.approver, self.requester} <= emailed)

	def test_only_system_managers_hear_about_what_only_they_can_approve(self):
		with patch("frappe.sendmail"):
			request = ask(self.requester, roles=("System Manager",))

		self.assertTrue(request.needs_system_manager)
		self.assertFalse(
			frappe.db.exists("Notification Log", {"for_user": self.approver, "document_name": request.name})
		)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log", {"for_user": self.system_manager, "document_name": request.name}
			)
		)
