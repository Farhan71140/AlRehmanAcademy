import csv, os, secrets, sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
DB = os.path.join(app.root_path, "academy.db")
CATS = {"male": ("Male Islamic Courses", "male-quran.webp", 24),
        "female": ("Female Islamic Courses", "female-quran.webp", 24),
        "kids": ("Kids Islamic Courses", "kids-learning.webp", 20),
        "professional": ("Professional Islamic Courses", "professional-islamic.webp", 8)}
CONTENT = {
 "hero_title": "Knowledge. Faith. Excellence.",
 "hero_sub": "Discover a Deeper Understanding of Islam.",
 "hero_text": "Explore structured Islamic educational programmes designed to nurture knowledge, strengthen faith and develop character across every generation.",
 "about_text": "Al Rehman Islamic Academy offers structured Islamic education for men, women, children and professionals.",
 "faculty_text": "Our faculty profiles are published here by the academy.",
 "contact_email": "", "contact_phone": ""}

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

def init():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    c.executescript("""CREATE TABLE IF NOT EXISTS courses(id INTEGER PRIMARY KEY, category TEXT, name TEXT, duration TEXT,
      description TEXT DEFAULT '', syllabus TEXT DEFAULT '', objectives TEXT DEFAULT '', eligibility TEXT DEFAULT '', featured INT DEFAULT 0,
      UNIQUE(category,name));
    CREATE TABLE IF NOT EXISTS enquiries(id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, name TEXT, email TEXT,
      phone TEXT, age INT, gender TEXT, category TEXT, course TEXT, pref TEXT, message TEXT, status TEXT DEFAULT 'New');
    CREATE TABLE IF NOT EXISTS content(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS admin(id INTEGER PRIMARY KEY, pw TEXT);""")
    for k, v in CONTENT.items(): c.execute("INSERT OR IGNORE INTO content VALUES(?,?)", (k, v))
    if not c.execute("SELECT 1 FROM admin").fetchone():
        pw = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(10)
        c.execute("INSERT INTO admin(pw) VALUES(?)", (generate_password_hash(pw),))
        print(f"\n>>> ADMIN PASSWORD: {pw}  (set ADMIN_PASSWORD env var to choose your own)\n")
    path = os.path.join(app.root_path, "data", "courses.csv")
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("name"):
                c.execute("INSERT OR IGNORE INTO courses(category,name,duration,description,syllabus,objectives,eligibility,featured) VALUES(?,?,?,?,?,?,?,?)",
                  (r["category"].strip().lower(), r["name"].strip(), r["duration"].strip(), r.get("description",""), r.get("syllabus",""),
                   r.get("objectives",""), r.get("eligibility",""), 1 if r.get("featured","").strip() in ("1","yes") else 0))
    for k, (t, _, n) in CATS.items():
        have = c.execute("SELECT COUNT(*) FROM courses WHERE category=?", (k,)).fetchone()[0]
        if have != n: print(f"WARNING: {t}: {have} courses loaded, expected {n}")
    c.commit(); c.close()

def content():
    return {r["k"]: r["v"] for r in db().execute("SELECT * FROM content")}

@app.context_processor
def inject():
    return dict(C=content(), CATS=CATS, csrf=csrf_token)

def csrf_token():
    session.setdefault("_csrf", secrets.token_hex(16)); return session["_csrf"]

@app.before_request
def check_csrf():
    if request.method == "POST" and request.form.get("_csrf") != session.get("_csrf"): abort(400)

def admin_only(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"): return redirect(url_for("login"))
        return f(*a, **k)
    return w

@app.route("/")
def home():
    feat = db().execute("SELECT * FROM courses WHERE featured=1 LIMIT 6").fetchall()
    counts = {r["category"]: r["n"] for r in db().execute("SELECT category, COUNT(*) n FROM courses GROUP BY category")}
    return render_template("index.html", feat=feat, counts=counts)

@app.route("/courses")
def courses():
    q, cat = request.args.get("q", "").strip(), request.args.get("cat", "")
    sql, args = "SELECT * FROM courses WHERE name LIKE ?", [f"%{q}%"]
    if cat in CATS: sql += " AND category=?"; args.append(cat)
    rows = db().execute(sql + " ORDER BY category, name", args).fetchall()
    return render_template("courses.html", rows=rows, q=q, cat=cat)

@app.route("/course/<int:cid>")
def course(cid):
    c = db().execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone() or abort(404)
    return render_template("course.html", c=c)

@app.route("/enquire", methods=["POST"])
def enquire():
    f = request.form
    if not (f.get("name") and f.get("email") and f.get("phone")):
        flash("Please complete name, email and phone."); return redirect(url_for("home") + "#contact")
    try: age = int(f.get("age") or 0)
    except ValueError: age = 0
    db().execute("INSERT INTO enquiries(name,email,phone,age,gender,category,course,pref,message) VALUES(?,?,?,?,?,?,?,?,?)",
      (f["name"][:120], f["email"][:160], f["phone"][:40], age, f.get("gender", ""), f.get("category", ""), f.get("course", "")[:160],
       f.get("pref", ""), f.get("message", "")[:2000]))
    db().commit(); flash("Thank you. Your enquiry has been received and our admissions team will contact you shortly.")
    return redirect(url_for("home") + "#contact")

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        row = db().execute("SELECT pw FROM admin").fetchone()
        if check_password_hash(row["pw"], request.form.get("password", "")):
            session.clear(); session["admin"] = True; return redirect(url_for("admin"))
        flash("Incorrect password.")
    return render_template("login.html")

@app.route("/admin/logout")
def logout():
    session.clear(); return redirect(url_for("home"))

@app.route("/admin")
@admin_only
def admin():
    return render_template("admin.html", enq=db().execute("SELECT * FROM enquiries ORDER BY id DESC").fetchall(),
                           rows=db().execute("SELECT * FROM courses ORDER BY category,name").fetchall())

@app.route("/admin/course/<cid>", methods=["GET", "POST"])
@admin_only
def edit_course(cid):
    c = None if cid == "new" else (db().execute("SELECT * FROM courses WHERE id=?", (cid,)).fetchone() or abort(404))
    if request.method == "POST":
        f = request.form
        v = (f["category"], f["name"].strip(), f["duration"].strip(), f["description"], f["syllabus"], f["objectives"], f["eligibility"], 1 if f.get("featured") else 0)
        if c: db().execute("UPDATE courses SET category=?,name=?,duration=?,description=?,syllabus=?,objectives=?,eligibility=?,featured=? WHERE id=?", v + (cid,))
        else: db().execute("INSERT INTO courses(category,name,duration,description,syllabus,objectives,eligibility,featured) VALUES(?,?,?,?,?,?,?,?)", v)
        db().commit(); flash("Course saved."); return redirect(url_for("admin"))
    return render_template("edit_course.html", c=c)

@app.route("/admin/enquiry/<int:eid>", methods=["POST"])
@admin_only
def enquiry_status(eid):
    db().execute("UPDATE enquiries SET status=? WHERE id=?", (request.form["status"], eid)); db().commit()
    return redirect(url_for("admin") + "#enquiries")

@app.route("/admin/content", methods=["POST"])
@admin_only
def save_content():
    for k in CONTENT:
        if k in request.form: db().execute("INSERT OR REPLACE INTO content VALUES(?,?)", (k, request.form[k]))
    db().commit(); flash("Website content updated."); return redirect(url_for("admin") + "#content")

init()
if __name__ == "__main__":
    app.run(debug=False)
