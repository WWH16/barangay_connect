# Barangay Connect

Barangay Connect is a centralized report and incident management system designed to streamline communication and action between residents, barangay staff, and local officials.

---

## 👥 Users & Stakeholders

Based on the system design requirements, the platform supports three primary user types, as well as indirect stakeholders:

### User Type 1: Resident
* **Role and Responsibilities:**
  * Submit complaints and incident reports
  * Track complaint status
  * Provide additional details and evidence when needed
* **Needs and Expectations:**
  * Easy and intuitive reporting process
  * Fast response time from the barangay
  * Real-time case updates
* **Information Flow:**
  * **Provided:** Personal information, complaint/incident details, and file evidence (photos/documents).
  * **Received:** Step-by-step case status changes, notifications, and resolution updates.
* **Access Privileges:** Submit new reports, view personal reports dashboard, and receive updates.
* **Possible Concerns:** Privacy of personal details, slow or delayed resolutions.

### User Type 2: Barangay Staff
* **Role and Responsibilities:**
  * Review submitted complaints
  * Verify information accuracy
  * Update case status (Pending ➔ In Progress ➔ Resolved)
* **Needs and Expectations:**
  * Organized records and easy filtering
  * Efficient, clear workflow pipelines
* **Information Flow:**
  * **Provided:** Investigation updates, internal case remarks.
  * **Received:** Real-time notifications of new resident complaints, resident profile information.
* **Access Privileges:** Manage complaints registry, update case status, update progress records.
* **Possible Concerns:** High workload volume, data accuracy validation.

### User Type 3: Barangay Administrator/Officials
* **Role and Responsibilities:**
  * Oversee entire barangay operations
  * Assign cases to specific staff members
  * Make operational decisions based on aggregated analytics
* **Needs and Expectations:**
  * Accurate, clear reports
  * Reliable system monitoring and analytics tools
* **Information Flow:**
  * **Provided:** Staff case assignments, official resolutions, decisions.
  * **Received:** Interactive system analytics, performance reports, monthly volumes.
* **Access Privileges:** Full system access, staff assignment capabilities, reports and analytics dashboard.
* **Possible Concerns:** Information security, system uptime, and reliability.

### 🌐 Indirect Stakeholders
* **Municipal Government:** For city-wide data aggregation and support.
* **Community Organizations:** Collaborating on resolved neighborhood concerns.
* **IT Support Personnel:** Maintaining system reliability and security.
* **Emergency Response Teams:** For critical incidents requiring immediate rescue/police dispatch.

---

## 🛠️ Codebase Mapping & Implementation

The stakeholders map directly to the implementation details of the application:
1. **User Roles:** Handled by [Profile.role](file:///S:/PROJECTS/barangay_connect/resident/models.py#L8-L12) choice field with roles `resident`, `staff`, and `official` (Administrator).
2. **Access Control:** Verified using custom decorators and helper properties like [is_resident](file:///S:/PROJECTS/barangay_connect/resident/models.py#L20-L22), [is_staff](file:///S:/PROJECTS/barangay_connect/resident/models.py#L29-L31), and [is_official](file:///S:/PROJECTS/barangay_connect/resident/models.py#L24-L26).
3. **Reports:** Managed through the [Report](file:///S:/PROJECTS/barangay_connect/resident/models.py#L37-L58) model with `report_type` (`complaint` or `incident`) and `status` (`Pending`, `In Progress`, `Resolved`).
4. **Analytics:** Gathered in [views.py](file:///S:/PROJECTS/barangay_connect/barangay_app/views.py#L93) and visually displayed to officials using Chart.js on the [official_reports.html](file:///S:/PROJECTS/barangay_connect/barangay_app/templates/barangay_app/official_reports.html) page.

---

## 💻 Tech Stack
* **Framework:** Django (Python)
* **Database:** SQLite
* **Frontend:** Tailwind CSS, HTML5, Vanilla JavaScript, Lucide Icons
* **Charts & Analytics:** Chart.js
