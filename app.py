from flask import Flask, render_template, request, redirect, session, url_for, flash 
from flask import jsonify
import sqlite3
import os
import calendar
import csv
import openpyxl
from datetime import datetime, date




app = Flask(__name__)
app.secret_key = "secret123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "crm.db")

import sqlite3

# ================= DATABASE =================
def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # ---------- AGENTS ----------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        mobile TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        created_by TEXT
    )
    """)

    # ---------- LEADS ----------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT,
    customer TEXT,
    mobile TEXT,
    alt_mobile TEXT,
    email TEXT,
    property_type TEXT,
    category TEXT,
    source TEXT,
    enquiry_type TEXT,
    enquiry_from TEXT,
    budget TEXT,
    stage TEXT,
    status TEXT,
    enquiry_date TEXT,
    next_follow TEXT,
    meeting_date TEXT,
    expected_closing TEXT,
    owner TEXT,
    handled_by TEXT,
    followup_type TEXT,
    last_followed TEXT,
    remarks TEXT,
    created_by TEXT
)

    """)

    # ---------- REMARKS ----------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS remarks
 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        remark TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------- ATTENDANCE ----------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        in_time TEXT,
        out_time TEXT,
        work_duration TEXT,
        status TEXT,
        ip_address TEXT,
        latitude TEXT,
        longitude TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------- AUTO ADD MISSING COLUMNS (LEADS) ----------
    cur.execute("PRAGMA table_info(leads)")
    lead_cols = [c[1] for c in cur.fetchall()]

    if "alt_mobile" not in lead_cols:
        cur.execute("ALTER TABLE leads ADD COLUMN alt_mobile TEXT")

    if "budget" not in lead_cols:
        cur.execute("ALTER TABLE leads ADD COLUMN budget TEXT")

    if "created_role" not in lead_cols:
        cur.execute("ALTER TABLE leads ADD COLUMN created_role TEXT")    


# ================= ATTENDANCE TABLE =================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        in_time TEXT,
        out_time TEXT,
        work_duration TEXT,
        status TEXT,
        ip_address TEXT,
        latitude TEXT,
        longitude TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)



# ================= DEFAULT ADMIN =================
ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "admin123"

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Admin login
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session.update({
                "user_id": 0,  
                "email": email,
                "role": "admin",
                "name": "Admin"
            })
            return redirect(url_for("dashboard"))

        # Agent / Manager / User
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM agents WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session.update({
                "user_id": user["id"],
                "email": user["email"],
                "role": user["role"],
                "name": user["name"]
            })
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid Login")

    return render_template("login.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "email" not in session:
        return redirect(url_for("login"))

    email = session["email"]
    role  = session["role"]
    name  = session["name"]

    conn = get_db()
    cur = conn.cursor()

    # ================= TOTAL LEADS =================
    if role == "admin":
        cur.execute("SELECT COUNT(*) FROM leads")
    elif role == "Manager":
        cur.execute("""
            SELECT COUNT(*) FROM leads
            WHERE created_by IN (
                SELECT email FROM agents WHERE created_by=?
            )
        """, (email,))
    else:  # User
        cur.execute("SELECT COUNT(*) FROM leads WHERE created_by=?", (email,))
    total_leads = cur.fetchone()[0]

    # ================= TOTAL USERS (AGENTS) =================
    if role == "admin":
        cur.execute("SELECT COUNT(*) FROM agents WHERE role='User'")
        total_agents = cur.fetchone()[0]
    elif role == "Manager":
        cur.execute("""
            SELECT COUNT(*) FROM agents
            WHERE role='User' AND created_by=?
        """, (email,))
        total_agents = cur.fetchone()[0]
    else:
        total_agents = 0

    # ================= TOTAL MANAGERS (ADMIN ONLY) =================
    if role == "admin":
        cur.execute("SELECT COUNT(*) FROM agents WHERE role='Manager'")
        total_managers = cur.fetchone()[0]
    else:
        total_managers = 0

    # ================= LEADS BY STATUS =================
    def status_count(status):
        if role == "admin":
            cur.execute("SELECT COUNT(*) FROM leads WHERE status=?", (status,))
        elif role == "Manager":
            cur.execute("""
                SELECT COUNT(*) FROM leads
                WHERE status=? AND created_by IN (
                    SELECT email FROM agents WHERE created_by=?
                )
            """, (status, email))
        else:
            cur.execute("""
                SELECT COUNT(*) FROM leads
                WHERE status=? AND created_by=?
            """, (status, email))
        return cur.fetchone()[0]

    new_leads      = status_count("New")
    followup_leads = status_count("Follow Up")
    closed_leads   = status_count("Closed")
    booked_leads   = status_count("Booked")
    lost_leads     = status_count("Lost")

    # ================= ROLE DISTRIBUTION (ADMIN ONLY) =================
    if role == "admin":
        cur.execute("SELECT COUNT(*) FROM agents WHERE role='admin'")
        admin_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM agents WHERE role='Manager'")
        manager_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM agents WHERE role='User'")
        user_count = cur.fetchone()[0]
    else:
        admin_count = manager_count = user_count = 0

    conn.close()

    return render_template(
        "dashboard.html",
        name=name,
        email=email,
        role=role,
        total_leads=total_leads,
        total_agents=total_agents,
        total_managers=total_managers,
        new_leads=new_leads,
        followup_leads=followup_leads,
        closed_leads=closed_leads,
        lost_leads=lost_leads,
        admin_count=admin_count,
        manager_count=manager_count,
        user_count=user_count
    )
#===================chart======================
@app.route("/chart/monthly-leads")
def chart_monthly_leads():
    if "email" not in session:
        return {"error": "login required"}, 403

    role  = session["role"]
    email = session["email"]

    conn = get_db()
    cur = conn.cursor()

    if role == "admin":
        cur.execute("""
            SELECT strftime('%m', enquiry_date) m, COUNT(*) c
            FROM leads GROUP BY m
        """)
    elif role == "Manager":
        cur.execute("""
            SELECT strftime('%m', enquiry_date) m, COUNT(*) c
            FROM leads
            WHERE created_by IN (
                SELECT email FROM agents WHERE created_by=?
            )
            GROUP BY m
        """,(email,))
    else:
        cur.execute("""
            SELECT strftime('%m', enquiry_date) m, COUNT(*) c
            FROM leads WHERE created_by=?
            GROUP BY m
        """,(email,))

    rows = cur.fetchall()
    conn.close()

    result = {str(i).zfill(2):0 for i in range(1,13)}
    for r in rows:
        if r["m"]:
            result[r["m"]] = r["c"]

    return list(result.values())

@app.route("/chart/monthly-leads")
def monthly_leads():
    from_date = request.args.get("from_date")
    to_date   = request.args.get("to_date")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
      SELECT strftime('%Y-%m', enquiry_date) AS m, COUNT(*) c
      FROM leads
      WHERE enquiry_date BETWEEN ? AND ?
      GROUP BY m
      ORDER BY m
    """, (from_date, to_date))

    rows = cur.fetchall()
    conn.close()

    labels = []
    values = []

    for r in rows:
        labels.append(r["m"])
        values.append(r["c"])

    return {
        "labels": labels,
        "values": values
    }





@app.route("/chart/status-data")
def chart_status_data():
    if "email" not in session:
        return {}, 403

    role  = session["role"]
    email = session["email"]

    conn = get_db()
    cur = conn.cursor()

    if role == "admin":
        cur.execute("""
            SELECT LOWER(TRIM(status)) st, COUNT(*) c
            FROM leads
            GROUP BY st
        """)
    elif role == "Manager":
        cur.execute("""
            SELECT LOWER(TRIM(status)) st, COUNT(*) c
            FROM leads
            WHERE created_by IN (
                SELECT email FROM agents WHERE created_by=?
            )
            GROUP BY st
        """, (email,))
    else:
        cur.execute("""
            SELECT LOWER(TRIM(status)) st, COUNT(*) c
            FROM leads
            WHERE created_by=?
            GROUP BY st
        """, (email,))

    rows = cur.fetchall()
    conn.close()

    # ✅ ALL STATUSES (INCLUDING BOOKED)
    data = {
        "New": 0,
        "Follow Up": 0,
        "Closed": 0,
        "Lost": 0,
        "Booked": 0
    }

    for r in rows:
        st = r["st"]
        if st == "new":
            data["New"] += r["c"]
        elif st in ("follow up", "followup"):
            data["Follow Up"] += r["c"]
        elif st == "closed":
            data["Closed"] += r["c"]
        elif st == "lost":
            data["Lost"] += r["c"]
        elif st == "booked":
            data["Booked"] += r["c"]

    return data


@app.route("/chart/role-distribution")
def chart_role_distribution():
    if "email" not in session:
        return {"error": "login required"}, 403

    role = session["role"]
    email = session["email"]
    conn = get_db()
    cur = conn.cursor()

    if role == "admin":
        cur.execute("SELECT COUNT(*) FROM agents WHERE role='Admin'")
        admin = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM agents WHERE role='Manager'")
        manager = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM agents WHERE role='User'")
        user = cur.fetchone()[0]

    elif role == "Manager":
        admin = 0
        manager = 1
        cur.execute("SELECT COUNT(*) FROM agents WHERE role='User' AND created_by=?", (email,))
        user = cur.fetchone()[0]

    else:
        admin = manager = 0
        user = 1

    conn.close()
    return {"Admin": admin, "Manager": manager, "User": user}




#=================Add Agent=========================
@app.route("/add_agent", methods=["GET", "POST"])
def add_agent():
    if "email" not in session:
        return redirect(url_for("login"))

    role = session["role"]

    if role == "User":
        return "Access Denied", 403

    if request.method == "POST":
        new_email = request.form["email"]
        new_role  = request.form["role"]

        if role == "Manager" and new_role != "User":
            flash("Manager can create only User", "error")
            return redirect(url_for("add_agent"))

        conn = get_db()
        cur = conn.cursor()

        # 🔴 CHECK EMAIL EXISTS
        cur.execute("SELECT id FROM agents WHERE email=?", (new_email,))
        existing = cur.fetchone()

        if existing:
            conn.close()
            flash("❌ Email already exists!", "error")
            return redirect(url_for("add_agent"))

        # ✅ INSERT IF NOT EXISTS
        cur.execute("""
            INSERT INTO agents (name, mobile, email, password, role, created_by)
            VALUES (?,?,?,?,?,?)
        """, (
            request.form["name"],
            request.form["mobile"],
            new_email,
            request.form["password"],
            new_role,
            session["email"]
        ))

        conn.commit()
        conn.close()

        flash("✅ Agent created successfully", "success")
        return redirect(url_for("manage_agent"))

    return render_template("add_agent.html", role=role)

@app.route("/manage_agent")
def manage_agent():
    if "email" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ================= FETCH AGENTS =================
    if session["role"] == "admin":
        agents = cur.execute(
            "SELECT * FROM agents ORDER BY id DESC"
        ).fetchall()

        managers = cur.execute(
            "SELECT COUNT(*) FROM agents WHERE role='Manager'"
        ).fetchone()[0]

        users = cur.execute(
            "SELECT COUNT(*) FROM agents WHERE role='User'"
        ).fetchone()[0]

    elif session["role"] == "Manager":
        agents = cur.execute(
            "SELECT * FROM agents WHERE created_by=? ORDER BY id DESC",
            (session["email"],)
        ).fetchall()

        users = cur.execute(
            "SELECT COUNT(*) FROM agents WHERE role='User' AND created_by=?",
            (session["email"],)
        ).fetchone()[0]

        managers = 0   # ❌ manager ko manager count nahi dikhega

    conn.close()

    return render_template(
        "manage_agent.html",
        agents=agents,
        managers=managers,
        users=users,
        role=session["role"]
    )




#==========================add Lead =================
@app.route("/add_lead", methods=["GET", "POST"])
def add_lead():
    if "email" not in session:
        return redirect(url_for("login"))
    
    today = datetime.now().strftime("%d-%m-%Y") 

    
    if request.method == "POST":
        conn = get_db()
        conn.execute("""
    INSERT INTO leads (
        project, customer, mobile, alt_mobile, email, property_type,
        category, source, enquiry_type, enquiry_from,
        budget, enquiry_date, stage, status,
        next_follow, meeting_date,
        expected_closing, owner, handled_by,
        followup_type, last_followed, remarks, created_by
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
    request.form.get("project"),
    request.form.get("customer"),
    request.form.get("mobile"),
    request.form.get("alt_mobile"),   # ✅ VERY IMPORTANT
    request.form.get("email"),
    request.form.get("property_type"),
    request.form.get("category"),
    request.form.get("source"),
    request.form.get("enquiry_type"),
    request.form.get("enquiry_from"),
    request.form.get("budget"),
     today,   # ✅ SYSTEM DATE (DD-MM-YYYY)
    request.form.get("stage"),
   
    request.form.get("status"),
    request.form.get("next_follow"),
    request.form.get("meeting_date"),
    request.form.get("expected_closing"),
    request.form.get("owner"),
    request.form.get("handled_by"),
    request.form.get("followup_type"),
    request.form.get("last_followed"),
    request.form.get("remarks"),
    session["email"]
))

        conn.commit()
        conn.close()

        flash("Lead added successfully")
        return redirect(url_for("manage_lead"))

    today = datetime.now().strftime("%d-%m-%Y")
    return render_template("add_lead.html", role=session["role"], today=today)


# ================= MANAGE LEAD =================
@app.route("/manage-lead")
def manage_lead():
    if "email" not in session:
        return redirect(url_for("login"))

    role  = session["role"]
    email = session["email"]
    conn  = get_db()

    # ===== FETCH LEADS =====
    if role == "admin":
        leads = conn.execute("""
            SELECT l.*, a.name AS creator_name
            FROM leads l
            LEFT JOIN agents a ON a.email=l.created_by
        """).fetchall()

        users = conn.execute("""
            SELECT name,email FROM agents
            WHERE role IN ('User','Manager')
        """).fetchall()

    elif role == "Manager":
        leads = conn.execute("""
            SELECT l.*, a.name AS creator_name
            FROM leads l
            LEFT JOIN agents a ON a.email=l.created_by
            WHERE l.created_by IN (
              SELECT email FROM agents WHERE created_by=?
            )
        """,(email,)).fetchall()

        users = conn.execute("""
            SELECT name,email FROM agents
            WHERE role='User' AND created_by=?
        """,(email,)).fetchall()

    else:
        leads = conn.execute("""
            SELECT l.*, a.name AS creator_name
            FROM leads l
            LEFT JOIN agents a ON a.email=l.created_by
            WHERE l.created_by=?
        """,(email,)).fetchall()

        users = []

    conn.close()

    return render_template(
        "manage_lead.html",
        leads=leads,
        users=users,
        role=role
    )


#---=========================================================================================================

@app.route("/get_lead/<int:id>")
def get_lead(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM leads WHERE id=?", (id,))
    row = cur.fetchone()
    conn.close()

    if row:
        return dict(row)   # ✅ JSON return
    return {}




@app.route("/update_lead", methods=["POST"])
def update_lead():
    data = request.form
    lead_id = data.get("id")
    remark = data.get("remarks", "").strip()

    conn = get_db()
    cur = conn.cursor()

    # 🔹 Update lead
    cur.execute("""
        UPDATE leads SET
            project=?,
            customer=?,
            mobile=?,
            alt_mobile=?, 
            email=?,
            category=?,
            source=?,
            enquiry_type=?,
            followup_type=?,
            budget=?,
            
            next_follow=?,
            stage=?,
            status=?,
            handled_by=?,
            owner=?
        WHERE id=?
    """, (
        data.get("project"),
        data.get("customer"),
        data.get("mobile"),
        data.get("alt_mobile"),
        data.get("email"),
        data.get("category"),
        data.get("source"),
        data.get("enquiry_type"),
        data.get("followup_type"),
        data.get("budget"),
        
        data.get("next_follow"),
        data.get("stage"),
        data.get("status"),
        data.get("handled_by"),
        data.get("owner"),
        lead_id
    ))

    # 🔥 SAVE REMARK HISTORY (VERY IMPORTANT)
    if remark:
        cur.execute("""
            INSERT INTO lead_remarks (lead_id, remark)
            VALUES (?, ?)
    """, (lead_id, remark))

    conn.commit()
    conn.close()

    return {"success": True}



@app.route("/download_leads")
def download_leads():
    from_date = request.args.get("from_date")
    to_date   = request.args.get("to_date")
    project   = request.args.get("project")
    category  = request.args.get("category")
    source    = request.args.get("source")
    enquiry   = request.args.get("enquiry")
    stage     = request.args.get("stage")
    status    = request.args.get("status")
    search    = request.args.get("search")

    query = "SELECT * FROM leads WHERE 1=1"
    params = []

    if from_date and to_date:
        query += " AND enquiry_date BETWEEN ? AND ?"
        params.extend([from_date, to_date])

    if project:
        query += " AND project = ?"
        params.append(project)

    if category:
        query += " AND category = ?"
        params.append(category)

    if source:
        query += " AND source = ?"
        params.append(source)

    if enquiry:
        query += " AND enquiry_type = ?"
        params.append(enquiry)

    if stage:
        query += " AND stage = ?"
        params.append(stage)

    if status:
        query += " AND status = ?"
        params.append(status)

    if search:
        query += """
        AND (
          customer LIKE ? OR
          mobile LIKE ? OR
          email LIKE ?
        )
        """
        s = f"%{search}%"
        params.extend([s, s, s])

    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute(query, params).fetchall()
    conn.close()

    # ===== CSV DOWNLOAD =====
    import csv
    from io import StringIO
    from flask import Response

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(rows[0].keys() if rows else [])

    for r in rows:
        writer.writerow(list(r))

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition":"attachment;filename=filtered_leads.csv"}
    )


#=======================Remark====================
@app.route("/add_remark", methods=["POST"])
def add_remark():
    lead_id = request.form["lead_id"]
    remark = request.form["remark"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO remarks
 (lead_id, remark)
        VALUES (?, ?)
    """, (lead_id, remark))
    conn.commit()
    conn.close()

    return {"success": True}


@app.route("/get_remarks/<int:lead_id>")
def get_remarks(lead_id):
    conn = sqlite3.connect("crm.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get initial remark from leads table
    cur.execute("SELECT remarks, enquiry_date FROM leads WHERE id=?", (lead_id,))
    lead = cur.fetchone()

    # Get history from remarks table
    cur.execute("""
    SELECT remark,
    strftime('%d-%m-%Y %H:%M:%S', created_at) as created_at
    FROM remarks 
    WHERE lead_id=? 
    ORDER BY created_at ASC
""", (lead_id,))

    history = cur.fetchall()

    conn.close()

    remarks_list = []

    # Add first remark (when lead created)
    if lead and lead["remarks"]:
        remarks_list.append({
            "remark": lead["remarks"],
            "created_at": lead["enquiry_date"]
        })

    # Add updated remarks
    for r in history:
        remarks_list.append({
            "remark": r["remark"],
            "created_at": r["created_at"]
        })

    return jsonify({
        "remarks": remarks_list,
        "total": len(remarks_list)
    })


@app.route("/update_remark", methods=["POST"])
def update_remark():
    data = request.get_json()

    lead_id = data.get("lead_id")
    remark = data.get("remark")

    if not lead_id or not remark:
        return jsonify({"success": False})

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO remarks (lead_id, remark, created_at)
        VALUES (?, ?, datetime('now','localtime'))
    """, (lead_id, remark))

    conn.commit()
    conn.close()

    return jsonify({"success": True})



# ============== Attendance ===================


GOOGLE_MAPS_API_KEY = "AIzaSyDAIu4vVzJbPllBsCatnx3ETiI-bkZEXV4"


@app.route("/attendance")
def attendance():
    if "email" not in session:
        return redirect(url_for("login"))

    role = session["role"]
    user_id = session["user_id"]
    email = session["email"]

    # ================= YEAR / MONTH =================
    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))

    from calendar import monthrange
    total_days = monthrange(year, month)[1]
    days = list(range(1, total_days + 1))
    today = date.today().isoformat()

    db = get_db()

    # ================= USERS (ROLE WISE) =================bxjuj
   
    

    
    if role == "admin":
        users = db.execute("""
            SELECT id, name FROM agents
            WHERE role IN ('User','Manager')
        """).fetchall()

    elif role == "Manager":
        users = db.execute("""
            SELECT id, name FROM agents
            WHERE created_by=? OR id=?
        """, (email, user_id)).fetchall()

    else:  # User
        users = db.execute("""
            SELECT id, name FROM agents
            WHERE id=?
        """, (user_id,)).fetchall()

    # ================= ATTENDANCE MAP =================
    attendance_rows = db.execute("""
        SELECT user_id, date
        FROM attendance
        WHERE substr(date,1,7)=?
    """, (f"{year}-{month:02d}",)).fetchall()

    attendance_map = {}
    for r in attendance_rows:
        attendance_map.setdefault(r["user_id"], []).append(r["date"])

    # ================= TABLE VIEW DATA =================
    q = """
      SELECT u.name, a.*
      FROM attendance a
      JOIN agents u ON u.id=a.user_id
      WHERE 1=1
    """
    params = []

    if role == "Manager":
        q += " AND (u.created_by=? OR u.id=?)"
        params += [email, user_id]

    elif role == "User":
        q += " AND a.user_id=?"
        params.append(user_id)

    q += " ORDER BY a.date DESC"

    rows = db.execute(q, params).fetchall()

    return render_template(
        "attendance.html",
        rows=rows,
        role=role,
        google_key=GOOGLE_MAPS_API_KEY,

        # 👇 Calendar variables
        users=users,
        days=days,
        year=year,
        month=month,
        today=today,
        attendance_map=attendance_map
    )



@app.route("/attendance/in", methods=["POST"])
def attendance_in():

    role = session.get("role")
    if role not in ["User", "Manager"]:
        return jsonify({"msg":"Only User or Manager can mark attendance"}), 403

    db = get_db()
    today = date.today().isoformat()
    now = datetime.datetime.now().strftime("%H:%M:%S")
    ip = request.remote_addr
    data = request.json
    user_id = session["user_id"]

    already = db.execute("""
        SELECT id FROM attendance
        WHERE user_id=? AND date=?
    """,(user_id, today)).fetchone()

    if already:
        return jsonify({"msg":"Attendance already marked today"})

    db.execute("""
        INSERT INTO attendance
        (user_id,date,in_time,status,ip_address,latitude,longitude)
        VALUES (?,?,?,?,?,?,?)
    """,(
        user_id, today, now, "Present", ip,
        data.get("lat"), data.get("lng")
    ))

    db.commit()
    return jsonify({"msg":"IN marked successfully"})





@app.route("/attendance/out", methods=["POST"])
def attendance_out():

    if session.get("role") not in ["User", "Manager"]:
        return jsonify({"msg": "Not allowed"}), 403

    db = get_db()
    today = date.today().isoformat()
    now = datetime.datetime.now().strftime("%H:%M:%S")
    data = request.json or {}
    user_id = session["user_id"]

    row = db.execute("""
        SELECT * FROM attendance
        WHERE user_id=? AND date=?
    """, (user_id, today)).fetchone()

    if not row:
        db.close()
        return jsonify({"msg": "IN not marked yet"})

    if row["out_time"]:
        db.close()
        return jsonify({"msg": "OUT already marked"})

    duration = str(
        datetime.datetime.strptime(now, "%H:%M:%S") -
        datetime.datetime.strptime(row["in_time"], "%H:%M:%S")
    )

    try:
        db.execute("""
            UPDATE attendance
            SET out_time=?, work_duration=?,
                out_latitude=?, out_longitude=?
            WHERE id=?
        """, (
            now, duration,
            data.get("lat"), data.get("lng"),
            row["id"]
        ))
        db.commit()
    except Exception as e:
        db.close()
        return jsonify({"msg": f"DB Error: {e}"}), 500

    db.close()
    return jsonify({"msg": "OUT marked successfully"})


  






@app.route("/attendance/today")
def attendance_today():
    if "user_id" not in session:
        return jsonify({})

    today = date.today().isoformat()
    db = get_db()

    row = db.execute("""
        SELECT in_time,out_time FROM attendance
        WHERE user_id=? AND date=?
    """,(session["user_id"],today)).fetchone()

    return jsonify({
        "in_done": bool(row and row["in_time"]),
        "out_done": bool(row and row["out_time"])
    })

@app.route("/attendance/export")
def attendance_export():

    if "email" not in session:
        return redirect(url_for("login"))

    role = session["role"]
    if role == "User":
        return "Not allowed", 403

    from_date = request.args.get("from") or None
    to_date = request.args.get("to") or None

    q = """
      SELECT u.name,
             a.date,
             a.in_time,
             a.out_time,
             a.work_duration,
             a.ip_address
      FROM attendance a
      JOIN agents u ON u.id=a.user_id
      WHERE 1=1
    """
    params = []

    if from_date and to_date:
        q += " AND a.date BETWEEN ? AND ?"
        params += [from_date, to_date]

    if role == "Manager":
        q += " AND (u.created_by=? OR u.id=?)"
        params += [session["email"], session["user_id"]]

    q += " ORDER BY a.date DESC"

    db = get_db()
    rows = db.execute(q, params).fetchall()

    import csv
    from io import StringIO
    from flask import Response

    output = StringIO()
    writer = csv.writer(output)

    # ✅ SAFE HEADER
    writer.writerow([
        "Name","Date","In Time","Out Time",
        "Work Duration","IP Address"
    ])

    for r in rows:
        writer.writerow([
            r["name"],
            r["date"],
            r["in_time"],
            r["out_time"],
            r["work_duration"],
            r["ip_address"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=attendance_report.csv"
        }
    )




# ======================== Attendence Rules============== 

@app.route("/attendance/rules/save", methods=["POST"])
def save_attendance_rules():
    if session.get("role") != "admin":
        return jsonify({"msg": "Unauthorized"}), 403

    data = request.json

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO attendance_rules
        (rule_name, shift_start, shift_end, grace_minutes,
         full_day_hours, half_day_hours,
         auto_deduction, anomaly_tracking, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        data.get("rule_name"),
        data.get("shift_start"),
        data.get("shift_end"),
        data.get("grace_minutes"),
        data.get("full_day_hours"),
        data.get("half_day_hours"),
        1 if data.get("auto_deduction") else 0,
        1 if data.get("anomaly_tracking") else 0,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return jsonify({"msg": "Rules saved successfully"})



# ======================== Bulk Upload ============== 
@app.route("/bulk_upload", methods=["POST"])
def bulk_upload():

    if session.get("role") != "admin":
        flash("Unauthorized access", "danger")
        return redirect(url_for("add_lead"))

    file = request.files.get("file")
    if not file:
        flash("No file selected", "danger")
        return redirect(url_for("add_lead"))

    filename = file.filename.lower()
    today = date.today().isoformat()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    def insert_row(row):
        
        cur.execute("""
INSERT INTO leads (
 project, source, category, enquiry_type,
 customer, mobile, alt_mobile, email,
 enquiry_from, budget, stage, status,
 enquiry_date, next_follow, meeting_date,
 expected_closing, owner, handled_by,
 followup_type, last_followed, remarks,
 created_by, created_role
)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
""", (
 row["project"],
 row["source"],
 row["category"],
 row["enquiry_type"],
 row["customer"],
 row["mobile"],
 row.get("alt_mobile",""),
 row.get("email",""),
 row.get("Enquiry From",""),
 row.get("budget",0),
 row["stage"],
 row["status"],
 row.get("Enquiry Date",""),
 row.get("next_follow Up",""),
 row.get("Meeting / Visit",""),
 row.get("Expected Closing",""),
 row["owner"],
 row["handled_by"],
 row["follow up_type"],
 row.get("Last Followed",""),
 row.get("remarks",""),
 session["email"],      # ✅ EMAIL
 session["role"]
))

    # ===== CSV =====
    if filename.endswith(".csv"):
        reader = csv.DictReader(file.stream.read().decode("utf-8").splitlines())
        for row in reader:
            insert_row(row)

    # ===== EXCEL =====
    elif filename.endswith(".xlsx"):
        wb = openpyxl.load_workbook(file)
        sheet = wb.active
        headers = [cell.value for cell in sheet[1]]

        for r in sheet.iter_rows(min_row=2, values_only=True):
            row = dict(zip(headers, r))
            insert_row(row)

    else:
        flash("Invalid file type", "danger")
        return redirect(url_for("add_lead"))

    conn.commit()
    conn.close()

    flash("Bulk upload successful", "success")
    return redirect(url_for("manage_lead"))


# ================== BULK Assign ================
@app.route("/bulk_assign", methods=["POST"])
def bulk_assign():

    if session.get("role") == "User":
        return {"success":False,"message":"Unauthorized"}

    data = request.get_json()
    user = data.get("user")
    leads = data.get("leads", [])

    if not user or not leads:
        return {"success":False,"message":"Invalid data"}

    conn = get_db()
    cur  = conn.cursor()

    cur.executemany("""
        UPDATE leads
        SET created_by=?
        WHERE id=?
    """, [(user, lid) for lid in leads])

    conn.commit()
    conn.close()

    return {"success":True}




@app.route("/download_sample_file")
def download_sample_file():

    from io import StringIO
    import csv
    from flask import Response

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "project",
        "source",
        "category",
        "enquiry_type",
        "customer",
        "mobile",
        "alt_mobile",
        "email",
        "Enquiry From",
        "budget",
        "status",
        "stage",
        "Enquiry Date",
        "next_follow Up",
        "Meeting / Visit",
        "Expected Closing",
        "owner",
        "handled_by",
        "follow up_type",
        "Last Followed",
        "remarks",
        "created_by"
    ])

   
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sample_leads_file.csv"
        }
    )



# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()     # 👈 FIRST (VERY IMPORTANT)
    app.run(debug=True)
