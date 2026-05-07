from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import hashlib, os
from datetime import datetime
import psycopg2
import psycopg2.extras

app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/api/*": {"origins": "*"}})

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        pw_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        dept TEXT DEFAULT '',
        active INTEGER DEFAULT 0,
        pending INTEGER DEFAULT 1,
        reg_date TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        zone TEXT DEFAULT ''
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS mat_codes (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        maker TEXT DEFAULT '',
        cap TEXT DEFAULT '',
        cat TEXT DEFAULT ''
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS mat_ids (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        ref TEXT DEFAULT ''
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS motors (
        id TEXT PRIMARY KEY,
        mat_code TEXT,
        mat_id TEXT,
        name TEXT,
        maker TEXT DEFAULT '',
        cap TEXT DEFAULT '',
        loc TEXT DEFAULT '',
        shelf TEXT DEFAULT '',
        status TEXT DEFAULT '재고',
        reg_date TEXT,
        reg_by TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id SERIAL PRIMARY KEY,
        motor_id TEXT NOT NULL,
        dt TEXT NOT NULL,
        type TEXT NOT NULL,
        from_loc TEXT DEFAULT '',
        to_loc TEXT DEFAULT '',
        by_user TEXT DEFAULT '',
        memo TEXT DEFAULT ''
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS special_issues (
        id SERIAL PRIMARY KEY,
        motor_id TEXT NOT NULL,
        type TEXT NOT NULL,
        tag_class TEXT DEFAULT 'tag-i',
        icon TEXT DEFAULT 'i',
        description TEXT DEFAULT ''
    )""")

    today = datetime.now().strftime('%Y-%m-%d')

    # 기본 계정
    c.execute("INSERT INTO users VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
              ('master','관리자',hash_pw('1234'),'master','관리부',1,0,today))
    c.execute("INSERT INTO users VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
              ('user01','김설비',hash_pw('1234'),'user','설비팀',1,0,today))

    # 기본 위치
    locs = [
        ('LOC-001','A창고-1번','A구역'),('LOC-002','A창고-2번','A구역'),
        ('LOC-003','A창고-3번','A구역'),('LOC-004','A창고-5번','A구역'),
        ('LOC-005','B창고-1번','B구역'),('LOC-006','B창고-2번','B구역'),
        ('LOC-007','C창고-1번','C구역'),('LOC-008','C창고-4번','C구역'),
        ('LOC-009','수리센터','외부'),  ('LOC-010','B라인 현장','현장'),
        ('LOC-011','D라인 현장','현장'),
    ]
    for l in locs:
        c.execute("INSERT INTO locations VALUES (%s,%s,%s) ON CONFLICT (code) DO NOTHING", l)

    # 기본 자재코드
    codes = [
        ('MTR-1001','유도전동기','효성','15 kW','일반'),
        ('MTR-1002','서보모터','Siemens','2.2 kW','정밀'),
        ('MTR-1003','감속모터','삼성전기','7.5 kW','일반'),
        ('MTR-1004','펌프모터','LS산전','3.7 kW','일반'),
    ]
    for code in codes:
        c.execute("INSERT INTO mat_codes VALUES (%s,%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING", code)

    # 기본 자재ID
    mids = [
        ('IM-001','유도전동기 15kW #1','MTR-1001'),
        ('IM-007','유도전동기 22kW #7','MTR-1001'),
        ('SM-008','서보모터 2.2kW #8', 'MTR-1002'),
        ('GM-015','감속모터 7.5kW #15','MTR-1003'),
        ('PM-003','펌프모터 3.7kW #3', 'MTR-1004'),
    ]
    for mid in mids:
        c.execute("INSERT INTO mat_ids VALUES (%s,%s,%s) ON CONFLICT (id) DO NOTHING", mid)

    # 기본 자재 샘플
    motors = [
        ('m001','MTR-1001','IM-001','유도전동기','효성','15 kW','A창고-3번','3번 선반','재고',today,'관리자'),
        ('m002','MTR-1002','SM-008','서보모터','Siemens','2.2 kW','B라인 현장','','반출중',today,'관리자'),
        ('m003','MTR-1003','GM-015','감속모터','삼성전기','7.5 kW','C창고-1번','1번 선반','재고',today,'관리자'),
        ('m004','MTR-1001','IM-007','유도전동기','ABB','22 kW','수리센터','','수리중','2025-03-10','관리자'),
        ('m005','MTR-1004','PM-003','펌프모터','LS산전','3.7 kW','A창고-5번','2번 선반','재고',today,'관리자'),
    ]
    for m in motors:
        c.execute("INSERT INTO motors VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING", m)

    conn.commit()
    conn.close()
    print("✓ DB 초기화 완료 (PostgreSQL)")


# ══════════════════════════════════════════
# 정적 파일
# ══════════════════════════════════════════
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


# ══════════════════════════════════════════
# AUTH API
# ══════════════════════════════════════════
@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM users WHERE id=%s AND pw_hash=%s", (d['id'], hash_pw(d['pw'])))
    u = c.fetchone()
    conn.close()
    if not u:
        return jsonify({'ok':False,'msg':'아이디 또는 비밀번호가 올바르지 않습니다.'})
    if u['pending']:
        return jsonify({'ok':False,'msg':'가입 신청 중입니다. 마스터 승인을 기다려 주세요.'})
    if not u['active']:
        return jsonify({'ok':False,'msg':'비활성화된 계정입니다.'})
    return jsonify({'ok':True,'user':{'id':u['id'],'name':u['name'],'role':u['role'],'dept':u['dept']}})

@app.route('/api/signup', methods=['POST'])
def signup():
    d = request.json
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT id FROM users WHERE id=%s", (d['id'],))
    if c.fetchone():
        conn.close()
        return jsonify({'ok':False,'msg':'이미 사용 중인 아이디입니다.'})
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("INSERT INTO users VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
              (d['id'],d['name'],hash_pw(d['pw']),'user',d.get('dept',''),0,1,today))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})


# ══════════════════════════════════════════
# USERS API
# ══════════════════════════════════════════
@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT id,name,role,dept,active,pending,reg_date FROM users")
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/users', methods=['POST'])
def add_user():
    d = request.json
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT id FROM users WHERE id=%s", (d['id'],))
    if c.fetchone():
        conn.close()
        return jsonify({'ok':False,'msg':'이미 존재하는 아이디입니다.'})
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("INSERT INTO users VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
              (d['id'],d['name'],hash_pw(d['pw']),d.get('role','user'),d.get('dept',''),1,0,today))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/users/<uid>/approve', methods=['POST'])
def approve_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET active=1, pending=0 WHERE id=%s", (uid,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/users/<uid>/toggle', methods=['POST'])
def toggle_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET active = CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=%s", (uid,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/users/<uid>', methods=['DELETE'])
def delete_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=%s", (uid,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})


# ══════════════════════════════════════════
# MOTORS API
# ══════════════════════════════════════════
@app.route('/api/motors', methods=['GET'])
def get_motors():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM motors")
    motors = c.fetchall()
    result = []
    for m in motors:
        md = dict(m)
        c.execute("SELECT * FROM history WHERE motor_id=%s ORDER BY dt ASC", (m['id'],))
        md['history'] = [dict(h) for h in c.fetchall()]
        result.append(md)
    conn.close()
    return jsonify(result)

@app.route('/api/motors/<mid>', methods=['GET'])
def get_motor(mid):
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM motors WHERE id=%s", (mid,))
    m = c.fetchone()
    if not m:
        conn.close()
        return jsonify({'ok':False,'msg':'자재를 찾을 수 없습니다.'}), 404
    md = dict(m)
    c.execute("SELECT * FROM history WHERE motor_id=%s ORDER BY dt ASC", (mid,))
    md['history'] = [dict(h) for h in c.fetchall()]
    conn.close()
    return jsonify(md)

@app.route('/api/motors/by-matid/<matid>', methods=['GET'])
def get_motor_by_matid(matid):
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM motors WHERE mat_id=%s", (matid,))
    m = c.fetchone()
    if not m:
        conn.close()
        return jsonify({'ok':False,'msg':'자재를 찾을 수 없습니다.'}), 404
    md = dict(m)
    c.execute("SELECT * FROM history WHERE motor_id=%s ORDER BY dt ASC", (m['id'],))
    md['history'] = [dict(h) for h in c.fetchall()]
    conn.close()
    return jsonify(md)

@app.route('/api/motors', methods=['POST'])
def add_motor():
    d = request.json
    import uuid
    mid = 'm' + uuid.uuid4().hex[:8]
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO motors VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
              (mid, d['matCode'], d['matId'], d['name'], d.get('maker',''),
               d.get('cap',''), d['loc'], d.get('shelf',''),
               d.get('status','재고'), d['regDate'], d['regBy']))
    if d.get('memo'):
        c.execute("INSERT INTO history(motor_id,dt,type,from_loc,to_loc,by_user,memo) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                  (mid, d['regDate']+' 07:00', '반입', '', d['loc'], d['regBy'], d['memo']))
    conn.commit()
    conn.close()
    return jsonify({'ok':True,'id':mid})


# ══════════════════════════════════════════
# HISTORY API
# ══════════════════════════════════════════
@app.route('/api/history', methods=['GET'])
def get_history():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("""
        SELECT h.*, m.mat_code, m.mat_id, m.name as motor_name
        FROM history h
        JOIN motors m ON h.motor_id = m.id
        ORDER BY h.dt DESC
    """)
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/motors/<mid>/history/<int:hid>', methods=['PUT'])
def update_history(mid, hid):
    d = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE history SET type=%s, to_loc=%s, dt=%s, memo=%s WHERE id=%s AND motor_id=%s",
              (d['type'], d['toLoc'], d['dt'], d.get('memo',''), hid, mid))
    if d['type'] in ('반입','반출','수리'):
        new_status = {'반입':'재고','반출':'반출중','수리':'수리중'}.get(d['type'])
        c.execute("UPDATE motors SET loc=%s, status=%s WHERE id=%s", (d['toLoc'], new_status, mid))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})
    d = request.json
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM motors WHERE id=%s", (mid,))
    m = c.fetchone()
    if not m:
        conn.close()
        return jsonify({'ok':False,'msg':'자재 없음'}), 404
    c.execute("INSERT INTO history(motor_id,dt,type,from_loc,to_loc,by_user,memo) VALUES (%s,%s,%s,%s,%s,%s,%s)",
              (mid, d['dt'], d['type'], m['loc'], d['toLoc'], d['by'], d.get('memo','')))
    new_status = {'반입':'재고','반출':'반출중','수리':'수리중'}.get(d['type'], m['status'])
    c.execute("UPDATE motors SET loc=%s, status=%s WHERE id=%s", (d['toLoc'], new_status, mid))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})


# ══════════════════════════════════════════
# SETTINGS API
# ══════════════════════════════════════════
@app.route('/api/locations', methods=['GET'])
def get_locations():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM locations")
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/locations', methods=['POST'])
def add_location():
    d = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO locations VALUES (%s,%s,%s) ON CONFLICT (code) DO UPDATE SET name=%s, zone=%s",
              (d['code'],d['name'],d.get('zone',''),d['name'],d.get('zone','')))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/locations/<code>', methods=['DELETE'])
def del_location(code):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM locations WHERE code=%s", (code,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/matcodes', methods=['GET'])
def get_matcodes():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM mat_codes ORDER BY code")
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/matcodes', methods=['POST'])
def add_matcode():
    d = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO mat_codes VALUES (%s,%s,%s,%s,%s) ON CONFLICT (code) DO UPDATE SET name=%s, maker=%s, cap=%s, cat=%s",
              (d['code'],d['name'],d.get('maker',''),d.get('cap',''),d.get('cat',''),
               d['name'],d.get('maker',''),d.get('cap',''),d.get('cat','')))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/matcodes/<code>', methods=['DELETE'])
def del_matcode(code):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM mat_codes WHERE code=%s", (code,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/matids', methods=['GET'])
def get_matids():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM mat_ids ORDER BY ref, id")
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/matids', methods=['POST'])
def add_matid():
    d = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO mat_ids VALUES (%s,%s,%s) ON CONFLICT (id) DO UPDATE SET name=%s, ref=%s",
              (d['id'],d['name'],d.get('ref',''),d['name'],d.get('ref','')))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/matids/<mid>', methods=['DELETE'])
def del_matid(mid):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM mat_ids WHERE id=%s", (mid,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/special-issues', methods=['GET'])
def get_special_issues():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM special_issues")
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ══════════════════════════════════════════
# 실행
# ══════════════════════════════════════════
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
