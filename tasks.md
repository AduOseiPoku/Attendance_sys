# Church QR Attendance MVP Tasks

This file turns `plan.md` into an implementation checklist.

## Phase 0: Project Decisions

- [ ] This is **single-church only**: one recurring venue, one QR flow, one check-in landing page.
- [ ] Keep the MVP scope limited to member lookup, onboarding, attendance logging, admin reporting, and QR generation.
- [ ] Enforce “single-church” in the implementation: **no Church model** and **no church foreign keys** on `Member` / `AttendanceLog`.
- [ ] Exclude payments, messaging, complex analytics, and role-based permissions from the first release.


## Phase 1: Project Setup and Data Model

### 1.1 Start the Django project

- [ ] Create the Django project root.
- [ ] Install Django, PostgreSQL driver, and QR generation dependencies.
- [ ] Configure the virtual environment for the workspace.
- [ ] Create the main Django app for attendance.

### 1.2 Configure settings

- [ ] Add the attendance app to `INSTALLED_APPS`.
- [ ] Configure PostgreSQL as the default database.
- [ ] Set template directories for the project.
- [ ] Set static file support for templates and future assets.

### 1.3 Build the database models

- [ ] Create `Member` with `student_id`, `name`, `phone_number`, `address`, `created_at`, and `updated_at`.
- [ ] Add an index or fast lookup support for `name`.
- [ ] Create `AttendanceLog` with `member`, `timestamp`, and optional service grouping fields if needed later.
- [ ] Add a uniqueness rule to prevent duplicate check-ins in the same visit window.
- [ ] Register the models in the Django admin.
- [ ] Run migrations and verify the schema is created.

## Phase 2: QR Landing Flow

### 2.1 Create the landing route

- [ ] Add the `/scan/` route.
- [ ] Make the route render the main church check-in landing page.
- [ ] Show the church name and a short instruction message.

### 2.2 Add the entry choices

- [ ] Add a button for "I am a member".
- [ ] Add a button for "I am new here".
- [ ] Make the page mobile-first and easy to use on a phone.

### 2.3 Connect QR generation

- [ ] Create a QR generation script.
- [ ] Point the QR to the `/scan/` page.
- [ ] Save the generated QR image for printing or sharing.

## Phase 3: Member Search and Auto-Fill

### 3.1 Create the search endpoint

- [ ] Add `/scan/search/` as a JSON endpoint.
- [ ] Accept search text from the frontend.
- [ ] Search by partial name and partial student ID.
- [ ] Limit the returned results to a small number.

### 3.2 Build the live search UI

- [ ] Add a search box for members.
- [ ] Add debounced requests so the database is not hit on every keypress.
- [ ] Render matching members in a dropdown list.
- [ ] Allow selecting a member from the list.

### 3.3 Auto-fill selected member data

- [ ] Fill the form fields when a member is selected.
- [ ] Keep the selected member ID available for confirmation.
- [ ] Show a confirm attendance action after selection.

### 3.4 Handle no-match behavior

- [ ] Show a clear no-results message.
- [ ] Offer onboarding when the search returns nothing.
- [ ] Preserve the typed input so onboarding starts with the same details.

## Phase 4: Attendance Confirmation

### 4.1 Create the confirmation endpoint

- [ ] Add `/scan/confirm/`.
- [ ] Re-check that the selected member still exists.
- [ ] Validate that the check-in is still allowed.

### 4.2 Log attendance

- [ ] Create an attendance record for the current visit.
- [ ] Prevent duplicate attendance for the same church visit.
- [ ] Return a friendly success message after saving.

### 4.3 Handle duplicate check-ins

- [ ] Detect when the member is already checked in.
- [ ] Return a non-error response that explains the person is already recorded.
- [ ] Keep the UI from allowing accidental double submits.

## Phase 5: New Visitor Onboarding

### 5.1 Create onboarding routes

- [ ] Add `/onboard/` for the form.
- [ ] Add `/onboard/submit/` for the POST submission.
- [ ] Allow the onboarding page to be opened from the landing page or search fallback.

### 5.2 Build the onboarding form

- [ ] Collect student ID.
- [ ] Collect full name.
- [ ] Collect phone number.
- [ ] Collect address.
- [ ] Make the form mobile-friendly.

### 5.3 Validate onboarding submissions

- [ ] Reject empty required fields.
- [ ] Check whether the student ID already exists.
- [ ] If the student ID exists, route the person back to member selection.
- [ ] If it does not exist, create the member profile.
- [ ] Create the attendance record immediately after the profile is created.

### 5.4 Show onboarding success

- [ ] Display a success screen after registration and check-in.
- [ ] Show the church name and the person’s name on the success screen.

## Phase 6: Templates and UX

### 6.1 Create shared layout styling

- [ ] Use consistent Tailwind CDN styling across all pages.
- [ ] Keep the design simple, clean, and easy to use on mobile.
- [ ] Make form spacing and button sizes touch-friendly.

### 6.2 Create templates

- [ ] Build the landing page template.
- [ ] Build the member lookup template.
- [ ] Build the onboarding template.
- [ ] Build the success template.

### 6.3 Add frontend interactions

- [ ] Add JavaScript for autocomplete.
- [ ] Add request debouncing.
- [ ] Add the dropdown selection behavior.
- [ ] Add auto-fill behavior.

## Phase 7: Admin Reporting

### 7.1 Admin configuration

- [ ] Register the attendance models in admin.
- [ ] Show useful list columns for quick review.
- [ ] Keep admin actions simple.

### 7.2 Attendance reporting

- [ ] Show the count of checked-in members for the day or service window.
- [ ] Show the list of checked-in members for the day.
- [ ] Avoid global present/absent reporting unless the church defines an expected roster.

## Phase 8: Validation and Testing

### 8.1 Member search tests

- [ ] Test partial name search.
- [ ] Test partial student ID search.
- [ ] Test no-results behavior.

### 8.2 Onboarding tests

- [ ] Test onboarding for a brand-new person.
- [ ] Test duplicate student ID handling.
- [ ] Test validation for empty fields.

### 8.3 Attendance tests

- [ ] Test a successful member check-in.
- [ ] Test duplicate check-in prevention.
- [ ] Test a deleted or missing member before confirmation.

### 8.4 UI flow tests

- [ ] Test the QR landing page.
- [ ] Test switching between member and new visitor flows.
- [ ] Test mobile-sized layouts.

## Definition of Done

- [ ] Scanning the QR opens the church landing page.
- [ ] A member can search by name or student ID.
- [ ] Selecting a match auto-fills the form.
- [ ] A confirmed member is checked in once per visit.
- [ ] A new visitor can register and be checked in.
- [ ] The admin can view church attendance.
- [ ] Missing or duplicate data is handled cleanly.

## Build Order Summary

1. Set up the Django project and PostgreSQL.
2. Create the models and migrations.
3. Build the `/scan/` landing page.
4. Add the live member search endpoint and UI.
5. Add attendance confirmation.
6. Add onboarding for new visitors.
7. Add admin reporting.
8. Run validation tests and fix edge cases.
