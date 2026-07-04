# Barangay Connect - User Roles & Access Control List (ACL)

This document describes the different user roles in **Barangay Connect**, their database definitions, and the specific URLs they are authorized to access.

---

## Summary of Roles

| Role | Database `role` Value | Allowed Dashboard | Access Scope |
| :--- | :--- | :--- | :--- |
| **Resident** | `'resident'` | Resident Dashboard | Can submit and view their own personal reports |
| **Barangay Staff** | `'staff'` | Staff Dashboard | Can manage only the reports specifically assigned to them |
| **Barangay Official** | `'official'` | Staff Dashboard | Full control over all reports, assignments, users, logs, and backups |
| **Superuser** (Developer) | *Default `'official'` with `is_superuser`* | Staff Dashboard | Full system permissions (treated as an Official) |

---

## Route Access Matrix

### 1. Resident Role
Standard resident accounts. These users can submit feedback and monitor their own case reports.

* **Dashboard URL:** `/dashboard/`
* **Authorized Links:**
  * Login / Logout: `/` or `/login/`, `/logout/`
  * Submit Report: `/submit-report/`
* **Restricted Links:**
  * ❌ `/staff/*` (Staff Dashboards & report controls)
  * ❌ `/official/*` (Official panels, user management, database controls)

---

### 2. Barangay Staff Role
Staff accounts created by officials. They can view, edit, resolve, and update remarks **only for cases assigned to them**.

* **Dashboard URL:** `/staff/dashboard/`
* **Authorized Links:**
  * View Assigned Reports: `/staff/dashboard/`
  * Update Report Status: `/staff/update-report-status/<int:report_id>/`
  * Update Report Remarks: `/staff/update-report-remarks/<int:report_id>/`
  * Edit Report Details: `/staff/edit-report/<str:report_type>/<int:report_id>/`
  * Delete Report: `/staff/delete-report/<str:report_type>/<int:report_id>/`
  * Email SMTP Testing: `/staff/test-email/`
* **Restricted Links:**
  * ❌ `/staff/assign-report/...` (Only Officials can assign reports)
  * ❌ `/official/*` (User management, backups, activity logs)

---

### 3. Barangay Official Role
Officials have full access to view all reports, manage assignments, register staff, review logs, and configure database backups.

* **Dashboard URL:** `/staff/dashboard/`
* **Authorized Links:**
  * *All Staff Links listed above.*
  * Assign Report to Staff: `/staff/assign-report/<int:report_id>/`
  * View All Barangay Reports: `/official/reports/`
  * User Accounts Management: `/official/users/` (Add: `/official/users/add/` \| Edit: `/official/users/edit/<int:id>/`)
  * System Activity Log: `/official/activity-log/`
  * Database Backup & Recovery: `/official/backup-recovery/` (Create, Download, Upload, Restore, Delete backups, Update settings)

---

### 4. Superuser Role (Developer/Admin)
Primary system administrator accounts. They are automatically granted **Barangay Official** access permissions.

* **Dashboard URL:** `/staff/dashboard/`
* **Authorized Links:**
  * **All frontend pages** (Resident, Staff, and Official features).

---

## How Access Control is Enforced

1. **Frontend Redirection:** 
   The helper `_redirect_by_role` in `resident/views.py` inspects the logged-in user and sends them to `/staff/dashboard/` if they are staff, official, or a superuser (evaluated via `is_staff_or_official`); otherwise, they are sent to `/dashboard/`.
2. **View Protection:**
   * Views under `/official/` verify that `request.user.role == 'official'` (and since superuser accounts default to the `'official'` role, they pass this check and have full access).
   * Views under `/staff/` check `request.user.is_resident` property (which evaluates to `False` for staff, officials, and superusers) and will redirect residents away if they attempt direct URL navigation.

