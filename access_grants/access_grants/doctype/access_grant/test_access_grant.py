# Copyright (c) 2026, Grayhat and Contributors
# See LICENSE

import frappe
from frappe.tests import IntegrationTestCase


def make_grant(roles=("System Manager",), allow="User", applicable_for=("User",)):
	return frappe.get_doc(
		{
			"doctype": "Access Grant",
			"title": frappe.generate_hash(length=8),
			"roles": [{"role": role} for role in roles],
			"allow": allow,
			"applicable_for": [{"document_type": doctype} for doctype in applicable_for],
		}
	)


class IntegrationTestAccessGrant(IntegrationTestCase):
	def test_saves_for_a_linked_document_type(self):
		make_grant().insert()

	def test_rejects_roles_frappe_assigns_on_its_own(self):
		self.assertRaises(frappe.ValidationError, make_grant(roles=("All",)).insert)

	def test_rejects_a_document_type_with_no_link_to_the_restricted_one(self):
		self.assertRaises(frappe.ValidationError, make_grant(applicable_for=("Role",)).insert)

	def test_rejects_a_child_table_as_the_restriction(self):
		self.assertRaises(frappe.ValidationError, make_grant(allow="Has Role").insert)
