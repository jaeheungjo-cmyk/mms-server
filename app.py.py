"""
MMS — 모터 자재 관리 시스템 백엔드
Flask + SQLite
실행: python app.py
접속: http://localhost:5000
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, hashlib, os, json
from datetime import datetime

app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/api/*": {"origins": "*"}})  # 모든 출처 허용

DB_PATH = 'mms.db'

# ══════════════════════════════════════════
# DB 초기화
# ══════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        pw_hash     TEXT NOT NULL,
        role        TEXT DEFAULT 'user',
        dept        TEXT DEFAULT '',
        active      INTEGER DEFAULT 0,
        pending     INTEGER DEFAULT 1,
        reg_date    TEXT
    );

    CREATE TABLE IF NOT EXISTS locations (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        zone TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS mat_codes (
        code  TEXT PRIMARY KEY,
        name  TEXT NOT NULL,
        maker TEXT DEFAULT '',
        cap   TEXT DEFAULT '',
        cat   TEXT DEFAULT ''
    );


    CREATE TABLE IF NOT EXISTS mat_ids (
        id   TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        ref  TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS motors (
        id        TEXT PRIMARY KEY,
        mat_code  TEXT,
        mat_id    TEXT,
        name      TEXT,
        maker     TEXT DEFAULT '',
        cap       TEXT DEFAULT '',
        loc       TEXT DEFAULT '',
        shelf     TEXT DEFAULT '',
        status    TEXT DEFAULT '재고',
        reg_date  TEXT,
        reg_by    TEXT
    );

    CREATE TABLE IF NOT EXISTS history (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        motor_id  TEXT NOT NULL,
        dt        TEXT NOT NULL,
        type      TEXT NOT NULL,
        from_loc  TEXT DEFAULT '',
        to_loc    TEXT DEFAULT '',
        by_user   TEXT DEFAULT '',
        memo      TEXT DEFAULT '',
        FOREIGN KEY(motor_id) REFERENCES motors(id)
    );

    CREATE TABLE IF NOT EXISTS special_issues (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        motor_id  TEXT NOT NULL,
        type      TEXT NOT NULL,
        tag_class TEXT DEFAULT 'tag-i',
        icon      TEXT DEFAULT 'i',
        desc      TEXT DEFAULT ''
    );
    """)

    today = datetime.now().strftime('%Y-%m-%d')

    # 기본 마스터 계정
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?,?,?)",
              ('master','관리자',hash_pw('1234'),'master','관리부',1,0,today))
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?,?,?)",
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
    c.executemany("INSERT OR IGNORE INTO locations VALUES (?,?,?)", locs)

    # 기본 자재코드
    codes = [
        ('MTR-1001','유도전동기','효성','15 kW','일반'),
        ('MTR-1002','서보모터','Siemens','2.2 kW','정밀'),
        ('MTR-1003','감속모터','삼성전기','7.5 kW','일반'),
        ('MTR-1004','펌프모터','LS산전','3.7 kW','일반'),
    ]
    c.executemany("INSERT OR IGNORE INTO mat_codes VALUES (?,?,?,?,?)", codes)

    # 기본 자재ID
    mids = [
        ('IM-001','유도전동기 15kW #1','MTR-1001'),
        ('IM-007','유도전동기 22kW #7','MTR-1001'),
        ('SM-008','서보모터 2.2kW #8', 'MTR-1002'),
        ('GM-015','감속모터 7.5kW #15','MTR-1003'),
        ('PM-003','펌프모터 3.7kW #3', 'MTR-1004'),
    ]
    c.executemany("INSERT OR IGNORE INTO mat_ids VALUES (?,?,?)", mids)

    # 기본 자재 샘플
    motors = [
        ('m001','MTR-1001','IM-001','유도전동기','효성',  '15 kW','A창고-3번','3번 선반','재고',    today,'관리자'),
        ('m002','MTR-1002','SM-008','서보모터',  'Siemens','2.2 kW','B라인 현장','',      '반출중',  today,'관리자'),
        ('m003','MTR-1003','GM-015','감속모터',  '삼성전기','7.5 kW','C창고-1번','1번 선반','재고',   today,'관리자'),
        ('m004','MTR-1001','IM-007','유도전동기','ABB',    '22 kW', '수리센터', '',        '수리중','2025-03-10','관리자'),
        ('m005','MTR-1004','PM-003','펌프모터',  'LS산전', '3.7 kW','A창고-5번','2번 선반','재고',   today,'관리자'),
    ]
    c.executemany("INSERT OR IGNORE INTO motors VALUES (?,?,?,?,?,?,?,?,?,?,?)", motors)

    # 기본 이력
    hist = [
        ('m001',today+' 07:12','반입','수리센터','A창고-3번','관리자','수리완료 후 복귀'),
        ('m002',today+' 08:05','반출','A창고-2번','B라인 현장','김설비','B라인 교체 작업'),
        ('m003',today+' 09:33','반입','D라인 현장','C창고-1번','관리자',''),
        ('m004','2025-03-10 14:30','수리','C창고-4번','수리센터','박설비','▲ 외부수리 지연 30일 초과'),
        ('m005',today+' 11:02','반입','B라인 현장','A창고-5번','김설비',''),
    ]
    for h in hist:
        c.execute("INSERT OR IGNORE INTO history(motor_id,dt,type,from_loc,to_loc,by_user,memo) "
                  "SELECT ?,?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM history WHERE motor_id=? AND dt=?)",
                  (*h, h[0], h[1]))

    # 기본 특이이력
    issues = [
        ('m004','지연',   'tag-r','▲','외부 수리 의뢰 후 30일 초과, 복귀 예정일 미도래'),
        ('m002','확인필요','tag-w','!','등록 위치(B창고-2번)와 실제 위치 불일치 확인 필요'),
        ('m003','점검예정','tag-i','i','3일 후 정기점검 예정, 반출 스케줄 조정 필요'),
    ]
    c.executemany("INSERT OR IGNORE INTO special_issues(motor_id,type,tag_class,icon,desc) "
                  "SELECT ?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM special_issues WHERE motor_id=? AND type=?)",
                  [(*x, x[0], x[1]) for x in issues])

    # 기존 DB에 maker/cap 컬럼 추가 (이미 있으면 무시)
    for col_sql in [
        "ALTER TABLE mat_codes ADD COLUMN maker TEXT DEFAULT ''",
        "ALTER TABLE mat_codes ADD COLUMN cap   TEXT DEFAULT ''",
    ]:
        try: conn.execute(col_sql)
        except: pass

    conn.commit()
    conn.close()
    print("✓ DB 초기화 완료")


# ══════════════════════════════════════════
# 정적 파일 (index.html)
# ══════════════════════════════════════════
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:path>')
def static_files(path):
    return send_from_directory('static', path)


# ══════════════════════════════════════════
# AUTH API
# ══════════════════════════════════════════
@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=? AND pw_hash=?",
                     (d['id'], hash_pw(d['pw']))).fetchone()
    conn.close()
    if not u:
        return jsonify({'ok':False,'msg':'아이디 또는 비밀번호가 올바르지 않습니다.'})
    if u['pending']:
        return jsonify({'ok':False,'msg':'가입 신청 중입니다. 마스터 승인을 기다려 주세요.'})
    if not u['active']:
        return jsonify({'ok':False,'msg':'비활성화된 계정입니다. 관리자에게 문의하세요.'})
    return jsonify({'ok':True,'user':{'id':u['id'],'name':u['name'],'role':u['role'],'dept':u['dept']}})

@app.route('/api/signup', methods=['POST'])
def signup():
    d = request.json
    conn = get_db()
    exists = conn.execute("SELECT id FROM users WHERE id=?", (d['id'],)).fetchone()
    if exists:
        conn.close()
        return jsonify({'ok':False,'msg':'이미 사용 중인 아이디입니다.'})
    today = datetime.now().strftime('%Y-%m-%d')
    conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
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
    rows = conn.execute("SELECT id,name,role,dept,active,pending,reg_date FROM users").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/users', methods=['POST'])
def add_user():
    d = request.json
    conn = get_db()
    exists = conn.execute("SELECT id FROM users WHERE id=?", (d['id'],)).fetchone()
    if exists:
        conn.close()
        return jsonify({'ok':False,'msg':'이미 존재하는 아이디입니다.'})
    today = datetime.now().strftime('%Y-%m-%d')
    conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
                 (d['id'],d['name'],hash_pw(d['pw']),d.get('role','user'),d.get('dept',''),1,0,today))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/users/<uid>/approve', methods=['POST'])
def approve_user(uid):
    conn = get_db()
    conn.execute("UPDATE users SET active=1, pending=0 WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/users/<uid>/toggle', methods=['POST'])
def toggle_user(uid):
    conn = get_db()
    conn.execute("UPDATE users SET active = CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/users/<uid>', methods=['DELETE'])
def delete_user(uid):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})


# ══════════════════════════════════════════
# MOTORS API
# ══════════════════════════════════════════
@app.route('/api/motors', methods=['GET'])
def get_motors():
    conn = get_db()
    motors = conn.execute("SELECT * FROM motors").fetchall()
    result = []
    for m in motors:
        md = dict(m)
        hist = conn.execute(
            "SELECT * FROM history WHERE motor_id=? ORDER BY dt ASC", (m['id'],)).fetchall()
        md['history'] = [dict(h) for h in hist]
        result.append(md)
    conn.close()
    return jsonify(result)

@app.route('/api/motors/<mid>', methods=['GET'])
def get_motor(mid):
    conn = get_db()
    m = conn.execute("SELECT * FROM motors WHERE id=?", (mid,)).fetchone()
    if not m:
        conn.close()
        return jsonify({'ok':False,'msg':'자재를 찾을 수 없습니다.'}), 404
    md = dict(m)
    hist = conn.execute(
        "SELECT * FROM history WHERE motor_id=? ORDER BY dt ASC", (mid,)).fetchall()
    md['history'] = [dict(h) for h in hist]
    conn.close()
    return jsonify(md)

@app.route('/api/motors/by-matid/<matid>', methods=['GET'])
def get_motor_by_matid(matid):
    conn = get_db()
    m = conn.execute("SELECT * FROM motors WHERE mat_id=?", (matid,)).fetchone()
    if not m:
        conn.close()
        return jsonify({'ok':False,'msg':'자재를 찾을 수 없습니다.'}), 404
    md = dict(m)
    hist = conn.execute(
        "SELECT * FROM history WHERE motor_id=? ORDER BY dt ASC", (m['id'],)).fetchall()
    md['history'] = [dict(h) for h in hist]
    conn.close()
    return jsonify(md)

@app.route('/api/motors', methods=['POST'])
def add_motor():
    d = request.json
    import uuid
    mid = 'm' + uuid.uuid4().hex[:8]
    conn = get_db()
    conn.execute("INSERT INTO motors VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (mid, d['matCode'], d['matId'], d['name'], d.get('maker',''),
                  d.get('cap',''), d['loc'], d.get('shelf',''),
                  d.get('status','재고'), d['regDate'], d['regBy']))
    if d.get('memo'):
        conn.execute("INSERT INTO history(motor_id,dt,type,from_loc,to_loc,by_user,memo) VALUES (?,?,?,?,?,?,?)",
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
    q = """
        SELECT h.*, m.mat_code, m.mat_id, m.name as motor_name
        FROM history h
        JOIN motors m ON h.motor_id = m.id
        ORDER BY h.dt DESC
    """
    rows = conn.execute(q).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/motors/<mid>/history', methods=['POST'])
def add_history(mid):
    d = request.json
    conn = get_db()
    m = conn.execute("SELECT * FROM motors WHERE id=?", (mid,)).fetchone()
    if not m:
        conn.close()
        return jsonify({'ok':False,'msg':'자재 없음'}), 404
    conn.execute("INSERT INTO history(motor_id,dt,type,from_loc,to_loc,by_user,memo) VALUES (?,?,?,?,?,?,?)",
                 (mid, d['dt'], d['type'], m['loc'], d['toLoc'], d['by'], d.get('memo','')))
    new_status = {'반입':'재고','반출':'반출중','수리':'수리중'}.get(d['type'], m['status'])
    conn.execute("UPDATE motors SET loc=?, status=? WHERE id=?", (d['toLoc'], new_status, mid))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})


# ══════════════════════════════════════════
# SETTINGS API
# ══════════════════════════════════════════
@app.route('/api/locations', methods=['GET'])
def get_locations():
    conn = get_db()
    rows = conn.execute("SELECT * FROM locations").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/locations', methods=['POST'])
def add_location():
    d = request.json
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO locations VALUES (?,?,?)", (d['code'],d['name'],d.get('zone','')))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/locations/<code>', methods=['DELETE'])
def del_location(code):
    conn = get_db()
    conn.execute("DELETE FROM locations WHERE code=?", (code,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/matcodes', methods=['GET'])
def get_matcodes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM mat_codes ORDER BY code").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/matcodes', methods=['POST'])
def add_matcode():
    d = request.json
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO mat_codes VALUES (?,?,?,?,?)",
                 (d['code'], d['name'], d.get('maker',''), d.get('cap',''), d.get('cat','')))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/matcodes/<code>', methods=['DELETE'])
def del_matcode(code):
    conn = get_db()
    conn.execute("DELETE FROM mat_codes WHERE code=?", (code,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/matids', methods=['GET'])
def get_matids():
    conn = get_db()
    rows = conn.execute("SELECT * FROM mat_ids ORDER BY ref, id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/matids', methods=['POST'])
def add_matid():
    d = request.json
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO mat_ids VALUES (?,?,?)", (d['id'],d['name'],d.get('ref','')))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/matids/<mid>', methods=['DELETE'])
def del_matid(mid):
    conn = get_db()
    conn.execute("DELETE FROM mat_ids WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/special-issues', methods=['GET'])
def get_special_issues():
    conn = get_db()
    rows = conn.execute("SELECT * FROM special_issues").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ══════════════════════════════════════════
# 실행
# ══════════════════════════════════════════
# 앱 시작 시 DB 초기화 (Render 환경 포함)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"MMS 서버 시작 — port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
