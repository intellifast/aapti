import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class AgencyPlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["ARCTURIDE_DB"] = str(Path(cls.tempdir.name) / "platform.db")
        os.environ["ARCTURIDE_DEMO_DATA"] = "1"
        cls.module = importlib.import_module("app")
        cls.app = cls.module.app
        cls.app.config.update(TESTING=True)

    def login(self, email, password):
        client = self.app.test_client()
        response = client.post("/login", data={"email": email, "password": password})
        self.assertEqual(response.status_code, 302)
        return client

    def test_manager_can_use_every_core_module(self):
        client = self.login("vikash@aapti.local", "vikash123")
        dashboard = client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        for text in (b"CRM", b"Clients", b"Work", b"Creator Studio", b"Reports", b"Team"):
            self.assertIn(text, dashboard.data)
        for path in ("/crm", "/clients", "/work", "/content", "/team", "/settings"):
            self.assertEqual(client.get(path).status_code, 200, path)
        settings = client.get("/settings")
        for service in (b"Website Development", b"Social Media Management", b"UGC Production", b"SEO", b"Paid Advertising"):
            self.assertIn(service, settings.data)

    def test_admin_can_create_user_and_prepare_password_reset(self):
        client = self.login("vikash@aapti.local", "vikash123")
        admin_page = client.get("/admin/users")
        self.assertEqual(admin_page.status_code, 200)
        self.assertIn(b"Users & access", admin_page.data)
        self.assertIn(b"Last login", admin_page.data)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        self.assertIsNotNone(con.execute("SELECT last_login_at FROM users WHERE email='vikash@aapti.local'").fetchone()[0])
        con.close()

        created = client.post("/admin/users", data={
            "name": "New Team Member",
            "email": "new.member@aapti.local",
            "role": "employee",
            "password": "firstpass123",
        }, follow_redirects=True)
        self.assertEqual(created.status_code, 200)
        self.assertIn(b"new.member@aapti.local", created.data)
        self.assertIn(b"Password setup link", created.data)

        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        con.row_factory = sqlite3.Row
        user = con.execute("SELECT * FROM users WHERE email='new.member@aapti.local'").fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(user["must_reset_password"], 1)
        token_row = con.execute("SELECT token_hash FROM password_reset_tokens WHERE user_id=? ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
        con.close()
        self.assertIsNotNone(token_row)

        reset_prepared = client.post(f"/admin/users/{user['id']}/reset", follow_redirects=True)
        self.assertEqual(reset_prepared.status_code, 200)
        self.assertIn(b"Password setup link", reset_prepared.data)

    def test_stage_two_dashboard_is_connected_and_role_aware(self):
        manager = self.login("vikash@aapti.local", "vikash123")
        dashboard = manager.get("/")
        self.assertEqual(dashboard.status_code, 200)
        for text in (b"Due today", b"Client approvals", b"Clients at risk", b"Team capacity", b"What needs attention", b"DELIVERY PULSE", b"PROJECT PROGRESS", b"Recent activity"):
            self.assertIn(text, dashboard.data)
        self.assertIn(b"SEO audit findings for approval", dashboard.data)
        self.assertIn(b"Chowdary Organic Growth", dashboard.data)
        self.assertNotIn(b"Expected this month", dashboard.data)

        employee = self.login("swapna@aapti.local", "swapna123")
        employee_dashboard = employee.get("/")
        self.assertEqual(employee_dashboard.status_code, 200)
        self.assertIn(b"Team capacity", employee_dashboard.data)
        self.assertIn(b"SEO keyword research", employee_dashboard.data)
        self.assertNotIn(b"Create 90-day SEO strategy", employee_dashboard.data)

        portal_client = self.login("client@chowdary.local", "client123")
        client_dashboard = portal_client.get("/")
        self.assertEqual(client_dashboard.status_code, 200)
        self.assertIn(b"Your client workspace", client_dashboard.data)
        self.assertIn(b"Client approvals", client_dashboard.data)
        self.assertNotIn(b"Team capacity", client_dashboard.data)
        self.assertNotIn(b"Clients at risk", client_dashboard.data)

    def test_service_project_generates_workflow_and_searchable_tasks(self):
        client = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        service_id = con.execute("SELECT id FROM services WHERE code='website'").fetchone()[0]
        manager_id = con.execute("SELECT id FROM users WHERE name='Vikash'").fetchone()[0]
        con.close()
        created_client = client.post("/clients", data={"name": "Website Workflow Client", "industry": "Technology", "service_id": service_id, "account_manager_id": manager_id})
        self.assertEqual(created_client.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        client_id = con.execute("SELECT id FROM clients WHERE name='Website Workflow Client'").fetchone()[0]
        before = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        con.close()
        response = client.post("/work/projects", data={
            "name": "Corporate website rebuild", "client_id": client_id, "manager_id": manager_id,
            "service_id": service_id, "start_date": "2026-06-22", "due_date": "2026-09-30",
            "description": "Rebuild the corporate website.", "create_starter_tasks": "on",
        })
        self.assertEqual(response.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        generated = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] - before
        task_titles = {row[0] for row in con.execute("SELECT title FROM tasks WHERE title IN ('Run website discovery call','Create sitemap and user flow','Launch website and handover')").fetchall()}
        con.close()
        self.assertEqual(generated, 9)
        self.assertEqual(task_titles, {"Run website discovery call", "Create sitemap and user flow", "Launch website and handover"})
        search = client.get("/search?q=sitemap")
        self.assertIn(b"Create sitemap and user flow", search.data)

    def test_project_creation_does_not_allocate_tasks_by_default(self):
        client = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        service_id = con.execute("SELECT id FROM services WHERE code='branding'").fetchone()[0]
        manager_id = con.execute("SELECT id FROM users WHERE name='Vikash'").fetchone()[0]
        con.close()
        self.assertEqual(client.post("/clients", data={"name": "Branding Only Client", "industry": "Retail", "service_id": service_id, "account_manager_id": manager_id}).status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        client_id = con.execute("SELECT id FROM clients WHERE name='Branding Only Client'").fetchone()[0]
        before = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        con.close()
        response = client.post("/work/projects", data={
            "name": "Brand launch", "client_id": client_id, "manager_id": manager_id,
            "service_id": service_id, "start_date": "2026-06-22",
        })
        self.assertEqual(response.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        after = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        project_service = con.execute(
            "SELECT COUNT(*) FROM projects p JOIN project_services ps ON ps.project_id=p.id WHERE p.name='Brand launch' AND ps.service_id=?",
            (service_id,),
        ).fetchone()[0]
        con.close()
        self.assertEqual(after, before)
        self.assertEqual(project_service, 1)

    def test_crm_content_and_task_actions(self):
        client = self.login("vikash@aapti.local", "vikash123")
        created = client.post("/crm/leads", data={"company": "Test Prospect", "stage": "New", "service_interest": "SEO"})
        self.assertEqual(created.status_code, 302)
        self.assertIn(b"Test Prospect", client.get("/crm").data)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        client_id = con.execute("SELECT id FROM clients WHERE name='Chowdary Spinners'").fetchone()[0]
        owner_id = con.execute("SELECT id FROM users WHERE name='Swapna'").fetchone()[0]
        service_id = con.execute("SELECT id FROM services WHERE code='website'").fetchone()[0]
        con.close()
        service_lead = client.post("/crm/leads", data={"company": "Dropdown Service Prospect", "stage": "New", "service_id": service_id})
        self.assertEqual(service_lead.status_code, 302)
        self.assertIn(b"Website Development", client.get("/crm").data)
        content = client.post("/content", data={"title": "New reel idea", "client_id": client_id, "owner_id": owner_id, "platform": "Instagram", "format": "Reel", "status": "Idea", "client_visible": "on"})
        self.assertEqual(content.status_code, 302)
        self.assertIn(b"New reel idea", client.get("/content?mode=studio").data)

    def test_stage_three_crm_pipeline_fields_activity_and_convert_action(self):
        client = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        owner_id = con.execute("SELECT id FROM users WHERE name='Vikash'").fetchone()[0]
        con.close()
        created = client.post("/crm/leads", data={
            "company": "Pipeline Health Co",
            "contact_name": "Meera",
            "email": "meera@example.com",
            "phone": "9999999999",
            "source": "Cold email",
            "stage": "Qualified",
            "owner_id": owner_id,
            "next_follow_up": "2026-06-24",
            "service_interest": "Website + SEO",
            "expected_value": "125000",
            "probability": "60",
            "website": "https://pipeline.example",
            "industry": "Healthcare",
            "notes": "Asked for a website and SEO plan.",
        })
        self.assertEqual(created.status_code, 302)
        crm = client.get("/crm")
        for text in (b"Pipeline Health Co", b"Pipeline value", b"Weighted value", b"Follow-ups due", b"Lead activity", b"Convert to client", b"Website + SEO", b"60%"):
            self.assertIn(text, crm.data)
        for text in (b"Interested service/workstream", b"Expected project value", b"Win probability (%)", b"Used to calculate weighted pipeline value.", b"Next follow-up date", b"When the owner should contact this lead next."):
            self.assertIn(text, crm.data)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        lead_id = con.execute("SELECT id FROM leads WHERE company='Pipeline Health Co'").fetchone()[0]
        self.assertEqual(con.execute("SELECT expected_value,probability,industry FROM leads WHERE id=?", (lead_id,)).fetchone(), (125000.0, 60, "Healthcare"))
        self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM lead_activities WHERE lead_id=?", (lead_id,)).fetchone()[0], 1)
        con.close()

        self.assertEqual(client.post(f"/crm/leads/{lead_id}/notes", data={"note": "Sent proposal deck."}).status_code, 302)
        self.assertEqual(client.post(f"/crm/leads/{lead_id}/stage", data={"stage": "Proposal"}).status_code, 302)
        conversion_page = client.get(f"/crm/leads/{lead_id}/convert")
        self.assertEqual(conversion_page.status_code, 200)
        self.assertIn(b"Create client workspace", conversion_page.data)
        self.assertIn(b"Website Development", conversion_page.data)
        self.assertIn(b"Create the client portal login separately in Admin Users", conversion_page.data)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        self.assertEqual(con.execute("SELECT stage FROM leads WHERE id=?", (lead_id,)).fetchone()[0], "Proposal")
        actions = [row[0] for row in con.execute("SELECT action FROM lead_activities WHERE lead_id=? ORDER BY id", (lead_id,)).fetchall()]
        con.close()
        self.assertIn("Note added", actions)
        self.assertIn("Stage changed", actions)

    def test_stage_four_lead_conversion_creates_client_services_and_workstreams(self):
        client = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        owner_id = con.execute("SELECT id FROM users WHERE name='Vikash'").fetchone()[0]
        website_id = con.execute("SELECT id FROM services WHERE code='website'").fetchone()[0]
        seo_id = con.execute("SELECT id FROM services WHERE code='seo'").fetchone()[0]
        con.close()
        client.post("/crm/leads", data={
            "company": "Convert Me Pvt Ltd",
            "contact_name": "Anil",
            "email": "anil@example.com",
            "source": "Referral",
            "stage": "Proposal",
            "owner_id": owner_id,
            "service_interest": "Website and SEO",
            "expected_value": "210000",
            "probability": "80",
            "website": "https://convert.example",
            "industry": "Manufacturing",
            "notes": "Website rebuild with SEO foundation.",
        })
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        lead_id = con.execute("SELECT id FROM leads WHERE company='Convert Me Pvt Ltd'").fetchone()[0]
        before_projects = con.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        before_tasks = con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        con.close()
        response = client.post(f"/crm/leads/{lead_id}/convert", data={
            "account_manager_id": owner_id,
            "start_date": "2026-07-01",
            "due_date": "2026-08-15",
            "scope": "Approved website and SEO onboarding scope.",
            "service_id": [website_id, seo_id],
            "create_starter_tasks": "on",
        })
        self.assertEqual(response.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        client_row = con.execute("SELECT id,account_manager_id,primary_contact,contact_email FROM clients WHERE name='Convert Me Pvt Ltd'").fetchone()
        self.assertIsNotNone(client_row)
        self.assertEqual(client_row[1], owner_id)
        self.assertEqual(client_row[2], "Anil")
        self.assertEqual(client_row[3], "anil@example.com")
        linked = {row[0] for row in con.execute("SELECT service_id FROM client_services WHERE client_id=?", (client_row[0],))}
        self.assertEqual(linked, {website_id, seo_id})
        self.assertEqual(con.execute("SELECT stage FROM leads WHERE id=?", (lead_id,)).fetchone()[0], "Won")
        self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM projects").fetchone()[0] - before_projects, 2)
        self.assertGreater(con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], before_tasks)
        actions = [row[0] for row in con.execute("SELECT action FROM lead_activities WHERE lead_id=?", (lead_id,)).fetchall()]
        con.close()
        self.assertIn("Converted to client", actions)
        clients_page = client.get("/clients")
        self.assertIn(b"Convert Me Pvt Ltd", clients_page.data)
        self.assertIn(b"Website Development", clients_page.data)

    def test_stage_five_service_templates_create_service_specific_tasks(self):
        client = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        owner_id = con.execute("SELECT id FROM users WHERE name='Vikash'").fetchone()[0]
        social_id = con.execute("SELECT id FROM services WHERE code='social'").fetchone()[0]
        ugc_id = con.execute("SELECT id FROM services WHERE code='ugc'").fetchone()[0]
        con.close()
        client.post("/crm/leads", data={
            "company": "Template Client",
            "contact_name": "Nisha",
            "email": "nisha@example.com",
            "stage": "Proposal",
            "owner_id": owner_id,
            "service_interest": "Social and UGC",
        })
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        lead_id = con.execute("SELECT id FROM leads WHERE company='Template Client'").fetchone()[0]
        con.close()
        page = client.get(f"/crm/leads/{lead_id}/convert")
        self.assertIn(b"starter tasks", page.data)
        self.assertIn(b"Plan monthly social calendar", page.data)
        self.assertIn(b"Shortlist UGC angles", page.data)
        response = client.post(f"/crm/leads/{lead_id}/convert", data={
            "account_manager_id": owner_id,
            "start_date": "2026-07-01",
            "due_date": "2026-08-15",
            "service_id": [social_id, ugc_id],
            "create_starter_tasks": "on",
        })
        self.assertEqual(response.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        titles = {row[0] for row in con.execute("SELECT title FROM tasks WHERE title IN ('Plan monthly social calendar','Send calendar and creatives for approval','Shortlist UGC angles','Send final videos for approval')").fetchall()}
        con.close()
        self.assertEqual(titles, {"Plan monthly social calendar", "Send calendar and creatives for approval", "Shortlist UGC angles", "Send final videos for approval"})

    def test_client_portal_is_isolated_and_can_approve(self):
        client = self.login("client@chowdary.local", "client123")
        dashboard = client.get("/")
        self.assertIn(b"Your client workspace", dashboard.data)
        self.assertNotIn(b"CRM", dashboard.data)
        self.assertEqual(client.get("/crm").status_code, 302)
        portal = client.get("/portal")
        self.assertIn(b"CHOWDARY SPINNERS", portal.data)
        self.assertNotIn(b"GreenRoot Foods", portal.data)
        content_page = client.get("/content")
        self.assertIn(b"SEO audit findings for approval", content_page.data)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        item_id = con.execute("SELECT id FROM content_items WHERE title='SEO audit findings for approval'").fetchone()[0]
        con.close()
        decision = client.post(f"/content/{item_id}/status", data={"status": "Approved"})
        self.assertEqual(decision.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        self.assertEqual(con.execute("SELECT status FROM content_items WHERE id=?", (item_id,)).fetchone()[0], "Approved")
        con.close()
        self.assertEqual(client.post("/work/tasks", data={"title": "Forbidden"}).status_code, 403)

    def test_employee_gets_personal_work_without_admin_controls(self):
        client = self.login("swapna@aapti.local", "swapna123")
        work = client.get("/work")
        self.assertEqual(work.status_code, 200)
        self.assertIn(b"SEO keyword research", work.data)
        self.assertNotIn(b"Create 90-day SEO strategy", work.data)
        self.assertEqual(client.get("/settings").status_code, 403)
        self.assertEqual(client.post("/clients", data={"name": "Forbidden Client"}).status_code, 403)

    def test_old_login_session_is_upgraded_before_workspace_writes(self):
        client = self.login("vikash@aapti.local", "vikash123")
        with client.session_transaction() as stale_session:
            stale_session.pop("workspace_id", None)
            stale_session.pop("client_id", None)
        response = client.post("/settings/services", data={
            "name": "Conversion Optimisation",
            "description": "Landing page and funnel improvement.",
            "stages": "Audit, Experiment Plan, Implementation, Client Review, Report",
        })
        self.assertEqual(response.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        saved = con.execute("SELECT workspace_id FROM services WHERE code='conversion-optimisation'").fetchone()
        con.close()
        self.assertIsNotNone(saved)
        self.assertIsNotNone(saved[0])

    def test_failed_duplicate_write_does_not_lock_following_requests(self):
        client = self.login("vikash@aapti.local", "vikash123")
        duplicate = client.post("/settings/services", data={"name": "SEO", "stages": "Audit, Report"})
        self.assertEqual(duplicate.status_code, 303)
        self.assertEqual(client.get("/clients").status_code, 200)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        service_id = con.execute("SELECT id FROM services WHERE code='seo'").fetchone()[0]
        con.close()
        created = client.post("/clients", data={"name": "Lock Recovery Client", "industry": "Testing", "service_id": service_id})
        self.assertEqual(created.status_code, 302)
        self.assertIn(b"Lock Recovery Client", client.get("/clients").data)

    def test_client_services_and_work_views_are_connected(self):
        client = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        seo_id = con.execute("SELECT id FROM services WHERE code='seo'").fetchone()[0]
        social_id = con.execute("SELECT id FROM services WHERE code='social'").fetchone()[0]
        con.close()
        response = client.post("/clients", data={
            "name": "Multi Service Client", "industry": "Retail",
            "service_id": [seo_id, social_id], "primary_contact": "Riya",
        })
        self.assertEqual(response.status_code, 302)
        page = client.get("/clients")
        self.assertIn(b"Multi Service Client", page.data)
        self.assertIn(b"Social Media Management", page.data)
        self.assertIn(b"Client service workstreams", page.data)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        client_id = con.execute("SELECT id FROM clients WHERE name='Multi Service Client'").fetchone()[0]
        linked = {row[0] for row in con.execute("SELECT service_id FROM client_services WHERE client_id=?", (client_id,))}
        con.close()
        self.assertEqual(linked, {seo_id, social_id})
        updated = client.post(f"/clients/{client_id}/services", data={"service_id": social_id})
        self.assertEqual(updated.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        self.assertEqual(con.execute("SELECT service_id FROM client_services WHERE client_id=?", (client_id,)).fetchall(), [(social_id,)])
        con.close()
        work = client.get("/work")
        self.assertIn(b"Active workstreams", work.data)
        self.assertIn(b"Stage progress", work.data)
        self.assertIn(b"Next task", work.data)
        self.assertIn(b'data-task-view-mode="board"', work.data)
        self.assertIn(b'data-task-view-mode="calendar"', work.data)
        self.assertIn(b'data-task-row', work.data)
        self.assertIn(b'data-project-services', work.data)
        calendar_page = client.get("/work?view=calendar")
        self.assertIn(b'data-initial-task-view="calendar"', calendar_page.data)
        self.assertIn(b"Open work calendar", calendar_page.data)

    def test_stage_six_client_portal_shows_service_roadmap(self):
        client = self.login("client@chowdary.local", "client123")
        portal = client.get("/portal")
        self.assertEqual(portal.status_code, 200)
        self.assertIn(b"Your service workstreams", portal.data)
        self.assertIn(b"Chowdary Organic Growth", portal.data)
        self.assertIn(b"Next task", portal.data)
        self.assertIn(b"Stage progress", portal.data)

    def test_stage_seven_task_fields_filters_and_views_are_useful(self):
        client = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        project_id, client_id = con.execute("SELECT id,client_id FROM projects ORDER BY id LIMIT 1").fetchone()
        service_id = con.execute("SELECT id FROM services WHERE code='seo'").fetchone()[0]
        stage_id = con.execute("SELECT id FROM workflow_stages WHERE service_id=? ORDER BY position LIMIT 1", (service_id,)).fetchone()[0]
        owner_id = con.execute("SELECT id FROM users WHERE name='Swapna'").fetchone()[0]
        con.close()
        response = client.post("/work/tasks", data={
            "title": "Stage 7 approval task",
            "project_id": project_id,
            "service_id": service_id,
            "stage_id": stage_id,
            "assignee_id": owner_id,
            "status": "Client Review",
            "priority": "High",
            "estimated_hours": "3.5",
            "due_date": "2026-06-30",
            "description": "Needs client-facing review before completion.",
            "client_visible": "on",
        })
        self.assertEqual(response.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        task_id, estimated_hours, saved_stage_id, client_visible = con.execute("SELECT id,estimated_hours,stage_id,client_visible FROM tasks WHERE title='Stage 7 approval task'").fetchone()
        con.close()
        self.assertEqual((estimated_hours, saved_stage_id, client_visible), (3.5, stage_id, 1))

        work = client.get("/work")
        for text in (b"Estimated hours", b"Workflow stage", b"Client visible / approval-related", b"class=\"work-filter\"", b"Service / stage", b"Approval"):
            self.assertIn(text, work.data)
        self.assertIn(b"data-task-form", work.data)
        self.assertIn(b"data-task-project", work.data)
        self.assertIn(b"data-task-service", work.data)
        self.assertIn(b"data-task-stage", work.data)
        self.assertIn(f'data-service="{service_id}"'.encode(), work.data)
        self.assertIn(f'data-url="/work/tasks/{task_id}"'.encode(), work.data)
        self.assertIn(b"data-hours=\"3.5\"", work.data)
        self.assertIn(b"data-approval=\"1\"", work.data)
        task_page = client.get(f"/work/tasks/{task_id}")
        self.assertEqual(task_page.status_code, 200)
        for text in (b"Stage 7 approval task", b"WORK DETAILS", b"Needs client-facing review before completion.", b"Update status", b"Edit task", b"Save task changes", b"Work updates", b"Post update"):
            self.assertIn(text, task_page.data)

        updated = client.post(f"/work/tasks/{task_id}", data={
            "title": "Updated stage 7 task",
            "project_id": project_id,
            "service_id": service_id,
            "stage_id": stage_id,
            "assignee_id": owner_id,
            "status": "Working",
            "priority": "Low",
            "progress": "45",
            "estimated_hours": "4.25",
            "due_date": "2026-07-01",
            "description": "Updated task notes.",
            "client_visible": "on",
        })
        self.assertEqual(updated.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        saved = con.execute("SELECT title,status,priority,progress,estimated_hours,due_date,description,client_visible FROM tasks WHERE id=?", (task_id,)).fetchone()
        con.close()
        self.assertEqual(saved, ("Updated stage 7 task", "Working", "Low", 45, 4.25, "2026-07-01", "Updated task notes.", 1))
        note = client.post(f"/work/tasks/{task_id}/updates", data={"body": "Finished first pass, waiting on assets.", "client_visible": "on"}, follow_redirects=True)
        self.assertEqual(note.status_code, 200)
        self.assertIn(b"Finished first pass, waiting on assets.", note.data)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        comment = con.execute("SELECT body,client_visible FROM entity_comments WHERE entity_type='task' AND entity_id=? ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
        con.close()
        self.assertEqual(comment, ("Finished first pass, waiting on assets.", 1))

        filtered = client.get(f"/work?client_id={client_id}&service_id={service_id}&assignee_id={owner_id}&status=Client+Review&approval=required&due=week")
        self.assertNotIn(b"Updated stage 7 task", filtered.data)
        filtered = client.get(f"/work?client_id={client_id}&service_id={service_id}&assignee_id={owner_id}&status=Working&due=week")
        self.assertIn(b"Updated stage 7 task", filtered.data)
        unrelated = client.get(f"/work?client_id={client_id}&service_id={service_id}&assignee_id={owner_id}&status=Completed&approval=required")
        self.assertNotIn(b"Updated stage 7 task", unrelated.data)
        status_redirect = client.post(f"/work/tasks/{task_id}/status", data={"status": "Internal Review", "next": f"/work/tasks/{task_id}"})
        self.assertEqual(status_redirect.location, f"/work/tasks/{task_id}")

    def test_task_assignment_rejects_project_service_stage_mismatch(self):
        client = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        project_id = con.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()[0]
        project_services = [row[0] for row in con.execute("SELECT service_id FROM project_services WHERE project_id=?", (project_id,)).fetchall()]
        other = con.execute(
            "SELECT id FROM services WHERE id NOT IN (%s) ORDER BY id LIMIT 1" % ",".join("?" for _ in project_services),
            project_services,
        ).fetchone()
        self.assertIsNotNone(other)
        service_id = other[0]
        stage_id = con.execute("SELECT id FROM workflow_stages WHERE service_id=? ORDER BY position LIMIT 1", (service_id,)).fetchone()[0]
        con.close()

        response = client.post("/work/tasks", data={
            "title": "Mismatched project service task",
            "project_id": project_id,
            "service_id": service_id,
            "stage_id": stage_id,
            "status": "Not started",
            "priority": "Medium",
        })
        self.assertEqual(response.status_code, 303)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        saved = con.execute("SELECT COUNT(*) FROM tasks WHERE title='Mismatched project service task'").fetchone()[0]
        con.close()
        self.assertEqual(saved, 0)

    def test_stage_eight_team_capacity_uses_estimated_hours(self):
        client = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        project_id = con.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()[0]
        service_id = con.execute("SELECT id FROM services WHERE code='seo'").fetchone()[0]
        owner_id = con.execute("SELECT id FROM users WHERE name='Swapna'").fetchone()[0]
        con.close()
        response = client.post("/work/tasks", data={
            "title": "Capacity overload planning task",
            "project_id": project_id,
            "service_id": service_id,
            "assignee_id": owner_id,
            "status": "Not started",
            "priority": "High",
            "estimated_hours": "48",
            "due_date": "2026-06-26",
        })
        self.assertEqual(response.status_code, 302)
        team = client.get("/team")
        self.assertEqual(team.status_code, 200)
        for text in (b"8h/day", b"40h/week", b"Assigned this week", b"Available", b"Next due work", b"Capacity overload planning task", b"Overloaded"):
            self.assertIn(text, team.data)
        dashboard = client.get("/")
        self.assertIn(b"Team capacity", dashboard.data)
        self.assertIn(b"h / 40h this week", dashboard.data)

    def test_stage_nine_client_approvals_are_actionable(self):
        manager = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        project_id = con.execute("SELECT p.id FROM projects p JOIN clients c ON c.id=p.client_id WHERE c.name='Chowdary Spinners' LIMIT 1").fetchone()[0]
        client_id = con.execute("SELECT id FROM clients WHERE name='Chowdary Spinners'").fetchone()[0]
        service_id = con.execute("SELECT id FROM services WHERE code='seo'").fetchone()[0]
        owner_id = con.execute("SELECT id FROM users WHERE name='Vikash'").fetchone()[0]
        con.close()
        self.assertEqual(manager.post("/work/tasks", data={
            "title": "Approve technical SEO scope",
            "project_id": project_id,
            "service_id": service_id,
            "assignee_id": owner_id,
            "status": "Client Review",
            "priority": "High",
            "estimated_hours": "2",
            "due_date": "2026-06-29",
            "description": "Confirm the recommended technical fixes.",
            "client_visible": "on",
        }).status_code, 302)
        self.assertEqual(manager.post("/content", data={
            "title": "Approval caption draft",
            "client_id": client_id,
            "project_id": project_id,
            "owner_id": owner_id,
            "platform": "LinkedIn",
            "format": "Post",
            "status": "Client Review",
            "client_visible": "on",
        }).status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        task_id = con.execute("SELECT id FROM tasks WHERE title='Approve technical SEO scope'").fetchone()[0]
        content_id = con.execute("SELECT id FROM content_items WHERE title='Approval caption draft'").fetchone()[0]
        self.assertEqual(con.execute("SELECT approval_status FROM tasks WHERE id=?", (task_id,)).fetchone()[0], "Waiting for client")
        self.assertEqual(con.execute("SELECT approval_status FROM content_items WHERE id=?", (content_id,)).fetchone()[0], "Waiting for client")
        con.close()

        portal_client = self.login("client@chowdary.local", "client123")
        portal = portal_client.get("/portal")
        self.assertIn(b"Work waiting for your approval", portal.data)
        self.assertIn(b"Approve technical SEO scope", portal.data)
        self.assertIn(b"Approval caption draft", portal.data)
        self.assertIn(b"Request changes", portal.data)
        self.assertEqual(portal_client.post(f"/work/tasks/{task_id}/approval", data={"decision": "approve", "comment": "Looks good."}).status_code, 302)
        self.assertEqual(portal_client.post(f"/content/{content_id}/approval", data={"decision": "changes", "comment": "Please make the hook stronger."}).status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        self.assertEqual(con.execute("SELECT status,approval_status,progress FROM tasks WHERE id=?", (task_id,)).fetchone(), ("Approved", "Approved", 100))
        self.assertEqual(con.execute("SELECT status,approval_status FROM content_items WHERE id=?", (content_id,)).fetchone(), ("Changes Requested", "Changes requested"))
        notes = [row[0] for row in con.execute("SELECT body FROM entity_comments WHERE entity_type IN ('task','content') AND body IN ('Looks good.','Please make the hook stronger.')").fetchall()]
        con.close()
        self.assertEqual(set(notes), {"Looks good.", "Please make the hook stronger."})
        dashboard = manager.get("/")
        self.assertIn(b"Client approvals", dashboard.data)

    def test_stage_ten_content_calendar_filters_and_rich_fields(self):
        client = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        client_id = con.execute("SELECT id FROM clients WHERE name='Chowdary Spinners'").fetchone()[0]
        project_id = con.execute("SELECT id FROM projects WHERE client_id=? LIMIT 1", (client_id,)).fetchone()[0]
        service_id = con.execute("SELECT id FROM services WHERE code='social'").fetchone()[0]
        owner_id = con.execute("SELECT id FROM users WHERE name='Swapna'").fetchone()[0]
        con.close()
        response = client.post("/content", data={
            "title": "July founder reel script",
            "client_id": client_id,
            "project_id": project_id,
            "service_id": service_id,
            "platform": "Instagram",
            "format": "Reel",
            "pillar": "Founder story",
            "idea": "Show the founder explaining the yarn quality process.",
            "brief": "Warm behind-the-scenes reel.",
            "script": "Hook, three process points, CTA.",
            "caption": "Quality starts before spinning.",
            "creative_reference": "Reference: handheld factory walkthrough",
            "performance_summary": "Target: saves and profile visits",
            "result_notes": "Review after publishing.",
            "owner_id": owner_id,
            "status": "Scheduled",
            "publish_date": "2026-07-08",
            "client_visible": "on",
        })
        self.assertEqual(response.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        saved = con.execute("SELECT service_id,creative_reference,performance_summary,result_notes FROM content_items WHERE title='July founder reel script'").fetchone()
        con.close()
        self.assertEqual(saved, (service_id, "Reference: handheld factory walkthrough", "Target: saves and profile visits", "Review after publishing."))
        page = client.get(f"/content?mode=calendar&platform=Instagram&service_id={service_id}&status=Scheduled&month=2026-07")
        self.assertEqual(page.status_code, 200)
        for text in (b"Content Calendar", b"PUBLISHING PLAN", b"July 2026", b"July founder reel script", b"All platforms", b"Service/workstream", b"Creator Studio", b"Approvals", b"Performance"):
            self.assertIn(text, page.data)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        content_id = con.execute("SELECT id FROM content_items WHERE title='July founder reel script'").fetchone()[0]
        con.close()
        self.assertIn(f'href="/content/{content_id}"'.encode(), page.data)
        studio = client.get(f"/content?mode=studio&platform=Instagram&service_id={service_id}&status=Scheduled&month=2026-07")
        for text in (b"Creator Studio", b"PRODUCTION BOARD", b"Ref: Reference", b"Script: Hook", b"Open / edit"):
            self.assertIn(text, studio.data)
        detail = client.get(f"/content/{content_id}")
        self.assertEqual(detail.status_code, 200)
        for text in (b"CONTENT ITEM", b"Edit content", b"Content updates", b"Save content changes"):
            self.assertIn(text, detail.data)
        edited = client.post(f"/content/{content_id}", data={
            "title": "Updated founder reel script",
            "client_id": client_id,
            "project_id": project_id,
            "service_id": service_id,
            "platform": "Instagram",
            "format": "Reel",
            "pillar": "Founder story",
            "idea": "Updated idea",
            "brief": "Updated brief",
            "script": "Updated script",
            "caption": "Updated caption",
            "creative_reference": "Updated reference",
            "performance_summary": "Updated performance",
            "result_notes": "Updated result notes",
            "owner_id": owner_id,
            "status": "Internal Review",
            "publish_date": "2026-07-09",
            "client_visible": "on",
        })
        self.assertEqual(edited.status_code, 302)
        note = client.post(f"/content/{content_id}/updates", data={"body": "Creative draft is ready for review.", "client_visible": "on"}, follow_redirects=True)
        self.assertEqual(note.status_code, 200)
        self.assertIn(b"Creative draft is ready for review.", note.data)
        status_redirect = client.post(f"/content/{content_id}/status", data={"status": "Client Review", "next": f"/content/{content_id}"})
        self.assertEqual(status_redirect.location, f"/content/{content_id}")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        saved_edit = con.execute("SELECT title,status,publish_date,brief FROM content_items WHERE id=?", (content_id,)).fetchone()
        comment = con.execute("SELECT body,client_visible FROM entity_comments WHERE entity_type='content' AND entity_id=? ORDER BY id DESC LIMIT 1", (content_id,)).fetchone()
        con.close()
        self.assertEqual(saved_edit, ("Updated founder reel script", "Client Review", "2026-07-09", "Updated brief"))
        self.assertEqual(comment, ("Creative draft is ready for review.", 1))
        performance = client.get(f"/content?mode=performance&platform=Instagram&service_id={service_id}&status=Scheduled&month=2026-07")
        self.assertNotIn(b"Updated founder reel script", performance.data)
        hidden = client.get(f"/content?mode=calendar&platform=LinkedIn&service_id={service_id}&status=Scheduled&month=2026-07")
        self.assertNotIn(b"Updated founder reel script", hidden.data)

    def test_stage_eleven_manual_results_dashboard_and_portal(self):
        manager = self.login("vikash@aapti.local", "vikash123")
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        client_id = con.execute("SELECT id FROM clients WHERE name='Chowdary Spinners'").fetchone()[0]
        service_id = con.execute("SELECT id FROM services WHERE code='seo'").fetchone()[0]
        project_id = con.execute("SELECT id FROM projects WHERE client_id=? LIMIT 1", (client_id,)).fetchone()[0]
        task_id = con.execute("SELECT id FROM tasks WHERE project_id=? ORDER BY id LIMIT 1", (project_id,)).fetchone()[0]
        content_id = con.execute("SELECT id FROM content_items WHERE client_id=? ORDER BY id LIMIT 1", (client_id,)).fetchone()[0]
        con.close()
        response = manager.post("/results", data={
            "client_id": client_id,
            "service_id": service_id,
            "project_id": project_id,
            "task_id": task_id,
            "content_id": content_id,
            "result_type": "SEO",
            "title": "Organic visibility improved",
            "metric_label": "Keyword movement",
            "metric_value": "+18%",
            "comparison": "vs last month",
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "summary": "Priority keywords moved after on-page fixes.",
            "client_visible": "on",
        })
        self.assertEqual(response.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        saved = con.execute("SELECT result_type,metric_value,client_visible FROM client_results WHERE title='Organic visibility improved'").fetchone()
        con.close()
        self.assertEqual(saved, ("SEO", "+18%", 1))
        dashboard = manager.get("/")
        for text in (b"Service-wise outcomes", b"Record result", b"Organic visibility improved", b"+18%", b"Keyword movement"):
            self.assertIn(text, dashboard.data)
        reports = manager.get("/reports")
        for text in (b"Management reports", b"REALTIME REPORTS", b"Organic visibility improved", b"Service-wise activity", b"Oldest waiting approvals"):
            self.assertIn(text, reports.data)

        portal_client = self.login("client@chowdary.local", "client123")
        self.assertEqual(portal_client.post("/results", data={"title": "Forbidden", "result_type": "SEO", "client_id": client_id}).status_code, 403)
        portal = portal_client.get("/portal")
        for text in (b"What improved or shipped", b"Organic visibility improved", b"+18%", b"Priority keywords moved"):
            self.assertIn(text, portal.data)

    def test_stage_twelve_permissions_legacy_routes_and_docs_are_ready(self):
        manager = self.login("vikash@aapti.local", "vikash123")
        employee = self.login("swapna@aapti.local", "swapna123")
        portal_client = self.login("client@chowdary.local", "client123")

        self.assertEqual(employee.post("/work/tasks", data={"title": "Employee should not assign"}).status_code, 403)
        self.assertEqual(employee.post("/work/projects", data={"name": "Employee project"}).status_code, 403)
        self.assertEqual(employee.post("/results", data={"title": "Employee result", "result_type": "SEO", "client_id": 1}).status_code, 403)
        self.assertEqual(employee.get("/settings").status_code, 403)
        self.assertEqual(portal_client.get("/crm").status_code, 302)
        self.assertEqual(portal_client.get("/settings").status_code, 403)

        self.assertEqual(manager.get("/module/work").status_code, 302)
        self.assertEqual(manager.get("/module/old-reports").status_code, 404)

        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        chowdary_id = con.execute("SELECT id FROM clients WHERE name='Chowdary Spinners'").fetchone()[0]
        other_id = con.execute("SELECT id FROM clients WHERE name!='Chowdary Spinners' ORDER BY id LIMIT 1").fetchone()[0]
        other_project_id = con.execute("SELECT id FROM projects WHERE client_id!=? ORDER BY id LIMIT 1", (chowdary_id,)).fetchone()
        if other_project_id is None:
            other_project_id = con.execute("INSERT INTO projects(workspace_id,client_id,name,status) VALUES(?,?,?,?)", (1, other_id, "Other client project", "Active")).lastrowid
        else:
            other_project_id = other_project_id[0]
        con.commit()
        con.close()
        invalid = manager.post("/results", data={
            "client_id": chowdary_id,
            "project_id": other_project_id,
            "result_type": "SEO",
            "title": "Invalid cross-client result",
        })
        self.assertEqual(invalid.status_code, 303)
        self.assertNotIn(b"Invalid cross-client result", manager.get("/").data)

        readme = Path(__file__).resolve().parents[1].joinpath("README.md").read_text(encoding="utf-8")
        for text in ("CRM Lead -> Client -> Service -> Workstream -> Task/Content -> Approval -> Result", "Manual results dashboard", "Admin:", "Manager can", "Employee can", "Client can"):
            self.assertIn(text, readme)

    def test_all_mutating_forms_validate_and_remain_usable(self):
        manager = self.login("vikash@aapti.local", "vikash123")
        for path in ("/crm/leads", "/clients", "/work/tasks", "/content", "/settings/services"):
            self.assertIn(manager.post(path, data={}).status_code, (302, 303), path)
        self.assertEqual(manager.post("/work/projects", data={"name": "Incomplete"}).status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        project_id = con.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()[0]
        service_id = con.execute("SELECT service_id FROM project_services WHERE project_id=? ORDER BY service_id LIMIT 1", (project_id,)).fetchone()[0]
        owner_id = con.execute("SELECT id FROM users WHERE name='Swapna'").fetchone()[0]
        con.close()
        task_response = manager.post("/work/tasks", data={"title": "Mutation audit task", "project_id": project_id, "service_id": service_id, "assignee_id": owner_id})
        self.assertEqual(task_response.status_code, 302)
        con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
        task_id = con.execute("SELECT id FROM tasks WHERE title='Mutation audit task'").fetchone()[0]
        con.close()
        self.assertEqual(manager.post(f"/work/tasks/{task_id}/status", data={"status": "Working"}).status_code, 302)
        client = self.login("client@chowdary.local", "client123")
        self.assertEqual(client.post("/portal/requests", data={"title": "Please update the homepage copy", "priority": "Medium"}).status_code, 302)
        self.assertEqual(client.get("/portal").status_code, 200)
        self.assertEqual(manager.get("/clients").status_code, 200)


if __name__ == "__main__":
    unittest.main()
