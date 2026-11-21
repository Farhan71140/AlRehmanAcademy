import csv, json, os, secrets, time
import urllib.request
from functools import wraps

import psycopg2
import psycopg2.extras
from flask import (Flask, render_template, request, redirect, url_for, session,
                   flash, g, abort, jsonify)

try:  # optional: loads .env when running locally
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__, static_folder="public/static")
ON_VERCEL = bool(os.environ.get("VERCEL"))
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),  # set SECRET_KEY on Vercel!
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=ON_VERCEL,
)

DATABASE_URL = os.environ.get("DATABASE_URL", "")      # Supabase "Transaction pooler" URI
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")  # staff login password
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")      # key for the chat assistant (set on Vercel)
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
STATUSES = ["New", "Contacted", "Assessment", "Enrolled", "Declined"]

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
    "contact_email": "", "contact_phone": "",
    "donate_intro": "Every contribution, big or small, is a seed of lasting reward. Choose a cause close to your heart and give with sincerity.",
    "donate_link": "", "donate_upi": "", "donate_payee": "Al Rehman Islamic Academy",
    "donate_bank_holder": "", "donate_bank_name": "", "donate_bank_account": "", "donate_bank_ifsc": "",
    "donate_note": "Please mention your chosen cause when you donate, and contact us if you need a receipt or have any question about how your donation is used."}


# ---------------------------------------------------------------- database
def connect():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor, connect_timeout=10)


def db():
    if "db" not in g:
        g.db = connect()
    return g.db


def many(sql, args=()):
    with db().cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def one(sql, args=()):
    with db().cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()


def run(sql, args=()):
    with db().cursor() as cur:
        cur.execute(sql, args)
    db().commit()


@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d:
        d.close()


def like(q):
    """Escape % and _ so visitors can't use them as wildcards."""
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def init():
    """Tables are created by supabase/supabase_schema.sql. This only fills in defaults."""
    if not DATABASE_URL:
        print("WARNING: DATABASE_URL is not set, the site cannot reach Supabase.")
        return
    c = connect()
    try:
        with c.cursor() as cur:
            cur.execute("INSERT INTO content(k,v) SELECT * FROM unnest(%s::text[], %s::text[]) ON CONFLICT (k) DO NOTHING",
                        (list(CONTENT.keys()), list(CONTENT.values())))
            cur.execute("SELECT COUNT(*) AS n FROM courses")
            if cur.fetchone()["n"] == 0:  # first run only: load data/courses.csv
                path = os.path.join(app.root_path, "data", "courses.csv")
                with open(path, encoding="utf-8") as f:
                    rows = [(r["category"].strip().lower(), r["name"].strip(), (r.get("duration") or "").strip(),
                             r.get("description") or "", r.get("syllabus") or "", r.get("objectives") or "",
                             r.get("eligibility") or "", 1 if (r.get("featured") or "").strip() in ("1", "yes") else 0)
                            for r in csv.DictReader(f) if r.get("name")]
                psycopg2.extras.execute_values(
                    cur, "INSERT INTO courses(category,name,duration,description,syllabus,objectives,eligibility,featured) "
                         "VALUES %s ON CONFLICT (category,name) DO NOTHING", rows)
            cur.execute("SELECT category, COUNT(*) AS n FROM courses GROUP BY category")
            have = {r["category"]: r["n"] for r in cur.fetchall()}
        c.commit()
        for k, (t, _, n) in CATS.items():
            if have.get(k, 0) != n:
                print(f"WARNING: {t}: {have.get(k, 0)} courses loaded, expected {n}")
    except Exception as e:  # keep the site importable even if the DB hiccups
        c.rollback()
        print("DB init problem:", e)
    finally:
        c.close()


_cc = {"t": 0, "v": {}}


def content():
    """Website text, cached for 20 seconds to save a database round-trip on every page."""
    if time.time() - _cc["t"] > 20:
        try:
            _cc.update(v={r["k"]: r["v"] for r in many("SELECT k, v FROM content")}, t=time.time())
        except Exception as e:  # DB problem: fall back to default text instead of crashing every page
            print("content() failed:", e)
            db().rollback()
    return {**CONTENT, **_cc["v"]}


# ---------------------------------------------------------------- security helpers
def csrf_token():
    session.setdefault("_csrf", secrets.token_hex(16))
    return session["_csrf"]


@app.context_processor
def inject():
    return dict(C=content(), CATS=CATS, csrf=csrf_token, is_admin=bool(session.get("admin")))


@app.before_request
def check_csrf():
    if request.method == "POST":
        token = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
        if not token or token != session.get("_csrf"):
            abort(400)


def admin_only(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return f(*a, **k)
    return w


# ---------------------------------------------------------------- public pages
@app.route("/")
def home():
    feat = many("SELECT * FROM courses WHERE featured=1 ORDER BY name LIMIT 6")
    counts = {r["category"]: r["n"] for r in many("SELECT category, COUNT(*) AS n FROM courses GROUP BY category")}
    return render_template("index.html", feat=feat, counts=counts)


@app.route("/courses")
def courses():
    q, cat = request.args.get("q", "").strip()[:80], request.args.get("cat", "")
    groups = {k: [] for k in CATS}  # catalogue order = the order courses were added (id)
    for r in many("SELECT id, category, name, duration FROM courses ORDER BY id"):
        if r["category"] in groups:
            groups[r["category"]].append(r)
    return render_template("courses.html", groups=groups, q=q, cat=cat)


@app.route("/course/<int:cid>")
def course(cid):
    c = one("SELECT * FROM courses WHERE id=%s", (cid,)) or abort(404)
    return render_template("course.html", c=c)


@app.route("/api/search")
def api_search():
    """Live results for the nav-bar search box."""
    q = request.args.get("q", "").strip()[:60]
    if len(q) < 2:
        return jsonify(results=[])
    rows = many("SELECT id, name, category, duration FROM courses WHERE name ILIKE %s "
                "ORDER BY (name ILIKE %s) DESC, name LIMIT 7", (like(q), like(q)[1:]))
    return jsonify(results=[dict(url=url_for("course", cid=r["id"]), name=r["name"], duration=r["duration"],
                                 cat=CATS[r["category"]][0] if r["category"] in CATS else r["category"])
                            for r in rows])


# ---------------------------------------------------------------- AI chat assistant
_cp = {"t": 0, "v": ""}
_hits = {}


def chat_prompt():
    """System prompt for the chat assistant. The course list comes from the database, cached for 10 minutes."""
    if time.time() - _cp["t"] > 600:
        try:
            groups = {}
            for r in many("SELECT id, category, name, duration FROM courses ORDER BY name"):
                groups.setdefault(r["category"], []).append(f"- {r['name']} ({r['duration']}) [/course/{r['id']}]")
            _cp.update(t=time.time(), v="\n".join(f"{CATS[k][0]}:\n" + "\n".join(v) for k, v in groups.items() if k in CATS))
        except Exception as e:
            print("chat_prompt failed:", e)
            db().rollback()
    catalog = _cp["v"] or "(course list unavailable right now: send visitors to the Courses page)"
    C = content()
    phone = C.get("contact_phone") or "+92 319 2788158"
    email = f", email {C['contact_email']}" if C.get("contact_email") else ""
    divisions = ", ".join(v[0] for v in CATS.values())
    return f"""You are the friendly website assistant for Al Rehman Islamic Academy, which offers structured Islamic education for men, women, children and professionals.

You help visitors with: choosing a course, course durations and categories, how to apply, and how to donate.

Academy facts:
- Divisions: {divisions}.
- Admissions: the visitor submits the enquiry form in the Contact section of the home page (/#contact). The admissions team replies personally and guides the choice of course. Learning preference can be online, in person or no preference.
- Contact: phone and WhatsApp {phone}{email}.
- Donations: the Donate section of the home page (/#donate). Visitors pick an amount in US dollars ($20, $50, $100, $150, $200, or their own amount) and a cause: masjid construction and care, feeding the hungry, orphans and widows, Quran and Islamic education, Zakat, Sadaqah Jariyah, medical and emergency aid, Qurbani and Eid.

Course catalog (name, recommended duration, page link):
{catalog}

Rules:
- Keep replies short: 2 to 5 lines. Warm and respectful. Plain text only, except links.
- When you recommend a course, link it as [Course name](/course/ID) using exactly the link given in the catalog.
- Use only the facts above. Never invent fees, schedules, start dates, teacher names or bank details. If something is not covered, say you do not have that detail and suggest the enquiry form or WhatsApp.
- Do not give Islamic rulings (fatwas) or settle religious disputes. Say that is a question for the academy's teachers and offer the enquiry form or WhatsApp.
- Stay on topic: the academy, its courses, admissions and donations. Politely decline anything unrelated.
- Reply in the language the visitor writes in."""


@app.route("/api/chat", methods=["POST"])
def api_chat():
    if not GROQ_API_KEY:
        return jsonify(error="The assistant is not set up yet. Please use WhatsApp or the enquiry form."), 503
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or request.remote_addr or "?"
    now = time.time()
    recent = [t for t in _hits.get(ip, []) if now - t < 60]
    if len(recent) >= 10:
        return jsonify(error="Too many messages. Please wait a minute and try again."), 429
    if len(_hits) > 2000:
        _hits.clear()
    _hits[ip] = recent + [now]

    msgs = []
    for m in ((request.get_json(silent=True) or {}).get("messages") or [])[-10:]:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str) and m["content"].strip():
            msgs.append({"role": m["role"], "content": m["content"][:600]})
    if not msgs or msgs[-1]["role"] != "user":
        return jsonify(error="Please type a message."), 400

    payload = {"model": GROQ_MODEL, "messages": [{"role": "system", "content": chat_prompt()}] + msgs,
               "max_tokens": 700, "temperature": 0.5}
    if GROQ_MODEL.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"  # keeps replies fast and stops the model spending all tokens on thinking
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + GROQ_API_KEY,
                 "User-Agent": "alrehman-site/1.0"})  # Groq's firewall rejects the default Python user agent
    try:
        with urllib.request.urlopen(req, timeout=9) as r:
            reply = (json.load(r)["choices"][0]["message"].get("content") or "").strip()
    except Exception as e:
        print("chat failed:", type(e).__name__, str(e)[:200])
        return jsonify(error="Sorry, I could not answer just now. Please try again, or message us on WhatsApp."), 502
    return jsonify(reply=reply or "Sorry, I did not catch that. Could you rephrase your question?")


@app.route("/health")
def health():
    """Temporary diagnostic page: open /health to see what is wrong. Delete this route when everything works."""
    out = {"DATABASE_URL set": bool(DATABASE_URL), "SECRET_KEY set": bool(os.environ.get("SECRET_KEY")),
           "ADMIN_PASSWORD set": bool(ADMIN_PASSWORD)}
    if not DATABASE_URL:
        out["fix"] = "Add DATABASE_URL under Vercel > Settings > Environment Variables, then redeploy."
        return jsonify(out), 500
    try:
        c = connect()
        with c.cursor() as cur:
            cur.execute("SELECT to_regclass('public.courses') AS a, to_regclass('public.enquiries') AS b, to_regclass('public.content') AS c")
            t = cur.fetchone()
            out["connected"] = True
            out["tables exist"] = {"courses": bool(t["a"]), "enquiries": bool(t["b"]), "content": bool(t["c"])}
            if t["a"]:
                cur.execute("SELECT COUNT(*) AS n FROM courses")
                out["course rows"] = cur.fetchone()["n"]
        c.close()
        if not all(out["tables exist"].values()):
            out["fix"] = "Run supabase_schema.sql in the Supabase SQL Editor."
            return jsonify(out), 500
    except Exception as e:
        out["connected"] = False
        out["error"] = type(e).__name__
        out["detail"] = (str(e).strip().splitlines() or [""])[0][:220]
        return jsonify(out), 500
    return jsonify(out)


@app.route("/enquire", methods=["POST"])
def enquire():
    f = request.form
    if not (f.get("name") and f.get("email") and f.get("phone")):
        flash("Please complete name, email and phone.")
        return redirect(url_for("home") + "#contact")
    try:
        age = int(f.get("age") or 0)
    except ValueError:
        age = 0
    run("INSERT INTO enquiries(name,email,phone,age,gender,category,course,pref,message) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (f["name"][:120], f["email"][:160], f["phone"][:40], age, f.get("gender", ""), f.get("category", ""),
         f.get("course", "")[:160], f.get("pref", ""), f.get("message", "")[:2000]))
    flash("Thank you. Your enquiry has been received and our admissions team will contact you shortly.")
    return redirect(url_for("home") + "#contact")


# ---------------------------------------------------------------- staff area
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if ADMIN_PASSWORD and secrets.compare_digest(pw.encode(), ADMIN_PASSWORD.encode()):
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin"))
        time.sleep(1)  # slows down password guessing
        flash("Incorrect password." if ADMIN_PASSWORD else "ADMIN_PASSWORD is not set on the server.")
    elif session.get("admin"):
        return redirect(url_for("admin"))
    return render_template("login.html")


@app.route("/admin/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin")
@admin_only
def admin():
    return render_template("admin.html", enq=many("SELECT * FROM enquiries ORDER BY id DESC"),
                           rows=many("SELECT * FROM courses ORDER BY category, name"))


@app.route("/admin/course/<cid>", methods=["GET", "POST"])
@admin_only
def edit_course(cid):
    if cid != "new" and not cid.isdigit():
        abort(404)
    c = None if cid == "new" else (one("SELECT * FROM courses WHERE id=%s", (cid,)) or abort(404))
    if request.method == "POST":
        f = request.form
        v = (f["category"], f["name"].strip(), f["duration"].strip(), f["description"], f["syllabus"],
             f["objectives"], f["eligibility"], 1 if f.get("featured") else 0)
        try:
            if c:
                run("UPDATE courses SET category=%s,name=%s,duration=%s,description=%s,syllabus=%s,objectives=%s,"
                    "eligibility=%s,featured=%s WHERE id=%s", v + (cid,))
            else:
                run("INSERT INTO courses(category,name,duration,description,syllabus,objectives,eligibility,featured) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", v)
            flash("Course saved.")
        except psycopg2.IntegrityError:
            db().rollback()
            flash("A course with that name already exists in this category.")
        return redirect(url_for("admin"))
    return render_template("edit_course.html", c=c)


@app.route("/admin/enquiry/<int:eid>", methods=["POST"])
@admin_only
def enquiry_status(eid):
    status = request.form.get("status")
    if status in STATUSES:
        run("UPDATE enquiries SET status=%s WHERE id=%s", (status, eid))
    return redirect(url_for("admin") + "#enquiries")


@app.route("/admin/content", methods=["POST"])
@admin_only
def save_content():
    for k in CONTENT:
        if k in request.form:
            run("INSERT INTO content(k,v) VALUES(%s,%s) ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v", (k, request.form[k]))
    _cc["t"] = 0  # show the new text immediately
    flash("Website content updated.")
    return redirect(url_for("admin") + "#content")


init()
if __name__ == "__main__":
    app.run(debug=False)
