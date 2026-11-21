import os, sqlite3
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join("/tmp", "resume_job_tracker")
UPLOAD_DIR = os.path.join(INSTANCE_DIR, "uploads")

os.makedirs(INSTANCE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
DB_PATH = os.path.join(INSTANCE_DIR, "tracker.db")
STATUSES = ["Wishlist", "Applied", "Assessment", "Interview", "Offer", "Rejected"]
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            theme TEXT NOT NULL DEFAULT 'dark',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            location TEXT DEFAULT '',
            job_url TEXT DEFAULT '',
            salary TEXT DEFAULT '',
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Wishlist',
            applied_date TEXT DEFAULT '',
            follow_up_date TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            label TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
init_db()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.context_processor
def inject_globals():
    return {"statuses": STATUSES}

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email, and a password of at least 8 characters.", "error")
            return render_template("register.html")
        try:
            with db() as con:
                cur = con.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",
                                  (name, email, generate_password_hash(password)))
                session["user_id"] = cur.lastrowid
                session["user_name"] = name
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "error")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    with db() as con:
        apps = con.execute("SELECT * FROM applications WHERE user_id=? ORDER BY created_at DESC", (uid,)).fetchall()
        resume_count = con.execute("SELECT COUNT(*) FROM resumes WHERE user_id=?", (uid,)).fetchone()[0]
    counts = {s: sum(1 for a in apps if a["status"] == s) for s in STATUSES}
    upcoming = [a for a in apps if a["follow_up_date"] and a["follow_up_date"] >= date.today().isoformat()]
    upcoming.sort(key=lambda a: a["follow_up_date"])
    return render_template("dashboard.html", applications=apps, counts=counts,
                           total=len(apps), resume_count=resume_count, upcoming=upcoming[:5])

@app.route("/kanban")
@login_required
def kanban():
    with db() as con:
        apps = con.execute("SELECT * FROM applications WHERE user_id=? ORDER BY created_at DESC",
                           (session["user_id"],)).fetchall()
    return render_template("kanban.html", applications=apps)

@app.route("/applications/new", methods=["GET", "POST"])
@app.route("/applications/<int:app_id>/edit", methods=["GET", "POST"])
@login_required
def application_form(app_id=None):
    item = None
    if app_id:
        with db() as con:
            item = con.execute("SELECT * FROM applications WHERE id=? AND user_id=?",
                               (app_id, session["user_id"])).fetchone()
        if not item: abort(404)
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in
                ["company","role","location","job_url","salary","description","status","applied_date","follow_up_date","notes"]}
        if not data["company"] or not data["role"] or data["status"] not in STATUSES:
            flash("Company, job role, and a valid status are required.", "error")
            return render_template("application_form.html", item=item)
        with db() as con:
            if item:
                con.execute("""UPDATE applications SET company=?,role=?,location=?,job_url=?,salary=?,
                    description=?,status=?,applied_date=?,follow_up_date=?,notes=? WHERE id=? AND user_id=?""",
                    (*data.values(), app_id, session["user_id"]))
            else:
                con.execute("""INSERT INTO applications(user_id,company,role,location,job_url,salary,
                    description,status,applied_date,follow_up_date,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (session["user_id"], *data.values()))
        flash("Application saved successfully.", "success")
        return redirect(url_for("kanban"))
    return render_template("application_form.html", item=item)

@app.route("/applications/<int:app_id>/delete", methods=["POST"])
@login_required
def delete_application(app_id):
    with db() as con:
        con.execute("DELETE FROM applications WHERE id=? AND user_id=?", (app_id, session["user_id"]))
    flash("Application deleted.", "success")
    return redirect(request.referrer or url_for("kanban"))

@app.route("/api/applications/<int:app_id>/status", methods=["POST"])
@login_required
def update_status(app_id):
    status = request.json.get("status", "") if request.is_json else request.form.get("status", "")
    if status not in STATUSES: return jsonify(ok=False, error="Invalid status"), 400
    with db() as con:
        cur = con.execute("UPDATE applications SET status=? WHERE id=? AND user_id=?",
                          (status, app_id, session["user_id"]))
    if not cur.rowcount: return jsonify(ok=False, error="Not found"), 404
    return jsonify(ok=True)

@app.route("/resumes", methods=["GET", "POST"])
@login_required
def resumes():
    if request.method == "POST":
        file = request.files.get("resume")
        label = request.form.get("label", "").strip()
        if not file or not file.filename:
            flash("Choose a resume file first.", "error")
        elif not allowed_file(file.filename):
            flash("Only PDF, DOC, and DOCX files are allowed.", "error")
        else:
            original = secure_filename(file.filename)
            unique = f"{session['user_id']}_{int(datetime.now().timestamp())}_{original}"
            file.save(os.path.join(UPLOAD_DIR, unique))
            with db() as con:
                con.execute("INSERT INTO resumes(user_id,filename,original_name,label) VALUES(?,?,?,?)",
                            (session["user_id"], unique, original, label or "My resume"))
            flash("Resume uploaded.", "success")
        return redirect(url_for("resumes"))
    with db() as con:
        items = con.execute("SELECT * FROM resumes WHERE user_id=? ORDER BY created_at DESC",
                            (session["user_id"],)).fetchall()
    return render_template("resumes.html", resumes=items)

@app.route("/resumes/<int:resume_id>/download")
@login_required
def download_resume(resume_id):
    with db() as con:
        item = con.execute("SELECT * FROM resumes WHERE id=? AND user_id=?",
                           (resume_id, session["user_id"])).fetchone()
    if not item: abort(404)
    return send_from_directory(UPLOAD_DIR, item["filename"], as_attachment=True, download_name=item["original_name"])

@app.route("/resumes/<int:resume_id>/delete", methods=["POST"])
@login_required
def delete_resume(resume_id):
    with db() as con:
        item = con.execute("SELECT * FROM resumes WHERE id=? AND user_id=?",
                           (resume_id, session["user_id"])).fetchone()
        if item:
            path = os.path.join(UPLOAD_DIR, item["filename"])
            if os.path.exists(path): os.remove(path)
            con.execute("DELETE FROM resumes WHERE id=? AND user_id=?", (resume_id, session["user_id"]))
    flash("Resume deleted.", "success")
    return redirect(url_for("resumes"))

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    with db() as con:
        user = con.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        theme = request.form.get("theme", "dark")
        if name and theme in ("dark", "light"):
            with db() as con:
                con.execute("UPDATE users SET name=?,theme=? WHERE id=?", (name, theme, session["user_id"]))
            session["user_name"] = name
            flash("Settings updated.", "success")
            return redirect(url_for("settings"))
    return render_template("settings.html", user=user)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
