import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"
DB_PATH = Path(os.environ.get("RYD_DB_PATH", ROOT / "data" / "ryd.db"))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
SESSION_DAYS = 30


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS olympiads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                subject TEXT NOT NULL CHECK(subject IN ('Математика', 'Информатика')),
                event_date TEXT,
                goal TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                subject TEXT NOT NULL CHECK(subject IN ('Математика', 'Информатика')),
                color TEXT NOT NULL DEFAULT '#2563eb',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
                olympiad_id INTEGER REFERENCES olympiads(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL CHECK(difficulty IN ('Легко', 'Средне', 'Сложно')),
                status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned', 'in_progress', 'solved')),
                due_date TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(user_id, completed_at);
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        for name, definition in (
            ("planned_minutes", "INTEGER NOT NULL DEFAULT 0"),
            ("spent_minutes", "INTEGER NOT NULL DEFAULT 0"),
            ("condition_text", "TEXT NOT NULL DEFAULT ''"),
            ("condition_image", "TEXT"),
            ("problem_count", "INTEGER NOT NULL DEFAULT 1"),
            ("solved_count", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if name not in columns:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {definition}")
        conn.execute("UPDATE tasks SET solved_count=1 WHERE status='solved' AND solved_count=0")
        for table in ("topics", "olympiads"):
            schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()["sql"]
            if "Искусственный интеллект" not in schema:
                migrate_subject_table(conn, table)


def migrate_subject_table(conn, table):
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    extra = "color TEXT NOT NULL DEFAULT '#2563eb'" if table == "topics" else "event_date TEXT, goal TEXT NOT NULL DEFAULT ''"
    conn.execute(f"""CREATE TABLE {table}_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        subject TEXT NOT NULL CHECK(subject IN ('Математика', 'Информатика', 'Искусственный интеллект')),
        {extra}, created_at TEXT NOT NULL)""")
    fields = "id,user_id,name,subject,color,created_at" if table == "topics" else "id,user_id,name,subject,event_date,goal,created_at"
    conn.execute(f"INSERT INTO {table}_new({fields}) SELECT {fields} FROM {table}")
    conn.execute(f"DROP TABLE {table}")
    conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password, stored):
    try:
        salt_hex, expected = stored.split(":", 1)
        actual = hash_password(password, bytes.fromhex(salt_hex)).split(":", 1)[1]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def row_dict(row):
    return dict(row) if row else None


class ApiError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    server_version = "RYD/1.0"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def json_response(self, data, status=200, headers=None):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 5_000_000:
                raise ApiError(413, "Слишком большой запрос")
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            raise ApiError(400, "Некорректный JSON")

    def token(self):
        jar = cookies.SimpleCookie(self.headers.get("Cookie"))
        morsel = jar.get("ryd_session")
        return morsel.value if morsel else None

    def user(self, required=True):
        token = self.token()
        if token:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            with db() as conn:
                row = conn.execute(
                    """SELECT u.id, u.name, u.email, u.created_at FROM sessions s
                       JOIN users u ON u.id = s.user_id
                       WHERE s.token_hash = ? AND s.expires_at > ?""",
                    (token_hash, now()),
                ).fetchone()
                if row:
                    return row_dict(row)
        if required:
            raise ApiError(401, "Необходима авторизация")
        return None

    def route(self):
        return urlparse(self.path).path.rstrip("/") or "/"

    def do_GET(self):
        try:
            path = self.route()
            if path == "/api/me":
                return self.json_response({"user": self.user(False)})
            if path == "/api/dashboard":
                return self.dashboard()
            if path == "/api/olympiads":
                return self.list_items("olympiads")
            if path == "/api/topics":
                return self.list_items("topics")
            if path == "/api/notes":
                return self.list_notes()
            if path == "/api/tasks":
                return self.list_tasks()
            if path == "/api/stats":
                return self.stats()
            if path.startswith("/api/"):
                raise ApiError(404, "Маршрут не найден")
            return self.static(path)
        except ApiError as error:
            self.json_response({"error": error.message}, error.status)
        except Exception as error:
            print("Unhandled error:", repr(error))
            self.json_response({"error": "Внутренняя ошибка сервера"}, 500)

    def do_POST(self):
        try:
            path = self.route()
            if path == "/api/auth/register":
                return self.register()
            if path == "/api/auth/login":
                return self.login()
            if path == "/api/auth/logout":
                return self.logout()
            if path == "/api/olympiads":
                return self.create_olympiad()
            if path == "/api/topics":
                return self.create_topic()
            if path == "/api/tasks":
                return self.create_task()
            if path == "/api/notes":
                return self.create_note()
            raise ApiError(404, "Маршрут не найден")
        except ApiError as error:
            self.json_response({"error": error.message}, error.status)
        except sqlite3.IntegrityError:
            self.json_response({"error": "Такая запись уже существует или данные некорректны"}, 409)
        except Exception as error:
            print("Unhandled error:", repr(error))
            self.json_response({"error": "Внутренняя ошибка сервера"}, 500)

    def do_PATCH(self):
        try:
            parts = self.route().split("/")
            if len(parts) == 4 and parts[1:3] == ["api", "tasks"]:
                return self.update_task(int(parts[3]))
            raise ApiError(404, "Маршрут не найден")
        except ValueError:
            self.json_response({"error": "Некорректный идентификатор"}, 400)
        except ApiError as error:
            self.json_response({"error": error.message}, error.status)

    def do_DELETE(self):
        try:
            parts = self.route().split("/")
            if len(parts) == 4 and parts[1] == "api" and parts[2] in ("tasks", "topics", "olympiads", "notes"):
                return self.delete_item(parts[2], int(parts[3]))
            raise ApiError(404, "Маршрут не найден")
        except ValueError:
            self.json_response({"error": "Некорректный идентификатор"}, 400)
        except ApiError as error:
            self.json_response({"error": error.message}, error.status)

    def session_header(self, token, expires):
        secure = "; Secure" if os.environ.get("RYD_SECURE_COOKIE") == "1" else ""
        return {"Set-Cookie": f"ryd_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_DAYS * 86400}{secure}"}

    def register(self):
        data = self.body()
        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        if len(name) < 2 or "@" not in email or len(password) < 8:
            raise ApiError(400, "Укажите имя, корректную почту и пароль от 8 символов")
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO users(name, email, password_hash, created_at) VALUES(?, ?, ?, ?)",
                (name[:80], email[:160], hash_password(password), now()),
            )
            user_id = cur.lastrowid
            self.seed_user(conn, user_id)
        return self.start_session(user_id, 201)

    def login(self):
        data = self.body()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        with db() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise ApiError(401, "Неверная почта или пароль")
        return self.start_session(row["id"])

    def start_session(self, user_id, status=200):
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now(),))
            conn.execute(
                "INSERT INTO sessions(token_hash, user_id, expires_at) VALUES(?, ?, ?)",
                (hashlib.sha256(token.encode()).hexdigest(), user_id, expires.isoformat()),
            )
            user = row_dict(conn.execute("SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone())
        self.json_response({"user": user}, status, self.session_header(token, expires))

    def logout(self):
        token = self.token()
        if token:
            with db() as conn:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
        self.json_response({"ok": True}, headers={"Set-Cookie": "ryd_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

    def seed_user(self, conn, user_id):
        timestamp = now()
        topics = [("Комбинаторика", "Математика", "#2563eb"), ("Динамическое программирование", "Информатика", "#7c3aed"), ("Теория чисел", "Математика", "#0891b2")]
        ids = []
        for item in topics:
            ids.append(conn.execute("INSERT INTO topics(user_id, name, subject, color, created_at) VALUES(?, ?, ?, ?, ?)", (user_id, *item, timestamp)).lastrowid)
        olympiad_id = conn.execute("INSERT INTO olympiads(user_id, name, subject, event_date, goal, created_at) VALUES(?, ?, ?, ?, ?, ?)", (user_id, "Региональный этап ВсОШ", "Математика", None, "Уверенно решить 6 задач", timestamp)).lastrowid
        conn.execute("INSERT INTO tasks(user_id, topic_id, olympiad_id, title, description, difficulty, status, due_date, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", (user_id, ids[0], olympiad_id, "Разобрать принцип Дирихле", "Решить подборку из 5 задач.", "Средне", "in_progress", None, timestamp))
        conn.execute("INSERT INTO tasks(user_id, topic_id, title, description, difficulty, status, due_date, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)", (user_id, ids[1], "Задачи на рюкзак", "Повторить переходы и оптимизацию памяти.", "Сложно", "planned", None, timestamp))

    def list_items(self, table):
        user = self.user()
        order = "event_date IS NULL, event_date" if table == "olympiads" else "created_at DESC"
        with db() as conn:
            rows = [row_dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE user_id = ? ORDER BY {order}", (user["id"],))]
        self.json_response({table: rows})

    def list_tasks(self):
        user = self.user()
        with db() as conn:
            rows = [row_dict(row) for row in conn.execute(
                """SELECT t.*, p.name topic_name, p.subject, p.color, o.name olympiad_name
                   FROM tasks t LEFT JOIN topics p ON p.id=t.topic_id LEFT JOIN olympiads o ON o.id=t.olympiad_id
                   WHERE t.user_id=? ORDER BY CASE t.status WHEN 'in_progress' THEN 0 WHEN 'planned' THEN 1 ELSE 2 END, t.created_at DESC""", (user["id"],))]
        self.json_response({"tasks": rows})

    def list_notes(self):
        user = self.user()
        with db() as conn:
            rows = [row_dict(row) for row in conn.execute(
                "SELECT n.*, p.name topic_name FROM notes n JOIN topics p ON p.id=n.topic_id WHERE n.user_id=? ORDER BY n.created_at DESC",
                (user["id"],),
            )]
        self.json_response({"notes": rows})

    def create_olympiad(self):
        user, data = self.user(), self.body()
        name, subject = str(data.get("name", "")).strip(), data.get("subject")
        if not name or subject not in ("Математика", "Информатика", "Искусственный интеллект"):
            raise ApiError(400, "Заполните название и предмет")
        with db() as conn:
            cur = conn.execute("INSERT INTO olympiads(user_id,name,subject,event_date,goal,created_at) VALUES(?,?,?,?,?,?)", (user["id"], name[:160], subject, data.get("event_date") or None, str(data.get("goal", ""))[:300], now()))
            item = row_dict(conn.execute("SELECT * FROM olympiads WHERE id=?", (cur.lastrowid,)).fetchone())
        self.json_response({"olympiad": item}, 201)

    def create_topic(self):
        user, data = self.user(), self.body()
        name, subject = str(data.get("name", "")).strip(), data.get("subject")
        if not name or subject not in ("Математика", "Информатика", "Искусственный интеллект"):
            raise ApiError(400, "Заполните название и предмет")
        color = data.get("color") if str(data.get("color", "")).startswith("#") else "#2563eb"
        with db() as conn:
            cur = conn.execute("INSERT INTO topics(user_id,name,subject,color,created_at) VALUES(?,?,?,?,?)", (user["id"], name[:120], subject, color[:7], now()))
            item = row_dict(conn.execute("SELECT * FROM topics WHERE id=?", (cur.lastrowid,)).fetchone())
        self.json_response({"topic": item}, 201)

    def create_note(self):
        user, data = self.user(), self.body()
        title, content = str(data.get("title", "")).strip(), str(data.get("content", "")).strip()
        try:
            topic_id = int(data.get("topic_id"))
        except (TypeError, ValueError):
            raise ApiError(400, "Выберите тему")
        if not title or not content:
            raise ApiError(400, "Заполните название и текст конспекта")
        with db() as conn:
            if not conn.execute("SELECT 1 FROM topics WHERE id=? AND user_id=?", (topic_id, user["id"])).fetchone():
                raise ApiError(400, "Выбрана недоступная тема")
            cur = conn.execute("INSERT INTO notes(user_id,topic_id,title,content,created_at) VALUES(?,?,?,?,?)", (user["id"], topic_id, title[:160], content[:20000], now()))
        self.json_response({"id": cur.lastrowid}, 201)

    def create_task(self):
        user, data = self.user(), self.body()
        title, difficulty = str(data.get("title", "")).strip(), data.get("difficulty", "Средне")
        if not title or difficulty not in ("Легко", "Средне", "Сложно"):
            raise ApiError(400, "Заполните название и сложность")
        topic_id = int(data["topic_id"]) if data.get("topic_id") else None
        olympiad_id = int(data["olympiad_id"]) if data.get("olympiad_id") else None
        try:
            planned_minutes = max(0, min(int(data.get("planned_minutes") or 0), 100000))
            problem_count = max(1, min(int(data.get("problem_count") or 1), 10000))
        except (TypeError, ValueError):
            raise ApiError(400, "Некорректное время или количество задач")
        image = data.get("condition_image") or None
        if image and (not isinstance(image, str) or not image.startswith("data:image/jpeg;base64,") or len(image) > 4_500_000):
            raise ApiError(400, "Фото должно быть в формате JPEG и не больше 3 МБ")
        with db() as conn:
            for table, item_id in (("topics", topic_id), ("olympiads", olympiad_id)):
                if item_id and not conn.execute(f"SELECT 1 FROM {table} WHERE id=? AND user_id=?", (item_id, user["id"])).fetchone():
                    raise ApiError(400, "Выбрана недоступная связь")
            cur = conn.execute("""INSERT INTO tasks(user_id,topic_id,olympiad_id,title,description,difficulty,status,due_date,created_at,planned_minutes,condition_text,condition_image,problem_count)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (user["id"], topic_id, olympiad_id, title[:200], str(data.get("description", ""))[:2000], difficulty, "planned", data.get("due_date") or None, now(), planned_minutes, str(data.get("condition_text", ""))[:10000], image, problem_count))
        self.json_response({"id": cur.lastrowid}, 201)

    def update_task(self, item_id):
        user, data = self.user(), self.body()
        allowed = {"planned", "in_progress", "solved"}
        status = data.get("status")
        if status not in allowed:
            raise ApiError(400, "Некорректный статус")
        try:
            spent = max(0, min(int(data.get("spent_minutes") or 0), 100000))
            solved_count = max(0, int(data.get("solved_count") or 0))
        except (TypeError, ValueError):
            raise ApiError(400, "Некорректное время или количество решенных задач")
        if status == "solved" and spent <= 0:
            raise ApiError(400, "Укажите время, потраченное на задачу")
        completed = now() if status == "solved" else None
        with db() as conn:
            task = conn.execute("SELECT problem_count FROM tasks WHERE id=? AND user_id=?", (item_id, user["id"])).fetchone()
            if not task:
                raise ApiError(404, "Задача не найдена")
            if solved_count > task["problem_count"]:
                raise ApiError(400, "Решенных задач не может быть больше общего количества")
            cur = conn.execute("UPDATE tasks SET status=?, completed_at=?, spent_minutes=?, solved_count=? WHERE id=? AND user_id=?", (status, completed, spent, solved_count, item_id, user["id"]))
        if not cur.rowcount:
            raise ApiError(404, "Задача не найдена")
        self.json_response({"ok": True})

    def delete_item(self, table, item_id):
        user = self.user()
        with db() as conn:
            cur = conn.execute(f"DELETE FROM {table} WHERE id=? AND user_id=?", (item_id, user["id"]))
        if not cur.rowcount:
            raise ApiError(404, "Запись не найдена")
        self.json_response({"ok": True})

    def dashboard(self):
        user = self.user()
        with db() as conn:
            counts = row_dict(conn.execute("""SELECT COUNT(*) total, SUM(status='solved') solved, SUM(status='in_progress') active,
                SUM(completed_at >= datetime('now','-30 days')) month_solved, SUM(spent_minutes) spent_minutes, SUM(solved_count) solved_problems FROM tasks WHERE user_id=?""", (user["id"],)).fetchone())
            upcoming = [row_dict(r) for r in conn.execute("SELECT * FROM olympiads WHERE user_id=? AND event_date>=date('now') ORDER BY event_date LIMIT 3", (user["id"],))]
            recent = [row_dict(r) for r in conn.execute("""SELECT t.*, p.name topic_name, p.color, p.subject FROM tasks t LEFT JOIN topics p ON p.id=t.topic_id
                WHERE t.user_id=? ORDER BY CASE t.status WHEN 'in_progress' THEN 0 WHEN 'planned' THEN 1 ELSE 2 END, t.created_at DESC LIMIT 5""", (user["id"],))]
        counts = {key: (value or 0) for key, value in counts.items()}
        self.json_response({"counts": counts, "upcoming": upcoming, "tasks": recent})

    def stats(self):
        user = self.user()
        with db() as conn:
            days = {r["day"]: r["count"] for r in conn.execute("""SELECT date(completed_at) day, COUNT(*) count FROM tasks
                WHERE user_id=? AND completed_at >= datetime('now','-29 days') GROUP BY date(completed_at)""", (user["id"],))}
            subjects = [row_dict(r) for r in conn.execute("""SELECT p.subject, COUNT(t.id) total, SUM(t.status='solved') solved FROM topics p
                LEFT JOIN tasks t ON t.topic_id=p.id WHERE p.user_id=? GROUP BY p.subject""", (user["id"],))]
            topics = [row_dict(r) for r in conn.execute("""SELECT p.name, p.color, COUNT(t.id) total, SUM(t.status='solved') solved, SUM(t.spent_minutes) spent_minutes FROM topics p
                LEFT JOIN tasks t ON t.topic_id=p.id WHERE p.user_id=? GROUP BY p.id ORDER BY solved DESC, total DESC LIMIT 6""", (user["id"],))]
            month_topics = [row_dict(r) for r in conn.execute("""SELECT p.name, p.color, SUM(t.spent_minutes) spent_minutes, SUM(t.solved_count) solved_count FROM topics p
                JOIN tasks t ON t.topic_id=p.id WHERE p.user_id=? AND t.completed_at >= datetime('now','-29 days')
                GROUP BY p.id HAVING spent_minutes > 0 ORDER BY spent_minutes DESC""", (user["id"],))]
            day_topics = [row_dict(r) for r in conn.execute("""SELECT p.name, p.color, SUM(t.spent_minutes) spent_minutes, SUM(t.solved_count) solved_count FROM topics p
                JOIN tasks t ON t.topic_id=p.id WHERE p.user_id=? AND date(t.completed_at)=date('now')
                GROUP BY p.id HAVING spent_minutes > 0 ORDER BY spent_minutes DESC""", (user["id"],))]
        series = []
        today = datetime.now(timezone.utc).date()
        for offset in range(29, -1, -1):
            day = today - timedelta(days=offset)
            series.append({"date": day.isoformat(), "count": days.get(day.isoformat(), 0)})
        month_minutes = sum(item["spent_minutes"] or 0 for item in month_topics)
        day_minutes = sum(item["spent_minutes"] or 0 for item in day_topics)
        month_solved = sum(item["solved_count"] or 0 for item in month_topics)
        day_solved = sum(item["solved_count"] or 0 for item in day_topics)
        with db() as conn:
            lifetime = row_dict(conn.execute("SELECT SUM(spent_minutes) spent_minutes, SUM(solved_count) solved_count FROM tasks WHERE user_id=?", (user["id"],)).fetchone())
        self.json_response({"series": series, "subjects": subjects, "topics": topics,
                            "month_topics": month_topics, "day_topics": day_topics,
                            "month_minutes": month_minutes, "day_minutes": day_minutes,
                            "month_solved": month_solved, "day_solved": day_solved,
                            "lifetime_minutes": lifetime["spent_minutes"] or 0,
                            "lifetime_solved": lifetime["solved_count"] or 0})

    def static(self, path):
        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (PUBLIC / relative).resolve()
        if PUBLIC.resolve() not in target.parents and target != PUBLIC.resolve():
            raise ApiError(403, "Доступ запрещен")
        if not target.is_file():
            target = PUBLIC / "index.html"
        content = target.read_bytes()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") or mime == "application/javascript" else mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    init_db()
    print(f"RYD запущен: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
