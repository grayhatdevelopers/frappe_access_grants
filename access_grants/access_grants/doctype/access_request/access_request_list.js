// Copyright (c) 2026, Grayhat and contributors
// For license information, please see license.txt

const ACCESS_REQUEST_COLORS = {
	Requested: "orange",
	Approved: "blue",
	Active: "green",
	Expired: "gray",
	Revoked: "red",
	Rejected: "red",
	Withdrawn: "gray",
};

frappe.listview_settings["Access Request"] = {
	get_indicator(doc) {
		return [__(doc.status), ACCESS_REQUEST_COLORS[doc.status], `status,=,${doc.status}`];
	},
};
