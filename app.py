from flask import Flask, render_template, request, jsonify
import sqlite3
import io
import csv
from datetime import datetime
from functools import wraps
from flask import session, redirect, url_for, flash
from itsdangerous import URLSafeSerializer
from datetime import timedelta
import os

app = Flask(__name__)
DB_PATH = 'vehicle.db'

app.secret_key = os.environ.get('SECRET_KEY', 'change-this-to-a-random-string-2026')
app.permanent_session_lifetime = timedelta(minutes=30)  # ← Session expires in 30 min
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Tulip@c66')
serializer = URLSafeSerializer(app.secret_key)

def encrypt_id(id):
    return serializer.dumps(id)

def decrypt_id(token):
    try:
        return serializer.loads(token)
    except:
        return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        bound1_name TEXT DEFAULT 'Bound 1',
        bound2_name TEXT DEFAULT 'Bound 2',
        created_at TEXT DEFAULT (datetime('now', 'localtime'))
    )''')

    try:
        c.execute("ALTER TABLE locations ADD COLUMN created_at TEXT DEFAULT (datetime('now', 'localtime'))")
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS kenderaan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_id INTEGER NOT NULL,
        name TEXT DEFAULT '',
        plat TEXT DEFAULT '',
        berat TEXT DEFAULT '',
        gandar TEXT DEFAULT '',
        FOREIGN KEY (location_id) REFERENCES locations(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS ujian (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kenderaan_id INTEGER NOT NULL,
        row_num INTEGER NOT NULL,
        arah TEXT DEFAULT '',
        data_id TEXT DEFAULT '',
        tarikh TEXT DEFAULT '',
        kelajuan TEXT DEFAULT '',
        bil_gandar TEXT DEFAULT '',
        lorong TEXT DEFAULT '',
        berat_bacaan TEXT DEFAULT '',
        perbezaan TEXT DEFAULT '',
        remark TEXT DEFAULT '',
        UNIQUE(kenderaan_id, row_num)
    )''')

    c.execute("SELECT COUNT(*) FROM locations")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO locations (name) VALUES ('Location 1')")
        c.execute("INSERT INTO locations (name) VALUES ('Location 2')")
        loc1_id = 1
        for v in range(1, 4):
            c.execute("INSERT INTO kenderaan (location_id, name) VALUES (?, ?)",
                      (loc1_id, f'Kenderaan {v}'))
            kid = c.lastrowid
            for r in range(1, 11):
                c.execute("INSERT OR IGNORE INTO ujian (kenderaan_id, row_num) VALUES (?, ?)", (kid, r))

    conn.commit()
    conn.close()

# @app.route('/edit/<int:lid>')
# def edit_page(lid):
#     return render_template('edit.html', location_id=lid)

# @app.route('/edit/<token>')
# @login_required
# def edit_page(token):
#     lid = decrypt_id(token)
#     if lid is None:
#         return "Invalid or expired link", 404
#     return render_template('edit.html', location_id=lid, token=token)

@app.route('/edit/<token>')
@login_required
def edit_page(token):
    lid = decrypt_id(token)
    if lid is None:
        return "Invalid or expired link", 404
    return render_template('edit.html', location_id=lid, token=token,
                           logged_in=session.get('logged_in', False))


# @app.route('/view/<int:lid>')
# def view_page(lid):
#     return render_template('view.html', location_id=lid)

# @app.route('/view/<token>')
# def view_page(token):
#     lid = decrypt_id(token)
#     if lid is None:
#         return "Invalid or expired link", 404
#     return render_template('view.html', location_id=lid, token=token)

@app.route('/view/<token>')
def view_page(token):
    lid = decrypt_id(token)
    if lid is None:
        return "Invalid or expired link", 404
    return render_template('view.html', location_id=lid, token=token, logged_in=session.get('logged_in', False))

@app.route('/api/locations')
def get_locations():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM locations ORDER BY id")
    locs = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(locs)

@app.route('/api/locations', methods=['POST'])
def add_location():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO locations (name, bound1_name, bound2_name) VALUES (?, ?, ?)",
              (data.get('name', 'New Location'), data.get('bound1_name', 'Bound 1'), data.get('bound2_name', 'Bound 2')))
    conn.commit()
    lid = c.lastrowid
    conn.close()
    return jsonify({'status': 'ok', 'id': lid})

@app.route('/api/locations/<int:lid>', methods=['PUT'])
def update_location(lid):
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE locations SET name=?, bound1_name=?, bound2_name=? WHERE id=?",
              (data.get('name'), data.get('bound1_name'), data.get('bound2_name'), lid))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/locations/<int:lid>', methods=['DELETE'])
def delete_location(lid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM ujian WHERE kenderaan_id IN (SELECT id FROM kenderaan WHERE location_id=?)", (lid,))
    c.execute("DELETE FROM kenderaan WHERE location_id=?", (lid,))
    c.execute("DELETE FROM locations WHERE id=?", (lid,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

# ─── Data API ───
# @app.route('/api/data/<int:location_id>')
# def get_data(location_id):
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     c = conn.cursor()
#     c.execute("SELECT * FROM locations WHERE id=?", (location_id,))
#     loc = dict(c.fetchone()) if c.fetchone() else None
#     if not loc:
#         return jsonify({'error': 'Location not found'}), 404
#     c.execute("SELECT * FROM kenderaan WHERE location_id=? ORDER BY id", (location_id,))
#     kenderaan = [dict(r) for r in c.fetchall()]
#     kid_list = [k['id'] for k in kenderaan]
#     ujian = []
#     if kid_list:
#         placeholders = ','.join('?' * len(kid_list))
#         c.execute(f"SELECT * FROM ujian WHERE kenderaan_id IN ({placeholders}) ORDER BY kenderaan_id, row_num", kid_list)
#         ujian = [dict(r) for r in c.fetchall()]
#     conn.close()
#     return jsonify({'location': loc, 'kenderaan': kenderaan, 'ujian': ujian})

@app.route('/api/data/<int:location_id>')
def get_data(location_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM locations WHERE id=?", (location_id,))
    row = c.fetchone()                   
    if not row:                         
        conn.close()
        return jsonify({'error': 'Location not found'}), 404
    loc = dict(row)                      
    c.execute("SELECT * FROM kenderaan WHERE location_id=? ORDER BY id", (location_id,))
    kenderaan = [dict(r) for r in c.fetchall()]
    kid_list = [k['id'] for k in kenderaan]
    ujian = []
    if kid_list:
        placeholders = ','.join('?' * len(kid_list))
        c.execute(f"SELECT * FROM ujian WHERE kenderaan_id IN ({placeholders}) ORDER BY kenderaan_id, row_num", kid_list)
        ujian = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({'location': loc, 'kenderaan': kenderaan, 'ujian': ujian})

@app.route('/api/save/<int:location_id>', methods=['POST'])
def save_data(location_id):
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for k in data.get('kenderaan', []):
        c.execute("UPDATE kenderaan SET name=?, plat=?, berat=?, gandar=? WHERE id=? AND location_id=?",
                   (k.get('name',''), k.get('plat',''), k.get('berat',''), k.get('gandar',''), k['id'], location_id))
    for u in data.get('ujian', []):
        c.execute("""INSERT OR REPLACE INTO ujian
            (kenderaan_id, row_num, arah, data_id, tarikh, kelajuan,
             bil_gandar, lorong, berat_bacaan, perbezaan, remark)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (u['kenderaan_id'], u['row_num'], u.get('arah',''), u.get('data_id',''),
             u.get('tarikh',''), u.get('kelajuan',''), u.get('bil_gandar',''),
             u.get('lorong',''), u.get('berat_bacaan',''), u.get('perbezaan',''),
             u.get('remark','')))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/add_kenderaan/<int:location_id>', methods=['POST'])
def add_kenderaan(location_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    data = request.json
    name = data.get('name', 'Kenderaan Baru')
    c.execute("INSERT INTO kenderaan (location_id, name) VALUES (?, ?)", (location_id, name))
    kid = c.lastrowid
    for r in range(1, 11):
        c.execute("INSERT OR IGNORE INTO ujian (kenderaan_id, row_num) VALUES (?, ?)", (kid, r))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok', 'id': kid})

@app.route('/api/delete_kenderaan/<int:kenderaan_id>', methods=['DELETE'])
def delete_kenderaan(kenderaan_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM ujian WHERE kenderaan_id=?", (kenderaan_id,))
    c.execute("DELETE FROM kenderaan WHERE id=?", (kenderaan_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/api/add_row/<int:kenderaan_id>', methods=['POST'])
def add_row(kenderaan_id):
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO ujian (kenderaan_id, row_num) VALUES (?,?)",
              (kenderaan_id, data['row_num']))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

# @app.route('/api/export_csv/<int:location_id>')
# def export_csv(location_id):
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     c = conn.cursor()
#     c.execute("SELECT * FROM locations WHERE id=?", (location_id,))
#     loc = dict(c.fetchone()) if c.fetchone() else None
#     if not loc:
#         return "Location not found", 404
#     c.execute("SELECT * FROM kenderaan WHERE location_id=? ORDER BY id", (location_id,))
#     kenderaan = [dict(r) for r in c.fetchall()]
#     output = io.StringIO()
#     writer = csv.writer(output)
#     writer.writerow([f'Location: {loc["name"]}'])
#     writer.writerow([f'Bound 1: {loc["bound1_name"]}', f'Bound 2: {loc["bound2_name"]}'])
#     writer.writerow([])
#     for k in kenderaan:
#         writer.writerow([f'--- {k["name"] or "Kenderaan"} ---'])
#         writer.writerow(['Plat:', k['plat'], 'Berat:', k['berat'], 'Gandar:', k['gandar']])
#         writer.writerow([])
#         writer.writerow(['Bil', 'Arah/Bound', 'Data ID', 'Tarikh & Masa', 'Kelajuan',
#                          'Bil.Gandar', 'Lorong', 'Berat Bacaan', 'Perbezaan Julat %', 'Remark'])
#         c.execute("SELECT * FROM ujian WHERE kenderaan_id=? ORDER BY row_num", (k['id'],))
#         for u in c.fetchall():
#             writer.writerow([u['row_num'], u['arah'], u['data_id'], u['tarikh'],
#                            u['kelajuan'], u['bil_gandar'], u['lorong'],
#                            u['berat_bacaan'], u['perbezaan'], u['remark']])
#         writer.writerow([])
#     conn.close()
#     return output.getvalue(), 200, {'Content-Type': 'text/csv', 'Content-Disposition': f'attachment; filename=location_{location_id}.csv'}

@app.route('/api/export_csv/<int:location_id>')
def export_csv(location_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM locations WHERE id=?", (location_id,))
    row = c.fetchone()                 
    if not row:                      
        conn.close()
        return "Location not found", 404
    loc = dict(row)                     

    c.execute("SELECT * FROM kenderaan WHERE location_id=? ORDER BY id", (location_id,))
    kenderaan = [dict(r) for r in c.fetchall()]
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([f'Location: {loc["name"]}'])
    writer.writerow([f'Bound 1: {loc["bound1_name"]}', f'Bound 2: {loc["bound2_name"]}'])
    writer.writerow([])

    for k in kenderaan:
        writer.writerow([f'--- {k["name"] or "Kenderaan"} ---'])
        writer.writerow(['Plat:', k['plat'], 'Berat:', k['berat'], 'Gandar:', k['gandar']])
        writer.writerow([])
        writer.writerow(['Bil', 'Arah/Bound', 'Data ID', 'Tarikh & Masa', 'Kelajuan',
                         'Bil.Gandar', 'Lorong', 'Berat Bacaan', 'Perbezaan Julat %', 'Remark'])
        c.execute("SELECT * FROM ujian WHERE kenderaan_id=? ORDER BY row_num", (k['id'],))
        for u in c.fetchall():
            writer.writerow([u['row_num'], u['arah'], u['data_id'], u['tarikh'],
                           u['kelajuan'], u['bil_gandar'], u['lorong'],
                           u['berat_bacaan'], u['perbezaan'], u['remark']])
        writer.writerow([])

    conn.close()
    return output.getvalue(), 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': f'attachment; filename=location_{location_id}.csv'
    }

# @app.route('/testing')
# def testing_page():
#     return render_template('testing.html')

@app.route('/')
def home():
    return render_template('home.html', logged_in=session.get('logged_in', False))

@app.route('/testing')
def testing_page():
    return render_template('testing.html', logged_in=session.get('logged_in', False))


@app.route('/api/summary')
def get_summary():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM locations")
    total_locations = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM kenderaan")
    total_vehicles = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM ujian")
    total_rows = c.fetchone()[0]

    c.execute("""SELECT COUNT(*) FROM ujian 
                  WHERE data_id != '' OR berat_bacaan != '' OR tarikh != ''""")
    filled_rows = c.fetchone()[0]

    c.execute("""SELECT COUNT(*) FROM ujian 
                  WHERE CAST(REPLACE(REPLACE(perbezaan, ' %', ''), ',', '.') AS REAL) > 10""")
    high_deviation = c.fetchone()[0]

    c.execute("""SELECT l.id, l.name, 
                        COUNT(DISTINCT k.id) as vehicles,
                        COUNT(u.id) as total_tests,
                        SUM(CASE WHEN u.data_id != '' OR u.berat_bacaan != '' THEN 1 ELSE 0 END) as filled_tests
                 FROM locations l
                 LEFT JOIN kenderaan k ON k.location_id = l.id
                 LEFT JOIN ujian u ON u.kenderaan_id = k.id
                 GROUP BY l.id
                 ORDER BY l.id""")
    locations_data = [dict(r) for r in c.fetchall()]

    c.execute("""SELECT k.id, k.name, k.plat, l.name as loc_name, 
                        u.perbezaan, u.berat_bacaan
                FROM ujian u
                JOIN kenderaan k ON k.id = u.kenderaan_id
                JOIN locations l ON l.id = k.location_id
                WHERE ABS(CAST(REPLACE(REPLACE(u.perbezaan, ' %', ''), ',', '.') AS REAL)) > 10
                ORDER BY ABS(CAST(REPLACE(REPLACE(u.perbezaan, ' %', ''), ',', '.') AS REAL)) DESC
                LIMIT 10""")
    alerts = [dict(r) for r in c.fetchall()]    


    conn.close()

    return jsonify({
        'total_locations': total_locations,
        'total_vehicles': total_vehicles,
        'total_rows': total_rows,
        'filled_rows': filled_rows,
        'fill_percentage': round(total_rows / filled_rows * 100, 1) if total_rows > 0 else 0,
        'high_deviation': high_deviation,
        'locations': locations_data,
        'alerts': alerts
    })

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         password = request.form.get('password', '')
#         if password == ADMIN_PASSWORD:
#             session['logged_in'] = True
#             return redirect('/testing')
#         else:
#             return render_template('login.html', error='Wrong password')
#     return render_template('login.html', error='')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session.permanent = True          # ← Make session permanent (respects timeout)
            session['logged_in'] = True
            return redirect('/testing')
        else:
            return render_template('login.html', error='Wrong password')
    return render_template('login.html', error='')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@app.route('/api/tokens')
def get_tokens():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, created_at FROM locations ORDER BY id")
    locs = [{'id': r['id'], 'name': r['name'], 'created_at': r['created_at'],
             'token': encrypt_id(r['id'])} for r in c.fetchall()]
    conn.close()
    return jsonify(locs)


# @app.route('/api/latest')
# def get_latest():
#     conn = sqlite3.connect(DB_PATH)
#     conn.row_factory = sqlite3.Row
#     c = conn.cursor()
#     c.execute("""
#         SELECT u.id, u.kenderaan_id, u.row_num, u.data_id, u.berat_bacaan, u.perbezaan,
#                k.name as vehicle_name, k.plat, k.gandar, l.name as location_name
#         FROM ujian u
#         JOIN kenderaan k ON k.id = u.kenderaan_id
#         JOIN locations l ON l.id = k.location_id
#         WHERE u.data_id != '' OR u.berat_bacaan != ''
#         ORDER BY u.id DESC
#         LIMIT 3
#     """)
#     latest = [dict(r) for r in c.fetchall()]
#     conn.close()
#     return jsonify(latest)

@app.route('/api/latest')
def get_latest():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.kenderaan_id, u.row_num, u.data_id, u.berat_bacaan, u.perbezaan,
               k.name as vehicle_name, k.plat, k.gandar, l.name as location_name
        FROM ujian u
        JOIN kenderaan k ON k.id = u.kenderaan_id
        JOIN locations l ON l.id = k.location_id
        WHERE u.id IN (
            SELECT MAX(u2.id)          -- Latest row per vehicle
            FROM ujian u2
            WHERE u2.data_id != '' OR u2.berat_bacaan != ''
            GROUP BY u2.kenderaan_id
        )
        ORDER BY u.id DESC
        LIMIT 3
    """)
    latest = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(latest)

@app.route('/api/delete_row/<int:kenderaan_id>/<int:row_num>', methods=['DELETE'])
def delete_row(kenderaan_id, row_num):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM ujian WHERE kenderaan_id=? AND row_num=?", (kenderaan_id, row_num))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
