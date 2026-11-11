// Copyright (c) 2026, Grayhat and contributors
// For license information, please see license.txt

frappe.ui.form.on("Access Request", {
	setup(frm) {
		frm.set_query("role_profiles", () => ({
			query: "access_grants.access_requests.search_role_profiles",
		}));
	},
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status !== "Requested") {
			frm.set_read_only();
			frm.disable_save();
		}

		const me = frappe.session.user;
		const approver = frappe.user.has_role(["Access Approver", "System Manager"]);
		const decides = approver && frm.doc.user !== me;
		const requester = [frm.doc.user, frm.doc.owner].includes(me);
		const run = (method, args) => frm.call(method, args).then(() => frm.reload_doc());
		const button = (label, method, group) =>
			frm.add_custom_button(__(label), () => run(method), group && __(group));

		switch (frm.doc.status) {
			case "Requested":
				if (decides) {
					button("Approve", "approve", "Decide");
					button("Reject", "reject", "Decide");
				}
				if (requester) button("Withdraw", "withdraw");
				break;
			case "Approved":
				if (requester) button("Withdraw", "withdraw");
				if (approver) button("Revoke", "revoke");
				break;
			case "Active":
				if (frm.doc.requested_until && decides) {
					button("Approve More Time", "approve_more_time", "More Time");
					button("Reject More Time", "reject_more_time", "More Time");
				}
				if (requester && !frm.doc.requested_until) {
					frm.add_custom_button(__("Ask for More Time"), () =>
						frappe.prompt(
							{
								fieldname: "until",
								fieldtype: "Datetime",
								label: __("Until"),
								reqd: 1,
							},
							(values) => run("ask_for_more_time", { until: values.until }),
							__("Ask for More Time")
						)
					);
				}
				if (approver || frm.doc.user === me) {
					frm.add_custom_button(__("Revoke"), () =>
						frappe.confirm(__("Remove this access now?"), () => run("revoke"))
					);
				}
				break;
		}
	},
});
