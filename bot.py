"""
 THE OWEN BOT v3.2.0
 pip install vk_api pymysql
"""

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import sqlite3, threading, time, re, random, traceback, json, hashlib, os, logging
from datetime import datetime, timezone, timedelta

try:
    import pymysql
except ImportError:
    pymysql = None

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger("OWEN")

VK_TOKEN = os.environ.get("VK_TOKEN", "")
GROUP_ID = int(os.environ.get("VK_GROUP_ID", "237161820"))
GLOBAL_ADMINS = [1063123986, 1116397845]
SUPPORT_PEER = 2000000002
GADM_OWNER = 1063123986
GADM_DISABLED = set()
MSK = timezone(timedelta(hours=3))

if not VK_TOKEN:
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            cfg = json.load(f)
            VK_TOKEN = cfg.get("token", "")
            GROUP_ID = cfg.get("group_id", GROUP_ID)
            GLOBAL_ADMINS = cfg.get("global_admins", GLOBAL_ADMINS)
    else:
        logger.error("Токен не найден.")
        exit(1)


# ── CRMP / VK account binding integration ────────────────────────────────
# Эти параметры можно задать через env или config.json:
# "mysql": {"host":"127.0.0.1", "port":3306, "user":"root", "password":"", "database":"crmp"}
_cfg_all = {}
try:
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as _cf:
            _cfg_all = json.load(_cf)
except Exception:
    _cfg_all = {}
_mysql_cfg = _cfg_all.get("mysql", {}) if isinstance(_cfg_all.get("mysql", {}), dict) else {}

CRMP_DB_HOST = os.environ.get("MYSQL_HOST") or os.environ.get("DB_HOST") or _mysql_cfg.get("host", "")
CRMP_DB_PORT = int(os.environ.get("MYSQL_PORT") or os.environ.get("DB_PORT") or _mysql_cfg.get("port", 3306))
CRMP_DB_USER = os.environ.get("MYSQL_USER") or os.environ.get("DB_USER") or _mysql_cfg.get("user", "")
CRMP_DB_PASSWORD = os.environ.get("MYSQL_PASSWORD") or os.environ.get("DB_PASSWORD") or _mysql_cfg.get("password", "")
CRMP_DB_NAME = os.environ.get("MYSQL_DATABASE") or os.environ.get("DB_NAME") or _mysql_cfg.get("database", "")
CRMP_FLORIDA_ACCOUNTS_TABLE = os.environ.get("FLORIDA_ACCOUNTS_TABLE") or _cfg_all.get("florida_accounts_table", "accounts_1101")
CRMP_CODE_TTL_SECONDS = int(os.environ.get("CODE_TTL_SECONDS", _cfg_all.get("code_ttl_seconds", 600)))
CRMP_EVENT_POLL_INTERVAL = int(os.environ.get("EVENT_POLL_INTERVAL", _cfg_all.get("event_poll_interval", 5)))

CRMP_SERVERS = {
    "florida": {
        "key": "FLORIDA",
        "title": "FLORIDA",
        "accounts_table": CRMP_FLORIDA_ACCOUNTS_TABLE
    }
}

ALLOWED_SETTINGS = {
    "antispam","antimat","antilink","antiflood",
    "welcome_enabled","welcome_text","bye_enabled","bye_text",
    "slowmode","nightmode","night_start","night_end",
    "log_peer","captcha","max_warns","connected","support_mode",
    "chat_closed","log_chat"
}

CMD_DESCRIPTIONS = {
    "help":      ("0",    "📖 Список всех команд"),
    "yhelp":     ("0",    "✅ Ваши доступные команды"),
    "stats":     ("0",    "📊 Статистика пользователя"),
    "top":       ("0",    "🏆 Топ по сообщениям"),
    "roles":     ("0",    "📋 Список ролей чата"),
    "staff":     ("0",    "👥 Персонал чата"),
    "nick":      ("0",    "🏷 Ники пользователей"),
    "getinfo":   ("0",    "🔍 Наказания пользователя"),
    "notes":     ("50",   "📝 Заметки чата"),
    "delmsg":    ("50",   "🗑 Удалить сообщения бота"),
    "vig":       ("50",   "⚠️ Выдать выговор"),
    "unvig":     ("50",   "✅ Снять выговор"),
    "kick":      ("50",   "👢 Кикнуть пользователя"),
    "mute":      ("50",   "🔇 Замутить пользователя"),
    "unmute":    ("50",   "🔊 Размутить пользователя"),
    "list":      ("50",   "📋 Списки банов/мутов/чс/вигов"),
    "logchat":   ("50",   "📜 Лог действий игрока"),
    "leader":    ("80",   "🏢 Управление должностями"),
    "chat":      ("80",   "🚪 Открыть/закрыть чат"),
    "role":      ("80",   "🎭 Назначить роль"),
    "bl":        ("80",   "🚫 Добавить в чёрный список"),
    "unbl":      ("80",   "✅ Убрать из чёрного списка"),
    "ban":       ("60",   "🔨 Забанить пользователя"),
    "unban":     ("60",   "✅ Разбанить пользователя"),
    "newrole":   ("90",   "➕ Создать/изменить роль"),
    "delrole":   ("90",   "➖ Удалить роль"),
    "trusted":   ("90",   "🛡 Защита пользователя"),
    "gnick":     ("90",   "🌐 Глобальный ник"),
    "cmdname":   ("90",   "🔤 Алиасы команд"),
    "gban":      ("90",   "🌐🔨 Глобальный бан"),
    "gunban":    ("90",   "🌐✅ Глобальный разбан"),
    "gmute":     ("90",   "🌐🔇 Глобальный мут"),
    "gunmute":   ("90",   "🌐🔊 Глобальный размут"),
    "gkick":     ("90",   "🌐👢 Глобальный кик"),
    "gvig":      ("90",   "🌐⚠️ Глобальный выговор"),
    "gunvig":    ("90",   "🌐✅ Снять глобальный выговор"),
    "grole":     ("90",   "🌐🎭 Глобальная роль"),
    "cmd":       ("100",  "⚙️ Настройка прав команд"),
    "connect":   ("100",  "🔗 Пул чатов"),
    "import":    ("100",  "📥 Импорт настроек"),
    "logchat":   ("100",  "📜 Настройка лог-чата"),
    "start":     ("0",    "🎫 Создать тикет поддержки"),
    "msg":       ("1000", "📢 Рассылка во все чаты"),
    "listchat":  ("1000", "📋 Список всех чатов"),
    "vlads":     ("1000", "👑 Сменить владельца"),
    "renamrole": ("1000", "✏️ Переименовать роль 0/100"),
    "gcmdname":  ("1000", "🌐🔤 Глобальные алиасы"),
}

CMD_SUBCOMMANDS = {
    "nick":     ["set","remove","list"],
    "notes":    ["create","del","list"],
    "leader":   ["set","rem"],
    "trusted":  ["off"],
    "connect":  ["create","off"],
    "bl":       [],
    "unbl":     [],
    "list":     ["ban","mute","vig","bl"],
    "getinfo":  [],
    "cmdname":  ["list","del"],
    "gcmdname": ["list","del"],
    "logchat":  ["set","log"],
}

def is_ga_active(uid):
    return uid in GLOBAL_ADMINS and uid not in GADM_DISABLED

def fmt_msk(ts):
    dt = datetime.fromtimestamp(ts, tz=MSK)
    return dt.strftime("%d.%m.%Y %H:%M МСК")


class Database:
    def __init__(self, db_path="theowen.db"):
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._settings_cache = {}
        self._settings_cache_time = {}
        self._CACHE_TTL = 30
        self._create_tables()
        self._migrate_tables()

    def _create_tables(self):
        with self.lock:
            self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, role_name TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 1, emoji TEXT DEFAULT '',
                UNIQUE(peer_id, role_name), UNIQUE(peer_id, priority));

            CREATE TABLE IF NOT EXISTS user_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL, UNIQUE(peer_id, user_id),
                FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE);

            CREATE TABLE IF NOT EXISTS bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                banned_by INTEGER NOT NULL, reason TEXT DEFAULT '',
                ban_until REAL DEFAULT 0, created_at REAL DEFAULT 0,
                UNIQUE(peer_id, user_id));

            CREATE TABLE IF NOT EXISTS mutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                muted_by INTEGER NOT NULL, reason TEXT DEFAULT '',
                mute_until REAL DEFAULT 0, created_at REAL DEFAULT 0,
                UNIQUE(peer_id, user_id));

            CREATE TABLE IF NOT EXISTS cmd_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, command TEXT NOT NULL,
                min_priority INTEGER NOT NULL DEFAULT 100,
                UNIQUE(peer_id, command));

            CREATE TABLE IF NOT EXISTS chat_owners (
                peer_id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL);

            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, peer_id INTEGER NOT NULL,
                bl_type TEXT NOT NULL, added_by INTEGER NOT NULL,
                reason TEXT DEFAULT '', created_at REAL DEFAULT 0);

            CREATE TABLE IF NOT EXISTS viglist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                issued_by INTEGER NOT NULL, vig_type TEXT NOT NULL,
                reason TEXT DEFAULT '', created_at REAL DEFAULT 0);

            CREATE TABLE IF NOT EXISTS msg_count (
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                count INTEGER DEFAULT 0, PRIMARY KEY(peer_id, user_id));

            CREATE TABLE IF NOT EXISTS chat_members (
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                invited_by INTEGER DEFAULT 0, joined_at REAL DEFAULT 0,
                PRIMARY KEY(peer_id, user_id));

            CREATE TABLE IF NOT EXISTS chat_settings (
                peer_id INTEGER PRIMARY KEY,
                antispam INTEGER DEFAULT 0, antimat INTEGER DEFAULT 0,
                antilink INTEGER DEFAULT 0, antiflood INTEGER DEFAULT 0,
                welcome_enabled INTEGER DEFAULT 0, welcome_text TEXT DEFAULT '',
                bye_enabled INTEGER DEFAULT 0, bye_text TEXT DEFAULT '',
                slowmode INTEGER DEFAULT 0, nightmode INTEGER DEFAULT 0,
                night_start INTEGER DEFAULT 0, night_end INTEGER DEFAULT 8,
                log_peer INTEGER DEFAULT 0, captcha INTEGER DEFAULT 0,
                max_warns INTEGER DEFAULT 3, connected INTEGER DEFAULT 0,
                support_mode INTEGER DEFAULT 0, chat_closed INTEGER DEFAULT 0,
                log_chat INTEGER DEFAULT 0);

            CREATE TABLE IF NOT EXISTS chat_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pool_owner INTEGER NOT NULL, peer_id INTEGER NOT NULL,
                pool_name TEXT DEFAULT '', UNIQUE(peer_id));

            CREATE TABLE IF NOT EXISTS import_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE, peer_id INTEGER NOT NULL,
                created_at REAL DEFAULT 0);

            CREATE TABLE IF NOT EXISTS global_bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE, banned_by INTEGER NOT NULL,
                reason TEXT DEFAULT '', ban_until REAL DEFAULT 0,
                created_at REAL DEFAULT 0);

            CREATE TABLE IF NOT EXISTS global_mutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE, muted_by INTEGER NOT NULL,
                reason TEXT DEFAULT '', mute_until REAL DEFAULT 0,
                created_at REAL DEFAULT 0);

            CREATE TABLE IF NOT EXISTS global_vigs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, issued_by INTEGER NOT NULL,
                vig_type TEXT NOT NULL, reason TEXT DEFAULT '',
                created_at REAL DEFAULT 0);

            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, problem_text TEXT NOT NULL,
                problem_type TEXT NOT NULL, status TEXT DEFAULT 'open',
                created_at REAL DEFAULT 0, closed_at REAL DEFAULT 0,
                closed_by INTEGER DEFAULT 0);

            CREATE TABLE IF NOT EXISTS role_aliases (
                peer_id INTEGER NOT NULL, priority INTEGER NOT NULL,
                alias_name TEXT NOT NULL, alias_emoji TEXT DEFAULT '',
                PRIMARY KEY(peer_id, priority));

            CREATE TABLE IF NOT EXISTS chat_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, note_name TEXT NOT NULL,
                note_text TEXT DEFAULT '', attachments TEXT DEFAULT '',
                created_by INTEGER NOT NULL, created_at REAL DEFAULT 0,
                UNIQUE(peer_id, note_name));

            CREATE TABLE IF NOT EXISTS cmd_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, original_cmd TEXT NOT NULL,
                subcmd TEXT DEFAULT '', alias TEXT NOT NULL,
                UNIQUE(peer_id, alias));

            CREATE TABLE IF NOT EXISTS global_cmd_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_cmd TEXT NOT NULL, subcmd TEXT DEFAULT '',
                alias TEXT NOT NULL, UNIQUE(alias));

            CREATE TABLE IF NOT EXISTS nicknames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                nickname TEXT NOT NULL, UNIQUE(peer_id, user_id));

            CREATE TABLE IF NOT EXISTS global_nicknames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE, nickname TEXT NOT NULL);

            CREATE TABLE IF NOT EXISTS trusted_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                min_punish_priority INTEGER NOT NULL DEFAULT 100,
                set_by INTEGER NOT NULL, created_at REAL DEFAULT 0,
                UNIQUE(peer_id, user_id));

            CREATE TABLE IF NOT EXISTS leaders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                org_name TEXT NOT NULL, position TEXT NOT NULL,
                set_by INTEGER NOT NULL, created_at REAL DEFAULT 0,
                UNIQUE(peer_id, user_id));

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, actor_id INTEGER NOT NULL,
                target_id INTEGER, action TEXT NOT NULL,
                details TEXT DEFAULT '', created_at REAL DEFAULT 0);

            CREATE TABLE IF NOT EXISTS warns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                issued_by INTEGER NOT NULL, reason TEXT DEFAULT '',
                created_at REAL DEFAULT 0);
            """)
            self.conn.commit()

    def _migrate_tables(self):
        with self.lock:
            migrations = [
                "ALTER TABLE blacklist ADD COLUMN reason TEXT DEFAULT ''",
                "ALTER TABLE roles ADD COLUMN emoji TEXT DEFAULT ''",
                "ALTER TABLE chat_settings ADD COLUMN support_mode INTEGER DEFAULT 0",
                "ALTER TABLE chat_settings ADD COLUMN chat_closed INTEGER DEFAULT 0",
                "ALTER TABLE chat_pool ADD COLUMN pool_name TEXT DEFAULT ''",
                "ALTER TABLE cmd_aliases ADD COLUMN subcmd TEXT DEFAULT ''",
                "ALTER TABLE global_cmd_aliases ADD COLUMN subcmd TEXT DEFAULT ''",
                "ALTER TABLE chat_settings ADD COLUMN log_chat INTEGER DEFAULT 0",
            ]
            for sql in migrations:
                try:
                    self.cursor.execute(sql)
                    self.conn.commit()
                except sqlite3.OperationalError:
                    pass

    # ── кэш настроек ────────────────────────────────────────────────────────
    def _invalidate_settings_cache(self, peer_id):
        self._settings_cache.pop(peer_id, None)
        self._settings_cache_time.pop(peer_id, None)

    def get_settings(self, peer_id):
        now = time.time()
        if (peer_id in self._settings_cache and
                now - self._settings_cache_time.get(peer_id, 0) < self._CACHE_TTL):
            return self._settings_cache[peer_id]
        with self.lock:
            self.cursor.execute("SELECT * FROM chat_settings WHERE peer_id=?", (peer_id,))
            r = self.cursor.fetchone()
            if not r:
                self.cursor.execute("INSERT INTO chat_settings (peer_id) VALUES(?)", (peer_id,))
                self.conn.commit()
                self.cursor.execute("SELECT * FROM chat_settings WHERE peer_id=?", (peer_id,))
                r = self.cursor.fetchone()
            d = dict(r)
            self._settings_cache[peer_id] = d
            self._settings_cache_time[peer_id] = now
            return d

    def update_setting(self, peer_id, key, value):
        if key not in ALLOWED_SETTINGS:
            return
        with self.lock:
            self.cursor.execute("INSERT OR IGNORE INTO chat_settings (peer_id) VALUES(?)", (peer_id,))
            self.cursor.execute(f"UPDATE chat_settings SET {key}=? WHERE peer_id=?", (value, peer_id))
            self.conn.commit()
            self._invalidate_settings_cache(peer_id)

    # ── audit log ────────────────────────────────────────────────────────────
    def add_audit(self, peer_id, actor_id, target_id, action, details=""):
        with self.lock:
            self.cursor.execute(
                "INSERT INTO audit_log (peer_id,actor_id,target_id,action,details,created_at) VALUES(?,?,?,?,?,?)",
                (peer_id, actor_id, target_id, action, details, time.time()))
            self.conn.commit()

    def get_audit_for_target(self, peer_id, target_id, limit=10, offset=0):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM audit_log WHERE peer_id=? AND target_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (peer_id, target_id, limit, offset))
            return [dict(r) for r in self.cursor.fetchall()]

    def get_audit_count(self, peer_id, target_id):
        with self.lock:
            self.cursor.execute(
                "SELECT COUNT(*) as c FROM audit_log WHERE peer_id=? AND target_id=?",
                (peer_id, target_id))
            r = self.cursor.fetchone()
            return r["c"] if r else 0

    # ── warns ────────────────────────────────────────────────────────────────
    def add_warn(self, peer_id, user_id, issued_by, reason):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "INSERT INTO warns (peer_id,user_id,issued_by,reason,created_at) VALUES(?,?,?,?,?)",
                (peer_id, user_id, issued_by, reason, time.time()))
            self.conn.commit()
            return True

    def get_warns(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM warns WHERE peer_id=? AND user_id=? ORDER BY created_at DESC",
                (peer_id, user_id))
            return [dict(r) for r in self.cursor.fetchall()]

    def remove_warns(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM warns WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def remove_warn_by_id(self, warn_id):
        with self.lock:
            self.cursor.execute("DELETE FROM warns WHERE id=?", (warn_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def count_warns(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT COUNT(*) as c FROM warns WHERE peer_id=? AND user_id=?",
                (peer_id, user_id))
            r = self.cursor.fetchone()
            return r["c"] if r else 0

    # ── лидеры ──────────────────────────────────────────────────────────────
    def set_leader(self, peer_id, user_id, org_name, position, set_by):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO leaders (peer_id,user_id,org_name,position,set_by,created_at) VALUES(?,?,?,?,?,?)",
                (peer_id, user_id, org_name, position, set_by, time.time()))
            self.conn.commit()

    def remove_leader(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM leaders WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_leader(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM leaders WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_leader_list(self, peer_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM leaders WHERE peer_id=? ORDER BY org_name", (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    # ── trusted ─────────────────────────────────────────────────────────────
    def set_trusted(self, peer_id, user_id, min_punish_priority, set_by):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO trusted_users (peer_id,user_id,min_punish_priority,set_by,created_at) VALUES(?,?,?,?,?)",
                (peer_id, user_id, min_punish_priority, set_by, time.time()))
            self.conn.commit()

    def remove_trusted(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM trusted_users WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_trusted(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM trusted_users WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_trusted_list(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM trusted_users WHERE peer_id=? ORDER BY min_punish_priority DESC", (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    # ── владельцы ───────────────────────────────────────────────────────────
    def set_chat_owner(self, peer_id, owner_id):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO chat_owners (peer_id,owner_id) VALUES(?,?)", (peer_id, owner_id))
            self.conn.commit()

    def get_chat_owner(self, peer_id):
        with self.lock:
            self.cursor.execute("SELECT owner_id FROM chat_owners WHERE peer_id=?", (peer_id,))
            r = self.cursor.fetchone()
            return r["owner_id"] if r else None

    def _get_chat_owner_nolock(self, peer_id):
        self.cursor.execute("SELECT owner_id FROM chat_owners WHERE peer_id=?", (peer_id,))
        r = self.cursor.fetchone()
        return r["owner_id"] if r else None

    # ── роли ────────────────────────────────────────────────────────────────
    def create_or_update_role(self, peer_id, role_name, priority, emoji=""):
        """Создаёт или обновляет роль с приоритетом 0-100"""
        with self.lock:
            self.cursor.execute(
                "SELECT id FROM roles WHERE peer_id=? AND priority=?", (peer_id, priority))
            r = self.cursor.fetchone()
            if r:
                try:
                    self.cursor.execute(
                        "UPDATE roles SET role_name=?,emoji=? WHERE peer_id=? AND priority=?",
                        (role_name, emoji, peer_id, priority))
                    self.conn.commit()
                    return True, "updated"
                except sqlite3.IntegrityError:
                    return False, "Роль с таким именем уже существует."
            else:
                try:
                    self.cursor.execute(
                        "INSERT INTO roles (peer_id,role_name,priority,emoji) VALUES(?,?,?,?)",
                        (peer_id, role_name, priority, emoji))
                    self.conn.commit()
                    return True, "created"
                except sqlite3.IntegrityError:
                    return False, "Роль с таким именем или приоритетом уже существует."

    def delete_role(self, peer_id, priority):
        with self.lock:
            self.cursor.execute(
                "SELECT id FROM roles WHERE peer_id=? AND priority=?", (peer_id, priority))
            r = self.cursor.fetchone()
            if not r:
                return False, "Роль не найдена."
            self.cursor.execute("DELETE FROM user_roles WHERE role_id=?", (r["id"],))
            self.cursor.execute("DELETE FROM roles WHERE id=?", (r["id"],))
            self.conn.commit()
            return True, "OK"

    def get_roles(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM roles WHERE peer_id=? ORDER BY priority DESC", (peer_id,))
            return self.cursor.fetchall()

    def get_role_by_priority(self, peer_id, priority):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM roles WHERE peer_id=? AND priority=?", (peer_id, priority))
            return self.cursor.fetchone()

    def assign_role(self, peer_id, user_id, priority):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM roles WHERE peer_id=? AND priority=?", (peer_id, priority))
            r = self.cursor.fetchone()
            if not r:
                return False, "Роль не существует."
            self.cursor.execute(
                "INSERT OR REPLACE INTO user_roles (peer_id,user_id,role_id) VALUES(?,?,?)",
                (peer_id, user_id, r["id"]))
            self.conn.commit()
            return True, dict(r)

    def remove_role(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM user_roles WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            if self.cursor.rowcount == 0:
                return False, "У пользователя нет роли."
            self.conn.commit()
            return True, "OK"

    def get_user_role(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT r.role_name,r.priority,r.emoji FROM user_roles ur "
                "JOIN roles r ON ur.role_id=r.id WHERE ur.peer_id=? AND ur.user_id=?",
                (peer_id, user_id))
            row = self.cursor.fetchone()
            return dict(row) if row else None

    def get_chat_staff(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT ur.user_id,r.role_name,r.priority,r.emoji FROM user_roles ur "
                "JOIN roles r ON ur.role_id=r.id WHERE ur.peer_id=? ORDER BY r.priority DESC",
                (peer_id,))
            return [dict(row) for row in self.cursor.fetchall()]

    def get_user_priority(self, peer_id, user_id):
        with self.lock:
            if is_ga_active(user_id):
                return 1000
            o = self._get_chat_owner_nolock(peer_id)
            if o and o == user_id:
                return 100
            self.cursor.execute(
                "SELECT r.priority FROM user_roles ur JOIN roles r ON ur.role_id=r.id "
                "WHERE ur.peer_id=? AND ur.user_id=?", (peer_id, user_id))
            r = self.cursor.fetchone()
            return r["priority"] if r else 0

    def get_user_priority_pool(self, peer_id, user_id):
        with self.lock:
            if is_ga_active(user_id):
                return 1000
            o = self._get_chat_owner_nolock(peer_id)
            if o and o == user_id:
                return 100
            self.cursor.execute(
                "SELECT r.priority FROM user_roles ur JOIN roles r ON ur.role_id=r.id "
                "WHERE ur.peer_id=? AND ur.user_id=?", (peer_id, user_id))
            r = self.cursor.fetchone()
            p = r["priority"] if r else 0
            self.cursor.execute("SELECT pool_owner FROM chat_pool WHERE peer_id=?", (peer_id,))
            pool_row = self.cursor.fetchone()
            if pool_row:
                owner = pool_row["pool_owner"]
                self.cursor.execute("SELECT peer_id FROM chat_pool WHERE pool_owner=?", (owner,))
                peers = [x["peer_id"] for x in self.cursor.fetchall()]
                peers.append(owner)
            else:
                self.cursor.execute("SELECT peer_id FROM chat_pool WHERE pool_owner=?", (peer_id,))
                pp = self.cursor.fetchall()
                peers = [x["peer_id"] for x in pp] + [peer_id] if pp else []
            for pp in peers:
                if pp != peer_id:
                    self.cursor.execute(
                        "SELECT r.priority FROM user_roles ur JOIN roles r ON ur.role_id=r.id "
                        "WHERE ur.peer_id=? AND ur.user_id=?", (pp, user_id))
                    rr = self.cursor.fetchone()
                    if rr and rr["priority"] > p:
                        p = rr["priority"]
            return p

    # ── баны ────────────────────────────────────────────────────────────────
    def ban_user(self, peer_id, user_id, banned_by, reason, duration):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            bu = 0 if duration == 0 else time.time() + duration
            self.cursor.execute(
                "INSERT OR REPLACE INTO bans (peer_id,user_id,banned_by,reason,ban_until,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (peer_id, user_id, banned_by, reason, bu, time.time()))
            self.conn.commit()
            return True

    def unban_user(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM bans WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def is_banned(self, peer_id, user_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "SELECT * FROM bans WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.fetchone()
            if not r:
                return False
            if r["ban_until"] == 0:
                return True
            if time.time() > r["ban_until"]:
                self.cursor.execute("DELETE FROM bans WHERE id=?", (r["id"],))
                self.conn.commit()
                return False
            return True

    def get_ban_info(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM bans WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_all_bans(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM bans WHERE peer_id=? ORDER BY created_at DESC", (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    def get_expired_bans(self):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM bans WHERE ban_until > 0 AND ban_until <= ?", (time.time(),))
            return [dict(r) for r in self.cursor.fetchall()]

    # ── муты ────────────────────────────────────────────────────────────────
    def mute_user(self, peer_id, user_id, muted_by, reason, duration):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            mu = 0 if duration == 0 else time.time() + duration
            self.cursor.execute(
                "INSERT OR REPLACE INTO mutes (peer_id,user_id,muted_by,reason,mute_until,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (peer_id, user_id, muted_by, reason, mu, time.time()))
            self.conn.commit()
            return True

    def unmute_user(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM mutes WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def is_muted(self, peer_id, user_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "SELECT * FROM mutes WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.fetchone()
            if not r:
                return False
            if r["mute_until"] == 0:
                return True
            if time.time() > r["mute_until"]:
                self.cursor.execute("DELETE FROM mutes WHERE id=?", (r["id"],))
                self.conn.commit()
                return False
            return True

    def get_mute_info(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM mutes WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_all_mutes(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM mutes WHERE peer_id=? ORDER BY created_at DESC", (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    def get_expired_mutes(self):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM mutes WHERE mute_until > 0 AND mute_until <= ?", (time.time(),))
            return [dict(r) for r in self.cursor.fetchall()]

    # ── права команд ────────────────────────────────────────────────────────
    def set_cmd_permission(self, peer_id, command, min_priority):
        with self.lock:
            self.cursor.execute(
                "INSERT OR IGNORE INTO chat_settings (peer_id) VALUES(?)", (peer_id,))
            self.cursor.execute(
                "INSERT OR REPLACE INTO cmd_permissions (peer_id,command,min_priority) VALUES(?,?,?)",
                (peer_id, command, min_priority))
            self.conn.commit()

    def get_cmd_permission(self, peer_id, command):
        with self.lock:
            self.cursor.execute(
                "SELECT min_priority FROM cmd_permissions WHERE peer_id=? AND command=?",
                (peer_id, command))
            r = self.cursor.fetchone()
            return r["min_priority"] if r else None

    def get_all_cmd_permissions(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT command,min_priority FROM cmd_permissions WHERE peer_id=? ORDER BY command",
                (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    # ── чёрный список ───────────────────────────────────────────────────────
    def add_to_blacklist(self, user_id, peer_id, bl_type, added_by, reason):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "INSERT INTO blacklist (user_id,peer_id,bl_type,added_by,reason,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (user_id, peer_id, bl_type, added_by, reason, time.time()))
            self.conn.commit()
            return True

    def remove_from_blacklist(self, user_id, peer_id, bl_type=None):
        with self.lock:
            if bl_type:
                self.cursor.execute(
                    "DELETE FROM blacklist WHERE user_id=? AND peer_id=? AND bl_type=?",
                    (user_id, peer_id, bl_type))
            else:
                self.cursor.execute(
                    "DELETE FROM blacklist WHERE user_id=? AND peer_id=?", (user_id, peer_id))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def remove_from_blacklist_global(self, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM blacklist WHERE user_id=?", (user_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def is_blacklisted_in_chat(self, user_id, peer_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return []
            self.cursor.execute(
                "SELECT * FROM blacklist WHERE user_id=? AND "
                "(peer_id=? OR bl_type IN ('full_project','full_strict'))",
                (user_id, peer_id))
            return [dict(r) for r in self.cursor.fetchall()]

    def get_user_blacklist_entries(self, user_id, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM blacklist WHERE user_id=? AND "
                "(peer_id=? OR bl_type IN ('full_project','full_strict'))",
                (user_id, peer_id))
            return [dict(r) for r in self.cursor.fetchall()]

    def get_all_blacklist(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM blacklist WHERE peer_id=? OR "
                "bl_type IN ('full_project','full_strict') ORDER BY created_at DESC",
                (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    def get_all_chat_peers(self):
        with self.lock:
            self.cursor.execute("SELECT peer_id FROM chat_owners")
            return [r["peer_id"] for r in self.cursor.fetchall()]

    def get_pool_peers_for(self, peer_id):
        """Получить список peer_id в том же пуле что и peer_id"""
        with self.lock:
            self.cursor.execute("SELECT pool_owner FROM chat_pool WHERE peer_id=?", (peer_id,))
            r = self.cursor.fetchone()
            if r:
                owner = r["pool_owner"]
                self.cursor.execute(
                    "SELECT peer_id FROM chat_pool WHERE pool_owner=?", (owner,))
                peers = [x["peer_id"] for x in self.cursor.fetchall()]
                if owner not in peers:
                    peers.append(owner)
                return peers
            # может сам является владельцем пула
            self.cursor.execute(
                "SELECT peer_id FROM chat_pool WHERE pool_owner=?", (peer_id,))
            pp = self.cursor.fetchall()
            if pp:
                peers = [x["peer_id"] for x in pp]
                peers.append(peer_id)
                return peers
            return [peer_id]

    # ── выговоры ────────────────────────────────────────────────────────────
    def add_vig(self, peer_id, user_id, issued_by, vig_type, reason):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "INSERT INTO viglist (peer_id,user_id,issued_by,vig_type,reason,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (peer_id, user_id, issued_by, vig_type, reason, time.time()))
            self.conn.commit()
            return True

    def remove_vig_by_id(self, vig_id):
        with self.lock:
            self.cursor.execute("DELETE FROM viglist WHERE id=?", (vig_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def remove_vigs(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM viglist WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_vigs(self, peer_id, user_id=None):
        with self.lock:
            if user_id:
                self.cursor.execute(
                    "SELECT * FROM viglist WHERE peer_id=? AND user_id=? ORDER BY created_at DESC",
                    (peer_id, user_id))
            else:
                self.cursor.execute(
                    "SELECT * FROM viglist WHERE peer_id=? ORDER BY created_at DESC", (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    def get_vig_by_id(self, vig_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM viglist WHERE id=?", (vig_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def count_vigs_by_type(self, peer_id, user_id, vig_type):
        with self.lock:
            self.cursor.execute(
                "SELECT COUNT(*) as c FROM viglist WHERE peer_id=? AND user_id=? AND vig_type=?",
                (peer_id, user_id, vig_type))
            r = self.cursor.fetchone()
            return r["c"] if r else 0

    def get_vig_issuer_max_priority(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT issued_by FROM viglist WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            rows = self.cursor.fetchall()
            if not rows:
                return 0
            mx = 0
            for row in rows:
                iid = row["issued_by"]
                if iid in GLOBAL_ADMINS:
                    return 1000
                o = self._get_chat_owner_nolock(peer_id)
                if o and o == iid:
                    p = 100
                else:
                    self.cursor.execute(
                        "SELECT r.priority FROM user_roles ur JOIN roles r ON ur.role_id=r.id "
                        "WHERE ur.peer_id=? AND ur.user_id=?", (peer_id, iid))
                    rr = self.cursor.fetchone()
                    p = rr["priority"] if rr else 0
                if p > mx:
                    mx = p
            return mx

    # ── счётчик сообщений ───────────────────────────────────────────────────
    def increment_msg(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "INSERT INTO msg_count (peer_id,user_id,count) VALUES(?,?,1) "
                "ON CONFLICT(peer_id,user_id) DO UPDATE SET count=count+1",
                (peer_id, user_id))
            self.conn.commit()

    def get_msg_count(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT count FROM msg_count WHERE peer_id=? AND user_id=?",
                (peer_id, user_id))
            r = self.cursor.fetchone()
            return r["count"] if r else 0

    def get_top_msg(self, peer_id, limit=10):
        with self.lock:
            self.cursor.execute(
                "SELECT user_id,count FROM msg_count WHERE peer_id=? ORDER BY count DESC LIMIT ?",
                (peer_id, limit))
            return [dict(r) for r in self.cursor.fetchall()]

    # ── участники / кто добавил ─────────────────────────────────────────────
    def remember_member(self, peer_id, user_id, invited_by=0):
        """Запоминает, кто добавил пользователя в чат. Не затирает старого пригласившего без причины."""
        if not user_id or user_id <= 0:
            return
        with self.lock:
            self.cursor.execute(
                "SELECT invited_by FROM chat_members WHERE peer_id=? AND user_id=?",
                (peer_id, user_id))
            r = self.cursor.fetchone()
            if r:
                if invited_by and not r["invited_by"]:
                    self.cursor.execute(
                        "UPDATE chat_members SET invited_by=? WHERE peer_id=? AND user_id=?",
                        (invited_by, peer_id, user_id))
                    self.conn.commit()
                return
            self.cursor.execute(
                "INSERT OR REPLACE INTO chat_members (peer_id,user_id,invited_by,joined_at) VALUES(?,?,?,?)",
                (peer_id, user_id, invited_by or 0, time.time()))
            self.conn.commit()

    def get_member_info(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM chat_members WHERE peer_id=? AND user_id=?",
                (peer_id, user_id))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    # ── пул чатов ───────────────────────────────────────────────────────────
    def connect_to_pool(self, peer_id, owner_peer, pool_name=""):
        with self.lock:
            try:
                self.cursor.execute(
                    "INSERT OR REPLACE INTO chat_pool (pool_owner,peer_id,pool_name) VALUES(?,?,?)",
                    (owner_peer, peer_id, pool_name))
                self.conn.commit()
                return True
            except Exception:
                return False

    def disconnect_from_pool(self, peer_id):
        with self.lock:
            self.cursor.execute("DELETE FROM chat_pool WHERE peer_id=?", (peer_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0

    def get_pool_peers(self, peer_id):
        with self.lock:
            self.cursor.execute("SELECT pool_owner FROM chat_pool WHERE peer_id=?", (peer_id,))
            r = self.cursor.fetchone()
            if not r:
                self.cursor.execute(
                    "SELECT peer_id FROM chat_pool WHERE pool_owner=?", (peer_id,))
                peers = [x["peer_id"] for x in self.cursor.fetchall()]
                return peers + [peer_id] if peers else [peer_id]
            owner = r["pool_owner"]
            self.cursor.execute("SELECT peer_id FROM chat_pool WHERE pool_owner=?", (owner,))
            peers = [x["peer_id"] for x in self.cursor.fetchall()]
            if owner not in peers:
                peers.append(owner)
            return peers

    def get_pool_name(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT pool_name FROM chat_pool WHERE peer_id=? OR pool_owner=? LIMIT 1",
                (peer_id, peer_id))
            r = self.cursor.fetchone()
            return r["pool_name"] if r else ""

    def is_connected(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM chat_pool WHERE peer_id=? OR pool_owner=?", (peer_id, peer_id))
            return self.cursor.fetchone() is not None

    # ── импорт ──────────────────────────────────────────────────────────────
    def create_import_code(self, peer_id):
        with self.lock:
            code = hashlib.md5(
                f"{peer_id}{time.time()}{random.randint(0,999999)}".encode()
            ).hexdigest()[:12].upper()
            self.cursor.execute("DELETE FROM import_codes WHERE peer_id=?", (peer_id,))
            self.cursor.execute(
                "INSERT INTO import_codes (code,peer_id,created_at) VALUES(?,?,?)",
                (code, peer_id, time.time()))
            self.conn.commit()
            return code

    def get_import_source(self, code):
        with self.lock:
            self.cursor.execute("SELECT * FROM import_codes WHERE code=?", (code,))
            r = self.cursor.fetchone()
            if not r:
                return None
            if time.time() - r["created_at"] > 600:
                self.cursor.execute("DELETE FROM import_codes WHERE code=?", (code,))
                self.conn.commit()
                return None
            return r["peer_id"]

    def import_settings(self, from_peer, to_peer):
        with self.lock:
            self.cursor.execute("SELECT * FROM chat_settings WHERE peer_id=?", (from_peer,))
            s = self.cursor.fetchone()
            if not s:
                return False
            sd = dict(s)
            del sd["peer_id"]
            safe_sd = {k: v for k, v in sd.items() if k in ALLOWED_SETTINGS}
            if not safe_sd:
                return False
            keys = ",".join(safe_sd.keys())
            ph = ",".join(["?" for _ in safe_sd])
            vals = list(safe_sd.values())
            self.cursor.execute(
                f"INSERT OR REPLACE INTO chat_settings (peer_id,{keys}) VALUES(?,{ph})",
                [to_peer] + vals)
            self.cursor.execute("DELETE FROM roles WHERE peer_id=?", (to_peer,))
            self.cursor.execute("SELECT * FROM roles WHERE peer_id=?", (from_peer,))
            for role in self.cursor.fetchall():
                rd = dict(role)
                try:
                    self.cursor.execute(
                        "INSERT INTO roles (peer_id,role_name,priority,emoji) VALUES(?,?,?,?)",
                        (to_peer, rd["role_name"], rd["priority"], rd.get("emoji", "")))
                except sqlite3.IntegrityError:
                    pass
            self.cursor.execute("DELETE FROM cmd_permissions WHERE peer_id=?", (to_peer,))
            self.cursor.execute("SELECT * FROM cmd_permissions WHERE peer_id=?", (from_peer,))
            for cp in self.cursor.fetchall():
                cpd = dict(cp)
                self.cursor.execute(
                    "INSERT INTO cmd_permissions (peer_id,command,min_priority) VALUES(?,?,?)",
                    (to_peer, cpd["command"], cpd["min_priority"]))
            self.conn.commit()
            self._invalidate_settings_cache(to_peer)
            return True

    # ── алиасы ролей ────────────────────────────────────────────────────────
    def set_role_alias(self, peer_id, priority, alias_name, alias_emoji=""):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO role_aliases (peer_id,priority,alias_name,alias_emoji) "
                "VALUES(?,?,?,?)",
                (peer_id, priority, alias_name, alias_emoji))
            self.conn.commit()

    def get_role_alias(self, peer_id, priority):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM role_aliases WHERE peer_id=? AND priority=?", (peer_id, priority))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    # ── заметки ─────────────────────────────────────────────────────────────
    def create_note(self, peer_id, note_name, note_text, attachments, created_by):
        with self.lock:
            try:
                self.cursor.execute(
                    "INSERT INTO chat_notes (peer_id,note_name,note_text,attachments,created_by,created_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (peer_id, note_name.lower().strip(), note_text, attachments,
                     created_by, time.time()))
                self.conn.commit()
                return True, "OK"
            except sqlite3.IntegrityError:
                return False, "Заметка с таким названием уже существует."

    def update_note(self, peer_id, note_name, note_text, attachments, created_by):
        with self.lock:
            self.cursor.execute(
                "UPDATE chat_notes SET note_text=?,attachments=?,created_by=?,created_at=? "
                "WHERE peer_id=? AND note_name=?",
                (note_text, attachments, created_by, time.time(),
                 peer_id, note_name.lower().strip()))
            if self.cursor.rowcount == 0:
                return False, "Заметка не найдена."
            self.conn.commit()
            return True, "OK"

    def delete_note(self, peer_id, note_name):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM chat_notes WHERE peer_id=? AND note_name=?",
                (peer_id, note_name.lower().strip()))
            if self.cursor.rowcount == 0:
                return False, "Заметка не найдена."
            self.conn.commit()
            return True, "OK"

    def get_note(self, peer_id, note_name):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM chat_notes WHERE peer_id=? AND note_name=?",
                (peer_id, note_name.lower().strip()))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_all_notes(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM chat_notes WHERE peer_id=? ORDER BY note_name", (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    # ── алиасы команд ───────────────────────────────────────────────────────
    def add_cmd_alias(self, peer_id, original_cmd, subcmd, alias):
        with self.lock:
            try:
                self.cursor.execute(
                    "INSERT OR REPLACE INTO cmd_aliases (peer_id,original_cmd,subcmd,alias) "
                    "VALUES(?,?,?,?)",
                    (peer_id, original_cmd.lower(), subcmd.lower(), alias.lower()))
                self.conn.commit()
                return True
            except Exception:
                return False

    def remove_cmd_alias(self, peer_id, alias):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM cmd_aliases WHERE peer_id=? AND alias=?", (peer_id, alias.lower()))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_cmd_aliases(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM cmd_aliases WHERE peer_id=? ORDER BY original_cmd", (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    def resolve_alias(self, peer_id, text):
        with self.lock:
            tl = text.lower().strip()
            self.cursor.execute(
                "SELECT * FROM global_cmd_aliases ORDER BY LENGTH(alias) DESC")
            for a in self.cursor.fetchall():
                al = a["alias"]
                if tl == al or tl.startswith(al + " "):
                    rest = text[len(al):].strip()
                    subcmd = a["subcmd"] or ""
                    base = "/" + a["original_cmd"] + (" " + subcmd if subcmd else "")
                    return base + (" " + rest if rest else "")
            self.cursor.execute(
                "SELECT * FROM cmd_aliases WHERE peer_id=? ORDER BY LENGTH(alias) DESC",
                (peer_id,))
            for a in self.cursor.fetchall():
                al = a["alias"]
                if tl == al or tl.startswith(al + " "):
                    rest = text[len(al):].strip()
                    subcmd = a["subcmd"] or ""
                    base = "/" + a["original_cmd"] + (" " + subcmd if subcmd else "")
                    return base + (" " + rest if rest else "")
            return None

    def add_global_cmd_alias(self, original_cmd, subcmd, alias):
        with self.lock:
            try:
                self.cursor.execute(
                    "INSERT OR REPLACE INTO global_cmd_aliases (original_cmd,subcmd,alias) "
                    "VALUES(?,?,?)",
                    (original_cmd.lower(), subcmd.lower(), alias.lower()))
                self.conn.commit()
                return True
            except Exception:
                return False

    def remove_global_cmd_alias(self, alias):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM global_cmd_aliases WHERE alias=?", (alias.lower(),))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_global_cmd_aliases(self):
        with self.lock:
            self.cursor.execute("SELECT * FROM global_cmd_aliases ORDER BY original_cmd")
            return [dict(r) for r in self.cursor.fetchall()]

    # ── ники ────────────────────────────────────────────────────────────────
    def set_nickname(self, peer_id, user_id, nickname):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO nicknames (peer_id,user_id,nickname) VALUES(?,?,?)",
                (peer_id, user_id, nickname))
            self.conn.commit()

    def remove_nickname(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM nicknames WHERE peer_id=? AND user_id=?", (peer_id, user_id))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def remove_all_nicknames_user(self, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM nicknames WHERE user_id=?", (user_id,))
            self.conn.commit()

    def get_all_nicknames(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT user_id,nickname FROM nicknames WHERE peer_id=? ORDER BY nickname",
                (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    def set_global_nickname(self, user_id, nickname):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO global_nicknames (user_id,nickname) VALUES(?,?)",
                (user_id, nickname))
            self.conn.commit()

    def remove_global_nickname(self, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM global_nicknames WHERE user_id=?", (user_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_display_nickname(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT nickname FROM nicknames WHERE peer_id=? AND user_id=?",
                (peer_id, user_id))
            r = self.cursor.fetchone()
            if r:
                return r["nickname"]
            self.cursor.execute(
                "SELECT nickname FROM global_nicknames WHERE user_id=?", (user_id,))
            r = self.cursor.fetchone()
            return r["nickname"] if r else None

    # ── глобальные баны/муты/виги ───────────────────────────────────────────
    def global_ban_user(self, user_id, banned_by, reason, duration):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            bu = 0 if duration == 0 else time.time() + duration
            self.cursor.execute(
                "INSERT OR REPLACE INTO global_bans (user_id,banned_by,reason,ban_until,created_at) "
                "VALUES(?,?,?,?,?)",
                (user_id, banned_by, reason, bu, time.time()))
            self.conn.commit()
            return True

    def global_unban_user(self, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM global_bans WHERE user_id=?", (user_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def is_globally_banned(self, user_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute("SELECT * FROM global_bans WHERE user_id=?", (user_id,))
            r = self.cursor.fetchone()
            if not r:
                return False
            if r["ban_until"] == 0:
                return True
            if time.time() > r["ban_until"]:
                self.cursor.execute("DELETE FROM global_bans WHERE user_id=?", (user_id,))
                self.conn.commit()
                return False
            return True

    def get_global_ban_info(self, user_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM global_bans WHERE user_id=?", (user_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def global_mute_user(self, user_id, muted_by, reason, duration):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            mu = 0 if duration == 0 else time.time() + duration
            self.cursor.execute(
                "INSERT OR REPLACE INTO global_mutes (user_id,muted_by,reason,mute_until,created_at) "
                "VALUES(?,?,?,?,?)",
                (user_id, muted_by, reason, mu, time.time()))
            self.conn.commit()
            return True

    def global_unmute_user(self, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM global_mutes WHERE user_id=?", (user_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def is_globally_muted(self, user_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute("SELECT * FROM global_mutes WHERE user_id=?", (user_id,))
            r = self.cursor.fetchone()
            if not r:
                return False
            if r["mute_until"] == 0:
                return True
            if time.time() > r["mute_until"]:
                self.cursor.execute("DELETE FROM global_mutes WHERE user_id=?", (user_id,))
                self.conn.commit()
                return False
            return True

    def get_global_mute_info(self, user_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM global_mutes WHERE user_id=?", (user_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def add_global_vig(self, user_id, issued_by, vig_type, reason):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "INSERT INTO global_vigs (user_id,issued_by,vig_type,reason,created_at) "
                "VALUES(?,?,?,?,?)",
                (user_id, issued_by, vig_type, reason, time.time()))
            self.conn.commit()
            return True

    def remove_global_vigs(self, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM global_vigs WHERE user_id=?", (user_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def remove_global_vig_by_id(self, vig_id):
        with self.lock:
            self.cursor.execute("DELETE FROM global_vigs WHERE id=?", (vig_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_global_vigs(self, user_id=None):
        with self.lock:
            if user_id:
                self.cursor.execute(
                    "SELECT * FROM global_vigs WHERE user_id=? ORDER BY created_at DESC",
                    (user_id,))
            else:
                self.cursor.execute("SELECT * FROM global_vigs ORDER BY created_at DESC")
            return [dict(r) for r in self.cursor.fetchall()]

    def get_global_vig_by_id(self, vig_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM global_vigs WHERE id=?", (vig_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    # ── тикеты ──────────────────────────────────────────────────────────────
    def create_ticket(self, user_id, problem_text, problem_type):
        with self.lock:
            self.cursor.execute(
                "INSERT INTO support_tickets "
                "(user_id,problem_text,problem_type,status,created_at) VALUES(?,?,?,'open',?)",
                (user_id, problem_text, problem_type, time.time()))
            self.conn.commit()
            return self.cursor.lastrowid

    def get_open_ticket(self, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM support_tickets WHERE user_id=? AND status='open' "
                "ORDER BY created_at DESC LIMIT 1", (user_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def close_ticket(self, ticket_id, closed_by):
        with self.lock:
            self.cursor.execute(
                "UPDATE support_tickets SET status='closed',closed_at=?,closed_by=? WHERE id=?",
                (time.time(), closed_by, ticket_id))
            self.conn.commit()
            return self.cursor.rowcount > 0

    def get_ticket_by_id(self, ticket_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_all_chats_with_info(self):
        with self.lock:
            self.cursor.execute("SELECT peer_id,owner_id FROM chat_owners")
            return [dict(r) for r in self.cursor.fetchall()]

    # ── getinfo ─────────────────────────────────────────────────────────────
    def get_all_punishments_for_user(self, user_id):
        with self.lock:
            result = []
            self.cursor.execute(
                "SELECT id,peer_id,user_id,banned_by,reason,ban_until,created_at "
                "FROM bans WHERE user_id=? ORDER BY created_at DESC", (user_id,))
            for r in self.cursor.fetchall():
                d = dict(r); d["ptype"] = "ban"; result.append(d)

            self.cursor.execute(
                "SELECT id,peer_id,user_id,muted_by,reason,mute_until,created_at "
                "FROM mutes WHERE user_id=? ORDER BY created_at DESC", (user_id,))
            for r in self.cursor.fetchall():
                d = dict(r); d["ptype"] = "mute"; result.append(d)

            self.cursor.execute(
                "SELECT id,peer_id,user_id,issued_by,vig_type,reason,created_at "
                "FROM viglist WHERE user_id=? ORDER BY created_at DESC", (user_id,))
            for r in self.cursor.fetchall():
                d = dict(r); d["ptype"] = "vig"; result.append(d)

            self.cursor.execute(
                "SELECT id,peer_id,user_id,bl_type,reason,created_at "
                "FROM blacklist WHERE user_id=? ORDER BY created_at DESC", (user_id,))
            for r in self.cursor.fetchall():
                d = dict(r); d["ptype"] = "bl"; result.append(d)

            self.cursor.execute(
                "SELECT id,user_id,banned_by,reason,ban_until,created_at "
                "FROM global_bans WHERE user_id=?", (user_id,))
            for r in self.cursor.fetchall():
                d = dict(r); d["ptype"] = "gban"; d["peer_id"] = None; result.append(d)

            self.cursor.execute(
                "SELECT id,user_id,muted_by,reason,mute_until,created_at "
                "FROM global_mutes WHERE user_id=?", (user_id,))
            for r in self.cursor.fetchall():
                d = dict(r); d["ptype"] = "gmute"; d["peer_id"] = None; result.append(d)

            self.cursor.execute(
                "SELECT id,user_id,issued_by,vig_type,reason,created_at "
                "FROM global_vigs WHERE user_id=? ORDER BY created_at DESC", (user_id,))
            for r in self.cursor.fetchall():
                d = dict(r); d["ptype"] = "gvig"; d["peer_id"] = None; result.append(d)

            self.cursor.execute(
                "SELECT id,peer_id,user_id,issued_by,reason,created_at "
                "FROM warns WHERE user_id=? ORDER BY created_at DESC", (user_id,))
            for r in self.cursor.fetchall():
                d = dict(r); d["ptype"] = "warn"; result.append(d)

            result.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return result


DEFAULT_CMD_PERMISSIONS = {
    "bl": 80, "newrole": 90, "delrole": 90, "role": 80,
    "roles": 0, "help": 0, "yhelp": 0, "cmd": 100, "ban": 60,
    "unban": 60, "mute": 50, "unmute": 50, "kick": 50,
    "vig": 50, "unvig": 50, "unbl": 80, "top": 0,
    "connect": 100, "import": 100, "delmsg": 50,
    "staff": 0, "msg": 1000,
    "gban": 90, "gunban": 90,
    "gmute": 90, "gunmute": 90, "gkick": 90, "gvig": 90,
    "gunvig": 90, "grole": 90,
    "listchat": 1000, "start": 0,
    "stats": 0, "vlads": 1000, "renamrole": 1000,
    "notes": 50, "cmdname": 90,
    "gcmdname": 1000, "chat": 80,
    "nick": 0, "gnick": 90,
    "trusted": 90, "leader": 80,
    "list": 50, "getinfo": 0,
    "logchat": 100,
}


class PendingStore:
    def __init__(self, timeout=60):
        self.data = {}
        self.timeout = timeout
        self.lock = threading.Lock()

    def set(self, key, value):
        with self.lock:
            value["_created"] = time.time()
            self.data[key] = value

    def get(self, key):
        with self.lock:
            e = self.data.get(key)
            if not e:
                return None
            if time.time() - e["_created"] > self.timeout:
                del self.data[key]
                return None
            return e

    def pop(self, key):
        with self.lock:
            return self.data.pop(key, None)

    def has(self, key):
        with self.lock:
            e = self.data.get(key)
            if not e:
                return False
            if time.time() - e["_created"] > self.timeout:
                del self.data[key]
                return False
            return True

    def __contains__(self, key):
        return self.has(key)


bl_pending      = PendingStore(60)
vig_pending     = PendingStore(60)
unbl_pending    = PendingStore(60)
gvig_pending    = PendingStore(60)
support_pending = PendingStore(300)
unvig_pending   = PendingStore(120)
gunvig_pending  = PendingStore(120)
crmp_pending   = PendingStore(300)

class CRMPVKBridge:
    """Связка VK-бота с MySQL игрового сервера: привязка VK, /password, события игры."""
    def __init__(self, vk):
        self.vk = vk
        self._poll_started = False
        self.enabled = bool(pymysql and CRMP_DB_HOST and CRMP_DB_USER and CRMP_DB_NAME)
        if not pymysql:
            logger.warning("CRMP VK bridge disabled: установите PyMySQL: pip install pymysql")
        elif not self.enabled:
            logger.warning("CRMP VK bridge disabled: не заполнены MYSQL_HOST/MYSQL_USER/MYSQL_DATABASE")
        else:
            try:
                self.ensure_tables()
                logger.info("CRMP VK bridge connected")
            except Exception as e:
                self.enabled = False
                logger.error(f"CRMP VK bridge disabled: {e}")

    def safe_ident(self, ident):
        if not re.fullmatch(r"[A-Za-z0-9_]+", str(ident)):
            raise ValueError(f"Unsafe SQL identifier: {ident}")
        return f"`{ident}`"

    def conn(self):
        return pymysql.connect(
            host=CRMP_DB_HOST,
            port=CRMP_DB_PORT,
            user=CRMP_DB_USER,
            password=CRMP_DB_PASSWORD,
            database=CRMP_DB_NAME,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor
        )

    def execute(self, sql, params=None, fetch=False, one=False):
        if not self.enabled:
            return None if one else []
        params = params or ()
        with self.conn() as con:
            with con.cursor() as cur:
                cur.execute(sql, params)
                if fetch:
                    return cur.fetchone() if one else cur.fetchall()
                return cur.rowcount

    def ensure_tables(self):
        with self.conn() as con:
            with con.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS `vk_bind_codes` (
                      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                      `server` VARCHAR(32) NOT NULL,
                      `vk_id` BIGINT UNSIGNED NOT NULL,
                      `code` CHAR(6) NOT NULL,
                      `account_id` INT UNSIGNED DEFAULT NULL,
                      `player_name` VARCHAR(24) DEFAULT NULL,
                      `created_at` INT UNSIGNED NOT NULL,
                      `expires_at` INT UNSIGNED NOT NULL,
                      `used_at` INT UNSIGNED DEFAULT NULL,
                      PRIMARY KEY (`id`),
                      KEY `idx_server_code` (`server`, `code`),
                      KEY `idx_vk_server` (`vk_id`, `server`),
                      KEY `idx_expire` (`expires_at`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS `vk_account_links` (
                      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                      `server` VARCHAR(32) NOT NULL,
                      `account_id` INT UNSIGNED NOT NULL,
                      `account_name` VARCHAR(24) NOT NULL,
                      `vk_id` BIGINT UNSIGNED NOT NULL,
                      `bound_at` INT UNSIGNED NOT NULL,
                      PRIMARY KEY (`id`),
                      UNIQUE KEY `uniq_server_account` (`server`, `account_id`),
                      KEY `idx_server_vk` (`server`, `vk_id`),
                      KEY `idx_account_name` (`account_name`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS `vk_events` (
                      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                      `server` VARCHAR(32) NOT NULL,
                      `vk_id` BIGINT UNSIGNED NOT NULL,
                      `account_id` INT UNSIGNED NOT NULL,
                      `type` VARCHAR(32) NOT NULL,
                      `old_value` VARCHAR(128) DEFAULT NULL,
                      `new_value` VARCHAR(128) DEFAULT NULL,
                      `created_at` INT UNSIGNED NOT NULL,
                      `sent_at` INT UNSIGNED DEFAULT NULL,
                      PRIMARY KEY (`id`),
                      KEY `idx_unsent` (`sent_at`, `id`),
                      KEY `idx_vk` (`vk_id`),
                      KEY `idx_account` (`server`, `account_id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS `vk_password_logs` (
                      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                      `server` VARCHAR(32) NOT NULL,
                      `vk_id` BIGINT UNSIGNED NOT NULL,
                      `account_id` INT UNSIGNED NOT NULL,
                      `created_at` INT UNSIGNED NOT NULL,
                      PRIMARY KEY (`id`),
                      KEY `idx_vk` (`vk_id`),
                      KEY `idx_account` (`server`, `account_id`)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

    def now(self):
        return int(time.time())

    def server(self, server_key):
        return CRMP_SERVERS.get(server_key)

    def generate_bind_code(self, vk_id, server_key="florida"):
        srv = self.server(server_key)
        if not srv:
            raise ValueError("Неизвестный сервер")
        now = self.now()
        self.execute(
            "DELETE FROM vk_bind_codes WHERE expires_at < %s OR (server=%s AND vk_id=%s AND used_at IS NULL)",
            (now, srv["key"], vk_id)
        )
        code = None
        for _ in range(10):
            code = str(random.randint(100000, 999999))
            row = self.execute(
                "SELECT id FROM vk_bind_codes WHERE server=%s AND code=%s AND used_at IS NULL AND expires_at>%s LIMIT 1",
                (srv["key"], code, now), fetch=True, one=True
            )
            if not row:
                break
        self.execute(
            "INSERT INTO vk_bind_codes (server,vk_id,code,created_at,expires_at) VALUES(%s,%s,%s,%s,%s)",
            (srv["key"], vk_id, code, now, now + CRMP_CODE_TTL_SECONDS)
        )
        return code, srv

    def linked_accounts(self, vk_id, server_key="florida"):
        srv = self.server(server_key)
        if not srv:
            return []
        table = self.safe_ident(srv["accounts_table"])
        return self.execute(
            f"SELECT a.id,a.name,a.level FROM vk_account_links l JOIN {table} a ON a.id=l.account_id "
            "WHERE l.server=%s AND l.vk_id=%s ORDER BY a.name ASC LIMIT 39",
            (srv["key"], vk_id), fetch=True
        ) or []

    def change_password(self, vk_id, server_key, account_id, password):
        srv = self.server(server_key)
        if not srv:
            return False
        table = self.safe_ident(srv["accounts_table"])
        rows = self.execute(
            f"UPDATE {table} SET players_password=%s WHERE id=%s AND id IN "
            "(SELECT account_id FROM vk_account_links WHERE server=%s AND vk_id=%s AND account_id=%s)",
            (password, account_id, srv["key"], vk_id, account_id)
        )
        if rows == 1:
            self.execute(
                "INSERT INTO vk_password_logs (server,vk_id,account_id,created_at) VALUES(%s,%s,%s,%s)",
                (srv["key"], vk_id, account_id, self.now())
            )
            return True
        return False

    def event_text(self, ev):
        server = ev.get("server") or "SERVER"
        et = ev.get("type")
        if et == "bind":
            return (f"✅ Аккаунт {ev.get('new_value') or ('ID ' + str(ev.get('account_id')))} успешно привязан к этому VK.\n\n"
                    f"Сервер: {server}\n"
                    "Теперь доступны уведомления и смена пароля через /password.")
        if et == "nick_change":
            return (f"🔔 На сервере {server} изменён ник привязанного аккаунта.\n\n"
                    f"Было: {ev.get('old_value')}\n"
                    f"Стало: {ev.get('new_value')}")
        if et == "admin_login_code":
            return (f"🔐 Подтверждение входа в админ-панель\n\n"
                    f"Сервер: {server}\n"
                    f"Аккаунт: {ev.get('old_value') or ('ID ' + str(ev.get('account_id')))}\n"
                    f"Код: {ev.get('new_value')}\n\n"
                    "Введите этот код в игре в открывшемся окне.\n"
                    "Если это были не вы — срочно смените игровой и админ-пароль.")
        return f"ℹ️ Событие аккаунта на сервере {server}: {et}"

    def poll_events_once(self):
        if not self.enabled:
            return
        events = self.execute(
            "SELECT id,server,vk_id,account_id,type,old_value,new_value,created_at FROM vk_events "
            "WHERE sent_at IS NULL ORDER BY id ASC LIMIT 50",
            fetch=True
        ) or []
        for ev in events:
            try:
                self.vk.messages.send(
                    user_id=int(ev["vk_id"]),
                    random_id=random.randint(0, 2**31),
                    message=self.event_text(ev)
                )
                self.execute("UPDATE vk_events SET sent_at=%s WHERE id=%s", (self.now(), ev["id"]))
            except Exception as e:
                logger.error(f"CRMP event #{ev.get('id')} send err: {e}")

    def start_event_poller(self):
        if not self.enabled or self._poll_started:
            return
        self._poll_started = True
        def _watch():
            while True:
                try:
                    self.poll_events_once()
                except Exception as e:
                    logger.error(f"CRMP event poll err: {e}")
                time.sleep(max(2, CRMP_EVENT_POLL_INTERVAL))
        threading.Thread(target=_watch, daemon=True).start()
        logger.info("CRMP VK event poller started")

class Handlers:
    def __init__(self, vk, db, group_id):
        self.vk = vk
        self.db = db
        self.group_id = group_id
        self._nc = {}
        self._nc_lock = threading.Lock()
        self._auto_owner_lock = threading.Lock()
        self._auto_owner_done = set()
        self._gcmd_force = False
        self.crmp = CRMPVKBridge(vk)
        self.crmp.start_event_poller()

    # ── утилиты ─────────────────────────────────────────────────────────────

    def send(self, pid, msg, keyboard=None, attachment=None):
        p = {"peer_id": pid, "message": msg, "random_id": random.randint(0, 2**31)}
        if keyboard:
            p["keyboard"] = keyboard.get_keyboard()
        if attachment:
            p["attachment"] = attachment
        try:
            return self.vk.messages.send(**p)
        except Exception as e:
            logger.error(f"send err: {e}")
        return None

    def edit_msg(self, pid, cmid, msg, keyboard=None):
        p = {"peer_id": pid, "conversation_message_id": cmid,
             "message": msg, "keep_forward_messages": 1}
        if keyboard:
            p["keyboard"] = keyboard.get_keyboard()
        try:
            self.vk.messages.edit(**p)
        except Exception as e:
            logger.error(f"edit_msg err: {e}")

    def snack(self, event_id, uid, pid, text):
        try:
            self.vk.messages.sendMessageEventAnswer(
                event_id=event_id, user_id=uid, peer_id=pid,
                event_data=json.dumps({"type": "show_snackbar", "text": text[:90]}))
        except Exception as e:
            logger.error(f"snack err: {e}")

    def get_vk_names_batch(self, uids):
        """Батч-запрос имён пользователей"""
        if not uids:
            return {}
        unknown = []
        result = {}
        with self._nc_lock:
            for uid in uids:
                if uid in self._nc:
                    result[uid] = self._nc[uid]
                else:
                    unknown.append(uid)
        if not unknown:
            return result
        try:
            items = self.vk.users.get(user_ids=",".join(map(str, unknown)))
            with self._nc_lock:
                for i in items:
                    n = f"{i['first_name']} {i['last_name']}"
                    self._nc[i['id']] = n
                    result[i['id']] = n
        except Exception as e:
            logger.error(f"batch name err: {e}")
        for uid in unknown:
            if uid not in result:
                result[uid] = str(uid)
        return result

    def get_vk_name(self, uid):
        with self._nc_lock:
            if uid in self._nc:
                return self._nc[uid]
        r = self.get_vk_names_batch([uid])
        return r.get(uid, str(uid))

    def get_chat_title(self, peer_id):
        if not peer_id:
            return "Глобально"
        try:
            ci = self.vk.messages.getConversationsById(
                peer_ids=peer_id, group_id=self.group_id)
            items = ci.get("items", [])
            if items:
                return items[0].get("chat_settings", {}).get("title", f"Беседа {peer_id}")
        except Exception:
            pass
        return f"Беседа {peer_id}"

    def mention(self, uid):
        return f"@id{uid} ({self.get_vk_name(uid)})"

    def mention_nick(self, pid, uid):
        nick = self.db.get_display_nickname(pid, uid)
        if nick:
            return f"@id{uid} ({nick})"
        return f"@id{uid} ({self.get_vk_name(uid)})"

    def extract_attachments(self, msg):
        attachments = msg.get("attachments", [])
        if not attachments:
            return ""
        result = []
        for att in attachments:
            att_type = att.get("type")
            obj = att.get(att_type, {})
            owner_id = obj.get("owner_id")
            obj_id = obj.get("id")
            access_key = obj.get("access_key", "")
            if not owner_id or not obj_id:
                continue
            if att_type in ("photo","video","doc","audio","audio_message","wall","graffiti"):
                base = f"{att_type}{owner_id}_{obj_id}"
                if access_key:
                    base += f"_{access_key}"
                result.append(base)
        return ",".join(result)

    def parse_target(self, event):
        text = event.get("text", "")
        reply = event.get("reply_message")
        if reply:
            tid = reply.get("from_id")
            if tid and tid <= 0:
                return None, text
            parts = text.split(maxsplit=1)
            return tid, parts[1] if len(parts) > 1 else ""
        fwd = event.get("fwd_messages", [])
        if fwd:
            tid = fwd[0].get("from_id")
            if tid and tid <= 0:
                return None, text
            parts = text.split(maxsplit=1)
            return tid, parts[1] if len(parts) > 1 else ""
        m = re.search(r'\[id(\d+)\|[^\]]*\]', text)
        if m:
            tid = int(m.group(1))
            rest = text.split(maxsplit=1)
            rest = rest[1] if len(rest) > 1 else ""
            rest = re.sub(r'\[id\d+\|[^\]]*\]', '', rest).strip()
            return tid, rest
        parts = text.split()
        if len(parts) >= 2:
            try:
                return int(parts[1]), " ".join(parts[2:])
            except ValueError:
                pass
        return None, text

    def parse_target_from_rest(self, rest_text, event):
        reply = event.get("reply_message")
        if reply:
            tid = reply.get("from_id")
            if tid and tid > 0:
                return tid
        fwd = event.get("fwd_messages", [])
        if fwd:
            tid = fwd[0].get("from_id")
            if tid and tid > 0:
                return tid
        m = re.search(r'\[id(\d+)\|[^\]]*\]', rest_text)
        if m:
            return int(m.group(1))
        parts = rest_text.split()
        if parts:
            try:
                return int(parts[0])
            except ValueError:
                pass
        return None

    def is_ga(self, uid):
        if self._gcmd_force and uid == GADM_OWNER:
            return True
        return is_ga_active(uid)

    def get_prio(self, pid, uid):
        s = self.db.get_settings(pid)
        if s.get("connected"):
            return self.db.get_user_priority_pool(pid, uid)
        return self.db.get_user_priority(pid, uid)

    def min_prio(self, pid, cmd):
        p = self.db.get_cmd_permission(pid, cmd)
        return p if p is not None else DEFAULT_CMD_PERMISSIONS.get(cmd, 100)

    def has_perm(self, pid, uid, cmd):
        if self._gcmd_force and uid == GADM_OWNER:
            return True
        return self.get_prio(pid, uid) >= self.min_prio(pid, cmd)

    def format_role(self, pid, uid):
        if is_ga_active(uid):
            return "🌐 Глобальный Администратор (1000)"
        if self.get_prio(pid, uid) >= 100 and self.db.get_chat_owner(pid) == uid:
            alias = self.db.get_role_alias(pid, 100)
            if alias:
                em = alias.get("alias_emoji","") or ""
                nm = alias.get("alias_name","Владелец")
                return f"{em} {nm} (100)" if em else f"👑 {nm} (100)"
            return "👑 Владелец (100)"
        ri = self.db.get_user_role(pid, uid)
        if ri:
            em = ri.get("emoji","") or ""
            return f"{em} {ri['role_name']} ({ri['priority']})" if em else f"🎭 {ri['role_name']} ({ri['priority']})"
        alias = self.db.get_role_alias(pid, 0)
        if alias:
            em = alias.get("alias_emoji","") or ""
            nm = alias.get("alias_name","Пользователь")
            return f"{em} {nm} (0)" if em else f"👤 {nm} (0)"
        return "👤 Пользователь (0)"

    def auto_owner(self, pid, event):
        with self._auto_owner_lock:
            if pid in self._auto_owner_done:
                return
        if self.db.get_chat_owner(pid) is not None:
            with self._auto_owner_lock:
                self._auto_owner_done.add(pid)
            return
        try:
            ci = self.vk.messages.getConversationsById(
                peer_ids=pid, group_id=self.group_id)
            items = ci.get("items", [])
            if items:
                ow = items[0].get("chat_settings", {}).get("owner_id")
                if ow:
                    self.db.set_chat_owner(pid, ow)
                    with self._auto_owner_lock:
                        self._auto_owner_done.add(pid)
                    return
        except Exception:
            pass
        fid = event.get("from_id", 0)
        if fid > 0:
            self.db.set_chat_owner(pid, fid)
            with self._auto_owner_lock:
                self._auto_owner_done.add(pid)

    def parse_dur(self, t):
        t = t.strip().lower()
        if t in ('n','навсегда'):
            return 0, "навсегда"
        m = re.match(r'^(\d+)([smhd])$', t)
        if not m:
            return None, None
        a, u = int(m.group(1)), m.group(2)
        mul = {'s':1,'m':60,'h':3600,'d':86400}
        nm  = {'s':'сек.','m':'мин.','h':'ч.','d':'дн.'}
        return a*mul[u], f"{a} {nm[u]}"

    def kick(self, pid, uid):
        if uid in GLOBAL_ADMINS:
            return False
        try:
            cid = pid - 2000000000
            if cid > 0:
                self.vk.messages.removeChatUser(chat_id=cid, user_id=uid)
                return True
        except Exception:
            pass
        return False

    def reset_user_data(self, pid, uid):
        self.db.remove_role(pid, uid)
        self.db.remove_nickname(pid, uid)
        self.db.remove_trusted(pid, uid)
        self.db.remove_leader(pid, uid)

    def fmt_time(self, ts):
        if ts == 0:
            return "навсегда"
        left = ts - time.time()
        if left <= 0:
            return "истекло"
        if left < 60:   return f"{int(left)}с"
        if left < 3600: return f"{int(left/60)}м"
        if left < 86400:return f"{int(left/3600)}ч"
        return f"{int(left/86400)}д"

    def log_action(self, pid, actor_id, target_id, action, details=""):
        """Записать в audit_log и отправить в лог-чат если настроен"""
        self.db.add_audit(pid, actor_id, target_id, action, details)
        settings = self.db.get_settings(pid)
        log_chat = settings.get("log_chat", 0)
        if log_chat:
            try:
                actor_name = self.get_vk_name(actor_id)
                target_name = self.get_vk_name(target_id) if target_id else "—"
                ts = fmt_msk(time.time())
                msg = (f"📋 Лог | {ts}\n"
                       f"👮 {actor_name} (@id{actor_id})\n"
                       f"👤 {target_name}" + (f" (@id{target_id})" if target_id else "") + "\n"
                       f"⚡ {action}\n"
                       + (f"📝 {details}" if details else ""))
                self.vk.messages.send(
                    peer_id=log_chat, message=msg,
                    random_id=random.randint(0, 2**31))
            except Exception as e:
                logger.error(f"log_action send err: {e}")

    def get_pool_targets(self, pid):
        """Список чатов для /g команд — только чаты в том же пуле"""
        s = self.db.get_settings(pid)
        if not s.get("connected"):
            return [pid]
        return self.db.get_pool_peers_for(pid)

    # ── античит ─────────────────────────────────────────────────────────────

    def anticheat_check_punish(self, pid, fid, tid):
        if self.is_ga(fid):
            if self.is_ga(tid):
                return False, "⛔ Нельзя наказать Глобального Администратора."
            return True, ""
        if self.is_ga(tid):
            return False, "⛔ Нельзя наказать Глобального Администратора."
        tp = self.get_prio(pid, tid)
        up = self.get_prio(pid, fid)
        if tp >= up:
            return False, f"🛡 Античит: приоритет цели ({tp}) >= вашего ({up})."
        trusted = self.db.get_trusted(pid, tid)
        if trusted:
            min_p = trusted["min_punish_priority"]
            if up < min_p:
                return False, f"🛡 Античит: {self.mention(tid)} защищён — нужен приоритет >= {min_p}, ваш {up}."
        return True, ""

    def anticheat_check_unpunish(self, pid, fid, punisher_id):
        if self.is_ga(fid):
            return True, ""
        pp = self.get_prio(pid, punisher_id)
        up = self.get_prio(pid, fid)
        if pp > up:
            return False, f"🛡 Античит: наказание выдал человек с приоритетом {pp}, ваш — {up}."
        return True, ""

    def anticheat_check_role_assign(self, pid, fid, tid, new_priority):
        if self.is_ga(fid):
            return True, ""
        up  = self.get_prio(pid, fid)
        tcp = self.get_prio(pid, tid)
        if tcp >= up:
            return False, f"🛡 Античит: приоритет цели ({tcp}) >= вашего ({up})."
        if new_priority >= up:
            return False, f"🛡 Античит: нельзя выдать роль с приоритетом ({new_priority}) >= вашего ({up})."
        owner = self.db.get_chat_owner(pid)
        if owner and tid == owner:
            return False, "🛡 Античит: нельзя менять роль владельцу — только ГА может это."
        return True, ""

    def anticheat_check_role_remove(self, pid, fid, tid):
        if self.is_ga(fid):
            return True, ""
        up  = self.get_prio(pid, fid)
        tcp = self.get_prio(pid, tid)
        if tcp >= up:
            return False, f"🛡 Античит: приоритет цели ({tcp}) >= вашего ({up})."
        owner = self.db.get_chat_owner(pid)
        if owner and tid == owner:
            return False, "🛡 Античит: нельзя снять роль у владельца — только ГА может это."
        return True, ""

    def anticheat_check_role_create(self, pid, fid, priority):
        if self.is_ga(fid):
            return True, ""
        up = self.get_prio(pid, fid)
        if priority >= up:
            return False, f"🛡 Античит: нельзя создать роль с приоритетом ({priority}) >= вашего ({up})."
        return True, ""

    def anticheat_check_role_delete(self, pid, fid, priority):
        if self.is_ga(fid):
            return True, ""
        up = self.get_prio(pid, fid)
        if priority >= up:
            return False, f"🛡 Античит: нельзя удалить роль с приоритетом ({priority}) >= вашего ({up})."
        return True, ""

    def anticheat_check_owner_change(self, pid, fid):
        if self.is_ga(fid):
            return True, ""
        return False, "🛡 Античит: сменить владельца может только Глобальный Администратор."

    # ── автоснятие мутов/банов (фоновый поток) ──────────────────────────────

    def start_expiry_watcher(self):
        def _watch():
            while True:
                try:
                    self._process_expired()
                except Exception as e:
                    logger.error(f"expiry watcher err: {e}")
                time.sleep(30)
        t = threading.Thread(target=_watch, daemon=True)
        t.start()
        logger.info("Expiry watcher started")

    def _process_expired(self):
        now = time.time()
        # истёкшие баны
        expired_bans = self.db.get_expired_bans()
        for b in expired_bans:
            pid = b["peer_id"]
            uid = b["user_id"]
            self.db.unban_user(pid, uid)
            # снимаем только если не в муте (мут тоже ставит бан)
            if not self.db.is_muted(pid, uid):
                try:
                    self.send(pid, f"✅ Бан истёк!\n👤 {self.mention(uid)}")
                except Exception:
                    pass

        # истёкшие муты
        expired_mutes = self.db.get_expired_mutes()
        for m in expired_mutes:
            pid = m["peer_id"]
            uid = m["user_id"]
            self.db.unmute_user(pid, uid)
            self.db.unban_user(pid, uid)
            try:
                self.send(pid, f"🔊 Мут истёк!\n👤 {self.mention(uid)}")
            except Exception:
                pass

    # ── авто-наказания за выговоры/предупреждения ────────────────────────────

    def check_vig_auto_punish(self, pid, uid, fid):
        """
        2 грубых выговора → бан навсегда
        3 обычных выговора → бан навсегда
        2 предупреждения → 1 выговор
        """
        grubye = self.db.count_vigs_by_type(pid, uid, "грубый выговор")
        obychnye = self.db.count_vigs_by_type(pid, uid, "выговор")
        warns = self.db.count_warns(pid, uid)

        # 2 грубых → бан
        if grubye >= 2:
            self.db.ban_user(pid, uid, fid, "Автобан: 2 грубых выговора", 0)
            self.reset_user_data(pid, uid)
            self.kick(pid, uid)
            self.log_action(pid, fid, uid, "Автобан", "2 грубых выговора")
            self.send(pid,
                f"🔨 Автобан!\n"
                f"👤 {self.mention(uid)}\n"
                f"📋 Причина: 2 грубых выговора\n"
                f"⏳ навсегда")
            return

        # 3 обычных → бан
        if obychnye >= 3:
            self.db.ban_user(pid, uid, fid, "Автобан: 3 выговора", 0)
            self.reset_user_data(pid, uid)
            self.kick(pid, uid)
            self.log_action(pid, fid, uid, "Автобан", "3 выговора")
            self.send(pid,
                f"🔨 Автобан!\n"
                f"👤 {self.mention(uid)}\n"
                f"📋 Причина: 3 выговора\n"
                f"⏳ навсегда")
            return

        # 2 предупреждения → выговор
        if warns >= 2:
            self.db.remove_warns(pid, uid)
            self.db.add_vig(pid, uid, fid, "выговор", "Авто: 2 предупреждения")
            self.log_action(pid, fid, uid, "Авто-выговор", "2 предупреждения")
            self.send(pid,
                f"⚠️ Авто-выговор!\n"
                f"👤 {self.mention(uid)}\n"
                f"📋 Причина: накоплено 2 предупреждения\n"
                f"⚠️ Предупреждения сброшены")
            # рекурсивно проверяем — вдруг теперь хватает выговоров
            self.check_vig_auto_punish(pid, uid, fid)

    # ── события ─────────────────────────────────────────────────────────────

    def handle_chat_invite(self, pid, uid, inviter):
        self.db.remember_member(pid, uid, inviter if inviter and inviter > 0 else 0)
        if inviter and inviter > 0:
            self.db.remember_member(pid, inviter, 0)
        if self.db.is_globally_banned(uid):
            gi = self.db.get_global_ban_info(uid)
            self.send(pid,
                f"⛔ {self.mention(uid)} в бане!\n"
                f"👮 {self.mention(gi['banned_by'])}\n"
                f"📋 {gi.get('reason','—')}\n"
                f"⏳ {self.fmt_time(gi.get('ban_until',0))}")
            self.kick(pid, uid)
            return
        # проверяем локальный ЧС (все типы)
        bl = self.db.is_blacklisted_in_chat(uid, pid)
        if bl:
            types = [b["bl_type"] for b in bl]
            if any(t in ("full_project","full_strict","chat_admin","chat_local") for t in types):
                self.send(pid, f"🚫 {self.mention(uid)} в чёрном списке. Приглашение невозможно.")
                self.kick(pid, uid)
                return
        bi = self.db.get_ban_info(pid, uid)
        if not bi:
            return
        banner_prio  = self.get_prio(pid, bi["banned_by"])
        inviter_prio = self.get_prio(pid, inviter)
        if banner_prio > inviter_prio:
            self.send(pid,
                f"⛔ {self.mention(uid)} забанен!\n"
                f"👮 {self.mention(bi['banned_by'])}\n"
                f"📋 {bi.get('reason','—')}\n"
                f"⏳ {self.fmt_time(bi.get('ban_until',0))}\n"
                f"🛡 Приоритет забанившего ({banner_prio}) > вашего ({inviter_prio})")
            self.kick(pid, uid)
        else:
            self.db.unban_user(pid, uid)
            self.send(pid,
                f"✅ {self.mention(uid)} разбанен автоматически.\n"
                f"👤 Добавил: {self.mention(inviter)}")

    # ── CRMP VK integration: привязка / пароль / VK-коды ────────────────

    def crmp_is_private(self, pid, fid):
        return pid == fid and pid > 0 and pid < 2000000000

    def crmp_need_private(self, pid, fid):
        if self.crmp_is_private(pid, fid):
            return False
        self.send(pid, "🔐 Для безопасности напишите эту команду в личные сообщения сообщества.")
        return True

    def crmp_main_keyboard(self):
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("🔐 Получить код привязки", color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":"crmp_bind"}))
        kb.add_line()
        kb.add_callback_button("🔑 Сменить пароль", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button":"crmp_password"}))
        return kb

    def crmp_server_keyboard(self, action):
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("🌴 FLORIDA", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button":f"crmp_{action}_server_florida"}))
        kb.add_line()
        kb.add_callback_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":"crmp_cancel"}))
        return kb

    def crmp_cancel_keyboard(self):
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":"crmp_cancel"}))
        return kb

    def crmp_accounts_keyboard(self, server_key, accounts):
        kb = VkKeyboard(inline=True)
        for idx, acc in enumerate(accounts):
            if idx and idx % 2 == 0:
                kb.add_line()
            kb.add_callback_button(str(acc.get("name")), color=VkKeyboardColor.PRIMARY,
                payload=json.dumps({"button":f"crmp_password_account_{server_key}_{acc.get('id')}"}))
        kb.add_line()
        kb.add_callback_button("❌ Отмена", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":"crmp_cancel"}))
        return kb

    def cmd_bind(self, e, pid, fid):
        if self.crmp_need_private(pid, fid):
            return
        if not self.crmp.enabled:
            return self.send(pid, "❌ Привязка временно недоступна: не настроено подключение к MySQL игрового сервера.")
        self.send(pid,
            "🔐 Привязка ВКонтакте к игровому аккаунту\n\n"
            "Выберите сервер, для которого нужно получить код.",
            keyboard=self.crmp_server_keyboard("bind"))

    def cmd_password(self, e, pid, fid):
        if self.crmp_need_private(pid, fid):
            return
        if not self.crmp.enabled:
            return self.send(pid, "❌ Смена пароля временно недоступна: не настроено подключение к MySQL игрового сервера.")
        self.send(pid,
            "🔑 Смена пароля\n\nВыберите сервер, на котором находится аккаунт.",
            keyboard=self.crmp_server_keyboard("password"))

    def crmp_handle_waiting_password(self, pid, fid, text):
        if not self.crmp_is_private(pid, fid):
            return False
        st = crmp_pending.get(fid)
        if not st or st.get("stage") != "wait_new_password":
            return False
        password = text.strip()
        if len(password) < 6 or len(password) > 23:
            self.send(pid, "❌ Пароль должен быть от 6 до 23 символов. Напишите другой пароль или нажмите Отмена.")
            return True
        if re.search(r"\s", password):
            self.send(pid, "❌ В пароле не должно быть пробелов. Напишите другой пароль или нажмите Отмена.")
            return True
        ok = self.crmp.change_password(fid, st["server_key"], st["account_id"], password)
        crmp_pending.pop(fid)
        if ok:
            self.send(pid,
                f"✅ Пароль для аккаунта {st.get('account_name')} изменён.\n\n"
                "Теперь при следующем входе в игру используйте новый пароль.",
                keyboard=self.crmp_main_keyboard())
        else:
            self.send(pid, "❌ Не удалось сменить пароль. Аккаунт не найден или привязка была удалена.",
                      keyboard=self.crmp_main_keyboard())
        return True

    def handle_crmp_button(self, pid, uid, bt, cmid=None, event_id=None):
        if not bt.startswith("crmp_"):
            return False
        if self.crmp_need_private(pid, uid):
            return True
        if not self.crmp.enabled:
            self.send(pid, "❌ Функция временно недоступна: не настроено подключение к MySQL игрового сервера.")
            return True

        if bt == "crmp_cancel":
            crmp_pending.pop(uid)
            self.send(pid, "Действие отменено.", keyboard=self.crmp_main_keyboard())
            return True

        if bt == "crmp_bind":
            self.send(pid, "🔐 Выберите сервер:", keyboard=self.crmp_server_keyboard("bind"))
            return True

        if bt == "crmp_password":
            self.send(pid, "🔑 Выберите сервер:", keyboard=self.crmp_server_keyboard("password"))
            return True

        if bt.startswith("crmp_bind_server_"):
            server_key = bt.replace("crmp_bind_server_", "", 1)
            try:
                code, srv = self.crmp.generate_bind_code(uid, server_key)
                minutes = max(1, CRMP_CODE_TTL_SECONDS // 60)
                self.send(pid,
                    f"✅ Сервер: {srv['title']}\n\n"
                    f"Твой код привязки: {code}\n\n"
                    "Теперь зайди в игру и введи /bind или /vk.\n"
                    "Далее выбери ВКонтакте и введи этот код.\n\n"
                    f"⏳ Код действует {minutes} минут.\n"
                    "⚠️ Никому не передавайте код.",
                    keyboard=self.crmp_main_keyboard())
            except Exception as e:
                logger.error(f"bind code err: {e}")
                self.send(pid, "❌ Не удалось выдать код. Попробуйте позже.")
            return True

        if bt.startswith("crmp_password_server_"):
            server_key = bt.replace("crmp_password_server_", "", 1)
            accounts = self.crmp.linked_accounts(uid, server_key)
            srv = self.crmp.server(server_key) or {"title": server_key.upper()}
            if not accounts:
                self.send(pid,
                    f"На сервере {srv['title']} у вас пока нет привязанных аккаунтов.\n\n"
                    "Сначала получите код через /bind и введите его в игре.",
                    keyboard=self.crmp_main_keyboard())
            else:
                self.send(pid,
                    f"🔑 Сервер: {srv['title']}\n\nВыберите ник аккаунта, которому нужно сменить пароль:",
                    keyboard=self.crmp_accounts_keyboard(server_key, accounts))
            return True

        if bt.startswith("crmp_password_account_"):
            parts = bt.split("_")
            if len(parts) < 5:
                self.send(pid, "❌ Ошибка выбора аккаунта.")
                return True
            server_key = parts[3]
            try:
                account_id = int(parts[4])
            except ValueError:
                self.send(pid, "❌ Ошибка выбора аккаунта.")
                return True
            accounts = self.crmp.linked_accounts(uid, server_key)
            acc = next((a for a in accounts if int(a.get("id")) == account_id), None)
            if not acc:
                self.send(pid, "❌ Этот аккаунт не найден среди ваших привязок.", keyboard=self.crmp_main_keyboard())
                return True
            crmp_pending.set(uid, {
                "stage": "wait_new_password",
                "server_key": server_key,
                "account_id": account_id,
                "account_name": acc.get("name")
            })
            self.send(pid,
                f"✍️ Аккаунт: {acc.get('name')}\n\n"
                "Напишите новым сообщением новый пароль.\n\n"
                "Требования:\n"
                "• от 6 до 23 символов;\n"
                "• без пробелов;\n"
                "• не используйте пароль от других сайтов.",
                keyboard=self.crmp_cancel_keyboard())
            return True

        return True

    def handle_message(self, msg):
        text   = msg.get("text","").strip()
        pid    = msg.get("peer_id")
        fid    = msg.get("from_id")
        action = msg.get("action")
        if not pid or not fid:
            return
        if action:
            if action.get("type") in ("chat_invite_user", "chat_invite_user_by_link"):
                mid = action.get("member_id") or fid
                if mid and mid > 0:
                    self.handle_chat_invite(pid, mid, fid)
                    return
        self.auto_owner(pid, msg)
        self.db.get_settings(pid)
        if fid > 0:
            self.db.remember_member(pid, fid, 0)

        if not self.is_ga(fid):
            if self.db.is_globally_banned(fid):
                gi = self.db.get_global_ban_info(fid)
                self.send(pid, f"⛔ {self.mention(fid)} в бане!\n{gi.get('reason','')}")
                self.kick(pid, fid)
                return
            if self.db.is_globally_muted(fid):
                try:
                    cmid = msg.get("conversation_message_id")
                    if cmid:
                        self.vk.messages.delete(
                            cmids=cmid, peer_id=pid,
                            delete_for_all=1, group_id=self.group_id)
                except Exception:
                    pass
                return
            if self.db.is_muted(pid, fid):
                try:
                    cmid = msg.get("conversation_message_id")
                    if cmid:
                        self.vk.messages.delete(
                            cmids=cmid, peer_id=pid,
                            delete_for_all=1, group_id=self.group_id)
                except Exception:
                    pass
                return
            if self.db.is_banned(pid, fid):
                self.send(pid, f"⛔ {self.mention(fid)} в бане.")
                self.kick(pid, fid)
                return
            bl = self.db.is_blacklisted_in_chat(fid, pid)
            if bl:
                self.send(pid, f"🚫 {self.mention(fid)} в чёрном списке.")
                self.kick(pid, fid)
                return

        settings = self.db.get_settings(pid)
        if settings.get("chat_closed") and not self.is_ga(fid):
            if self.get_prio(pid, fid) < 80:
                try:
                    cmid = msg.get("conversation_message_id")
                    if cmid:
                        self.vk.messages.delete(
                            cmids=cmid, peer_id=pid,
                            delete_for_all=1, group_id=self.group_id)
                except Exception:
                    pass
                return

        if not text:
            return
        if fid > 0:
            self.db.increment_msg(pid, fid)

        tl = text.lower().strip()

        if self.crmp_handle_waiting_password(pid, fid, text):
            return

        # pending handlers
        if fid in support_pending:
            self.process_support_problem(pid, fid, text)
            return
        if fid in vig_pending and tl in ("грубый выговор","выговор","устный выговор"):
            self.process_vig_choice(pid, fid, tl)
            return
        if fid in gvig_pending and tl in ("грубый выговор","выговор","устный выговор"):
            self.process_gvig_choice(pid, fid, tl)
            return
        if fid in bl_pending and tl in ("чса","чсл","чсп","чсс"):
            self.process_bl_choice(pid, fid, tl)
            return
        if fid in unbl_pending and tl in ("чса","чсл","чсп","чсс","все"):
            self.process_unbl_choice(pid, fid, tl)
            return

        # заметки #имя
        if tl.startswith("#") and len(tl) > 1:
            note_name = tl[1:].strip()
            if note_name:
                note = self.db.get_note(pid, note_name)
                if note:
                    att = note.get("attachments","") or None
                    note_text = note.get("note_text","")
                    self.send(pid, note_text if note_text else f"#{note_name}",
                              attachment=att if att else None)
                    return

        if "фантик" in tl:
            self.send(pid,
                f"👋 Привет, {self.mention(fid)}!\n"
                f"🤖 Я — бот The Owen.\n"
                f"🎭 Роль: {self.format_role(pid, fid)}\n"
                f"📖 /help")
            return
        if tl == "!id":
            r = f"🔢 Peer ID: {pid}"
            if pid > 2000000000:
                r += f"\n💬 Chat ID: {pid - 2000000000}"
            self.send(pid, r)
            return
        if tl == "!test":
            self.send(pid, "✅ Бот работает!")
            return

        # resolve alias (глубина 1)
        resolved = self.db.resolve_alias(pid, text)
        if resolved and resolved != text:
            msg = dict(msg)
            msg["text"] = resolved
            text = resolved
            tl   = text.lower().strip()

        cmds = {
            "/help":     self.cmd_help,
            "/yhelp":    self.cmd_yhelp,
            "/newrole":  self.cmd_newrole,
            "/delrole":  self.cmd_delrole,
            "/roles":    self.cmd_roles,
            "/role":     self.cmd_role,
            "/cmdname":  self.cmd_cmdname,
            "/gcmdname": self.cmd_gcmdname,
            "/cmd":      self.cmd_cmd,
            "/ban":      self.cmd_ban,
            "/unban":    self.cmd_unban,
            "/mute":     self.cmd_mute,
            "/unmute":   self.cmd_unmute,
            "/kick":     self.cmd_kick,
            "/bl":       self.cmd_bl,
            "/unbl":     self.cmd_unbl,
            "/vig":      self.cmd_vig,
            "/unvig":    self.cmd_unvig,
            "/top":      self.cmd_top,
            "/connect":  self.cmd_connect,
            "/import":   self.cmd_import,
            "/delmsg":   self.cmd_delmsg,
            "/staff":    self.cmd_staff,
            "/msg":      self.cmd_msg,
            "/gban":     self.cmd_gban,
            "/gunban":   self.cmd_gunban,
            "/gmute":    self.cmd_gmute,
            "/gunmute":  self.cmd_gunmute,
            "/gkick":    self.cmd_gkick,
            "/gvig":     self.cmd_gvig,
            "/gunvig":   self.cmd_gunvig,
            "/listchat": self.cmd_listchat,
            "/grole":    self.cmd_grole,
            "/start":    self.cmd_start,
            "/bind":     self.cmd_bind,
            "/vk":       self.cmd_bind,
            "/password": self.cmd_password,
            "/пароль":   self.cmd_password,
            "/stats":    self.cmd_stats,
            "/стата":    self.cmd_stats,
            "/vlads":    self.cmd_vlads,
            "/renamrole":self.cmd_renamrole,
            "/notes":    self.cmd_notes,
            "/chat":     self.cmd_chat,
            "/nick":     self.cmd_nick,
            "/gnick":    self.cmd_gnick,
            "/trusted":  self.cmd_trusted,
            "/leader":   self.cmd_leader,
            "/gadm":     self.cmd_gadm,
            "/gcmd":     self.cmd_gcmd,
            "/list":     self.cmd_list,
            "/getinfo":  self.cmd_getinfo,
            "/logchat":  self.cmd_logchat,
        }
        for c, f in cmds.items():
            if tl.startswith(c) and (len(tl)==len(c) or tl[len(c)]==" "):
                f(msg, pid, fid)
                return

    # ── /gadm ────────────────────────────────────────────────────────────────

    def cmd_gadm(self, e, pid, fid):
        if fid != GADM_OWNER:
            return
        parts = e.get("text","").split()
        if len(parts) < 2:
            status = "OFF (обычный игрок)" if fid in GADM_DISABLED else "ON (Глобальный Администратор)"
            return self.send(pid, f"👤 Статус ГА: {status}\n\n/gadm off — снять\n/gadm on — восстановить")
        arg = parts[1].lower()
        if arg == "off":
            GADM_DISABLED.add(fid)
            self.send(pid, "✅ Привилегии ГА сняты. Вы — обычный игрок.")
        elif arg == "on":
            GADM_DISABLED.discard(fid)
            self.send(pid, "✅ Привилегии ГА восстановлены.")
        else:
            self.send(pid, "❌ /gadm on / /gadm off")

    # ── /gcmd ────────────────────────────────────────────────────────────────

    def cmd_gcmd(self, e, pid, fid):
        """Выполнение любой команды бота от имени GADM_OWNER, даже если /gadm off."""
        if fid != GADM_OWNER:
            return self.send(pid, "❌ Нет доступа.")
        text = e.get("text", "").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            return self.send(pid,
                "⚙️ /gcmd — выполнить любую команду бота как ГА\n\n"
                "📖 /gcmd [команда] [аргументы]\n\n"
                "💡 Примеры:\n"
                "/gcmd ban @user 1d причина\n"
                "/gcmd role @user 90\n"
                "/gcmd cmd ban 80\n"
                "/gcmd msg текст рассылки\n\n"
                "Можно писать команду с / или без него.")
        raw = parts[1].strip()
        if not raw:
            return self.send(pid, "❌ Укажите команду.")
        raw_parts = raw.split(maxsplit=1)
        cmd = raw_parts[0].lower().lstrip("/")
        rest = raw_parts[1] if len(raw_parts) > 1 else ""
        if cmd in ("gcmd", "gadm"):
            return self.send(pid, "❌ Эту команду через /gcmd выполнять нельзя.")

        cmd_map = {
            "help": self.cmd_help, "yhelp": self.cmd_yhelp,
            "newrole": self.cmd_newrole, "delrole": self.cmd_delrole,
            "roles": self.cmd_roles, "role": self.cmd_role,
            "cmdname": self.cmd_cmdname, "gcmdname": self.cmd_gcmdname,
            "cmd": self.cmd_cmd,
            "ban": self.cmd_ban, "unban": self.cmd_unban,
            "mute": self.cmd_mute, "unmute": self.cmd_unmute,
            "kick": self.cmd_kick, "bl": self.cmd_bl, "unbl": self.cmd_unbl,
            "vig": self.cmd_vig, "unvig": self.cmd_unvig,
            "top": self.cmd_top, "connect": self.cmd_connect,
            "import": self.cmd_import, "delmsg": self.cmd_delmsg,
            "staff": self.cmd_staff, "msg": self.cmd_msg,
            "gban": self.cmd_gban, "gunban": self.cmd_gunban,
            "gmute": self.cmd_gmute, "gunmute": self.cmd_gunmute,
            "gkick": self.cmd_gkick, "gvig": self.cmd_gvig,
            "gunvig": self.cmd_gunvig, "listchat": self.cmd_listchat,
            "grole": self.cmd_grole, "start": self.cmd_start,
            "bind": self.cmd_bind, "vk": self.cmd_bind,
            "password": self.cmd_password, "пароль": self.cmd_password,
            "stats": self.cmd_stats, "стата": self.cmd_stats,
            "vlads": self.cmd_vlads, "renamrole": self.cmd_renamrole,
            "notes": self.cmd_notes, "chat": self.cmd_chat,
            "nick": self.cmd_nick, "gnick": self.cmd_gnick,
            "trusted": self.cmd_trusted, "leader": self.cmd_leader,
            "list": self.cmd_list, "getinfo": self.cmd_getinfo,
            "logchat": self.cmd_logchat,
        }
        func = cmd_map.get(cmd)
        if not func:
            return self.send(pid, f"❌ Команда /{cmd} не найдена.")

        fake_e = dict(e)
        fake_e["text"] = "/" + cmd + ((" " + rest) if rest else "")
        old_force = self._gcmd_force
        self._gcmd_force = True
        try:
            func(fake_e, pid, fid)
        finally:
            self._gcmd_force = old_force

    # ── /help ────────────────────────────────────────────────────────────────

    def _main_help_keyboard(self, prefix="help"):
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("🔨 Модерация",   color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":f"{prefix}_mod"}))
        kb.add_callback_button("🎭 Роли",        color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":f"{prefix}_roles"}))
        kb.add_line()
        kb.add_callback_button("📝 Заметки/Ники",color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":f"{prefix}_notes"}))
        kb.add_callback_button("🌐 Глобальные",  color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":f"{prefix}_global"}))
        kb.add_line()
        kb.add_callback_button("⚙️ Настройки",   color=VkKeyboardColor.SECONDARY,
            payload=json.dumps({"button":f"{prefix}_settings"}))
        kb.add_callback_button("📋 Разное",      color=VkKeyboardColor.SECONDARY,
            payload=json.dumps({"button":f"{prefix}_misc"}))
        return kb

    def _back_keyboard(self, button):
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("◀ Назад", color=VkKeyboardColor.SECONDARY,
            payload=json.dumps({"button":button}))
        return kb

    def cmd_help(self, e, pid, fid):
        up = self.get_prio(pid, fid)
        self.send(pid,
            f"📖 The Owen Bot — Справка\n"
            f"{self.mention(fid)} | {self.format_role(pid, fid)}\n"
            f"🔑 Приоритет: {up}\n\n"
            f"Выберите категорию:", keyboard=self._main_help_keyboard("help"))

    def _help_text(self, category):
        cats = {
            "help_mod": (
                "🔨 Модерация\n\n"
                "/ban [юзер] [время] [причина] — бан\n"
                "/unban [юзер] — разбан\n"
                "/mute [юзер] [время] [причина] — мут\n"
                "/unmute [юзер] — размут\n"
                "/kick [юзер] [причина] — кик\n"
                "/vig [юзер] [причина] — выговор\n"
                "/unvig [юзер] — снять выговор\n"
                "/bl [юзер] [причина] — чёрный список\n"
                "/unbl [юзер] — убрать из ЧС\n"
                "/delmsg [1-100] — удалить сообщения бота\n"
                "/chat open/close — открыть/закрыть чат\n"
                "/trusted [юзер] [приоритет/off] — защита\n"
                "/list ban/mute/vig/bl — списки\n\n"
                "⏰ Время: 30s / 5m / 2h / 3d / n (навсегда)\n\n"
                "⚠️ Авто-наказания:\n"
                "2 грубых выговора → бан\n"
                "3 выговора → бан\n"
                "2 предупреждения → выговор"
            ),
            "help_roles": (
                "🎭 Роли\n\n"
                "/roles — список ролей\n"
                "/role [юзер] [приоритет] — назначить роль\n"
                "/role [юзер] 0 — снять роль\n"
                "/newrole [приоритет] [Эмодзи Название] — создать/изменить роль\n"
                "/delrole [приоритет] — удалить роль\n"
                "/staff — персонал чата\n"
                "/renamrole [0/100] [Эмодзи Название] — переименовать\n"
                "/vlads [юзер] — сменить владельца (ГА)\n\n"
                "💡 Приоритеты: 1–99 (кастом), 100 (владелец), 1000 (ГА)"
            ),
            "help_notes": (
                "📝 Заметки\n\n"
                "/notes list — список\n"
                "/notes create [название] [текст] — создать\n"
                "/notes del [название] — удалить\n"
                "/notes [название] — показать\n"
                "#название — быстрый вызов\n\n"
                "🏷 Ники\n\n"
                "/nick — ваш ник\n"
                "/nick set [ник] — установить свой\n"
                "/nick set [юзер] [ник] — другому (80+)\n"
                "/nick remove — убрать свой\n"
                "/nick list — все ники\n"
                "/gnick set [юзер] [ник] — глобальный ник (90+)\n"
                "/gnick remove [юзер] — убрать глобальный\n\n"
                "🏢 Организации\n\n"
                "/leader set [юзер] Орг | Должность\n"
                "/leader rem [юзер]\n"
                "/leader — список"
            ),
            "help_global": (
                "🌐 Глобальные команды (90+)\n\n"
                "/gban [юзер] [время] [причина]\n"
                "/gunban [юзер]\n"
                "/gmute [юзер] [время] [причина]\n"
                "/gunmute [юзер]\n"
                "/gkick [юзер] [причина]\n"
                "/gvig [юзер] [причина]\n"
                "/gunvig [юзер]\n"
                "/grole [юзер] [приоритет]\n\n"
                "⚠️ Работают только в чатах одного пула!\n\n"
                "🔤 Алиасы\n\n"
                "/cmdname [команда][суб] [алиас] — создать\n"
                "/cmdname list — список\n"
                "/cmdname del [алиас] — удалить\n"
                "/gcmdname — глобальные алиасы (ГА)\n\n"
                "💡 Пример: /cmdname nickset snick\n"
                "→ snick = /nick set"
            ),
            "help_settings": (
                "⚙️ Настройки (100)\n\n"
                "/cmd [команда] [приоритет] — права команд\n"
                "/cmd — текущие настройки\n"
                "/connect create [название] — создать пул\n"
                "/connect [peer_id] — подключиться\n"
                "/connect off — отключиться\n"
                "/import — экспорт настроек\n"
                "/import [код] — импорт\n"
                "/logchat set [id] — лог-чат\n"
                "/logchat off — отключить\n\n"
                "🌐 Только ГА\n\n"
                "/listchat — список чатов\n"
                "/msg [текст] — рассылка\n"
                "/gcmdname — глобальные алиасы\n"
                "/renamrole — переименовать 0/100\n"
                "/vlads — сменить владельца"
            ),
            "help_misc": (
                "📋 Разное\n\n"
                "/stats [юзер] — статистика\n"
                "/top — топ по сообщениям\n"
                "/getinfo [юзер] — все наказания\n"
                "/logchat log [юзер] — лог действий\n"
                "/list ban/mute/vig/bl — списки\n"
                "/roles — список ролей\n"
                "/staff — персонал\n"
                "/yhelp — ваши доступные команды\n"
                "/start — создать тикет поддержки\n\n"
                "🔢 !id — peer_id чата\n"
                "✅ !test — проверка бота\n"
                "#название — вызов заметки\n\n"
                "⏰ Форматы времени:\n"
                "30s / 5m / 2h / 3d / n (навсегда)"
            ),
        }
        return cats.get(category, "❌ Категория не найдена.")

    # ── /yhelp ───────────────────────────────────────────────────────────────

    def _cmd_category_map(self):
        return {
            "mod": ["ban","unban","mute","unmute","kick","vig","unvig","bl","unbl","delmsg","chat","trusted","list"],
            "roles": ["roles","role","newrole","delrole","staff","renamrole","vlads"],
            "notes": ["notes","nick","gnick","leader"],
            "global": ["gban","gunban","gmute","gunmute","gkick","gvig","gunvig","grole","cmdname","gcmdname"],
            "settings": ["cmd","connect","import","logchat","listchat","msg"],
            "misc": ["help","yhelp","stats","top","getinfo","start"],
        }

    def _cmd_category_title(self, cat):
        return {
            "mod":"🔨 Модерация",
            "roles":"🎭 Роли",
            "notes":"📝 Заметки/Ники",
            "global":"🌐 Глобальные",
            "settings":"⚙️ Настройки",
            "misc":"📋 Разное",
        }.get(cat, "📖 Команды")

    def _yhelp_text(self, pid, fid, cat):
        up = self.get_prio(pid, fid)
        cmds = self._cmd_category_map().get(cat, [])
        available = []
        hidden = 0
        for cmd in cmds:
            if cmd not in CMD_DESCRIPTIONS:
                continue
            needed = self.min_prio(pid, cmd)
            desc = CMD_DESCRIPTIONS[cmd][1]
            if up >= needed:
                available.append((needed, cmd, desc))
            else:
                hidden += 1
        available.sort(key=lambda x: (-x[0], x[1]))
        txt = (f"✅ Доступные команды: {self._cmd_category_title(cat)}\n"
               f"{self.mention(fid)} | {self.format_role(pid, fid)}\n"
               f"🔑 Приоритет: {up}\n\n")
        if not available:
            txt += "В этой категории у вас нет доступных команд."
        else:
            for needed, cmd, desc in available:
                txt += f"{desc} — /{cmd} ({needed})\n"
        txt += f"\nПоказано: {len(available)}"
        if hidden:
            txt += f" | Скрыто без прав: {hidden}"
        return txt

    def cmd_yhelp(self, e, pid, fid):
        up = self.get_prio(pid, fid)
        self.send(pid,
            f"✅ Ваши доступные команды\n"
            f"{self.mention(fid)} | {self.format_role(pid, fid)}\n"
            f"🔑 Приоритет: {up}\n\n"
            f"Выберите категорию:", keyboard=self._main_help_keyboard("yhelp"))

    # ── /logchat ─────────────────────────────────────────────────────────────

    def cmd_logchat(self, e, pid, fid):
        if not self.has_perm(pid, fid, "logchat"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 100.")
        text  = e.get("text","").strip()
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            settings  = self.db.get_settings(pid)
            log_chat  = settings.get("log_chat", 0)
            status    = f"Лог-чат: {log_chat}" if log_chat else "Лог-чат не настроен"
            return self.send(pid,
                f"📜 {status}\n\n"
                f"/logchat set [peer_id] — установить лог-чат\n"
                f"/logchat off — отключить\n"
                f"/logchat log [юзер] — лог действий игрока\n\n"
                f"💡 В лог-чат отправляются все модерационные действия")
        sub = parts[1].lower()
        if sub == "set":
            if len(parts) < 3:
                return self.send(pid, "❌ Укажите peer_id лог-чата.\n\n📖 /logchat set [peer_id]")
            try:
                lc = int(parts[2].strip())
            except ValueError:
                return self.send(pid, "❌ peer_id — число.")
            self.db.update_setting(pid, "log_chat", lc)
            self.send(pid, f"✅ Лог-чат установлен: {lc}")
        elif sub == "off":
            self.db.update_setting(pid, "log_chat", 0)
            self.send(pid, "✅ Лог-чат отключён.")
        elif sub == "log":
            if not self.has_perm(pid, fid, "logchat"):
                return self.send(pid, "❌ Нет прав.")
            tid, _ = self.parse_target(e)
            if not tid:
                if len(parts) >= 3:
                    try:
                        tid = int(parts[2].strip())
                    except ValueError:
                        pass
            if not tid:
                return self.send(pid, "❌ Укажите пользователя.\n\n📖 /logchat log [юзер]")
            self._send_logchat(pid, tid, fid, page=0)
        else:
            self.send(pid, "❌ /logchat set [id] / /logchat off / /logchat log [юзер]")

    def _send_logchat(self, pid, target, requester, page=0):
        PER_PAGE = 10
        total = self.db.get_audit_count(pid, target)
        logs  = self.db.get_audit_for_target(pid, target, limit=PER_PAGE, offset=page*PER_PAGE)

        txt = f"📜 Лог действий {self.mention(target)}\nВсего: {total}\n\n"
        if not logs:
            txt += "Действий нет."
        else:
            for l in logs:
                ts = fmt_msk(l["created_at"])
                txt += (f"⚡ {l['action']}\n"
                        f"   👮 {self.mention(l['actor_id'])}\n"
                        f"   🕐 {ts}\n"
                        + (f"   📝 {l['details']}\n" if l.get('details') else ""))

        kb = VkKeyboard(inline=True)
        has_prev = page > 0
        has_next = (page + 1) * PER_PAGE < total

        if has_prev:
            kb.add_callback_button("◀ Назад", color=VkKeyboardColor.SECONDARY,
                payload=json.dumps({"button": f"logchat_{target}_{page-1}"}))
        if has_next:
            kb.add_callback_button("▶ Далее", color=VkKeyboardColor.SECONDARY,
                payload=json.dumps({"button": f"logchat_{target}_{page+1}"}))

        if has_prev or has_next:
            self.send(pid, txt, keyboard=kb)
        else:
            self.send(pid, txt)

    # ── /roles ───────────────────────────────────────────────────────────────

    def cmd_roles(self, e, pid, fid):
        roles = self.db.get_roles(pid)
        oid   = self.db.get_chat_owner(pid)
        txt   = "🎭 Роли чата\n\n"
        txt  += "🌐 Глобальный Администратор (1000)\n"
        if oid:
            a100 = self.db.get_role_alias(pid, 100)
            if a100:
                em = a100.get("alias_emoji","") or ""
                nm = a100.get("alias_name","Владелец")
                txt += f"{em} {nm} (100)\n" if em else f"👑 {nm} (100)\n"
            else:
                txt += "👑 Владелец (100)\n"
        for r in roles:
            rd = dict(r)
            em = rd.get("emoji","") or ""
            txt += f"{em} {rd['role_name']} ({rd['priority']})\n" if em else f"🎭 {rd['role_name']} ({rd['priority']})\n"
        a0 = self.db.get_role_alias(pid, 0)
        if a0:
            em = a0.get("alias_emoji","") or ""
            nm = a0.get("alias_name","Пользователь")
            txt += f"{em} {nm} (0)\n" if em else f"👤 {nm} (0)\n"
        else:
            txt += "👤 Пользователь (0)\n"
        txt += f"\nВсего: {len(roles)+2}\n💡 /newrole [приоритет] [название]"
        self.send(pid, txt)

    # ── /staff ───────────────────────────────────────────────────────────────

    def cmd_staff(self, e, pid, fid):
        txt, kb = self._build_staff(pid, show_nicks=False)
        self.send(pid, txt, keyboard=kb)

    def _build_staff(self, pid, show_nicks=False):
        staff = self.db.get_chat_staff(pid)
        oid   = self.db.get_chat_owner(pid)
        rg    = {}

        # ГА — только активные
        gm = []
        for g in GLOBAL_ADMINS:
            if g in GADM_DISABLED:
                continue
            gm.append(self.mention_nick(pid, g) if show_nicks else self.mention(g))
        if gm:
            rg[1001] = {"d":"🌐 Глобальный Администратор (1000)","u":gm}

        # владелец
        if oid and oid not in GLOBAL_ADMINS:
            a100 = self.db.get_role_alias(pid, 100)
            if a100:
                em = a100.get("alias_emoji","") or ""
                nm = a100.get("alias_name","Владелец")
                d  = f"{em} {nm} (100)" if em else f"👑 {nm} (100)"
            else:
                d = "👑 Владелец (100)"
            m = self.mention_nick(pid, oid) if show_nicks else self.mention(oid)
            rg[100] = {"d":d,"u":[m]}
        elif oid and oid in GADM_DISABLED:
            # GADM_OWNER отключил ГА — показываем его как обычного с его ролью
            ri = self.db.get_user_role(pid, oid)
            if ri and ri["priority"] > 0:
                em = ri.get("emoji","") or ""
                d  = f"{em} {ri['role_name']} ({ri['priority']})" if em else f"🎭 {ri['role_name']} ({ri['priority']})"
                m  = self.mention_nick(pid, oid) if show_nicks else self.mention(oid)
                p  = ri["priority"]
                if p not in rg:
                    rg[p] = {"d":d,"u":[]}
                rg[p]["u"].append(m)

        # остальной персонал
        for s in (staff or []):
            uid = s["user_id"]
            if uid == oid or (uid in GLOBAL_ADMINS and uid not in GADM_DISABLED):
                continue
            # если это GADM_OWNER с отключёнными правами — уже добавили выше
            if uid in GADM_DISABLED and uid == oid:
                continue
            p  = s["priority"]
            em = s.get("emoji","") or ""
            d  = f"{em} {s['role_name']} ({p})" if em else f"🎭 {s['role_name']} ({p})"
            if p not in rg:
                rg[p] = {"d":d,"u":[]}
            m = self.mention_nick(pid, uid) if show_nicks else self.mention(uid)
            rg[p]["u"].append(m)

        if not rg:
            return "👥 Персонал пуст.", None

        txt = "👥 Персонал\n\n"
        for p in sorted(rg.keys(), reverse=True):
            members = "\n".join([f"— {u}" for u in rg[p]["u"]])
            txt += f"{rg[p]['d']}:\n{members}\n"

        kb = VkKeyboard(inline=True)
        if show_nicks:
            kb.add_callback_button("👤 Показать имена", color=VkKeyboardColor.PRIMARY,
                payload=json.dumps({"button":"staff_names"}))
        else:
            kb.add_callback_button("🏷 Показать ники", color=VkKeyboardColor.PRIMARY,
                payload=json.dumps({"button":"staff_nicks"}))
        return txt, kb

    def handle_staff_toggle(self, pid, show_nicks, event_id, uid, cmid):
        txt, kb = self._build_staff(pid, show_nicks=show_nicks)
        self.edit_msg(pid, cmid, txt, keyboard=kb)

    # ── /stats ───────────────────────────────────────────────────────────────

    def _build_stats_text(self, pid, target):
        name        = self.mention(target)
        role_str    = self.format_role(pid, target)
        nick        = self.db.get_display_nickname(pid, target)
        nick_str    = nick if nick else "Не установлен"
        trusted     = self.db.get_trusted(pid, target)
        trusted_str = f"🛡 Защищён (>= {trusted['min_punish_priority']})" if trusted else "Нет"
        leader_info = self.db.get_leader(pid, target)
        org_str     = f"📌 {leader_info['org_name']} | {leader_info['position']}" if leader_info else "Отсутствует"
        msg_count   = self.db.get_msg_count(pid, target)
        member_info = self.db.get_member_info(pid, target)
        if member_info and member_info.get("invited_by"):
            invited_str = self.mention(member_info["invited_by"])
        else:
            invited_str = "Неизвестно"
        joined_str = "Неизвестно"
        if member_info and member_info.get("joined_at"):
            joined_str = fmt_msk(member_info["joined_at"])

        punishments = []
        ban_info    = self.db.get_ban_info(pid, target)
        if ban_info and self.db.is_banned(pid, target):
            punishments.append(f"  🔨 Бан → {self.fmt_time(ban_info.get('ban_until',0))}")
        mute_info = self.db.get_mute_info(pid, target)
        if mute_info and self.db.is_muted(pid, target):
            punishments.append(f"  🔇 Мут → {self.fmt_time(mute_info.get('mute_until',0))}")
        vigs = self.db.get_vigs(pid, target)
        for v in vigs:
            punishments.append(f"  ⚠️ {v['vig_type'].title()}")
        warns = self.db.get_warns(pid, target)
        if warns:
            punishments.append(f"  ❗ Предупреждений: {len(warns)}")
        gban_info = self.db.get_global_ban_info(target)
        if gban_info and self.db.is_globally_banned(target):
            punishments.append(f"  🌐🔨 Глобальный бан → {self.fmt_time(gban_info.get('ban_until',0))}")
        gmute_info = self.db.get_global_mute_info(target)
        if gmute_info and self.db.is_globally_muted(target):
            punishments.append(f"  🌐🔇 Глобальный мут → {self.fmt_time(gmute_info.get('mute_until',0))}")
        punishments_str = "\n".join(punishments) if punishments else "  Нет"
        bl_entries  = self.db.get_user_blacklist_entries(target, pid)
        bl_types_map = {"chat_admin":"ЧСА","chat_local":"ЧСЛ","full_project":"ЧСП","full_strict":"ЧСС"}
        bl_str = ", ".join(list(set([bl_types_map.get(b["bl_type"],b["bl_type"]) for b in bl_entries]))) if bl_entries else "Нет"
        return (
            f"📊 Статистика\n"
            f"👤 {name}\n"
            f"🆔 VK ID: {target}\n"
            f"🏷 Ник: {nick_str}\n"
            f"🎭 Роль: {role_str}\n"
            f"🏢 Организация: {org_str}\n"
            f"🛡 Защита: {trusted_str}\n\n"
            f"💬 Сообщений в чате: {msg_count}\n"
            f"➕ Добавил в чат: {invited_str}\n"
            f"🕐 Первое появление: {joined_str}\n\n"
            f"⚠️ Активные наказания:\n{punishments_str}\n\n"
            f"🚫 Чёрный список: {bl_str}"
        )

    def _stats_keyboard(self, target):
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("📋 Показать наказания", color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":f"stats_getinfo_{target}"}))
        kb.add_line()
        kb.add_callback_button("🔄 Обновить", color=VkKeyboardColor.SECONDARY,
            payload=json.dumps({"button":f"stats_refresh_{target}"}))
        return kb

    def cmd_stats(self, e, pid, fid):
        tid, _ = self.parse_target(e)
        target = tid if tid else fid
        self.send(pid, self._build_stats_text(pid, target), keyboard=self._stats_keyboard(target))

    def handle_stats_refresh(self, pid, target, cmid=None):
        txt = self._build_stats_text(pid, target)
        kb = self._stats_keyboard(target)
        if cmid:
            self.edit_msg(pid, cmid, txt, keyboard=kb)
        else:
            self.send(pid, txt, keyboard=kb)

    # ── /getinfo ─────────────────────────────────────────────────────────────

    def cmd_getinfo(self, e, pid, fid):
        tid, _ = self.parse_target(e)
        target = tid if tid else fid
        self._send_getinfo(pid, target, fid, page=0, all_time=False)

    def _send_getinfo(self, pid, target, requester, page=0, all_time=False,
                      cmid=None, event_id=None, uid=None):
        PER_PAGE = 10
        punishments = self.db.get_all_punishments_for_user(target)
        pool_peers  = self.db.get_pool_peers_for(pid)

        if not all_time:
            active = []
            for p in punishments:
                pt = p.get("ptype","")
                if pt == "ban":
                    if self.db.is_banned(p.get("peer_id",0), target):
                        active.append(p)
                elif pt == "mute":
                    if self.db.is_muted(p.get("peer_id",0), target):
                        active.append(p)
                elif pt == "gban":
                    if self.db.is_globally_banned(target):
                        active.append(p)
                elif pt == "gmute":
                    if self.db.is_globally_muted(target):
                        active.append(p)
                elif pt in ("vig","bl","gvig","warn"):
                    active.append(p)
            punishments = active

        total = len(punishments)
        start = page * PER_PAGE
        chunk = punishments[start:start+PER_PAGE]

        mode_str  = "за всё время" if all_time else "активные"
        txt = f"🔍 Наказания {self.mention(target)} ({mode_str})\nВсего: {total}\n\n"

        bl_types_map = {"chat_admin":"ЧСА","chat_local":"ЧСЛ",
                        "full_project":"ЧСП","full_strict":"ЧСС"}
        pt_icons = {
            "ban":"🔨 Бан","mute":"🔇 Мут","vig":"⚠️ Выговор",
            "bl":"🚫 ЧС","gban":"🔨 Бан","gmute":"🔇 Мут",
            "gvig":"⚠️ Выговор","warn":"❗ Предупреждение",
        }

        if not chunk:
            txt += "Нет наказаний."
        else:
            for p in chunk:
                pt    = p.get("ptype","")
                icon  = pt_icons.get(pt, pt)
                ppid  = p.get("peer_id")
                # название чата / пул
                if ppid is None:
                    chat_name = "Глобально"
                elif ppid in pool_peers:
                    chat_name = self.get_chat_title(ppid)
                else:
                    chat_name = "-"

                until = ""
                if pt in ("ban","gban"):
                    bu = p.get("ban_until",0)
                    until = f" → {self.fmt_time(bu)}"
                elif pt in ("mute","gmute"):
                    mu = p.get("mute_until",0)
                    until = f" → {self.fmt_time(mu)}"

                reason       = p.get("reason","—")
                bl_type_str  = f" [{bl_types_map.get(p.get('bl_type',''),'')}]" if pt=="bl" else ""
                vig_type_str = f" {p.get('vig_type','').title()}" if pt in ("vig","gvig") else ""
                date_str     = fmt_msk(p.get("created_at",0)) if p.get("created_at") else ""

                txt += (f"{icon}{vig_type_str}{bl_type_str}{until}\n"
                        f"   📍 {chat_name}\n"
                        f"   📋 {reason}\n"
                        + (f"   🕐 {date_str}\n" if date_str else ""))

        kb = VkKeyboard(inline=True)
        row_added = False
        if page > 0:
            kb.add_callback_button("◀ Назад", color=VkKeyboardColor.SECONDARY,
                payload=json.dumps({"button":f"getinfo_{target}_{page-1}_{int(all_time)}"}))
            row_added = True
        if start + PER_PAGE < total:
            kb.add_callback_button("▶ Далее", color=VkKeyboardColor.SECONDARY,
                payload=json.dumps({"button":f"getinfo_{target}_{page+1}_{int(all_time)}"}))
            row_added = True
        if row_added:
            kb.add_line()

        if not all_time:
            kb.add_callback_button("📜 За всё время", color=VkKeyboardColor.PRIMARY,
                payload=json.dumps({"button":f"getinfo_{target}_0_1"}))
        else:
            kb.add_callback_button("✅ Только активные", color=VkKeyboardColor.POSITIVE,
                payload=json.dumps({"button":f"getinfo_{target}_0_0"}))

        if cmid and event_id and uid:
            self.edit_msg(pid, cmid, txt, keyboard=kb)
        else:
            self.send(pid, txt, keyboard=kb)

    # ── /list ────────────────────────────────────────────────────────────────

    def cmd_list(self, e, pid, fid):
        if not self.has_perm(pid, fid, "list"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 50+.")
        text  = e.get("text","").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            return self.send(pid,
                "📋 Списки\n\n"
                "/list ban — баны\n"
                "/list mute — муты\n"
                "/list vig — выговоры\n"
                "/list bl — чёрный список")
        sub = parts[1].strip().lower()
        if sub == "ban":
            items = self.db.get_all_bans(pid)
            if not items:
                return self.send(pid, "🔨 Список банов пуст.")
            txt = f"🔨 Баны ({len(items)}):\n\n"
            for i, b in enumerate(items[:30], 1):
                txt += (f"{i}. {self.mention(b['user_id'])}\n"
                        f"   ⏳ {self.fmt_time(b.get('ban_until',0))}\n"
                        f"   📋 {b.get('reason','—')}\n"
                        f"   🕐 {fmt_msk(b['created_at'])}\n")
            self.send(pid, txt)
        elif sub == "mute":
            items = self.db.get_all_mutes(pid)
            if not items:
                return self.send(pid, "🔇 Список мутов пуст.")
            txt = f"🔇 Муты ({len(items)}):\n\n"
            for i, m in enumerate(items[:30], 1):
                txt += (f"{i}. {self.mention(m['user_id'])}\n"
                        f"   ⏳ {self.fmt_time(m.get('mute_until',0))}\n"
                        f"   📋 {m.get('reason','—')}\n"
                        f"   🕐 {fmt_msk(m['created_at'])}\n")
            self.send(pid, txt)
        elif sub == "vig":
            items = self.db.get_vigs(pid)
            if not items:
                return self.send(pid, "⚠️ Список выговоров пуст.")
            txt = f"⚠️ Выговоры ({len(items)}):\n\n"
            for i, v in enumerate(items[:30], 1):
                txt += (f"{i}. {self.mention(v['user_id'])} — {v['vig_type'].title()}\n"
                        f"   📋 {v.get('reason','—')}\n"
                        f"   🕐 {fmt_msk(v['created_at'])}\n")
            self.send(pid, txt)
        elif sub == "bl":
            items = self.db.get_all_blacklist(pid)
            if not items:
                return self.send(pid, "🚫 Чёрный список пуст.")
            bl_types_map = {"chat_admin":"ЧСА","chat_local":"ЧСЛ",
                            "full_project":"ЧСП","full_strict":"ЧСС"}
            txt = f"🚫 Чёрный список ({len(items)}):\n\n"
            for i, b in enumerate(items[:30], 1):
                txt += (f"{i}. {self.mention(b['user_id'])} — {bl_types_map.get(b['bl_type'],b['bl_type'])}\n"
                        f"   📋 {b.get('reason','—')}\n"
                        f"   🕐 {fmt_msk(b['created_at'])}\n")
            self.send(pid, txt)
        else:
            self.send(pid, "❌ /list ban / mute / vig / bl")

    # ── /newrole ─────────────────────────────────────────────────────────────

    def cmd_newrole(self, e, pid, fid):
        if not self.has_perm(pid, fid, "newrole"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        parts = e.get("text","").split(maxsplit=2)
        if len(parts) < 3:
            return self.send(pid,
                "❌ Укажите приоритет и название.\n\n"
                "📖 /newrole [приоритет] [Эмодзи Название]\n\n"
                "💡 /newrole 50 🛡 Модератор\n"
                "💡 /newrole 0 👤 Гражданин\n"
                "💡 /newrole 100 👑 Глава\n"
                "⚠️ Диапазон: 0–100")
        try:
            pr = int(parts[1])
        except ValueError:
            return self.send(pid, "❌ Приоритет — число от 0 до 100.")
        if pr < 0 or pr > 100:
            return self.send(pid, "❌ Диапазон: 0–100.")

        # для 1-99 проверяем античит
        if 1 <= pr <= 99:
            ok, err = self.anticheat_check_role_create(pid, fid, pr)
            if not ok:
                return self.send(pid, err)
        elif pr in (0, 100):
            # только ГА может менять 0 и 100 через newrole
            if not self.is_ga(fid) and not (pr == 100 and self.db.get_chat_owner(pid) == fid):
                return self.send(pid, "❌ Изменить роль 0/100 может только ГА или владелец.")

        rt = parts[2].strip()
        emoji, rn = "", rt
        ep = re.match(
            r'^([\U0001F000-\U0001F9FF\U0001FA00-\U0001FA6F'
            r'\U0001FA70-\U0001FAFF\u2600-\u26FF\u2700-\u27BF])\s*(.+)$', rt)
        if ep:
            emoji, rn = ep.group(1), ep.group(2).strip()

        if pr in (0, 100):
            # используем role_aliases для 0 и 100
            self.db.set_role_alias(pid, pr, rn, emoji)
            d = f"{emoji} {rn} ({pr})" if emoji else f"{rn} ({pr})"
            self.send(pid, f"✅ Роль обновлена!\n🎭 «{d}»")
        else:
            ok, status = self.db.create_or_update_role(pid, rn, pr, emoji)
            if ok:
                d   = f"{emoji} {rn} ({pr})" if emoji else f"{rn} ({pr})"
                msg = f"✅ Роль {'обновлена' if status=='updated' else 'создана'}!\n🎭 «{d}»"
                if status == "created":
                    msg += f"\n\n💡 /role @user {pr}"
                self.send(pid, msg)
            else:
                self.send(pid, f"❌ {status}")

    # ── /delrole ─────────────────────────────────────────────────────────────

    def cmd_delrole(self, e, pid, fid):
        if not self.has_perm(pid, fid, "delrole"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        parts = e.get("text","").split()
        if len(parts) < 2:
            return self.send(pid, "❌ Укажите приоритет роли.\n\n📖 /delrole [приоритет]")
        try:
            pr = int(parts[1])
        except ValueError:
            return self.send(pid, "❌ Приоритет — число.")
        ok, err = self.anticheat_check_role_delete(pid, fid, pr)
        if not ok:
            return self.send(pid, err)
        r  = self.db.get_role_by_priority(pid, pr)
        d  = f"{(dict(r).get('emoji','') or '')} {dict(r)['role_name']} ({pr})" if r else f"? ({pr})"
        ok, mr = self.db.delete_role(pid, pr)
        self.send(pid, f"✅ Роль «{d.strip()}» удалена." if ok else f"❌ {mr}")

    # ── /role ────────────────────────────────────────────────────────────────

    def cmd_role(self, e, pid, fid):
        text = e.get("text","")
        tid, rest = self.parse_target(e)
        if not tid and len(text.split()) <= 1:
            return self.send(pid, f"🎭 Ваша роль: {self.format_role(pid, fid)}\n\n💡 /role @user [приоритет]")
        if tid and not rest.strip():
            return self.send(pid, f"🎭 Роль {self.mention(tid)}: {self.format_role(pid, tid)}")
        if not self.has_perm(pid, fid, "role"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 80+.")
        if not tid:
            return self.send(pid, "❌ Укажите пользователя и приоритет.")
        try:
            pa = int(rest.strip().split()[0])
        except (ValueError, IndexError):
            return self.send(pid, "❌ Укажите приоритет числом.")
        if pa == 0:
            ok, err = self.anticheat_check_role_remove(pid, fid, tid)
            if not ok:
                return self.send(pid, err)
            old = self.format_role(pid, tid)
            ok, mr = self.db.remove_role(pid, tid)
            if ok:
                self.log_action(pid, fid, tid, "Снять роль", f"{old}")
                return self.send(pid,
                    f"✅ Роль снята!\n👤 {self.mention(tid)}\n"
                    f"🎭 {old} → {self.format_role(pid, tid)}\n"
                    f"👮 {self.mention(fid)}")
            return self.send(pid, f"❌ {mr}")
        if pa < 1 or pa > 99:
            return self.send(pid, "❌ Диапазон: 1–99. Или 0 чтобы снять.")
        ok, err = self.anticheat_check_role_assign(pid, fid, tid, pa)
        if not ok:
            return self.send(pid, err)
        old = self.format_role(pid, tid)
        ok, res = self.db.assign_role(pid, tid, pa)
        if ok:
            self.log_action(pid, fid, tid, "Назначить роль", f"приоритет {pa}")
            self.send(pid,
                f"✅ Роль назначена!\n👤 {self.mention(tid)}\n"
                f"🎭 {old} → {self.format_role(pid, tid)}\n"
                f"👮 {self.mention(fid)}")
        else:
            self.send(pid, f"❌ {res}")

    # ── /ban ─────────────────────────────────────────────────────────────────

    def cmd_ban(self, e, pid, fid):
        if not self.has_perm(pid, fid, "ban"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 60+.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid,
                "❌ Укажите пользователя.\n\n"
                "📖 /ban [юзер] [время] [причина]\n"
                "⏰ 30s / 5m / 2h / 3d / n")
        ok, err = self.anticheat_check_punish(pid, fid, tid)
        if not ok:
            return self.send(pid, err)
        parts = rest.split(maxsplit=1)
        if not parts:
            return self.send(pid, "❌ Укажите время.\n⏰ 30s / 5m / 2h / 3d / n")
        dur, ht = self.parse_dur(parts[0])
        if dur is None:
            return self.send(pid, "❌ Неверный формат времени.\n⏰ 30s / 5m / 2h / 3d / n")
        reason = parts[1].strip() if len(parts) > 1 else "Не указана"
        self.db.ban_user(pid, tid, fid, reason, dur)
        self.reset_user_data(pid, tid)
        self.kick(pid, tid)
        self.log_action(pid, fid, tid, "Бан", f"{ht} | {reason}")
        self.send(pid,
            f"🔨 Бан!\n"
            f"👤 {self.mention(tid)}\n"
            f"👮 {self.mention(fid)}\n"
            f"📋 {reason}\n"
            f"⏳ {ht}")

    def cmd_unban(self, e, pid, fid):
        if not self.has_perm(pid, fid, "unban"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 60+.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.\n\n📖 /unban [юзер]")
        bi = self.db.get_ban_info(pid, tid)
        if bi:
            ok, err = self.anticheat_check_unpunish(pid, fid, bi["banned_by"])
            if not ok:
                return self.send(pid, err)
        if self.db.unban_user(pid, tid):
            self.log_action(pid, fid, tid, "Разбан")
            self.send(pid, f"✅ Разбан!\n👤 {self.mention(tid)}\n👮 {self.mention(fid)}")
        else:
            self.send(pid, f"❌ {self.mention(tid)} не в бане.")

    # ── /mute ────────────────────────────────────────────────────────────────

    def cmd_mute(self, e, pid, fid):
        if not self.has_perm(pid, fid, "mute"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 50+.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid,
                "❌ Укажите пользователя.\n\n"
                "📖 /mute [юзер] [время] [причина]\n"
                "⏰ 30s / 5m / 2h / 3d / n")
        ok, err = self.anticheat_check_punish(pid, fid, tid)
        if not ok:
            return self.send(pid, err)
        parts = rest.split(maxsplit=1)
        if not parts:
            return self.send(pid, "❌ Укажите время.")
        dur, ht = self.parse_dur(parts[0])
        if dur is None:
            return self.send(pid, "❌ Неверный формат времени.\n⏰ 30s / 5m / 2h / 3d / n")
        reason = parts[1].strip() if len(parts) > 1 else "Не указана"
        # мут = запись в mutes + бан чтобы нельзя было зайти + кик
        self.db.mute_user(pid, tid, fid, reason, dur)
        self.db.ban_user(pid, tid, fid, f"[Мут] {reason}", dur)
        try:
            cid = pid - 2000000000
            if cid > 0:
                self.vk.messages.removeChatUser(chat_id=cid, user_id=tid)
        except Exception:
            pass
        self.log_action(pid, fid, tid, "Мут", f"{ht} | {reason}")
        self.send(pid,
            f"🔇 Мут!\n"
            f"👤 {self.mention(tid)}\n"
            f"👮 {self.mention(fid)}\n"
            f"📋 {reason}\n"
            f"⏳ {ht}")

    def cmd_unmute(self, e, pid, fid):
        if not self.has_perm(pid, fid, "unmute"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 50+.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.\n\n📖 /unmute [юзер]")
        mi = self.db.get_mute_info(pid, tid)
        if mi:
            ok, err = self.anticheat_check_unpunish(pid, fid, mi["muted_by"])
            if not ok:
                return self.send(pid, err)
        self.db.unmute_user(pid, tid)
        self.db.unban_user(pid, tid)
        self.log_action(pid, fid, tid, "Размут")
        self.send(pid, f"🔊 Размут!\n👤 {self.mention(tid)}\n👮 {self.mention(fid)}")

    # ── /kick ────────────────────────────────────────────────────────────────

    def cmd_kick(self, e, pid, fid):
        if not self.has_perm(pid, fid, "kick"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 50+.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.\n\n📖 /kick [юзер] [причина]")
        ok, err = self.anticheat_check_punish(pid, fid, tid)
        if not ok:
            return self.send(pid, err)
        reason = rest.strip() or "Не указана"
        self.reset_user_data(pid, tid)
        if self.kick(pid, tid):
            self.log_action(pid, fid, tid, "Кик", reason)
            self.send(pid,
                f"👢 Кик!\n"
                f"👤 {self.mention(tid)}\n"
                f"👮 {self.mention(fid)}\n"
                f"📋 {reason}")
        else:
            self.send(pid, "❌ Не удалось кикнуть.")

    # ── /vig ─────────────────────────────────────────────────────────────────

    def cmd_vig(self, e, pid, fid):
        if not self.has_perm(pid, fid, "vig"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 50+.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.\n\n📖 /vig [юзер] [причина]")
        ok, err = self.anticheat_check_punish(pid, fid, tid)
        if not ok:
            return self.send(pid, err)
        reason = rest.strip() or "Не указана"
        vig_pending.set(fid, {"target_id":tid,"peer_id":pid,"reason":reason})
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("🔴 Грубый выговор", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":"vig_грубый выговор"}))
        kb.add_line()
        kb.add_callback_button("🟡 Выговор", color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":"vig_выговор"}))
        kb.add_line()
        kb.add_callback_button("🟢 Устный выговор", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button":"vig_устный выговор"}))
        self.send(pid, f"⚠️ Выговор для {self.mention(tid)}\n📋 {reason}\n\nВыберите тип:", keyboard=kb)

    def process_vig_choice(self, pid, fid, choice, cmid=None, event_id=None, uid=None):
        p = vig_pending.pop(fid)
        if not p:
            return
        if time.time() - p["_created"] > 60:
            return
        tid, reason = p["target_id"], p["reason"]
        self.db.add_vig(pid, tid, fid, choice, reason)
        total = len(self.db.get_vigs(pid, tid))
        self.log_action(pid, fid, tid, f"Выговор: {choice}", reason)
        msg_text = (f"⚠️ {choice.title()}!\n"
                    f"👤 {self.mention(tid)}\n"
                    f"👮 {self.mention(fid)}\n"
                    f"📋 {reason}\n"
                    f"📊 Всего выговоров: {total}")
        if cmid and event_id and uid:
            self.edit_msg(pid, cmid, msg_text)
        else:
            self.send(pid, msg_text)
        # авто-наказание
        self.check_vig_auto_punish(pid, tid, fid)

    def cmd_unvig(self, e, pid, fid):
        if not self.has_perm(pid, fid, "unvig"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 50+.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.\n\n📖 /unvig [юзер]")
        mx = self.db.get_vig_issuer_max_priority(pid, tid)
        mp = self.get_prio(pid, fid)
        if mx > mp and not self.is_ga(fid):
            return self.send(pid, f"🛡 Античит: выговор выдан с приоритетом {mx}, ваш — {mp}.")
        vigs = self.db.get_vigs(pid, tid)
        if not vigs:
            return self.send(pid, f"❌ У {self.mention(tid)} нет выговоров.")
        txt = f"⚠️ Выговоры {self.mention(tid)}:\n\n"
        kb  = VkKeyboard(inline=True)
        for i, v in enumerate(vigs[:5], 1):
            txt += f"{i}. {v['vig_type'].title()}\n   📋 {v['reason']}\n   👮 {self.mention(v['issued_by'])}\n"
            kb.add_callback_button(f"#{i}", color=VkKeyboardColor.NEGATIVE,
                payload=json.dumps({"button":f"unvig_{v['id']}"}))
            if i < len(vigs[:5]):
                kb.add_line()
        kb.add_line()
        kb.add_callback_button("✅ Снять все", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button":f"unvig_all_{tid}_{pid}"}))
        unvig_pending.set(fid, {"target_id":tid,"peer_id":pid})
        self.send(pid, txt + "\nВыберите:", keyboard=kb)

    def process_unvig_single(self, pid, fid, vig_id, cmid=None, event_id=None, uid=None):
        p = unvig_pending.pop(fid)
        if not p:
            return
        vig = self.db.get_vig_by_id(vig_id)
        if not vig:
            return
        if self.db.remove_vig_by_id(vig_id):
            self.log_action(pid, fid, vig["user_id"], "Снять выговор", vig['vig_type'])
            msg_text = (f"✅ Выговор снят!\n"
                        f"⚠️ {vig['vig_type'].title()}\n"
                        f"👤 {self.mention(vig['user_id'])}\n"
                        f"👮 {self.mention(fid)}")
            if cmid and event_id and uid:
                self.edit_msg(pid, cmid, msg_text)
            else:
                self.send(pid, msg_text)

    def process_unvig_all(self, pid, fid, tid, cmid=None, event_id=None, uid=None):
        p = unvig_pending.pop(fid)
        if not p:
            return
        if self.db.remove_vigs(pid, tid):
            self.log_action(pid, fid, tid, "Снять все выговоры")
            msg_text = f"✅ Все выговоры сняты!\n👤 {self.mention(tid)}\n👮 {self.mention(fid)}"
            if cmid and event_id and uid:
                self.edit_msg(pid, cmid, msg_text)
            else:
                self.send(pid, msg_text)
        else:
            self.send(pid, f"❌ У {self.mention(tid)} нет выговоров.")

    # ── /bl ──────────────────────────────────────────────────────────────────

    def cmd_bl(self, e, pid, fid):
        if not self.has_perm(pid, fid, "bl"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 80+.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid,
                "❌ Укажите пользователя.\n\n"
                "📖 /bl [юзер] [причина]\n\n"
                "🔹 ЧСА — Администрация (этот чат)\n"
                "🔹 ЧСЛ — Лидеры (этот чат)\n"
                "🔹 ЧСП — Проект (все чаты пула)\n"
                "🔹 ЧСС — Строгий (все чаты пула)")
        ok, err = self.anticheat_check_punish(pid, fid, tid)
        if not ok:
            return self.send(pid, err)
        reason = rest.strip() or "Не указана"
        bl_pending.set(fid, {"target_id":tid,"peer_id":pid,"reason":reason})
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("ЧСА", color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":"ЧСА"}))
        kb.add_callback_button("ЧСЛ", color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":"ЧСЛ"}))
        kb.add_line()
        kb.add_callback_button("ЧСП", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":"ЧСП"}))
        kb.add_callback_button("ЧСС", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":"ЧСС"}))
        self.send(pid,
            f"🚫 Чёрный список\n👤 {self.mention(tid)}\n📋 {reason}\n\n"
            f"ЧСА/ЧСЛ — только этот чат\n"
            f"ЧСП/ЧСС — все чаты пула\n\n⏰ 60 сек.", keyboard=kb)

    def process_bl_choice(self, pid, fid, choice, cmid=None, event_id=None, uid=None):
        p = bl_pending.pop(fid)
        if not p:
            return
        if time.time() - p["_created"] > 60:
            return
        tid, op, reason = p["target_id"], p["peer_id"], p["reason"]
        tr = self.format_role(pid, tid)
        tm = {"чса":"chat_admin","чсл":"chat_local","чсп":"full_project","чсс":"full_strict"}
        tn = {"чса":"ЧСА","чсл":"ЧСЛ","чсп":"ЧСП","чсс":"ЧСС"}
        if not self.db.add_to_blacklist(tid, op, tm[choice], fid, reason):
            return self.send(pid, "⛔ Нельзя добавить ГА в ЧС.")
        name = tn[choice]
        self.reset_user_data(pid, tid)
        self.log_action(pid, fid, tid, f"ЧС: {name}", reason)

        if choice in ("чса","чсл"):
            self.db.ban_user(op, tid, fid, f"{name}: {reason}", 0)
            self.kick(op, tid)
            msg_text = f"🚫 {self.mention(tid)}\n🎭 {tr} → {name}\n📋 {reason}"
        else:
            # только чаты пула
            pool_peers = self.get_pool_targets(op)
            for cp in pool_peers:
                self.db.ban_user(cp, tid, fid, f"{name}: {reason}", 0)
                self.reset_user_data(cp, tid)
                if self.kick(cp, tid) and cp != op:
                    self.send(cp,
                        f"🔨 Бан!\n"
                        f"👤 {self.mention(tid)}\n"
                        f"👮 {self.mention(fid)}\n"
                        f"📋 {reason}")
            msg_text = (f"🚫 {self.mention(tid)}\n🎭 {tr} → {name}\n📋 {reason}\n"
                        f"✅ Применено в {len(pool_peers)} чатах пула.")

        if cmid and event_id and uid:
            self.edit_msg(pid, cmid, msg_text)
        else:
            self.send(pid, msg_text)

    def cmd_unbl(self, e, pid, fid):
        if not self.has_perm(pid, fid, "unbl"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 80+.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.\n\n📖 /unbl [юзер]")
        unbl_pending.set(fid, {"target_id":tid,"peer_id":pid})
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("ЧСА", color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":"unbl_ЧСА"}))
        kb.add_callback_button("ЧСЛ", color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":"unbl_ЧСЛ"}))
        kb.add_line()
        kb.add_callback_button("ЧСП", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":"unbl_ЧСП"}))
        kb.add_callback_button("ЧСС", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":"unbl_ЧСС"}))
        kb.add_line()
        kb.add_callback_button("✅ Все", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button":"unbl_ВСЕ"}))
        self.send(pid, f"✅ Убрать из ЧС\n👤 {self.mention(tid)}\n\nВыберите тип:", keyboard=kb)

    def process_unbl_choice(self, pid, fid, choice, cmid=None, event_id=None, uid=None):
        p = unbl_pending.pop(fid)
        if not p:
            return
        if time.time() - p["_created"] > 60:
            return
        tid = p["target_id"]
        tm  = {"чса":"chat_admin","чсл":"chat_local","чсп":"full_project","чсс":"full_strict"}
        if choice == "все":
            self.db.remove_from_blacklist_global(tid)
            # снимаем бан во всех чатах пула
            pool_peers = self.get_pool_targets(pid)
            for cp in pool_peers:
                self.db.unban_user(cp, tid)
            msg_text = f"✅ {self.mention(tid)} убран из всех ЧС."
        else:
            self.db.remove_from_blacklist(tid, p["peer_id"], tm.get(choice))
            self.db.unban_user(pid, tid)
            msg_text = f"✅ {self.mention(tid)} убран из {choice.upper()}."

        self.log_action(pid, fid, tid, f"Снять ЧС: {choice.upper()}")
        if cmid and event_id and uid:
            self.edit_msg(pid, cmid, msg_text)
        else:
            self.send(pid, msg_text)

    # ── /gban /gunban /gmute /gunmute /gkick /gvig /gunvig /grole ────────────

    def cmd_gban(self, e, pid, fid):
        if not self.has_perm(pid, fid, "gban") and fid != GADM_OWNER:
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.\n\n📖 /gban [юзер] [время] [причина]")
        if tid in GLOBAL_ADMINS:
            return self.send(pid, "⛔ Нельзя забанить Глобального Администратора.")
        parts = rest.split(maxsplit=1)
        if not parts:
            return self.send(pid, "❌ Укажите время.")
        dur, ht = self.parse_dur(parts[0])
        if dur is None:
            return self.send(pid, "❌ Неверный формат времени.\n⏰ 30s / 5m / 2h / 3d / n")
        reason = parts[1].strip() if len(parts) > 1 else "Не указана"
        self.db.global_ban_user(tid, fid, reason, dur)
        pool_peers = self.get_pool_targets(pid)
        kicked = 0
        for peer in pool_peers:
            self.db.ban_user(peer, tid, fid, reason, dur)
            self.reset_user_data(peer, tid)
            if self.kick(peer, tid):
                kicked += 1
                if peer != pid:
                    self.send(peer,
                        f"🔨 Бан!\n"
                        f"👤 {self.mention(tid)}\n"
                        f"👮 {self.mention(fid)}\n"
                        f"📋 {reason}\n"
                        f"⏳ {ht}")
        self.log_action(pid, fid, tid, "Глобальный бан", f"{ht} | {reason}")
        self.send(pid,
            f"🔨 Бан!\n"
            f"👤 {self.mention(tid)}\n"
            f"👮 {self.mention(fid)}\n"
            f"📋 {reason}\n"
            f"⏳ {ht}\n"
            f"✅ Применено в {kicked}/{len(pool_peers)} чатах пула")

    def cmd_gunban(self, e, pid, fid):
        if not self.has_perm(pid, fid, "gunban") and fid != GADM_OWNER:
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.")
        if self.db.global_unban_user(tid):
            pool_peers = self.get_pool_targets(pid)
            for peer in pool_peers:
                self.db.unban_user(peer, tid)
            self.log_action(pid, fid, tid, "Глобальный разбан")
            self.send(pid, f"✅ Разбан!\n👤 {self.mention(tid)}\n👮 {self.mention(fid)}")
        else:
            self.send(pid, f"❌ {self.mention(tid)} не в глобальном бане.")

    def cmd_gmute(self, e, pid, fid):
        if not self.has_perm(pid, fid, "gmute") and fid != GADM_OWNER:
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.\n\n📖 /gmute [юзер] [время] [причина]")
        if tid in GLOBAL_ADMINS:
            return self.send(pid, "⛔ Нельзя замутить Глобального Администратора.")
        parts = rest.split(maxsplit=1)
        if not parts:
            return self.send(pid, "❌ Укажите время.")
        dur, ht = self.parse_dur(parts[0])
        if dur is None:
            return self.send(pid, "❌ Неверный формат времени.")
        reason = parts[1].strip() if len(parts) > 1 else "Не указана"
        self.db.global_mute_user(tid, fid, reason, dur)
        pool_peers = self.get_pool_targets(pid)
        for peer in pool_peers:
            self.db.mute_user(peer, tid, fid, reason, dur)
            self.db.ban_user(peer, tid, fid, reason, dur)
            try:
                cid = peer - 2000000000
                if cid > 0:
                    self.vk.messages.removeChatUser(chat_id=cid, user_id=tid)
            except Exception:
                pass
            if peer != pid:
                self.send(peer,
                    f"🔇 Мут!\n"
                    f"👤 {self.mention(tid)}\n"
                    f"👮 {self.mention(fid)}\n"
                    f"📋 {reason}\n"
                    f"⏳ {ht}")
        self.log_action(pid, fid, tid, "Глобальный мут", f"{ht} | {reason}")
        self.send(pid,
            f"🔇 Мут!\n"
            f"👤 {self.mention(tid)}\n"
            f"👮 {self.mention(fid)}\n"
            f"📋 {reason}\n"
            f"⏳ {ht}\n"
            f"✅ Применено в {len(pool_peers)} чатах пула")

    def cmd_gunmute(self, e, pid, fid):
        if not self.has_perm(pid, fid, "gunmute") and fid != GADM_OWNER:
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.")
        if self.db.global_unmute_user(tid):
            pool_peers = self.get_pool_targets(pid)
            for peer in pool_peers:
                self.db.unmute_user(peer, tid)
                self.db.unban_user(peer, tid)
            self.log_action(pid, fid, tid, "Глобальный размут")
            self.send(pid, f"🔊 Размут!\n👤 {self.mention(tid)}\n👮 {self.mention(fid)}")
        else:
            self.send(pid, f"❌ {self.mention(tid)} не в глобальном муте.")

    def cmd_gkick(self, e, pid, fid):
        if not self.has_perm(pid, fid, "gkick") and fid != GADM_OWNER:
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.")
        if tid in GLOBAL_ADMINS:
            return self.send(pid, "⛔ Нельзя кикнуть Глобального Администратора.")
        reason     = rest.strip() or "Не указана"
        pool_peers = self.get_pool_targets(pid)
        kicked     = 0
        for p in pool_peers:
            self.reset_user_data(p, tid)
            if self.kick(p, tid):
                kicked += 1
                if p != pid:
                    self.send(p,
                        f"👢 Кик!\n"
                        f"👤 {self.mention(tid)}\n"
                        f"👮 {self.mention(fid)}\n"
                        f"📋 {reason}")
        self.log_action(pid, fid, tid, "Глобальный кик", reason)
        self.send(pid,
            f"👢 Кик!\n"
            f"👤 {self.mention(tid)}\n"
            f"👮 {self.mention(fid)}\n"
            f"📋 {reason}\n"
            f"✅ Кикнут из {kicked}/{len(pool_peers)} чатов пула")

    def cmd_gvig(self, e, pid, fid):
        if not self.has_perm(pid, fid, "gvig") and fid != GADM_OWNER:
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.")
        if tid in GLOBAL_ADMINS:
            return self.send(pid, "⛔ Нельзя выдать выговор ГА.")
        reason = rest.strip() or "Не указана"
        gvig_pending.set(fid, {"target_id":tid,"peer_id":pid,"reason":reason})
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("🔴 Грубый выговор", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":"gvig_грубый выговор"}))
        kb.add_line()
        kb.add_callback_button("🟡 Выговор", color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button":"gvig_выговор"}))
        kb.add_line()
        kb.add_callback_button("🟢 Устный выговор", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button":"gvig_устный выговор"}))
        self.send(pid, f"⚠️ Выговор для {self.mention(tid)}\n📋 {reason}\n\nВыберите тип:", keyboard=kb)

    def process_gvig_choice(self, pid, fid, choice, cmid=None, event_id=None, uid=None):
        p = gvig_pending.pop(fid)
        if not p:
            return
        if time.time() - p["_created"] > 60:
            return
        tid, reason    = p["target_id"], p["reason"]
        pool_peers     = self.get_pool_targets(pid)
        self.db.add_global_vig(tid, fid, choice, reason)
        for peer in pool_peers:
            self.db.add_vig(peer, tid, fid, choice, reason)
            if peer != pid:
                self.send(peer,
                    f"⚠️ {choice.title()}!\n"
                    f"👤 {self.mention(tid)}\n"
                    f"👮 {self.mention(fid)}\n"
                    f"📋 {reason}")
        self.log_action(pid, fid, tid, f"Глобальный выговор: {choice}", reason)
        msg_text = (f"⚠️ {choice.title()}!\n"
                    f"👤 {self.mention(tid)}\n"
                    f"👮 {self.mention(fid)}\n"
                    f"📋 {reason}\n"
                    f"📊 Всего: {len(self.db.get_global_vigs(tid))}")
        if cmid and event_id and uid:
            self.edit_msg(pid, cmid, msg_text)
        else:
            self.send(pid, msg_text)
        self.check_vig_auto_punish(pid, tid, fid)

    def cmd_gunvig(self, e, pid, fid):
        if not self.has_perm(pid, fid, "gunvig") and fid != GADM_OWNER:
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.")
        gvigs = self.db.get_global_vigs(tid)
        if not gvigs:
            return self.send(pid, f"❌ У {self.mention(tid)} нет глобальных выговоров.")
        txt = f"⚠️ Глобальные выговоры {self.mention(tid)}:\n\n"
        kb  = VkKeyboard(inline=True)
        for i, v in enumerate(gvigs[:5], 1):
            txt += f"{i}. {v['vig_type'].title()}\n   📋 {v['reason']}\n   👮 {self.mention(v['issued_by'])}\n"
            kb.add_callback_button(f"#{i}", color=VkKeyboardColor.NEGATIVE,
                payload=json.dumps({"button":f"gunvig_{v['id']}"}))
            if i < len(gvigs[:5]):
                kb.add_line()
        kb.add_line()
        kb.add_callback_button("✅ Снять все", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button":f"gunvig_all_{tid}"}))
        gunvig_pending.set(fid, {"target_id":tid,"peer_id":pid})
        self.send(pid, txt + "\nВыберите:", keyboard=kb)

    def process_gunvig_single(self, pid, fid, vig_id, cmid=None, event_id=None, uid=None):
        p = gunvig_pending.pop(fid)
        if not p:
            return
        vig = self.db.get_global_vig_by_id(vig_id)
        if not vig:
            return
        if self.db.remove_global_vig_by_id(vig_id):
            self.log_action(pid, fid, vig["user_id"], "Снять глоб. выговор", vig['vig_type'])
            msg_text = (f"✅ Глобальный выговор снят!\n"
                        f"⚠️ {vig['vig_type'].title()}\n"
                        f"👤 {self.mention(vig['user_id'])}\n"
                        f"👮 {self.mention(fid)}")
            if cmid and event_id and uid:
                self.edit_msg(pid, cmid, msg_text)
            else:
                self.send(pid, msg_text)

    def process_gunvig_all(self, pid, fid, tid, cmid=None, event_id=None, uid=None):
        p = gunvig_pending.pop(fid)
        if not p:
            return
        if self.db.remove_global_vigs(tid):
            self.log_action(pid, fid, tid, "Снять все глоб. выговоры")
            msg_text = f"✅ Все глобальные выговоры сняты!\n👤 {self.mention(tid)}\n👮 {self.mention(fid)}"
            if cmid and event_id and uid:
                self.edit_msg(pid, cmid, msg_text)
            else:
                self.send(pid, msg_text)
        else:
            self.send(pid, f"❌ У {self.mention(tid)} нет выговоров.")

    def cmd_grole(self, e, pid, fid):
        if not self.has_perm(pid, fid, "grole") and fid != GADM_OWNER:
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.\n\n📖 /grole [юзер] [приоритет]")
        if tid in GLOBAL_ADMINS and fid != GADM_OWNER:
            return self.send(pid, "⛔ ГА защищён.")
        try:
            pa = int(rest.strip().split()[0])
        except (ValueError, IndexError):
            return self.send(pid, "❌ Укажите приоритет числом.")
        pool_peers = self.get_pool_targets(pid)
        assigned = 0; removed = 0
        if pa == 0:
            for peer in pool_peers:
                ok, _ = self.db.remove_role(peer, tid)
                if ok:
                    removed += 1
            self.log_action(pid, fid, tid, "Глобальная роль", "снята")
            return self.send(pid,
                f"✅ Роль снята!\n"
                f"👤 {self.mention(tid)}\n"
                f"👮 {self.mention(fid)}\n"
                f"Снято в {removed}/{len(pool_peers)} чатах пула")
        for peer in pool_peers:
            role = self.db.get_role_by_priority(peer, pa)
            if role:
                ok, _ = self.db.assign_role(peer, tid, pa)
                if ok:
                    assigned += 1
        self.log_action(pid, fid, tid, "Глобальная роль", f"приоритет {pa}")
        self.send(pid,
            f"✅ Роль назначена!\n"
            f"👤 {self.mention(tid)} → {pa}\n"
            f"👮 {self.mention(fid)}\n"
            f"Назначено в {assigned}/{len(pool_peers)} чатах пула")

    # ── остальные команды ────────────────────────────────────────────────────

    def cmd_delmsg(self, e, pid, fid):
        if not self.has_perm(pid, fid, "delmsg"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 50+.")
        parts = e.get("text","").split()
        if len(parts) < 2:
            return self.send(pid, "❌ Укажите количество.\n\n📖 /delmsg [1-100]")
        try:
            count = int(parts[1])
            if not (1 <= count <= 100):
                return self.send(pid, "❌ Диапазон: 1–100.")
        except ValueError:
            return self.send(pid, "❌ Укажите число от 1 до 100.")
        try:
            msgs = self.vk.messages.getHistory(peer_id=pid, count=count+5).get("items",[])
            bot_msgs = [m["conversation_message_id"] for m in msgs
                        if m.get("from_id") == -self.group_id
                        and m.get("conversation_message_id")]
            if not bot_msgs:
                return self.send(pid, "❌ Нет сообщений бота для удаления.")
            bot_msgs = bot_msgs[:count]
            for i in range(0, len(bot_msgs), 100):
                batch = bot_msgs[i:i+100]
                try:
                    self.vk.messages.delete(
                        cmids=",".join(map(str, batch)),
                        peer_id=pid, delete_for_all=1, group_id=self.group_id)
                except Exception as ex:
                    logger.error(f"delmsg batch err: {ex}")
            self.send(pid, f"🗑 Удалено {len(bot_msgs)} сообщений бота.")
        except Exception as ex:
            logger.error(f"delmsg err: {ex}")
            self.send(pid, "❌ Ошибка при удалении.")

    def cmd_top(self, e, pid, fid):
        top = self.db.get_top_msg(pid, 15)
        if not top:
            return self.send(pid, "📊 Статистика пуста.")
        medals = {1:"🥇",2:"🥈",3:"🥉"}
        txt    = "🏆 Топ по сообщениям\n\n"
        for i, t in enumerate(top, 1):
            txt += f"{medals.get(i,f'{i}.')} {self.mention(t['user_id'])} — {t['count']} сообщений\n"
        self.send(pid, txt)

    def cmd_connect(self, e, pid, fid):
        if not self.has_perm(pid, fid, "connect"):
            return self.send(pid, "❌ Только для владельца чата (100).")
        parts = e.get("text","").split(maxsplit=2)
        if len(parts) < 2:
            if self.db.is_connected(pid):
                pool  = self.db.get_pool_peers(pid)
                pname = self.db.get_pool_name(pid)
                ns    = f" «{pname}»" if pname else ""
                return self.send(pid,
                    f"🔗 Пул{ns}\n\nЧатов: {len(pool)}\n" +
                    "\n".join([f"— {p}" for p in pool]) +
                    f"\n\n/connect off — отключиться")
            return self.send(pid,
                "🔗 Пул чатов\n\nЧат не подключён.\n\n"
                "📖 /connect create [название] — создать\n"
                "/connect [peer_id] — подключиться\n"
                "/connect off — отключиться")
        arg = parts[1].lower()
        if arg == "create":
            pname = parts[2].strip() if len(parts) > 2 else ""
            self.db.connect_to_pool(pid, pid, pname)
            self.db.update_setting(pid, "connected", 1)
            ns = f" «{pname}»" if pname else ""
            self.send(pid, f"✅ Пул{ns} создан!\n🔑 /connect {pid}")
        elif arg == "off":
            self.db.disconnect_from_pool(pid)
            self.db.update_setting(pid, "connected", 0)
            self.send(pid, "✅ Чат отключён от пула.")
        else:
            try:
                op = int(arg)
            except ValueError:
                return self.send(pid, "❌ Укажите peer_id или create/off.")
            pname = self.db.get_pool_name(op)
            self.db.connect_to_pool(pid, op, pname)
            self.db.update_setting(pid, "connected", 1)
            ns = f" «{pname}»" if pname else ""
            self.send(pid, f"✅ Подключено к пулу{ns} {op}.")

    def cmd_import(self, e, pid, fid):
        if not self.has_perm(pid, fid, "import"):
            return self.send(pid, "❌ Только для владельца чата (100).")
        parts = e.get("text","").split()
        if len(parts) < 2:
            code = self.db.create_import_code(pid)
            return self.send(pid,
                f"📥 Импорт настроек\n\n🔑 Код: {code}\n\n"
                f"В другом чате:\n/import {code}\n\n⏰ 10 минут")
        code = parts[1].strip().upper()
        src  = self.db.get_import_source(code)
        if not src:
            return self.send(pid, "❌ Код не найден или истёк.")
        if src == pid:
            return self.send(pid, "❌ Нельзя импортировать в тот же чат.")
        if self.db.import_settings(src, pid):
            self.send(pid, f"✅ Настройки импортированы из {src}!")
        else:
            self.send(pid, "❌ Ошибка импорта.")

    def cmd_msg(self, e, pid, fid):
        if not self.is_ga(fid):
            return
        parts = e.get("text","").split(maxsplit=1)
        if len(parts) < 2:
            return self.send(pid, "❌ Укажите текст.\n\n📖 /msg [текст]")
        text      = parts[1].strip()
        all_peers = self.db.get_all_chat_peers()
        def broadcast():
            for peer in all_peers:
                try:
                    self.vk.messages.send(
                        peer_id=peer,
                        message=f"📢 Сообщение от Администрации:\n\n{text}",
                        random_id=random.randint(0, 2**31))
                    time.sleep(0.05)
                except Exception:
                    pass
        threading.Thread(target=broadcast, daemon=True).start()
        self.send(pid, f"📢 Рассылка запущена.\n📊 Чатов: {len(all_peers)}")

    def cmd_listchat(self, e, pid, fid):
        if not self.is_ga(fid):
            return self.send(pid, "❌ Только для Глобальных Администраторов.")
        chats = self.db.get_all_chats_with_info()
        if not chats:
            return self.send(pid, "📋 Нет чатов.")
        txt      = f"📋 Все чаты ({len(chats)})\n\n"
        peer_ids = [c['peer_id'] for c in chats[:50]]
        titles   = {}
        try:
            ci = self.vk.messages.getConversationsById(
                peer_ids=",".join(map(str, peer_ids)), group_id=self.group_id)
            for item in ci.get("items",[]):
                p = item.get("peer",{}).get("id")
                t = item.get("chat_settings",{}).get("title","?")
                if p:
                    titles[p] = t
        except Exception:
            pass
        for i, chat in enumerate(chats[:50], 1):
            peer  = chat['peer_id']
            owner = chat['owner_id']
            title = titles.get(peer, f"Беседа {peer}")
            txt  += f"{i}. {title}\n   👤 {self.mention(owner)} | {peer}\n"
        self.send(pid, txt)

    def cmd_vlads(self, e, pid, fid):
        ok, err = self.anticheat_check_owner_change(pid, fid)
        if not ok:
            return self.send(pid, err)
        tid, _ = self.parse_target(e)
        if not tid or tid <= 0:
            return self.send(pid, "❌ Укажите пользователя.\n\n📖 /vlads [юзер]")
        old_owner = self.db.get_chat_owner(pid)
        if old_owner and old_owner != tid:
            self.db.remove_role(pid, old_owner)
        self.db.set_chat_owner(pid, tid)
        self.log_action(pid, fid, tid, "Смена владельца")
        self.send(pid, f"👑 Новый владелец!\n👤 {self.mention(tid)}\n👮 {self.mention(fid)}")

    def cmd_renamrole(self, e, pid, fid):
        if not self.is_ga(fid):
            return self.send(pid, "❌ Только для Глобальных Администраторов.")
        parts = e.get("text","").split(maxsplit=2)
        if len(parts) < 3:
            return self.send(pid,
                "❌ Укажите приоритет и название.\n\n"
                "📖 /renamrole [0|100] [Эмодзи Название]\n\n"
                "💡 /renamrole 0 👤 Гражданин\n"
                "💡 /renamrole 100 👑 Глава")
        try:
            priority = int(parts[1])
        except ValueError:
            return self.send(pid, "❌ Приоритет — число (0 или 100).")
        if priority not in (0, 100):
            return self.send(pid, "❌ Только 0 или 100.")
        rt = parts[2].strip()
        emoji, rn = "", rt
        ep = re.match(
            r'^([\U0001F000-\U0001F9FF\U0001FA00-\U0001FA6F'
            r'\U0001FA70-\U0001FAFF\u2600-\u26FF\u2700-\u27BF])\s*(.+)$', rt)
        if ep:
            emoji, rn = ep.group(1), ep.group(2).strip()
        self.db.set_role_alias(pid, priority, rn, emoji)
        d        = f"{emoji} {rn} ({priority})" if emoji else f"{rn} ({priority})"
        original = "Пользователь" if priority == 0 else "Владелец"
        self.send(pid, f"✅ Переименовано!\n«{original} ({priority})» → «{d}»")

    def cmd_cmd(self, e, pid, fid):
        if not self.has_perm(pid, fid, "cmd"):
            return self.send(pid, "❌ Только для владельца чата (100).")
        parts = e.get("text","").split()
        if len(parts) < 2:
            perms = self.db.get_all_cmd_permissions(pid)
            pt    = "".join([f"/{p['command']} — {p['min_priority']}\n" for p in perms]) or "Настроек нет.\n"
            dt    = "".join([f"/{c} — {p}\n" for c, p in
                             sorted(DEFAULT_CMD_PERMISSIONS.items(), key=lambda x: -x[1])])
            return self.send(pid,
                f"⚙️ Права на команды\n\n"
                f"📋 Настроенные:\n{pt}\n"
                f"📋 По умолчанию:\n{dt}\n"
                f"📖 /cmd [команда] [приоритет]")
        if len(parts) < 3:
            return self.send(pid, "❌ Укажите команду и приоритет.")
        cn = parts[1].lower().replace("/","")
        try:
            mp = int(parts[2])
        except ValueError:
            return self.send(pid, "❌ Приоритет — число.")
        if mp < 0 or mp > 1000:
            return self.send(pid, "❌ Диапазон: 0–1000.")
        if cn not in DEFAULT_CMD_PERMISSIONS:
            return self.send(pid, f"❌ Команда «{cn}» не существует.")
        self.db.set_cmd_permission(pid, cn, mp)
        self.send(pid, f"✅ /{cn} — минимальный приоритет: {mp}")

    def cmd_notes(self, e, pid, fid):
        text  = e.get("text","").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            return self.send(pid,
                "📝 Заметки чата\n\n"
                "/notes list — список\n"
                "/notes create [название] [текст] — создать\n"
                "/notes [название] — показать\n"
                "/notes del [название] — удалить\n"
                "#название — быстрый вызов")
        args = parts[1].strip()
        al   = args.lower()
        if al == "list":
            notes = self.db.get_all_notes(pid)
            if not notes:
                return self.send(pid, "📝 Заметок нет.")
            txt = f"📝 Заметки ({len(notes)}):\n\n"
            for i, n in enumerate(notes, 1):
                txt += f"{i}. #{n['note_name']}{' 📎' if n.get('attachments') else ''}\n"
            txt += "\n💡 Вызов: #название"
            return self.send(pid, txt)
        if al.startswith("create "):
            if not self.has_perm(pid, fid, "notes"):
                return self.send(pid, "❌ Нет прав (50+).")
            cr = args[7:].strip()
            if not cr:
                return self.send(pid, "❌ Укажите название и текст.")
            cp = cr.split(maxsplit=1)
            nn = cp[0].strip().lower()
            nt = cp[1].strip() if len(cp) > 1 else ""
            if not re.match(r'^[a-zа-яё0-9_\-]+$', nn):
                return self.send(pid, "❌ Название: буквы, цифры, _ и -")
            att = self.extract_attachments(e)
            if not nt and not att:
                return self.send(pid, "❌ Укажите текст или прикрепите файл.")
            if self.db.get_note(pid, nn):
                ok, mr = self.db.update_note(pid, nn, nt, att, fid)
                self.send(pid, f"✅ Заметка #{nn} обновлена." if ok else f"❌ {mr}")
            else:
                ok, mr = self.db.create_note(pid, nn, nt, att, fid)
                self.send(pid, f"✅ Заметка #{nn} создана!\n💡 #{nn}" if ok else f"❌ {mr}")
            return
        if al.startswith("del "):
            if not self.has_perm(pid, fid, "notes"):
                return self.send(pid, "❌ Нет прав (50+).")
            nn = args[4:].strip().lower()
            if not nn:
                return self.send(pid, "❌ Укажите название.")
            ok, mr = self.db.delete_note(pid, nn)
            self.send(pid, f"✅ Заметка #{nn} удалена." if ok else f"❌ {mr}")
            return
        note = self.db.get_note(pid, al.strip())
        if note:
            att = note.get("attachments","") or None
            self.send(pid, note.get("note_text","") or f"#{al.strip()}",
                      attachment=att if att else None)
        else:
            self.send(pid, f"❌ Заметка #{al.strip()} не найдена.\n\n💡 /notes list")

    def cmd_chat(self, e, pid, fid):
        if not self.has_perm(pid, fid, "chat"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 80+.")
        text  = e.get("text","").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            settings = self.db.get_settings(pid)
            status   = "🔒 ЗАКРЫТ" if settings.get("chat_closed") else "🔓 ОТКРЫТ"
            return self.send(pid,
                f"🚪 Статус: {status}\n\n"
                f"/chat open — открыть\n"
                f"/chat close — закрыть\n\n"
                f"💡 Закрытый чат: пишут только 80+")
        arg = parts[1].strip().lower()
        if arg == "close":
            self.db.update_setting(pid, "chat_closed", 1)
            self.log_action(pid, fid, None, "Закрыть чат")
            self.send(pid, f"🔒 Чат закрыт!\n👮 {self.mention(fid)}")
        elif arg == "open":
            self.db.update_setting(pid, "chat_closed", 0)
            self.log_action(pid, fid, None, "Открыть чат")
            self.send(pid, f"🔓 Чат открыт!\n👮 {self.mention(fid)}")
        else:
            self.send(pid, "❌ /chat open / /chat close")

    def cmd_nick(self, e, pid, fid):
        text  = e.get("text","").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            nick = self.db.get_display_nickname(pid, fid)
            if nick:
                return self.send(pid,
                    f"🏷 Ваш ник: {nick}\n\n"
                    f"/nick set [ник] — изменить\n"
                    f"/nick remove — убрать\n"
                    f"/nick list — все ники")
            return self.send(pid,
                f"🏷 У вас нет ника.\n\n"
                f"/nick set [ник] — установить\n"
                f"/nick set [юзер] [ник] — другому (80+)\n"
                f"/nick list — все ники")
        args = parts[1].strip()
        al   = args.lower()
        if al == "list":
            nicks = self.db.get_all_nicknames(pid)
            if not nicks:
                return self.send(pid, "🏷 Ников нет.")
            txt = f"🏷 Ники чата ({len(nicks)}):\n\n"
            for i, n in enumerate(nicks, 1):
                txt += f"{i}. {self.mention(n['user_id'])} — {n['nickname']}\n"
            return self.send(pid, txt)
        if al.startswith("set"):
            sr = args[3:].strip()
            if not sr:
                return self.send(pid, "❌ Укажите ник.")
            tid = self.parse_target_from_rest(sr, e)
            if tid and tid != fid:
                if self.get_prio(pid, fid) < 80:
                    return self.send(pid, "❌ Для смены ника другому нужен приоритет 80+.")
                nt = re.sub(r'\[id\d+\|[^\]]*\]','',sr).strip()
                np = nt.split()
                if np:
                    try:
                        int(np[0]); np = np[1:]
                    except ValueError:
                        pass
                nick = " ".join(np).strip()
                if not nick:
                    return self.send(pid, "❌ Укажите ник после пользователя.")
                if len(nick) > 32:
                    return self.send(pid, "❌ Ник — не более 32 символов.")
                self.db.set_nickname(pid, tid, nick)
                self.send(pid, f"🏷 Ник изменён!\n👤 {self.mention(tid)}\n✏️ «{nick}»\n👮 {self.mention(fid)}")
            else:
                if tid == fid:
                    nt = re.sub(r'\[id\d+\|[^\]]*\]','',sr).strip()
                    np = nt.split()
                    if np:
                        try:
                            int(np[0]); np = np[1:]
                        except ValueError:
                            pass
                    nick = " ".join(np).strip()
                else:
                    nick = sr.strip()
                if not nick:
                    return self.send(pid, "❌ Укажите ник.")
                if len(nick) > 32:
                    return self.send(pid, "❌ Ник — не более 32 символов.")
                self.db.set_nickname(pid, fid, nick)
                self.send(pid, f"🏷 Ник установлен!\n✏️ «{nick}»")
            return
        if al.startswith("remove"):
            rr  = args[6:].strip()
            tid = self.parse_target_from_rest(rr, e) if rr else None
            if not tid:
                reply = e.get("reply_message")
                fwd   = e.get("fwd_messages",[])
                if reply:
                    tid = reply.get("from_id")
                elif fwd:
                    tid = fwd[0].get("from_id")
            if tid and tid > 0 and tid != fid:
                if self.get_prio(pid, fid) < 80:
                    return self.send(pid, "❌ Для снятия ника другому нужен приоритет 80+.")
                if self.db.remove_nickname(pid, tid):
                    self.send(pid, f"✅ Ник {self.mention(tid)} убран.\n👮 {self.mention(fid)}")
                else:
                    self.send(pid, f"❌ У {self.mention(tid)} нет ника.")
            else:
                if self.db.remove_nickname(pid, fid):
                    self.send(pid, "✅ Ваш ник убран.")
                else:
                    self.send(pid, "❌ У вас нет ника.")
            return
        self.send(pid,
            "❌ Неверный аргумент.\n\n"
            "/nick — ваш ник\n"
            "/nick list — список\n"
            "/nick set [ник] — установить\n"
            "/nick remove — убрать")

    def cmd_gnick(self, e, pid, fid):
        if not self.has_perm(pid, fid, "gnick"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        text  = e.get("text","").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            return self.send(pid,
                "🌐 Глобальные ники\n\n"
                "/gnick set [юзер] [ник] — установить\n"
                "/gnick remove [юзер] — убрать")
        args = parts[1].strip()
        al   = args.lower()
        if al.startswith("set"):
            sr = args[3:].strip()
            if not sr:
                return self.send(pid, "❌ Укажите пользователя и ник.")
            tid = self.parse_target_from_rest(sr, e)
            if not tid:
                return self.send(pid, "❌ Не могу найти пользователя.")
            nt = re.sub(r'\[id\d+\|[^\]]*\]','',sr).strip()
            np = nt.split()
            if np:
                try:
                    int(np[0]); np = np[1:]
                except ValueError:
                    pass
            nick = " ".join(np).strip()
            if not nick:
                return self.send(pid, "❌ Укажите ник.")
            if len(nick) > 32:
                return self.send(pid, "❌ Ник — не более 32 символов.")
            self.db.set_global_nickname(tid, nick)
            self.send(pid, f"🌐 Глобальный ник!\n👤 {self.mention(tid)}\n✏️ «{nick}»\n👮 {self.mention(fid)}")
            return
        if al.startswith("remove"):
            rr  = args[6:].strip()
            tid = self.parse_target_from_rest(rr, e)
            if not tid:
                reply = e.get("reply_message")
                fwd   = e.get("fwd_messages",[])
                if reply:
                    tid = reply.get("from_id")
                elif not tid and fwd:
                    tid = fwd[0].get("from_id")
            if not tid or tid <= 0:
                return self.send(pid, "❌ Укажите пользователя.")
            if self.db.remove_global_nickname(tid):
                self.send(pid, f"✅ Глобальный ник {self.mention(tid)} убран.\n👮 {self.mention(fid)}")
            else:
                self.send(pid, f"❌ У {self.mention(tid)} нет глобального ника.")
            return
        self.send(pid, "❌ /gnick set [юзер] [ник]\n/gnick remove [юзер]")

    def cmd_trusted(self, e, pid, fid):
        if not self.has_perm(pid, fid, "trusted"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        text  = e.get("text","").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            tl = self.db.get_trusted_list(pid)
            if not tl:
                txt = "🛡 Защищённых нет.\n\n"
            else:
                txt = "🛡 Защищённые:\n\n"
                for i, t in enumerate(tl, 1):
                    txt += f"{i}. {self.mention(t['user_id'])} — {t['min_punish_priority']}+\n   👤 {self.mention(t['set_by'])}\n"
                txt += f"\nВсего: {len(tl)}\n\n"
            txt += "/trusted [юзер] [приоритет] — защитить\n/trusted [юзер] off — снять"
            return self.send(pid, txt)
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ Укажите пользователя.")
        if self.is_ga(tid):
            return self.send(pid, "⛔ ГА уже защищён (1000).")
        rest = rest.strip()
        if not rest:
            trusted = self.db.get_trusted(pid, tid)
            if trusted:
                self.send(pid,
                    f"🛡 {self.mention(tid)} защищён!\n"
                    f"🔒 Наказать: >= {trusted['min_punish_priority']}\n"
                    f"👤 {self.mention(trusted['set_by'])}")
            else:
                self.send(pid, f"👤 {self.mention(tid)} не защищён.")
            return
        if rest.lower() == "off":
            if self.db.remove_trusted(pid, tid):
                self.send(pid, f"✅ Защита снята!\n👤 {self.mention(tid)}\n👮 {self.mention(fid)}")
            else:
                self.send(pid, f"❌ {self.mention(tid)} не был защищён.")
            return
        try:
            min_p = int(rest.split()[0])
        except (ValueError, IndexError):
            return self.send(pid, "❌ Укажите число (1–1000) или off.")
        if min_p < 1 or min_p > 1000:
            return self.send(pid, "❌ Диапазон: 1–1000.")
        up = self.get_prio(pid, fid)
        if min_p > up and not self.is_ga(fid):
            return self.send(pid, f"🛡 Античит: нельзя защиту ({min_p}) выше вашего ({up}).")
        self.db.set_trusted(pid, tid, min_p, fid)
        self.send(pid,
            f"🛡 Защита установлена!\n"
            f"👤 {self.mention(tid)}\n"
            f"🔒 Наказать: >= {min_p}\n"
            f"👮 {self.mention(fid)}")

    def cmd_leader(self, e, pid, fid):
        if not self.has_perm(pid, fid, "leader"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 80+.")
        text  = e.get("text","").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            leaders = self.db.get_leader_list(pid)
            if not leaders:
                txt = "🏢 Организации: пусто\n\n"
            else:
                txt = "🏢 Организации:\n\n"
                for i, l in enumerate(leaders, 1):
                    txt += (f"{i}. {self.mention(l['user_id'])}\n"
                            f"   📌 {l['org_name']} | {l['position']}\n"
                            f"   👤 {self.mention(l['set_by'])}\n")
                txt += f"\nВсего: {len(leaders)}\n\n"
            txt += "/leader set [юзер] Орг | Должность\n/leader rem [юзер]"
            return self.send(pid, txt)
        args = parts[1].strip()
        al   = args.lower()
        if al.startswith("set"):
            sr = args[3:].strip()
            if not sr:
                return self.send(pid, "❌ Укажите пользователя и должность.")
            tid = self.parse_target_from_rest(sr, e)
            if not tid:
                return self.send(pid, "❌ Не могу найти пользователя.")
            clean = re.sub(r'\[id\d+\|[^\]]*\]','',sr).strip()
            cp    = clean.split()
            if cp:
                try:
                    int(cp[0]); clean = " ".join(cp[1:])
                except ValueError:
                    pass
            if "|" not in clean:
                return self.send(pid, "❌ Нужен разделитель |\n\n💡 /leader set @user МВД | Нач.")
            org_parts = clean.split("|",1)
            org_name  = org_parts[0].strip()
            position  = org_parts[1].strip()
            if not org_name or not position:
                return self.send(pid, "❌ Организация и должность не могут быть пустыми.")
            if len(org_name) > 50:
                return self.send(pid, "❌ Не более 50 символов.")
            if len(position) > 50:
                return self.send(pid, "❌ Не более 50 символов.")
            self.db.set_leader(pid, tid, org_name, position, fid)
            self.send(pid,
                f"✅ Должность назначена!\n"
                f"👤 {self.mention(tid)}\n"
                f"📌 {org_name} | {position}\n"
                f"👮 {self.mention(fid)}")
            return
        if al.startswith("rem"):
            rr  = args[3:].strip()
            tid = self.parse_target_from_rest(rr, e)
            if not tid:
                return self.send(pid, "❌ Укажите пользователя.")
            if self.db.remove_leader(pid, tid):
                self.send(pid, f"✅ Должность снята!\n👤 {self.mention(tid)}\n👮 {self.mention(fid)}")
            else:
                self.send(pid, f"❌ У {self.mention(tid)} нет должности.")
            return
        self.send(pid, "❌ /leader set [юзер] Орг | Должность\n/leader rem [юзер]")

    def cmd_cmdname(self, e, pid, fid):
        if not self.has_perm(pid, fid, "cmdname"):
            return self.send(pid, "❌ Нет прав. Нужен приоритет 90+.")
        text  = e.get("text","").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            return self.send(pid,
                "🔤 Алиасы команд\n\n"
                "/cmdname [команда][суб] [алиас] — создать\n"
                "  Пример: /cmdname nickset snick\n"
                "  Пример: /cmdname ban /бан\n"
                "/cmdname list — список\n"
                "/cmdname del [алиас] — удалить\n\n"
                "💡 Составные:\n"
                "nickset → /nick set\n"
                "notescreate → /notes create\n"
                "leaderrem → /leader rem")
        args = parts[1].strip()
        al   = args.lower()
        if al == "list":
            aliases = self.db.get_cmd_aliases(pid)
            if not aliases:
                return self.send(pid, "🔤 Алиасов нет.")
            txt = "🔤 Алиасы:\n\n"
            for a in aliases:
                sub  = a.get("subcmd","") or ""
                full = f"/{a['original_cmd']}" + (f" {sub}" if sub else "")
                txt += f"{full} → {a['alias']}\n"
            return self.send(pid, txt)
        if al.startswith("del "):
            atd = args[4:].strip().lower()
            if not atd:
                return self.send(pid, "❌ Укажите алиас.")
            if self.db.remove_cmd_alias(pid, atd):
                self.send(pid, f"✅ Алиас «{atd}» удалён.")
            else:
                self.send(pid, f"❌ Алиас «{atd}» не найден.")
            return
        tokens = args.split()
        if len(tokens) < 2:
            return self.send(pid, "❌ Укажите команду и алиас.\n\n💡 /cmdname nickset snick")
        raw_cmd    = tokens[0].lower().replace("/","")
        alias_list = [t.strip().lower() for t in tokens[1:] if t.strip()]
        cmd, subcmd = self._parse_cmd_subcmd(raw_cmd)
        if not cmd:
            return self.send(pid, f"❌ Команда «{raw_cmd}» не найдена.")
        added = []
        for alias in alias_list:
            if self.db.add_cmd_alias(pid, cmd, subcmd, alias):
                added.append(alias)
        full = f"/{cmd}" + (f" {subcmd}" if subcmd else "")
        if added:
            self.send(pid, f"✅ Алиасы для {full}:\n" + "\n".join(added))
        else:
            self.send(pid, "❌ Не удалось добавить.")

    def _parse_cmd_subcmd(self, raw):
        raw = raw.replace("/","").strip()
        for cmd, subs in CMD_SUBCOMMANDS.items():
            if raw == cmd:
                return cmd, ""
            for sub in subs:
                if raw == cmd + sub:
                    return cmd, sub
        if raw in DEFAULT_CMD_PERMISSIONS:
            return raw, ""
        return None, None

    def cmd_gcmdname(self, e, pid, fid):
        if not self.is_ga(fid):
            return self.send(pid, "❌ Только для Глобальных Администраторов.")
        text  = e.get("text","").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            return self.send(pid,
                "🌐🔤 Глобальные алиасы\n\n"
                "/gcmdname [команда][суб] [алиас]\n"
                "  Пример: /gcmdname nickset snick\n"
                "/gcmdname list\n"
                "/gcmdname del [алиас]")
        args = parts[1].strip()
        al   = args.lower()
        if al == "list":
            aliases = self.db.get_global_cmd_aliases()
            if not aliases:
                return self.send(pid, "🌐🔤 Глобальных алиасов нет.")
            txt = "🌐🔤 Глобальные алиасы:\n\n"
            for a in aliases:
                sub  = a.get("subcmd","") or ""
                full = f"/{a['original_cmd']}" + (f" {sub}" if sub else "")
                txt += f"{full} → {a['alias']}\n"
            return self.send(pid, txt)
        if al.startswith("del "):
            atd = args[4:].strip().lower()
            if not atd:
                return self.send(pid, "❌ Укажите алиас.")
            if self.db.remove_global_cmd_alias(atd):
                self.send(pid, f"✅ Глобальный алиас «{atd}» удалён.")
            else:
                self.send(pid, f"❌ Не найден.")
            return
        tokens = args.split()
        if len(tokens) < 2:
            return self.send(pid, "❌ Укажите команду и алиасы.")
        raw_cmd    = tokens[0].lower().replace("/","")
        alias_list = [t.strip().lower() for t in tokens[1:] if t.strip()]
        cmd, subcmd = self._parse_cmd_subcmd(raw_cmd)
        if not cmd:
            return self.send(pid, f"❌ Команда «{raw_cmd}» не найдена.")
        added = []
        for alias in alias_list:
            if self.db.add_global_cmd_alias(cmd, subcmd, alias):
                added.append(alias)
        full = f"/{cmd}" + (f" {subcmd}" if subcmd else "")
        if added:
            self.send(pid, f"✅ Глобальные алиасы для {full}:\n" + "\n".join(added))
        else:
            self.send(pid, "❌ Не удалось добавить.")

    # ── поддержка ────────────────────────────────────────────────────────────

    def cmd_start(self, e, pid, fid):
        if pid != fid:
            return
        ot = self.db.get_open_ticket(fid)
        if ot:
            kb = VkKeyboard(inline=True)
            kb.add_callback_button("❌ Закрыть обращение", color=VkKeyboardColor.NEGATIVE,
                payload=json.dumps({"button":f"close_ticket_{ot['id']}"}))
            return self.send(pid,
                f"⚠️ У вас уже есть открытое обращение #{ot['id']}.\n"
                f"Сначала закройте его.", keyboard=kb)
        support_pending.set(fid, {"stage":"waiting_problem"})
        self.send(pid,
            "👋 Здравствуйте!\n🤖 Техподдержка The Owen\n\n"
            "📝 Опишите вашу проблему одним сообщением.")

    def process_support_problem(self, pid, fid, text):
        pending = support_pending.get(fid)
        if not pending:
            return
        if pending.get("stage") == "waiting_problem":
            support_pending.set(fid, {"stage":"waiting_type","problem_text":text})
            kb = VkKeyboard(inline=True)
            kb.add_callback_button("🖥 Сервер", color=VkKeyboardColor.PRIMARY,
                payload=json.dumps({"button":"support_server"}))
            kb.add_line()
            kb.add_callback_button("🤖 Бот", color=VkKeyboardColor.PRIMARY,
                payload=json.dumps({"button":"support_bot"}))
            kb.add_line()
            kb.add_callback_button("💳 Донат", color=VkKeyboardColor.PRIMARY,
                payload=json.dumps({"button":"support_donate"}))
            self.send(pid, "✅ Описание принято!\n\nВыберите категорию:", keyboard=kb)

    def handle_support_type_choice(self, pid, fid, problem_type, cmid=None, event_id=None, uid=None):
        pending = support_pending.pop(fid)
        if not pending or pending.get("stage") != "waiting_type":
            return
        problem_text = pending.get("problem_text","")
        type_names   = {"server":"🖥 Сервер","bot":"🤖 Бот","donate":"💳 Донат"}
        ticket_id    = self.db.create_ticket(fid, problem_text, problem_type)
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("❌ Закрыть обращение", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":f"close_ticket_{ticket_id}"}))
        msg_text = (f"✅ Обращение #{ticket_id} принято!\n"
                    f"📂 {type_names.get(problem_type,'?')}\n\n"
                    f"📝 {problem_text}\n\nОжидайте ответа.")
        if cmid and event_id and uid:
            self.edit_msg(pid, cmid, msg_text, keyboard=kb)
        else:
            self.send(pid, msg_text, keyboard=kb)
        try:
            sk = VkKeyboard(inline=True)
            sk.add_callback_button("✅ Закрыть", color=VkKeyboardColor.POSITIVE,
                payload=json.dumps({"button":f"support_close_{ticket_id}"}))
            self.vk.messages.send(
                peer_id=SUPPORT_PEER,
                message=(f"📩 ОБРАЩЕНИЕ #{ticket_id}\n"
                         f"👤 {self.mention(fid)}\n"
                         f"📂 {type_names.get(problem_type,'?')}\n\n"
                         f"📝 {problem_text}\n\n"
                         f"💡 Ответьте на это сообщение чтобы ответить пользователю."),
                keyboard=sk.get_keyboard(),
                random_id=random.randint(0, 2**31))
        except Exception as ex:
            logger.error(f"Support send err: {ex}")

    def handle_support_reply(self, msg):
        reply = msg.get("reply_message")
        if not reply:
            return
        match = re.search(r'ОБРАЩЕНИЕ #(\d+)', reply.get("text",""))
        if not match:
            return
        ticket_id = int(match.group(1))
        ticket    = self.db.get_ticket_by_id(ticket_id)
        if not ticket or ticket['status'] != 'open':
            return self.send(msg['peer_id'], f"❌ Обращение #{ticket_id} закрыто или не найдено.")
        user_id = ticket['user_id']
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("❌ Закрыть", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button":f"close_ticket_{ticket_id}"}))
        try:
            self.vk.messages.send(
                peer_id=user_id,
                message=f"📩 Ответ на обращение #{ticket_id}\n\n{msg.get('text','')}",
                keyboard=kb.get_keyboard(),
                random_id=random.randint(0, 2**31))
            self.send(msg['peer_id'], f"✅ Ответ отправлен {self.mention(user_id)}")
        except Exception as ex:
            self.send(msg['peer_id'], f"❌ Ошибка: {ex}")

    def handle_close_ticket(self, ticket_id, closed_by, peer_id, cmid=None, event_id=None, uid=None):
        ticket = self.db.get_ticket_by_id(ticket_id)
        if not ticket:
            return self.send(peer_id, f"❌ Обращение #{ticket_id} не найдено.")
        if ticket['status'] == 'closed':
            return self.send(peer_id, f"❌ Обращение #{ticket_id} уже закрыто.")
        self.db.close_ticket(ticket_id, closed_by)
        user_id = ticket['user_id']
        if peer_id != user_id:
            try:
                self.vk.messages.send(
                    peer_id=user_id,
                    message=f"✅ Обращение #{ticket_id} закрыто.\nСпасибо за обращение!",
                    random_id=random.randint(0, 2**31))
            except Exception:
                pass
            msg_text = f"✅ Обращение #{ticket_id} закрыто.\n{self.mention(user_id)} уведомлён."
        else:
            msg_text = f"✅ Обращение #{ticket_id} закрыто."
            try:
                self.vk.messages.send(
                    peer_id=SUPPORT_PEER,
                    message=f"ℹ️ Обращение #{ticket_id} закрыто пользователем {self.mention(user_id)}",
                    random_id=random.randint(0, 2**31))
            except Exception:
                pass
        if cmid and event_id and uid:
            self.edit_msg(peer_id, cmid, msg_text)
        else:
            self.send(peer_id, msg_text)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  🎮 The Owen Bot v3.2.0")
    print("=" * 50)
    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk         = vk_session.get_api()
        longpoll   = VkBotLongPoll(vk_session, GROUP_ID)
        try:
            gi = vk.groups.getById(group_id=GROUP_ID)
            print(f"  ✅ Сообщество: {gi[0]['name']}")
        except Exception as ex:
            print(f"  ❌ {ex}"); return
        db       = Database()
        handlers = Handlers(vk, db, GROUP_ID)
        handlers.start_expiry_watcher()
        print(f"  ✅ База данных подключена")
        print(f"  ✅ Глобальных администраторов: {len(GLOBAL_ADMINS)}")
        print("  🟢 Бот запущен! v3.2.0")
        print("=" * 50)

        for event in longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                msg = event.object.message
                try:
                    if msg.get("peer_id") == SUPPORT_PEER and msg.get("reply_message"):
                        handlers.handle_support_reply(msg)
                    else:
                        handlers.handle_message(msg)
                except Exception as ex:
                    logger.error(f"Err: {ex}")
                    traceback.print_exc()

            elif event.type == VkBotEventType.MESSAGE_EVENT:
                try:
                    eo   = event.object
                    uid  = eo.get("user_id")
                    pid  = eo.get("peer_id")
                    eid  = eo.get("event_id")
                    cmid = eo.get("conversation_message_id")
                    payload = eo.get("payload", {})

                    bt = ""
                    if isinstance(payload, dict):
                        bt = payload.get("button","")
                    elif isinstance(payload, str):
                        try:
                            bt = json.loads(payload).get("button","")
                        except Exception:
                            pass

                    if not bt or not uid or not pid:
                        continue

                    btl = bt.lower().strip()

                    def snack_ok(text="✅"):
                        try:
                            vk.messages.sendMessageEventAnswer(
                                event_id=eid, user_id=uid, peer_id=pid,
                                event_data=json.dumps({"type":"show_snackbar","text":text}))
                        except Exception:
                            pass

                    def snack_err(text):
                        try:
                            vk.messages.sendMessageEventAnswer(
                                event_id=eid, user_id=uid, peer_id=pid,
                                event_data=json.dumps({"type":"show_snackbar","text":text}))
                        except Exception:
                            pass

                    if handlers.handle_crmp_button(pid, uid, bt, cmid=cmid, event_id=eid):
                        snack_ok()
                        continue

                    # ── /help и /yhelp категории ──
                    if bt == "help_back":
                        up = handlers.get_prio(pid, uid)
                        handlers.edit_msg(pid, cmid,
                            f"📖 The Owen Bot — Справка\n"
                            f"🔑 Приоритет: {up}\n\n"
                            f"Выберите категорию:", keyboard=handlers._main_help_keyboard("help"))
                        snack_ok()

                    elif bt.startswith("help_"):
                        text = handlers._help_text(bt)
                        handlers.edit_msg(pid, cmid, text, keyboard=handlers._back_keyboard("help_back"))
                        snack_ok()

                    elif bt == "yhelp_back":
                        up = handlers.get_prio(pid, uid)
                        handlers.edit_msg(pid, cmid,
                            f"✅ Ваши доступные команды\n"
                            f"🔑 Приоритет: {up}\n\n"
                            f"Выберите категорию:", keyboard=handlers._main_help_keyboard("yhelp"))
                        snack_ok()

                    elif bt.startswith("yhelp_"):
                        cat = bt.split("_", 1)[1]
                        handlers.edit_msg(pid, cmid, handlers._yhelp_text(pid, uid, cat),
                            keyboard=handlers._back_keyboard("yhelp_back"))
                        snack_ok()

                    # ── stats ──
                    elif bt.startswith("stats_refresh_"):
                        try:
                            target = int(bt.split("_")[2])
                            handlers.handle_stats_refresh(pid, target, cmid=cmid)
                            snack_ok("✅ Обновлено")
                        except (ValueError, IndexError):
                            snack_err("❌ Ошибка")

                    elif bt.startswith("stats_getinfo_"):
                        try:
                            target = int(bt.split("_")[2])
                            handlers._send_getinfo(pid, target, uid, page=0, all_time=False,
                                cmid=cmid, event_id=eid, uid=uid)
                            snack_ok()
                        except (ValueError, IndexError):
                            snack_err("❌ Ошибка")

                    # ── staff toggle ──
                    elif bt == "staff_nicks":
                        handlers.handle_staff_toggle(pid, show_nicks=True,
                            event_id=eid, uid=uid, cmid=cmid)
                        snack_ok()

                    elif bt == "staff_names":
                        handlers.handle_staff_toggle(pid, show_nicks=False,
                            event_id=eid, uid=uid, cmid=cmid)
                        snack_ok()

                    # ── getinfo пагинация ──
                    elif bt.startswith("getinfo_"):
                        parts = bt.split("_")
                        if len(parts) >= 4:
                            try:
                                target   = int(parts[1])
                                page     = int(parts[2])
                                all_time = bool(int(parts[3]))
                                handlers._send_getinfo(pid, target, uid,
                                    page=page, all_time=all_time,
                                    cmid=cmid, event_id=eid, uid=uid)
                                snack_ok()
                            except (ValueError, IndexError):
                                snack_err("❌ Ошибка")

                    # ── logchat пагинация ──
                    elif bt.startswith("logchat_"):
                        parts = bt.split("_")
                        if len(parts) >= 3:
                            try:
                                target = int(parts[1])
                                page   = int(parts[2])
                                handlers._send_logchat(pid, target, uid, page=page)
                                snack_ok()
                            except (ValueError, IndexError):
                                snack_err("❌ Ошибка")

                    # ── support ──
                    elif bt.startswith("support_") and not bt.startswith("support_close_"):
                        handlers.handle_support_type_choice(
                            pid, uid, bt.split("_")[1],
                            cmid=cmid, event_id=eid, uid=uid)
                        snack_ok()

                    elif bt.startswith("close_ticket_"):
                        try:
                            handlers.handle_close_ticket(
                                int(bt.split("_")[2]), uid, pid,
                                cmid=cmid, event_id=eid, uid=uid)
                            snack_ok()
                        except (ValueError, IndexError):
                            snack_err("❌ Ошибка")

                    elif bt.startswith("support_close_"):
                        try:
                            handlers.handle_close_ticket(
                                int(bt.split("_")[2]), uid, pid,
                                cmid=cmid, event_id=eid, uid=uid)
                            snack_ok()
                        except (ValueError, IndexError):
                            snack_err("❌ Ошибка")

                    # ── bl / unbl ──
                    elif btl in ("чса","чсл","чсп","чсс"):
                        if uid in bl_pending:
                            handlers.process_bl_choice(pid, uid, btl,
                                cmid=cmid, event_id=eid, uid=uid)
                            snack_ok()
                        else:
                            snack_err("❌ Нет активного запроса")

                    elif bt.startswith("unbl_"):
                        if uid in unbl_pending:
                            handlers.process_unbl_choice(pid, uid, bt[5:].lower().strip(),
                                cmid=cmid, event_id=eid, uid=uid)
                            snack_ok()
                        else:
                            snack_err("❌ Нет активного запроса")

                    # ── vig / unvig ──
                    elif bt.startswith("vig_"):
                        if uid in vig_pending:
                            handlers.process_vig_choice(pid, uid, bt[4:].lower().strip(),
                                cmid=cmid, event_id=eid, uid=uid)
                            snack_ok()
                        else:
                            snack_err("❌ Нет активного запроса")

                    elif bt.startswith("gvig_"):
                        if uid in gvig_pending:
                            handlers.process_gvig_choice(pid, uid, bt[5:].lower().strip(),
                                cmid=cmid, event_id=eid, uid=uid)
                            snack_ok()
                        else:
                            snack_err("❌ Нет активного запроса")

                    elif bt.startswith("unvig_"):
                        rest = bt[6:]
                        if rest.startswith("all_"):
                            parts = rest[4:].split("_")
                            if len(parts) >= 2:
                                if uid in unvig_pending:
                                    try:
                                        handlers.process_unvig_all(
                                            int(parts[1]), uid, int(parts[0]),
                                            cmid=cmid, event_id=eid, uid=uid)
                                        snack_ok()
                                    except ValueError:
                                        snack_err("❌ Ошибка")
                                else:
                                    snack_err("❌ Нет активного запроса")
                        else:
                            try:
                                if uid in unvig_pending:
                                    handlers.process_unvig_single(
                                        pid, uid, int(rest),
                                        cmid=cmid, event_id=eid, uid=uid)
                                    snack_ok()
                                else:
                                    snack_err("❌ Нет активного запроса")
                            except ValueError:
                                snack_err("❌ Ошибка")

                    elif bt.startswith("gunvig_"):
                        rest = bt[7:]
                        if rest.startswith("all_"):
                            try:
                                if uid in gunvig_pending:
                                    handlers.process_gunvig_all(
                                        pid, uid, int(rest[4:]),
                                        cmid=cmid, event_id=eid, uid=uid)
                                    snack_ok()
                                else:
                                    snack_err("❌ Нет активного запроса")
                            except ValueError:
                                snack_err("❌ Ошибка")
                        else:
                            try:
                                if uid in gunvig_pending:
                                    handlers.process_gunvig_single(
                                        pid, uid, int(rest),
                                        cmid=cmid, event_id=eid, uid=uid)
                                    snack_ok()
                                else:
                                    snack_err("❌ Нет активного запроса")
                            except ValueError:
                                snack_err("❌ Ошибка")

                    else:
                        snack_ok()

                except Exception as ex:
                    logger.error(f"CB err: {ex}")
                    traceback.print_exc()

    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен.")
    except Exception as ex:
        logger.critical(f"Fatal: {ex}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
