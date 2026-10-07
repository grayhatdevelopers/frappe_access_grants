import frappe
from frappe.permissions import add_user_permission, has_permission
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

from access_grants.sync import MANAGED

COMPANY = "Access Grants Test Co"
ROLE = "Projects Manager"


def make_user(*roles):
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": f"{frappe.generate_hash(length=8)}@example.com",
			"first_name": "Test",
			"send_welcome_email": 0,
		}
	).insert()
	user.add_roles(*roles)
	return user.name


def make_employee(user=None):
	# ERPNext restricts a linked user to this employee and its company.
	employee = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": "Test",
			"gender": "Other",
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
			"company": COMPANY,
			"user_id": user,
			"create_user_permission": 1 if user else 0,
		}
	).insert()
	return employee.name


def make_grant():
	return frappe.get_doc(
		{
			"doctype": "Access Grant",
			"title": frappe.generate_hash(length=8),
			"roles": [{"role": ROLE}],
			"allow": "Employee",
			"applicable_for": [{"document_type": "Timesheet"}],
		}
	).insert()


def managed_rows(user):
	return frappe.get_all(
		"User Permission",
		filters={"user": user, MANAGED: 1},
		fields=["for_value", "applicable_for"],
		as_list=True,
	)


class IntegrationTestSync(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Company", COMPANY):
			from erpnext.setup.setup_wizard.operations import install_fixtures

			# A company cannot be created before ERPNext's base records exist.
			install_fixtures.install("United States")
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": COMPANY,
					"abbr": "AGT",
					"default_currency": "USD",
					"country": "United States",
				}
			).insert()
		frappe.get_doc({"doctype": "Gender", "gender": "Other"}).insert(ignore_if_duplicate=True)

	def setUp(self):
		for name in frappe.get_all("Access Grant", pluck="name"):
			frappe.delete_doc("Access Grant", name)
		self.manager = make_user("Employee", ROLE)
		self.manager_employee = make_employee(self.manager)
		self.staff_employee = make_employee(make_user("Employee"))
		timesheet = frappe.get_doc(
			{
				"doctype": "Timesheet",
				"employee": self.staff_employee,
				"company": COMPANY,
				"time_logs": [{"from_time": "2026-10-01 09:00:00", "hours": 1}],
			}
		).insert()
		self.timesheet = timesheet.name

	def manager_can(self, ptype, doctype, name):
		return has_permission(doctype, ptype, doc=name, user=self.manager, print_logs=False)

	def test_grant_lifts_the_restriction_only_where_it_says(self):
		self.assertFalse(self.manager_can("read", "Timesheet", self.timesheet))

		make_grant()

		self.assertIn((self.staff_employee, "Timesheet"), managed_rows(self.manager))
		self.assertTrue(self.manager_can("read", "Timesheet", self.timesheet))
		self.assertTrue(self.manager_can("write", "Timesheet", self.timesheet))
		with set_user(self.manager):
			self.assertIn(self.timesheet, frappe.get_list("Timesheet", pluck="name"))
		self.assertFalse(self.manager_can("read", "Employee", self.staff_employee))

	def test_no_row_for_the_users_own_employee(self):
		# ERPNext removes rows by user and employee alone, so it would delete ours for its own.
		make_grant()

		self.assertNotIn(self.manager_employee, [row[0] for row in managed_rows(self.manager)])

	def test_unrestricted_user_gets_no_rows(self):
		# Rows for other employees would hide the timesheets this user sees now.
		unrestricted = make_user("Employee", ROLE)

		make_grant()

		self.assertEqual(managed_rows(unrestricted), [])

	def test_rows_follow_the_role(self):
		make_grant()
		user = frappe.get_doc("User", self.manager)

		user.remove_roles(ROLE)
		self.assertEqual(managed_rows(self.manager), [])

		user.add_roles(ROLE)
		self.assertIn((self.staff_employee, "Timesheet"), managed_rows(self.manager))

	def test_rows_follow_the_records(self):
		make_grant()

		employee = make_employee()
		self.assertIn((employee, "Timesheet"), managed_rows(self.manager))

		# A row pointing at a record blocks deleting it.
		frappe.delete_doc("Employee", employee)
		self.assertNotIn((employee, "Timesheet"), managed_rows(self.manager))

	def test_rows_follow_the_grant(self):
		grant = make_grant()

		grant.enabled = 0
		grant.save()
		self.assertEqual(managed_rows(self.manager), [])

		grant.enabled = 1
		grant.save()
		self.assertTrue(managed_rows(self.manager))

		frappe.delete_doc("Access Grant", grant.name)
		self.assertEqual(managed_rows(self.manager), [])

	def test_rows_follow_the_restriction_erpnext_manages(self):
		make_grant()
		employee = frappe.get_doc("Employee", self.manager_employee)

		employee.create_user_permission = 0
		employee.save()
		self.assertEqual(frappe.get_all("User Permission", filters={"user": self.manager}), [])

		employee.create_user_permission = 1
		employee.save()
		self.assertIn((self.staff_employee, "Timesheet"), managed_rows(self.manager))
		self.assertFalse(self.manager_can("read", "Employee", self.staff_employee))

	def test_rows_added_by_hand_are_left_alone(self):
		add_user_permission("Employee", self.staff_employee, self.manager, applicable_for="Timesheet")
		by_hand = {"user": self.manager, "for_value": self.staff_employee, "applicable_for": "Timesheet"}

		grant = make_grant()
		self.assertNotIn((self.staff_employee, "Timesheet"), managed_rows(self.manager))

		frappe.delete_doc("Access Grant", grant.name)
		self.assertEqual(frappe.db.count("User Permission", by_hand), 1)

	def test_row_taken_over_by_hand_is_left_alone(self):
		grant = make_grant()
		taken_over = {"user": self.manager, "for_value": self.staff_employee, "applicable_for": "Timesheet"}
		row = frappe.get_doc("User Permission", taken_over)

		row.set(MANAGED, 0)
		row.save()
		frappe.delete_doc("Access Grant", grant.name)

		self.assertEqual(frappe.db.count("User Permission", taken_over), 1)
		self.assertTrue(self.manager_can("read", "Timesheet", self.timesheet))
