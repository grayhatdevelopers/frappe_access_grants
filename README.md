# Frappe Access Grants

Let a role see past a user permission on the document types you choose, without editing User Permissions by hand.

Built and maintained by [Grayhat](https://grayhat.studio).

## The problem

ERPNext restricts each employee's user to their own Employee record. That one restriction applies to every document type that links to Employee, so a project manager cannot open their team's Timesheets. The stock way around it is a User Permission row per manager per employee, added and removed by hand.

Frappe has no setting that exempts a role from a user permission, and permission hooks can only deny access, never grant it.

## What the app does

An **Access Grant** says: users holding *these roles*, who are restricted by *this document type*, see every record of *these document types*.

```text
Access Grant
  Roles:          Projects Manager
  Restricted By:  Employee
  Lifted For:     Timesheet
```

The app turns each grant into ordinary User Permission rows (Employee = each other employee, applicable for Timesheet) and keeps them current. Frappe enforces them as it always does, in lists, forms, reports and the API. The restriction stays in force everywhere the grant does not name, so the manager above still sees only their own Employee record, leave and salary slips.

Rows are added and removed when:

- a grant is saved, disabled or deleted;
- a user gains or loses one of its roles, or is disabled;
- a record of the restricted document type is created or deleted;
- the user's own restriction is added or removed.

A daily job repeats the sync for changes that bypass these events.

## Rows the app owns

Every row the app creates is ticked **Managed by Access Grants** on User Permission. The app only ever creates, changes or deletes ticked rows.

- A row you add yourself is never touched.
- Untick a managed row to keep it; the app leaves it alone from then on.
- A managed row you delete comes back on the next sync. Disable the grant to remove its rows.

## Things to know

- A user with no restriction of their own gets no rows. They already see every record.
- The app never writes a row for a user's own record. ERPNext manages that one.
- ERPNext also restricts employees to their Company. For access across companies, add a second grant restricted by Company.
- One row is written per user, per record, per document type. A grant for 10 managers over 200 employees and 2 document types is 4,000 rows.

## Requirements

Frappe Framework version 16. The app does not need ERPNext; the tests use ERPNext's Employee and Timesheet because that is the common case. CI tests every change against the ERPNext image pinned in [`ci.yml`](.github/workflows/ci.yml).

## Installation

From your bench directory, run:

```bash
bench get-app https://github.com/grayhatdevelopers/frappe_access_grants.git --branch main
bench --site your-site.example install-app access_grants
```

Installation adds the **Managed by Access Grants** field to User Permission.

## Development

Run the tests in a disposable Docker bench:

```bash
FRAPPE_IMAGE=frappe/erpnext:v16.36.0 tests/docker/run.sh
```

Pull requests target `develop` and are squash-merged; titles must be conventional commits. Releases are cut by semantic-release when `develop` is merged into `main`.

## License

MIT
