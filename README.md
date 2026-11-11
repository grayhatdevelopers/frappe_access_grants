# Frappe Access Grants

Let a role see past a user permission on the document types you choose, without editing User Permissions by hand.

A small layer over Frappe's User Permissions for teams where some roles, such as project managers, need to see other people's records.

Built and maintained by [Grayhat](https://grayhat.studio).

## From one grant to working access

ERPNext restricts each employee's user to their own Employee record, and that restriction follows every document type that links to Employee. A project manager therefore cannot open their team's Timesheets unless someone adds a User Permission per manager, per employee.

An Access Grant replaces that manual work:

```text
Access Grant
  For Roles:       Projects Manager
  Allow All:       Employee
  Applicable For:  Timesheet
  -> one User Permission per manager, per other employee, applicable for Timesheet
  -> Frappe enforces them in lists, forms, reports and the API
```

The restriction stays in force everywhere the grant does not name. The manager above still sees only their own Employee record, leave and salary slips.

## What you can do

- Give several roles access in one grant, or the users of a role profile, or both.
- Apply a grant to several document types at once.
- Use any document type users are restricted by, not only Employee.
- Disable a grant to withdraw its access, and enable it again to restore it.
- See every row the app created by filtering User Permission on **Managed by Access Grants**.
- Keep a row yourself by unticking that field; the app leaves it alone from then on.
- Add your own User Permissions alongside; the app never touches them.
- Give someone extra roles for a set time with an **Access Request**, which takes them back at the end.

## Requirements

Frappe Framework version 16. ERPNext is not required. CI tests every change against the ERPNext image pinned in [`ci.yml`](.github/workflows/ci.yml), because Employee and Timesheet are the common case.

## Installation

From your bench directory, run:

```bash
bench get-app https://github.com/grayhatdevelopers/frappe_access_grants.git --branch main
bench --site your-site.example install-app access_grants
bench --site your-site.example migrate
```

Installation adds a **Managed by Access Grants** field to User Permission.

## Create a grant

Open **Access Grants** from the desk and add an **Access Grant**:

![An Access Grant that lets project managers see every timesheet](docs/images/access-grant.png)

| Field | Description | Example |
| --- | --- | --- |
| Title | Name of the grant | Project managers see all timesheets |
| For Roles | Users holding any of these roles get the access | Projects Manager |
| For Role Profiles | Users assigned any of these role profiles get the access | Project Leads |
| Allow All | The document type whose records are all allowed | Employee |
| Applicable For | The document types the access applies to | Timesheet |
| Enabled | Untick to withdraw the access without deleting the grant | Ticked |

A grant names roles, role profiles or both, and covers a user who matches either. Use a role profile when the profile is what you manage: removing it from a user withdraws the access, whatever roles the user keeps.

Saving the grant creates the rows in the background, usually within a few seconds. Only System Managers can create grants.

![The User Permission list filtered to the rows the grant created](docs/images/managed-rows.png)

A grant only affects users who are restricted to specific records of the **Allow All** document type. Everyone else already sees every record and gets no rows.

## How the rows are kept current

Rows are added and removed when:

- a grant is saved, disabled or deleted;
- a user gains or loses one of its roles or role profiles, or is disabled;
- a role profile's roles change;
- a record of the **Allow All** document type is created or deleted;
- the user's own restriction is added or removed.

A daily job repeats the sync for changes that bypass these events, such as direct database writes. A managed row deleted by hand comes back on the next sync; disable the grant to remove its rows.

## Temporary access

An **Access Request** gives a user extra roles until a set time, then takes them back.

1. Someone opens **Access Request**, picks the roles or role profiles they need, an Until time and a reason, and saves. A request is for yourself; approvers can create one for anyone.
2. Approvers get a notification by email and in the desk's bell. An approver opens the request and clicks **Decide > Approve** or **Reject**. They can shorten Until before approving.
3. At From, the roles are added. At Until, they come off within 5 minutes. The requester can **Ask for More Time**; an approver approves or rejects the new end time. An approver, or the user, can **Revoke** it early.

| Who | Can |
| --- | --- |
| Any desk user | Ask for access for themselves, see their own requests, withdraw or give back their access |
| Access Approver | Decide any request except their own, for up to 7 days, without System Manager |
| System Manager | Decide any request except their own, including System Manager and longer windows |

A System Manager grants access directly by creating a request for someone else and approving it.

What it guarantees:

- Only the roles the request added come off. A role the user already had stays, and so does a role another active request still gives.
- A role profile's roles are added, not the profile itself, so ending the request removes them cleanly.
- For a user with a role profile, Frappe resets their roles to the profile's whenever their user record is saved. Active requests put their roles back on that save.
- Every request keeps who asked, why, who decided and when, and Frappe's Permission Log records each role change on the user.

The notifications are standard Frappe **Notification** rules (Access Request New, More Time, Decided, More Time Decided). Change their wording or recipients by disabling one and duplicating it. They need an outgoing email account: without one, Frappe logs "Failed to send Notification" and the bell entry is skipped too.

## Limits

- One row is written per user, per record, per document type. A grant for 10 managers over 200 employees and 2 document types is 4,000 rows.
- ERPNext also restricts employees to their Company. For access across companies, add a second grant that allows all Company records.
- Access is all records or none. A grant cannot be limited to, say, one project's timesheets.

## Development

Run the tests in a disposable Docker bench, as CI does. Set `FRAPPE_IMAGE` to the version in [`ci.yml`](.github/workflows/ci.yml), for example:

```bash
FRAPPE_IMAGE=frappe/erpnext:v16.52.1 tests/docker/run.sh
```

Or from an existing bench that has ERPNext installed:

```bash
bench --site your-site.example run-tests --app access_grants
```

Run formatting and lint checks from the app directory:

```bash
pre-commit install
pre-commit run --all-files
```

Pull requests target `develop` and are squash-merged; titles must be conventional commits.

## Help and project links

- [Issue tracker](https://github.com/grayhatdevelopers/frappe_access_grants/issues)
- [Frappe Framework](https://github.com/frappe/frappe)
- [Grayhat](https://grayhat.studio)

For support and other enquiries, email [info@grayhat.studio](mailto:info@grayhat.studio).

## Contributing

Contributions are welcome. Open an issue to report a bug or discuss a change before submitting a pull request.

## License

Frappe Access Grants is built by [Grayhat](https://grayhat.studio) and released under the [MIT License](LICENSE).
