import sqlite3

from werkzeug.security import generate_password_hash


def main():
    con = sqlite3.connect("arcturide.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS password_reset_tokens(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, token_hash TEXT NOT NULL UNIQUE, purpose TEXT DEFAULT 'reset', expires_at TEXT NOT NULL, used_at TEXT, created_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    user_columns = {row["name"] for row in cur.execute("PRAGMA table_info(users)").fetchall()}
    if "workspace_id" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN workspace_id INTEGER")
    if "client_id" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN client_id INTEGER")
    if "must_reset_password" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN must_reset_password INTEGER DEFAULT 0")
    if "created_at" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
        cur.execute("UPDATE users SET created_at=CURRENT_TIMESTAMP WHERE created_at IS NULL")

    workspace = cur.execute("SELECT id FROM workspaces WHERE slug='aapti' ORDER BY id LIMIT 1").fetchone()
    if workspace:
        workspace_id = workspace["id"]
    else:
        workspace_id = cur.execute("INSERT INTO workspaces(name,slug) VALUES(?,?)", ("Aapti", "aapti")).lastrowid

    admin = cur.execute("SELECT id FROM users WHERE lower(email)=? ORDER BY id LIMIT 1", ("vikash@aapti.local",)).fetchone()
    if admin:
        admin_id = admin["id"]
        cur.execute(
            "UPDATE users SET role='admin',workspace_id=?,active=1,client_id=NULL,client_name=NULL,manager_id=NULL,must_reset_password=0 WHERE id=?",
            (workspace_id, admin_id),
        )
    else:
        admin_id = cur.execute(
            "INSERT INTO users(name,email,password,role,workspace_id,active) VALUES(?,?,?,?,?,1)",
            ("Vikash", "vikash@aapti.local", generate_password_hash("vikash123"), "admin", workspace_id),
        ).lastrowid

    for table in (
        "entity_comments",
        "comments",
        "activities",
        "uploads",
        "notifications",
        "password_reset_tokens",
        "lead_activities",
        "client_results",
        "client_requests",
        "content_items",
        "tasks",
        "project_services",
        "projects",
        "client_services",
        "leads",
        "clients",
        "records",
    ):
        cur.execute(f"DELETE FROM {table}")

    cur.execute("DELETE FROM users WHERE id<>?", (admin_id,))
    con.commit()
    con.close()
    print(f"cleaned_live_db_keep_admin_id={admin_id}")


if __name__ == "__main__":
    main()
