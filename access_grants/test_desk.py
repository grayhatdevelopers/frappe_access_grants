import frappe
from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import auto_generate_sidebar_from_module
from frappe.tests import IntegrationTestCase

MODULE = "Access Grants"


class IntegrationTestDesk(IntegrationTestCase):
	def test_one_sidebar_for_the_module(self):
		sidebars = frappe.get_all(
			"Workspace Sidebar", filters={"module": MODULE, "for_user": ["is", "not set"]}, pluck="name"
		)
		self.assertEqual(sidebars, [MODULE])
		# Frappe generates a second sidebar for a module that has none named after it.
		self.assertNotIn(MODULE, [sidebar.title for sidebar in auto_generate_sidebar_from_module()])

	def test_desk_icon_opens_the_sidebar(self):
		icon = frappe.db.get_value("Desktop Icon", MODULE, ["link_type", "link_to", "standard"], as_dict=True)
		self.assertEqual(icon, {"link_type": "Workspace Sidebar", "link_to": MODULE, "standard": 1})
