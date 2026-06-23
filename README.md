# Aapti

A connected operating system for a digital marketing agency: CRM, client services, workstreams, task assignment, content planning, client approvals, capacity, and manual results tracking.

## Run locally

```powershell
python app.py
```

Open `http://127.0.0.1:5000`.

Initial admin login:

- Admin: `vikash@aapti.local` / `vikash123`

After signing in, open **Admin Users** to create manager, employee, and client accounts with their own email addresses and password setup links.

## What is included in v1

- CRM lead pipeline with service interest, owner, follow-ups, activity notes, and conversion to client.
- Client workspaces with selected services and account owner.
- Service-driven projects/workstreams with generated starter tasks.
- Work module with list, board, and calendar views.
- Task assignment with owner, stage, estimated hours, priority, due date, approval status, and filters.
- Team capacity based on estimated task hours using an 8h/day and 40h/week default.
- Content Studio for ideas, briefs, scripts, captions, creative references, approval status, publishing calendar, and result notes.
- Client portal with isolated client-visible work, approvals, requests, content, workstreams, and shared results.
- Client approval workflow for tasks and content: waiting, approved, and changes requested.
- Manual results dashboard by client/service for SEO, social, UGC/video, paid ads, website, and content outcomes.
- Realtime Reports module for clients, leads, work, content, approvals, capacity, project progress, and results.
- Admin user management with role-based access, account activation/deactivation, and password setup/reset links.
- Ask Aapti workspace assistant with role-filtered context and optional Gemini integration.

## Product flow

The app is built around this chain:

`CRM Lead -> Client -> Service -> Workstream -> Task/Content -> Approval -> Result`

Avoid adding standalone modules unless they support this chain.

## Role behavior

- Admin can create users, reset passwords, activate/deactivate accounts, and access all workspace modules.
- Manager can create clients, services, projects, tasks, results, and manage workflow setup.
- Employee can view assigned work, content, and team capacity relevant to them.
- Client can only see their own client-visible portal data and can approve/request changes where allowed.

## Configuration

Set `SECRET_KEY` in production.

For live password reset emails, configure SMTP environment variables:

```powershell
$env:SMTP_HOST="smtp.example.com"
$env:SMTP_PORT="587"
$env:SMTP_USERNAME="your-smtp-user"
$env:SMTP_PASSWORD="your-smtp-password"
$env:SMTP_FROM="no-reply@yourdomain.com"
```

Without SMTP, admins can still create users and share setup links from the Admin Users page, but public forgot-password emails will not be delivered.

SQLite data is stored in the configured database path; uploaded files are stored in `uploads/`.

## Gemini intelligence

Set the Gemini API key before starting the app. The key is used only by the Flask server and is never sent to the browser.

```powershell
$env:GEMINI_API_KEY="your-key-here"
$env:GEMINI_MODEL="gemini-2.5-flash"
python app.py
```

Alternatively, copy `.env.example` to `.env`, add your key, and restart the app. The `.env` file is excluded from Git.

If Gemini is not configured or temporarily unavailable, Ask Aapti falls back to local workspace answers.

## Validation

Run:

```powershell
python -m py_compile app.py
python tests\test_app.py
```
