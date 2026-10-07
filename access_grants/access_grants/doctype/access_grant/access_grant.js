// Copyright (c) 2026, Grayhat and contributors
// For license information, please see license.txt

frappe.ui.form.on("Access Grant", {
	setup(frm) {
		frm.set_query("allow", () => ({ filters: { issingle: 0, istable: 0 } }));
		// The same list User Permission offers for "Applicable For".
		frm.set_query("applicable_for", () => ({
			query: "frappe.core.doctype.user_permission.user_permission.get_applicable_for_doctype_list",
			filters: { doctype: frm.doc.allow },
		}));
	},
});
