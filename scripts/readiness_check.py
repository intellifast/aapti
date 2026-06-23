import importlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def expect(condition, label):
    if not condition:
        raise AssertionError(label)
    print(f"ok {label}")


def main():
    tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    os.environ["ARCTURIDE_DB"] = str(Path(tempdir.name) / "readiness.db")
    os.environ.pop("ARCTURIDE_DEMO_DATA", None)
    app_module = importlib.import_module("app")
    flask_app = app_module.app
    flask_app.config.update(TESTING=True)

    client = flask_app.test_client()
    response = client.post("/login", data={"email": "vikash@aapti.local", "password": "vikash123"})
    expect(response.status_code == 302, "admin login")

    for path in ("/", "/admin/users", "/crm", "/clients", "/work", "/content", "/team", "/portal", "/settings"):
        response = client.get(path)
        expect(response.status_code == 200, f"admin route {path}")
        expect(b"Traceback" not in response.data, f"no traceback {path}")

    created_user = client.post(
        "/admin/users",
        data={
            "name": "Launch Employee",
            "email": "launch.employee@aapti.local",
            "role": "employee",
            "password": "launchpass123",
        },
        follow_redirects=True,
    )
    expect(created_user.status_code == 200, "admin creates employee")
    expect(b"Password setup link" in created_user.data, "setup link prepared")

    con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
    con.row_factory = sqlite3.Row
    employee = con.execute("SELECT * FROM users WHERE email=?", ("launch.employee@aapti.local",)).fetchone()
    token = con.execute(
        "SELECT token_hash FROM password_reset_tokens WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (employee["id"],),
    ).fetchone()
    con.close()
    expect(employee is not None and employee["must_reset_password"] == 1, "employee requires setup password")
    expect(token is not None, "employee setup token stored")

    employee_client = flask_app.test_client()
    response = employee_client.post(
        "/login",
        data={"email": "launch.employee@aapti.local", "password": "launchpass123"},
        follow_redirects=False,
    )
    expect(response.status_code == 302 and "/reset-password/" in response.headers.get("Location", ""), "first login redirects to reset")

    service_id = sqlite3.connect(os.environ["ARCTURIDE_DB"]).execute("SELECT id FROM services WHERE code='seo'").fetchone()[0]
    client.post(
        "/clients",
        data={
            "name": "Launch Client",
            "industry": "Manufacturing",
            "primary_contact": "Client Owner",
            "contact_email": "client.owner@example.com",
            "service_id": service_id,
        },
    )
    con = sqlite3.connect(os.environ["ARCTURIDE_DB"])
    con.row_factory = sqlite3.Row
    client_row = con.execute("SELECT * FROM clients WHERE name=?", ("Launch Client",)).fetchone()
    con.close()
    expect(client_row is not None, "admin creates client")

    created_client_user = client.post(
        "/admin/users",
        data={
            "name": "Launch Client User",
            "email": "launch.client@aapti.local",
            "role": "client",
            "client_id": client_row["id"],
            "password": "clientpass123",
        },
    )
    expect(created_client_user.status_code == 302, "admin creates linked client user")

    forbidden_client = flask_app.test_client()
    response = forbidden_client.post("/login", data={"email": "launch.client@aapti.local", "password": "clientpass123"})
    expect(response.status_code == 302 and "/reset-password/" in response.headers.get("Location", ""), "client first login redirects to reset")

    lead = client.post("/crm/leads", data={"company": "Launch Lead", "stage": "New", "service_interest": "SEO"})
    expect(lead.status_code == 302, "admin creates lead")

    project = client.post(
        "/work/projects",
        data={"name": "Launch SEO", "client_id": client_row["id"], "service_id": service_id},
    )
    expect(project.status_code == 302, "admin creates project")

    task = client.post("/work/tasks", data={"title": "Launch task", "service_id": service_id})
    expect(task.status_code == 302, "admin creates task")

    content = client.post("/content", data={"title": "Launch content", "client_id": client_row["id"]})
    expect(content.status_code == 302, "admin creates content")

    result = client.post(
        "/results",
        data={"client_id": client_row["id"], "result_type": "SEO", "title": "Launch result"},
    )
    expect(result.status_code == 302, "admin creates result")

    print("readiness_check=ok")


if __name__ == "__main__":
    main()
