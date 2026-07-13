import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
from datetime import date as date_type, datetime, timedelta, timezone
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

STUDY_QUIZZES = {
    "foundation": [
        ("Сколько столбцов будет у произведения матриц размеров 3x4 и 4x2?", ("2",), "Произведение имеет размер 3x2."),
        ("Как называется максимальное число линейно независимых строк или столбцов матрицы?", ("ранг", "rank"), "Это ранг матрицы."),
        ("Какое предварительное преобразование данных обязательно перед PCA?", ("центрирование", "центрировать", "вычесть среднее"), "PCA применяют к центрированным данным."),
        ("Как называется точка, представляющая центр кластера в k-means?", ("центроид", "центр кластера"), "На шаге обновления k-means пересчитывает центроиды."),
        ("Какую норму обычно минимизирует k-means: L1 или квадрат L2?", ("l2", "квадрат l2", "евклидову", "евклидово расстояние"), "Функция потерь k-means основана на квадратах евклидовых расстояний."),
        ("Чему равен скалярный продукт ортогональных векторов?", ("0", "нулю"), "У перпендикулярных векторов скалярное произведение равно нулю."),
        ("Как называется вектор из частных производных функции?", ("градиент",), "Градиент указывает направление быстрейшего роста функции."),
        ("Куда направлен шаг градиентного спуска: по градиенту или против него?", ("против", "против градиента", "в минус градиент"), "Для минимизации двигаются в направлении минус градиента."),
        ("Что чаще всего происходит при слишком большом learning rate?", ("расходимость", "модель расходится", "перескакивание минимума"), "Шаги могут перескакивать минимум, и оптимизация расходится."),
        ("Как называется число lambda в равенстве Av = lambda*v?", ("собственное значение", "собственное число"), "Lambda является собственным значением матрицы A."),
    ],
    "validation": [
        ("Как называется попадание информации из test в обучение?", ("утечка", "утечка данных", "data leakage", "leakage"), "Это утечка данных, делающая оценку завышенной."),
        ("Какой split сохраняет доли классов?", ("stratified", "стратифицированный", "stratified split"), "Stratified split сохраняет пропорции классов."),
        ("Какой split нужен, если строки одного пользователя не должны попасть в разные выборки?", ("group", "group split", "групповой"), "Используют group split по идентификатору пользователя."),
        ("Какая метрика объединяет precision и recall гармоническим средним?", ("f1", "f1-score", "f1 score"), "Это F1-score."),
        ("Что предпочтительнее при сильном дисбалансе и редком положительном классе: ROC-AUC или PR-AUC?", ("pr-auc", "pr auc", "prauc"), "PR-AUC лучше отражает качество на редком положительном классе."),
        ("Как называется доля найденных положительных объектов среди всех реальных положительных?", ("recall", "полнота"), "Это recall, или полнота."),
        ("Как называется доля верных положительных прогнозов среди всех положительных прогнозов?", ("precision", "точность"), "Это precision."),
        ("Какую ошибку сильнее штрафует RMSE по сравнению с MAE?", ("большую", "большие ошибки", "выбросы"), "Из-за квадрата RMSE сильнее реагирует на крупные ошибки."),
        ("На какой выборке окончательно оценивают выбранную модель?", ("test", "тестовой", "тестовая"), "Test используют один раз для итоговой оценки."),
        ("Какой вид валидации нужен для данных, упорядоченных по времени?", ("time-series split", "time series split", "временной", "по времени"), "Будущее не должно попадать в обучение для прошлого."),
    ],
    "models": [
        ("Как называется простая модель, с которой сравнивают улучшения?", ("baseline", "бейслайн"), "Сначала фиксируют baseline."),
        ("Какой объект sklearn объединяет preprocessing и модель без утечки?", ("pipeline", "пайплайн"), "Pipeline применяет преобразования внутри каждого split."),
        ("Какой метод PyTorch вычисляет градиенты?", ("backward", "backward()"), "Обычно вызывают loss.backward()."),
        ("Какой метод оптимизатора обновляет веса?", ("step", "step()", "optimizer.step()"), "optimizer.step() применяет вычисленные градиенты."),
        ("Что нужно вызвать перед новым backward, чтобы очистить прошлые градиенты?", ("zero_grad", "zero_grad()", "optimizer.zero_grad()"), "В PyTorch градиенты накапливаются, поэтому их обнуляют."),
        ("Какой режим включает model.eval()?", ("оценки", "валидации", "инференса", "evaluation"), "eval переключает слои в режим оценки."),
        ("Как называется подбор параметров модели по validation?", ("подбор гиперпараметров", "тюнинг", "hyperparameter tuning"), "Параметры выбирают по validation, не по test."),
        ("Какая асимптотика у классического бинарного поиска?", ("o(log n)", "log n", "логарифмическая"), "На каждом шаге область поиска делится пополам."),
        ("Как называется сохранение промежуточных ответов в динамическом программировании?", ("мемоизация", "memoization"), "Мемоизация не позволяет пересчитывать одинаковые состояния."),
        ("Какой алгоритм обхода графа использует очередь: BFS или DFS?", ("bfs", "поиск в ширину"), "BFS обрабатывает вершины по слоям через очередь."),
    ],
    "nlp": [
        ("Как называется разбиение текста на элементы словаря модели?", ("токенизация", "tokenization"), "Токенизация преобразует текст в последовательность токенов."),
        ("Какая маска скрывает padding от attention?", ("attention mask", "attention_mask", "маска внимания"), "Attention mask отмечает реальные токены и padding."),
        ("Какая классическая модель признаков взвешивает слова по частоте в документе и корпусе?", ("tf-idf", "tfidf"), "TF-IDF является сильным текстовым baseline."),
        ("Как называется сходство, основанное на угле между эмбеддингами?", ("cosine similarity", "косинусное сходство", "косинусная близость"), "Cosine similarity сравнивает направления векторов."),
        ("Какие три матрицы используются в self-attention?", ("q k v", "q, k, v", "query key value", "query, key, value"), "Self-attention строится на Query, Key и Value."),
        ("Какой блок Transformer обычно двунаправленно кодирует вход: encoder или decoder?", ("encoder", "энкодер"), "Encoder видит контекст с обеих сторон без causal mask."),
        ("К какому типу моделей относится BERT: encoder или decoder?", ("encoder", "энкодер", "encoder-like"), "BERT является encoder-like моделью."),
        ("Как называется дообучение всех весов готовой модели?", ("fine-tuning", "fine tuning", "файнтюнинг"), "При fine-tuning обновляются веса предобученной модели."),
        ("Что делает causal mask в decoder?", ("скрывает будущие токены", "запрещает смотреть в будущее", "маскирует будущие токены"), "Токен не должен получать информацию из будущих позиций."),
        ("Какой слой переводит id токена в плотный вектор?", ("embedding", "эмбеддинг", "embedding layer"), "Embedding layer сопоставляет индексу обучаемый вектор."),
    ],
    "applied": [
        ("Как называется поиск ближайших документов по эмбеддингу запроса?", ("semantic search", "семантический поиск", "vector search", "векторный поиск"), "Это semantic/vector search."),
        ("Какая retrieval-метрика показывает, найден ли релевантный документ в первых k результатах?", ("recall@k", "recall at k"), "Recall@k измеряет полноту выдачи до позиции k."),
        ("Как называется повторная сортировка кандидатов более точной моделью?", ("reranking", "реранжирование"), "Reranker уточняет порядок документов после retrieval."),
        ("Как называется разбиение документа на фрагменты для RAG?", ("chunking", "чанкинг"), "Chunking определяет единицы индексирования и retrieval."),
        ("Как называется изменение распределения входных данных со временем?", ("data drift", "дрейф данных"), "Data drift нужно отслеживать после запуска модели."),
        ("Как называется компромисс между недообучением и переобучением?", ("bias-variance", "bias variance", "смещение-дисперсия"), "Это bias-variance trade-off."),
        ("Что должно быть зафиксировано для воспроизводимого случайного эксперимента?", ("seed", "random seed", "случайное зерно"), "Фиксированный seed помогает повторить split и обучение."),
        ("Как называется анализ примеров, на которых модель ошиблась?", ("error analysis", "анализ ошибок"), "Error analysis определяет направления следующих экспериментов."),
        ("Как называется самый простой рабочий вариант решения?", ("baseline", "бейслайн"), "Baseline показывает, дают ли сложные эксперименты улучшение."),
        ("Какой SQL-оператор вычисляет значение по условию?", ("case when", "case"), "CASE WHEN реализует условную логику в SQL."),
    ],
    "interview": [
        ("Как называется метрика, непосредственно связанная с целью продукта?", ("бизнес-метрика", "business metric"), "Техническую метрику выбирают с учетом бизнес-метрики."),
        ("Как называется запуск модели на группе объектов по расписанию?", ("batch inference", "batch", "пакетный инференс"), "Batch inference обрабатывает накопившуюся партию."),
        ("Как называется выдача прогноза сразу по запросу пользователя?", ("online inference", "online", "онлайн инференс"), "Online inference требует низкой задержки."),
        ("Какой файл обычно описывает запуск и устройство проекта на GitHub?", ("readme", "readme.md"), "README должен содержать постановку, запуск и результаты."),
        ("Как называется проверка кандидата на реальном бизнес-сценарии без готовой формулы?", ("ml case", "ml-case", "ml кейс"), "ML-case проверяет постановку задачи и выбор решения."),
        ("Что нельзя использовать для выбора лучшего эксперимента: validation или test?", ("test", "тест", "тестовую выборку"), "Иначе итоговая оценка становится смещенной."),
        ("Как называется наблюдение за качеством модели после запуска?", ("мониторинг", "monitoring"), "Мониторинг отслеживает качество, задержки и drift."),
        ("Как называется статистически значимое изменение распределения признаков?", ("data drift", "дрейф данных"), "Data drift может ухудшить модель даже без изменения кода."),
        ("Как называется ограниченная версия продукта для проверки гипотезы?", ("mvp", "minimum viable product"), "MVP позволяет проверить ценность до сложной реализации."),
        ("Что нужно назвать после результата проекта: только успехи или также ограничения?", ("ограничения", "также ограничения", "limitations"), "Честный рассказ включает ошибки и ограничения решения."),
    ],
}


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
            CREATE TABLE IF NOT EXISTS study_plan_progress (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                plan_date TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, plan_date)
            );
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
        plan_columns = {row["name"] for row in conn.execute("PRAGMA table_info(study_plan_progress)")}
        if "drills_completed" not in plan_columns:
            conn.execute("ALTER TABLE study_plan_progress ADD COLUMN drills_completed INTEGER NOT NULL DEFAULT 0")
            conn.execute("UPDATE study_plan_progress SET drills_completed=7 WHERE completed=1")
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
            if path == "/api/study-plan":
                return self.study_plan()
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
            if path == "/api/study-plan/check":
                return self.check_plan_answer()
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
            if len(parts) == 4 and parts[1:3] == ["api", "study-plan"]:
                return self.update_plan_day(parts[3])
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
        if "status" not in data:
            return self.edit_task(user, item_id, data)
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

    def edit_task(self, user, item_id, data):
        title, difficulty = str(data.get("title", "")).strip(), data.get("difficulty")
        if not title or difficulty not in ("Легко", "Средне", "Сложно"):
            raise ApiError(400, "Заполните название и сложность")
        try:
            topic_id = int(data["topic_id"]) if data.get("topic_id") else None
            olympiad_id = int(data["olympiad_id"]) if data.get("olympiad_id") else None
            planned_minutes = max(0, min(int(data.get("planned_minutes") or 0), 100000))
            problem_count = max(1, min(int(data.get("problem_count") or 1), 10000))
        except (TypeError, ValueError):
            raise ApiError(400, "Некорректные связи, время или количество задач")
        image = data.get("condition_image")
        if image and (not isinstance(image, str) or not image.startswith("data:image/jpeg;base64,") or len(image) > 4_500_000):
            raise ApiError(400, "Фото должно быть в формате JPEG и не больше 3 МБ")
        with db() as conn:
            current = conn.execute("SELECT solved_count, condition_image FROM tasks WHERE id=? AND user_id=?", (item_id, user["id"])).fetchone()
            if not current:
                raise ApiError(404, "Задача не найдена")
            if current["solved_count"] > problem_count:
                raise ApiError(400, "Общее количество не может быть меньше уже решенных задач")
            for table, linked_id in (("topics", topic_id), ("olympiads", olympiad_id)):
                if linked_id and not conn.execute(f"SELECT 1 FROM {table} WHERE id=? AND user_id=?", (linked_id, user["id"])).fetchone():
                    raise ApiError(400, "Выбрана недоступная связь")
            if "condition_image" not in data:
                image = current["condition_image"]
            conn.execute("""UPDATE tasks SET topic_id=?, olympiad_id=?, title=?, description=?, difficulty=?, due_date=?,
                planned_minutes=?, problem_count=?, condition_text=?, condition_image=? WHERE id=? AND user_id=?""",
                (topic_id, olympiad_id, title[:200], str(data.get("description", ""))[:2000], difficulty,
                 data.get("due_date") or None, planned_minutes, problem_count, str(data.get("condition_text", ""))[:10000],
                 image, item_id, user["id"]))
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

    def study_plan_item(self, day):
        weekday = day.weekday()
        if day <= date_type(2026, 7, 31):
            phase = "Темы 9–10 · математика и фундамент"
            tasks = [
                "Повторить линейную алгебру: матричное умножение, ранг и собственные векторы",
                "Практика: реализовать k-means или градиентный спуск через NumPy",
                "Закрыть текущий семинар и самостоятельно решить домашнюю работу",
                "Решить 5 коротких задач по линейной алгебре",
                "Алгоритмы: массивы, строки, словари и оценка сложности",
                "Мини-проект: масштабирование, PCA и k-means на небольшом датасете",
                "Недельный тест по темам 3–10 и разбор ошибок",
            ]
            drills = [
                ("Вычисли произведение двух матриц 2x2, найди ранг результата и проверь ответ в NumPy.", "Объясни, что означают линейная зависимость, ранг и собственный вектор.", "Можешь без конспекта связать собственные векторы с направлением главных компонент."),
                ("Реализуй один шаг k-means: расстояния, назначение кластеров и пересчет центров.", "Объясни, почему масштаб признаков и инициализация меняют результат k-means.", "Код не использует sklearn и совпадает с ним на простом наборе точек."),
                ("Повтори одно решение домашней работы с нуля и выпиши два места, где ошибся раньше.", "Расскажи решение самой сложной задачи так, будто отвечаешь преподавателю.", "Каждый переход обоснован, а не восстановлен по памяти из разбора."),
                ("Реши 5 задач: матричное умножение, транспонирование, ранг, базис и линейная зависимость.", "Объясни геометрический смысл скалярного произведения и нормы.", "Не менее 4 из 5 ответов верны без подсказок."),
                ("Реши две задачи на массивы или словари с ограничением 30 минут на каждую.", "Для каждого решения назови временную и пространственную сложность.", "Оба решения проходят граничные случаи: пустой ввод, один элемент и повторы."),
                ("Сделай scaling, PCA и k-means на одном датасете и построй график кластеров.", "Объясни, почему визуально красивые кластеры не обязательно полезны.", "Есть метрика качества, baseline и письменный вывод об ограничениях."),
                ("Ответь письменно на 10 вопросов по темам 3–10 без конспекта.", "За 5 минут объясни PCA, k-means и градиентный спуск.", "Минимум 8 из 10 ответов верны; ошибки добавлены в список повторения."),
            ]
        elif day <= date_type(2026, 8, 31):
            phase = "Темы 11–15 · EDA, метрики и валидация"
            tasks = [
                "Семинар текущего модуля и конспект на 1–2 страницы",
                "Домашняя работа без подсказок, затем выписать ошибки",
                "Практика EDA: пропуски, выбросы, распределения и корреляции",
                "Алгоритмы: 2 задачи без подсказок",
                "SQL: SELECT, WHERE, GROUP BY и JOIN",
                "Сравнить метрики на несбалансированных данных",
                "Повтор недели: leakage, train/validation/test и cross-validation",
            ]
            drills = [
                ("Сожми текущий семинар до пяти тезисов и одного примера на каждый тезис.", "Ответь на 5 вопросов по семинару без конспекта.", "Можешь назвать предположения метода, ограничения и подходящую метрику."),
                ("Перерешай одну задачу домашней работы другим способом.", "Объясни причину каждой ошибки из первой попытки.", "Повторное решение получено без просмотра разбора."),
                ("На незнакомом датасете найди пропуски, выбросы и подозрительные корреляции.", "Назови три источника утечки данных при EDA.", "Каждое наблюдение подтверждено таблицей или графиком, а не впечатлением."),
                ("Реши две задачи на строки, сортировки или хеш-таблицы за 60 минут.", "Докажи корректность ключевого шага одного решения.", "Решения проходят собственные граничные тесты."),
                ("Напиши запрос с JOIN, GROUP BY и HAVING на двух связанных таблицах.", "Объясни разницу WHERE и HAVING, INNER и LEFT JOIN.", "Результат проверен вручную на маленьком наборе данных."),
                ("Посчитай precision, recall, F1, ROC-AUC и PR-AUC для несбалансированного примера.", "Объясни, какую метрику выберешь при дорогом false negative.", "Выбор метрики связан с ценой ошибок и бизнес-задачей."),
                ("Для трех кейсов выбери split: stratified, group или time-series.", "Объясни, почему тест нельзя использовать для подбора гиперпараметров.", "Во всех кейсах указаны возможная утечка и честная схема валидации."),
            ]
        elif day <= date_type(2026, 10, 31):
            phase = "Темы 16–23 · алгоритмы, модели и нейросети"
            tasks = [
                "Семинар курса и карточки с ключевыми определениями",
                "Домашняя работа: сначала собственное решение, потом разбор",
                "Решить 2 алгоритмические задачи и оценить сложность",
                "SQL: CTE, подзапросы или оконные функции",
                "Практика ML: baseline, Pipeline и таблица экспериментов",
                "PyTorch: написать или улучшить training loop",
                "Повторить неделю и объяснить одну тему вслух за 5 минут",
            ]
            drills = [
                ("Составь 7 карточек по текущей теме: термин на одной стороне, смысл и пример на другой.", "Объясни тему без формул, затем добавь формальное определение.", "На все карточки отвечаешь без паузы дольше 20 секунд."),
                ("Воспроизведи ключевой алгоритм домашней работы на чистом листе.", "Назови альтернативный подход и сравни сложности.", "Решение проходит примеры и два собственных граничных теста."),
                ("Реши две задачи текущего алгоритмического блока с таймером.", "Обоснуй корректность и сложность лучшего решения.", "Нет скрытой квадратичной операции внутри цикла."),
                ("Реши SQL-задачу с CTE и оконной функцией.", "Объясни порядок выполнения частей SQL-запроса.", "Запрос корректно обрабатывает NULL и повторяющиеся строки."),
                ("Сравни baseline и настроенную модель в одном Pipeline.", "Объясни, какие параметры нельзя подбирать на test.", "Эксперимент воспроизводим: seed, split, метрика и параметры записаны."),
                ("Напиши forward, loss, backward и optimizer step без копирования.", "Объясни chain rule и назначение zero_grad.", "Loss уменьшается, shapes проверены, модель умеет перейти в eval mode."),
                ("Выбери слабую тему недели и ответь на 10 быстрых вопросов.", "Проведи пятиминутный рассказ с примером и ограничениями.", "Минимум 8 ответов верны без конспекта."),
            ]
        elif day <= date_type(2026, 12, 31):
            phase = "Темы 24–29 · NLP, attention и трансформеры"
            tasks = [
                "Семинар: токенизация, embeddings или self-attention",
                "Домашняя работа и повторная реализация через 2–3 дня",
                "Собрать TF-IDF baseline для текстовой классификации",
                "Решить 2 задачи по графам, динамике или оптимизации",
                "SQL-сессия: 3 задачи с агрегациями и JOIN",
                "Практика: сравнить baseline с нейросетевой моделью",
                "Устно объяснить Transformer, BERT и маски без конспекта",
            ]
            drills = [
                ("Токенизируй три предложения и проверь input_ids, padding и attention_mask.", "Объясни разницу токена, эмбеддинга и позиционного кодирования.", "Можешь предсказать shapes тензоров на каждом шаге."),
                ("Повтори ключевую реализацию модуля без просмотра исходного решения.", "Объясни, где в решении возможна утечка или переобучение.", "Результат воспроизводится на той же валидации."),
                ("Обучи TF-IDF + LogisticRegression и сохрани метрики как baseline.", "Объясни, почему такой baseline обязателен перед нейросетью.", "Есть F1, confusion matrix и пять разобранных ошибок."),
                ("Реши две задачи на графы, динамику или оптимизацию с оценкой сложности.", "Докажи корректность перехода или алгоритма обхода.", "Решения проходят граничные и случайные маленькие тесты."),
                ("Напиши SQL-запрос с двумя JOIN и агрегацией.", "Объясни, как JOIN может случайно размножить строки.", "Проверены количество строк до и после соединения."),
                ("Сравни baseline и нейросеть на одном split и одной метрике.", "Объясни три причины, почему сложная модель может проиграть baseline.", "Вывод опирается на метрики и анализ ошибок."),
                ("Нарисуй self-attention и подпиши Q, K, V, softmax и mask.", "Сравни encoder, decoder и BERT без конспекта.", "Можешь объяснить назначение каждого блока и размеры матриц."),
            ]
        elif day <= date_type(2027, 2, 28):
            phase = "Закрепление · классический ML, SQL и LLM"
            tasks = [
                "Повторить классический ML и ответить на 10 вопросов собеседования",
                "Решить 3 алгоритмические задачи",
                "SQL: оконные функции, даты и CASE WHEN",
                "Разобрать leakage, bias-variance и выбор метрики",
                "RAG: проверить retrieval на контрольном наборе вопросов",
                "Работа над главным проектом: эксперимент или анализ ошибок",
                "Недельный mock interview и список пробелов",
            ]
            drills = [
                ("Ответь на 10 случайных вопросов по классическому ML с таймером 90 секунд.", "Сравни линейную модель, дерево и boosting для одного кейса.", "В каждом ответе есть предположения, метрика и риск ошибки."),
                ("Реши три алгоритмические задачи: easy, medium и повтор слабой темы.", "Объясни решение medium до написания кода.", "Все задачи проходят тесты в пределах заявленной сложности."),
                ("Реши три SQL-задачи на окна, даты и CASE WHEN.", "Объясни PARTITION BY и отличие ROW_NUMBER от RANK.", "Запросы проверены на NULL, ties и границах дат."),
                ("Найди leakage в трех описаниях ML-пайплайна.", "Объясни bias-variance trade-off на примере.", "Для каждого кейса предложена честная валидация и метрика."),
                ("Сравни два chunking-подхода по Recall@k на контрольных вопросах.", "Объясни разницу retrieval, reranking и generation.", "Есть численная метрика и разбор минимум трех провалов."),
                ("Проведи один воспроизводимый эксперимент главного проекта.", "За 3 минуты расскажи baseline, split, метрику и результат.", "Эксперимент запускается по README и записан в таблицу."),
                ("Запиши mock interview и выпиши пять слабых ответов.", "Повтори слабые ответы без слов-паразитов и ухода от вопроса.", "Каждый новый ответ короче двух минут и содержит конкретный пример."),
            ]
        elif day <= date_type(2027, 4, 30):
            phase = "Собеседования · проект, ML-case и резюме"
            tasks = [
                "ML-интервью: метрики, валидация и вопросы по проекту",
                "Алгоритмическая задача с таймером 35 минут",
                "SQL-сессия из 3 задач",
                "ML-case: постановка задачи, baseline и бизнес-метрика",
                "Обновить README и воспроизводимый запуск проекта",
                "Mock interview: рассказ о себе и главном проекте",
                "Разобрать ошибки недели и повторить слабые темы",
            ]
            drills = [
                ("Пройди 15 вопросов по ML с ограничением 90 секунд на ответ.", "Объясни метрику, split и leakage своего проекта.", "Не менее 12 ответов полные и без подсказок."),
                ("Реши одну medium-задачу за 35 минут в чистом редакторе.", "Сначала проговори идею, доказательство и сложность.", "Код проходит примеры и собственные edge cases."),
                ("Реши три SQL-задачи подряд без документации.", "Объясни результат каждой промежуточной таблицы.", "Все запросы корректны для NULL и дубликатов."),
                ("Разбери ML-case от бизнес-цели до мониторинга модели.", "Защити выбор baseline, split и offline-метрики.", "Указаны ограничения, цена ошибок и план эксперимента."),
                ("Запусти проект строго по README в чистом окружении.", "Расскажи, что не сработало и почему.", "Команда запуска воспроизводима, секретов и абсолютных путей нет."),
                ("Проведи 45-минутное mock interview с записью.", "Ответь на уточняющие вопросы по проекту без презентации.", "После разбора сформулированы три конкретных улучшения."),
                ("Перерешай три ошибки недели без просмотра ответов.", "Объясни правильные решения простыми словами.", "Повторные ответы верны и занесены в карточки."),
            ]
        else:
            phase = "Финальная подготовка · симуляции отбора"
            tasks = [
                "Повторить классический ML и статистику",
                "Алгоритмическая задача в формате отбора",
                "SQL-сессия и проверка типичных ошибок",
                "PyTorch или NLP: 30 минут вопросов и практики",
                "Провести полный ML-case",
                "Повторить карточки по главному проекту",
                "Легкое повторение, сон и план следующей недели",
            ]
            drills = [
                ("Реши смешанный тест из 15 вопросов по ML и статистике.", "Объясни три самых слабых ответа повторно.", "Не менее 12 правильных ответов без конспекта."),
                ("Реши алгоритмическую задачу в полном формате отбора.", "Проговори решение до кода и оцени сложность.", "Уложился во время, код проходит edge cases."),
                ("Реши SQL-секцию с таймером и без документации.", "Объясни JOIN, окна и агрегации из решения.", "Нет ошибок на NULL, дубликатах и границах дат."),
                ("Воспроизведи training loop или NLP pipeline с нуля.", "Объясни shapes, loss, режимы train и eval.", "Код запускается, результат воспроизводим."),
                ("Проведи ML-case от постановки задачи до мониторинга.", "Защити метрики и схему валидации перед воображаемым интервьюером.", "Ответ учитывает бизнес-цену ошибок и data drift."),
                ("Расскажи о проекте за 5 минут, затем за 90 секунд.", "Ответь на пять неудобных вопросов об ограничениях.", "Рассказ конкретен: данные, baseline, эксперимент, результат."),
                ("Повтори только три слабые темы, не открывая новых.", "Кратко объясни каждую тему перед сном.", "Подготовка завершена вовремя, сохранен нормальный режим сна."),
            ]
        quiz_key = self.study_quiz_key(day)
        quiz_bank = STUDY_QUIZZES[quiz_key]
        quiz_start = day.toordinal() % len(quiz_bank)
        quiz_items = [quiz_bank[(quiz_start + offset) % len(quiz_bank)] for offset in range(3)]
        drill_names = ("Быстрый вопрос", "Проверка понимания", "Контрольный вопрос")
        return {"date": day.isoformat(), "phase": phase, "title": tasks[weekday], "weekday": weekday,
                "drills": [{"id": index, "name": drill_names[index], "text": item[0]}
                           for index, item in enumerate(quiz_items)]}

    def study_quiz_key(self, day):
        if day <= date_type(2026, 7, 31):
            return "foundation"
        if day <= date_type(2026, 8, 31):
            return "validation"
        if day <= date_type(2026, 10, 31):
            return "models"
        if day <= date_type(2026, 12, 31):
            return "nlp"
        if day <= date_type(2027, 2, 28):
            return "applied"
        return "interview"

    def check_plan_answer(self):
        user, data = self.user(), self.body()
        try:
            day = date_type.fromisoformat(str(data.get("date", "")))
            drill_id = int(data.get("drill_id"))
        except (TypeError, ValueError):
            raise ApiError(400, "Некорректный вопрос")
        today = datetime.now(timezone.utc).date()
        if day < today or day > date_type(2027, 6, 1) or drill_id not in range(3):
            raise ApiError(400, "Вопрос недоступен")
        answer = " ".join(str(data.get("answer", "")).strip().lower().replace("ё", "е").split())
        if not answer or len(answer) > 200:
            raise ApiError(400, "Введите короткий ответ")
        quiz_bank = STUDY_QUIZZES[self.study_quiz_key(day)]
        question = quiz_bank[(day.toordinal() % len(quiz_bank) + drill_id) % len(quiz_bank)]
        accepted = {" ".join(value.lower().replace("ё", "е").split()) for value in question[1]}
        correct = answer in accepted
        with db() as conn:
            saved = conn.execute("SELECT completed, drills_completed FROM study_plan_progress WHERE user_id=? AND plan_date=?",
                                 (user["id"], day.isoformat())).fetchone()
            completed = bool(saved["completed"]) if saved else False
            mask = saved["drills_completed"] if saved else 0
            if correct:
                mask |= 1 << drill_id
            conn.execute("""INSERT INTO study_plan_progress(user_id,plan_date,completed,drills_completed,updated_at)
                VALUES(?,?,?,?,?) ON CONFLICT(user_id,plan_date) DO UPDATE SET drills_completed=excluded.drills_completed,
                updated_at=excluded.updated_at""", (user["id"], day.isoformat(), int(completed), mask, now()))
        self.json_response({"correct": correct, "drills_completed": mask,
                            "explanation": question[2] if correct else "Ответ не совпал. Проверь термин или вычисление и попробуй еще раз."})

    def study_plan(self):
        user = self.user()
        start = datetime.now(timezone.utc).date()
        end = date_type(2027, 6, 1)
        with db() as conn:
            progress = {r["plan_date"]: r for r in conn.execute(
                "SELECT plan_date, completed, drills_completed FROM study_plan_progress WHERE user_id=?", (user["id"],))}
        days = []
        cursor = start
        while cursor <= end:
            item = self.study_plan_item(cursor)
            saved = progress.get(item["date"])
            item["completed"] = bool(saved["completed"]) if saved else False
            item["drills_completed"] = saved["drills_completed"] if saved else 0
            days.append(item)
            cursor += timedelta(days=1)
        self.json_response({"start": start.isoformat(), "end": end.isoformat(), "days": days,
                            "completed": sum(item["completed"] for item in days)})

    def update_plan_day(self, plan_date):
        user, data = self.user(), self.body()
        try:
            day = date_type.fromisoformat(plan_date)
        except ValueError:
            raise ApiError(400, "Некорректная дата")
        if day < datetime.now(timezone.utc).date() or day > date_type(2027, 6, 1):
            raise ApiError(400, "Дата вне периода подготовки")
        completed = bool(data.get("completed"))
        with db() as conn:
            saved = conn.execute("SELECT drills_completed FROM study_plan_progress WHERE user_id=? AND plan_date=?",
                                 (user["id"], plan_date)).fetchone()
            drills_completed = saved["drills_completed"] if saved else 0
            if completed and drills_completed != 7:
                raise ApiError(400, "Сначала правильно ответьте на все три вопроса")
            conn.execute("""INSERT INTO study_plan_progress(user_id,plan_date,completed,drills_completed,updated_at)
                VALUES(?,?,?,?,?) ON CONFLICT(user_id,plan_date) DO UPDATE SET completed=excluded.completed,
                drills_completed=excluded.drills_completed, updated_at=excluded.updated_at""",
                (user["id"], plan_date, int(completed), drills_completed, now()))
        self.json_response({"ok": True, "completed": completed, "drills_completed": drills_completed})

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
