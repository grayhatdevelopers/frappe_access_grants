# Copyright (c) 2026, Grayhat and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.form.linked_with import get_linked_doctypes
from frappe.model.document import Document
from frappe.permissions import AUTOMATIC_ROLES

from access_grants.sync import clear_allow_doctypes, request_sync


class AccessGrant(Document):
	def validate(self):
		self.validate_roles()
		self.validate_document_types()

	def validate_roles(self):
		for row in self.roles:
			if row.role in AUTOMATIC_ROLES:
				# Frappe gives these to users on its own, so no user record lists them.
				frappe.throw(_("{0} is assigned automatically and cannot be used here.").format(row.role))

	def validate_document_types(self):
		meta = frappe.get_meta(self.allow)
		if meta.istable or meta.issingle:
			frappe.throw(_("{0} cannot restrict users.").format(self.allow))

		# A user permission only reaches a document type through a link to the restricted one.
		linked = {self.allow, *get_linked_doctypes(self.allow, True)}
		for row in self.applicable_for:
			if row.document_type not in linked:
				frappe.throw(_("{0} has no link to {1}.").format(row.document_type, self.allow))

	def on_update(self):
		clear_allow_doctypes()
		request_sync()

	def after_delete(self):
		clear_allow_doctypes()
		request_sync()
