import frappe
from frappe.desk.doctype.sidebar.sidebar import get_sidebar
from frappe.tests import IntegrationTestCase

MODULE = "Access Grants"


class IntegrationTestDesk(IntegrationTestCase):
	def test_module_has_the_shipped_sidebar(self):
		# Without one, Frappe computes a sidebar from the module's contents.
		sidebar = get_sidebar(MODULE)
		self.assertEqual((sidebar.app, sidebar.standard), ("access_grants", 1))
		self.assertEqual([item.link_to for item in sidebar.items], ["Access Grant", "User Permission"])

	def test_desk_icon_opens_the_sidebar(self):
		# Icons are imported only on sites using the icon grid, which finds a sidebar by its module.
		icon = frappe.get_file_json(frappe.get_app_path("access_grants", "desktop_icon", "access_grants.json"))
		self.assertEqual((icon["link_type"], icon["link_to"]), ("Workspace Sidebar", MODULE))
