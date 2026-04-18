"""
 DARKNESSRUSSIA BOT v2.8.1 (CRMP)
 pip install vk_api
"""

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import sqlite3, threading, time, re, random, traceback, json, hashlib, os, logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger("DR")

VK_TOKEN = os.environ.get("VK_TOKEN", "")
GROUP_ID = int(os.environ.get("VK_GROUP_ID", "237780255"))
GLOBAL_ADMINS = [1063123986]
SUPPORT_PEER = 2000002

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

ALLOWED_SETTINGS = {
    "antispam", "antimat", "antilink", "antiflood",
    "welcome_enabled", "welcome_text", "bye_enabled", "bye_text",
    "slowmode", "nightmode", "night_start", "night_end",
    "log_peer", "captcha", "max_warns", "connected", "support_mode",
    "chat_closed"
}

# Список тегов для команд
CMD_PREFIXES = ["!", " ", "/"]

# Русские команды (тег ! или пробел)
RU_CMDS = {
    "помощь": "drhelp",
    "бан": "drban",
    "разбан": "drunban",
    "мут": "drmute",
    "размут": "drunmute",
    "кик": "drkick",
    "чс": "drbl",
    "снятьчс": "drunbl",
    "выговор": "drvig",
    "снятьвыговор": "drunvig",
    "топ": "drtop",
    "персонал": "drstaff",
    "роль": "drrole",
    "роли": "drroles",
    "новаяроль": "drnewrole",
    "удалитьроль": "drdelrole",
    "стата": "drstats",
    "заметки": "drnotes",
    "ник": "drnick",
    "чат": "drchat",
    "лидер": "drleader",
    "довер": "drtrusted",
    "сообщение": "drmsg",
}

# Английские команды (тег / или !)
EN_CMDS = {
    "drhelp": "drhelp",
    "drban": "drban",
    "drunban": "drunban",
    "drmute": "drmute",
    "drunmute": "drunmute",
    "drkick": "drkick",
    "drbl": "drbl",
    "drunbl": "drunbl",
    "drvig": "drvig",
    "drunvig": "drunvig",
    "drtop": "drtop",
    "drstaff": "drstaff",
    "drrole": "drrole",
    "drroles": "drroles",
    "drnewrole": "drnewrole",
    "drdelrole": "drdelrole",
    "drstats": "drstats",
    "drnotes": "drnotes",
    "drnick": "drnick",
    "drchat": "drchat",
    "drleader": "drleader",
    "drtrusted": "drtrusted",
    "drmsg": "drmsg",
    "drcmd": "drcmd",
    "drcmdname": "drcmdname",
    "drgcmdname": "drgcmdname",
    "drconnect": "drconnect",
    "drimport": "drimport",
    "drdelmsg": "drdelmsg",
    "drgban": "drgban",
    "drgunban": "drgunban",
    "drgmute": "drgmute",
    "drgunmute": "drgunmute",
    "drgkick": "drgkick",
    "drgvig": "drgvig",
    "drgunvig": "drgunvig",
    "drlistchat": "drlistchat",
    "drgrole": "drgrole",
    "drstart": "drstart",
    "drvlads": "drvlads",
    "drrenamrole": "drrenamrole",
    "drgnick": "drgnick",
}


def resolve_command(text):
    """
    Разбирает текст и возвращает (cmd_key, rest_text) или (None, None).
    Поддерживает теги: !, пробел в начале, /
    Русские команды: ! или пробел
    Английские команды: / или !
    """
    if not text:
        return None, None

    tl = text.strip()

    # Определяем тег
    prefix = None
    if tl.startswith("!"):
        prefix = "!"
        body = tl[1:].strip()
    elif tl.startswith("/"):
        prefix = "/"
        body = tl[1:].strip()
    elif text.startswith(" "):
        prefix = " "
        body = tl
    else:
        return None, None

    if not body:
        return None, None

    parts = body.split(maxsplit=1)
    cmd_word = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    # Русские команды — теги ! и пробел
    if prefix in ("!", " "):
        if cmd_word in RU_CMDS:
            return RU_CMDS[cmd_word], rest

    # Английские команды — теги / и !
    if prefix in ("/", "!"):
        if cmd_word in EN_CMDS:
            return EN_CMDS[cmd_word], rest

    return None, None


class Database:
    def __init__(self, db_path="darknessrussia.db"):
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_tables()
        self._migrate_tables()

    def _create_tables(self):
        with self.lock:
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER NOT NULL,
                role_name TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 1,
                emoji TEXT DEFAULT '', UNIQUE(peer_id, role_name), UNIQUE(peer_id, priority))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS user_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL, role_id INTEGER NOT NULL,
                UNIQUE(peer_id, user_id), FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL, banned_by INTEGER NOT NULL,
                reason TEXT DEFAULT '', ban_until REAL DEFAULT 0,
                created_at REAL DEFAULT 0, UNIQUE(peer_id, user_id))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS mutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL, muted_by INTEGER NOT NULL,
                reason TEXT DEFAULT '', mute_until REAL DEFAULT 0,
                created_at REAL DEFAULT 0, UNIQUE(peer_id, user_id))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS cmd_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER NOT NULL,
                command TEXT NOT NULL, min_priority INTEGER NOT NULL DEFAULT 100,
                UNIQUE(peer_id, command))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS chat_owners (
                peer_id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                peer_id INTEGER NOT NULL, bl_type TEXT NOT NULL,
                added_by INTEGER NOT NULL, reason TEXT DEFAULT '',
                created_at REAL DEFAULT 0)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS viglist (
                id INTEGER PRIMARY KEY AUTOINCREMENT, peer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL, issued_by INTEGER NOT NULL,
                vig_type TEXT NOT NULL, reason TEXT DEFAULT '',
                created_at REAL DEFAULT 0)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS msg_count (
                peer_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                count INTEGER DEFAULT 0, PRIMARY KEY(peer_id, user_id))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS chat_settings (
                peer_id INTEGER PRIMARY KEY, antispam INTEGER DEFAULT 0,
                antimat INTEGER DEFAULT 0, antilink INTEGER DEFAULT 0,
                antiflood INTEGER DEFAULT 0, welcome_enabled INTEGER DEFAULT 0,
                welcome_text TEXT DEFAULT '', bye_enabled INTEGER DEFAULT 0,
                bye_text TEXT DEFAULT '', slowmode INTEGER DEFAULT 0,
                nightmode INTEGER DEFAULT 0, night_start INTEGER DEFAULT 0,
                night_end INTEGER DEFAULT 8, log_peer INTEGER DEFAULT 0,
                captcha INTEGER DEFAULT 0, max_warns INTEGER DEFAULT 3,
                connected INTEGER DEFAULT 0, support_mode INTEGER DEFAULT 0,
                chat_closed INTEGER DEFAULT 0)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS chat_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT, pool_owner INTEGER NOT NULL,
                peer_id INTEGER NOT NULL, UNIQUE(peer_id))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS import_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE,
                peer_id INTEGER NOT NULL, created_at REAL DEFAULT 0)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS global_bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE,
                banned_by INTEGER NOT NULL, reason TEXT DEFAULT '',
                ban_until REAL DEFAULT 0, created_at REAL DEFAULT 0)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS global_mutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE,
                muted_by INTEGER NOT NULL, reason TEXT DEFAULT '',
                mute_until REAL DEFAULT 0, created_at REAL DEFAULT 0)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS global_vigs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                issued_by INTEGER NOT NULL, vig_type TEXT NOT NULL,
                reason TEXT DEFAULT '', created_at REAL DEFAULT 0)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                problem_text TEXT NOT NULL, problem_type TEXT NOT NULL,
                status TEXT DEFAULT 'open', created_at REAL DEFAULT 0,
                closed_at REAL DEFAULT 0, closed_by INTEGER DEFAULT 0)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS role_aliases (
                peer_id INTEGER NOT NULL, priority INTEGER NOT NULL,
                alias_name TEXT NOT NULL, alias_emoji TEXT DEFAULT '',
                PRIMARY KEY(peer_id, priority))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS chat_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL, note_name TEXT NOT NULL,
                note_text TEXT DEFAULT '', attachments TEXT DEFAULT '',
                created_by INTEGER NOT NULL, created_at REAL DEFAULT 0,
                UNIQUE(peer_id, note_name))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS cmd_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL,
                original_cmd TEXT NOT NULL,
                alias TEXT NOT NULL,
                UNIQUE(peer_id, alias))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS global_cmd_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_cmd TEXT NOT NULL,
                alias TEXT NOT NULL,
                UNIQUE(alias))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS nicknames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                nickname TEXT NOT NULL,
                UNIQUE(peer_id, user_id))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS global_nicknames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                nickname TEXT NOT NULL)""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS trusted_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                min_punish_priority INTEGER NOT NULL DEFAULT 100,
                set_by INTEGER NOT NULL,
                created_at REAL DEFAULT 0,
                UNIQUE(peer_id, user_id))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS leaders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                org_name TEXT NOT NULL,
                position TEXT NOT NULL,
                set_by INTEGER NOT NULL,
                created_at REAL DEFAULT 0,
                UNIQUE(peer_id, user_id))""")
            self.cursor.execute("""CREATE TABLE IF NOT EXISTS msg_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL UNIQUE,
                chat_name TEXT DEFAULT '')""")
            self.conn.commit()

    def _migrate_tables(self):
        with self.lock:
            for sql in [
                "ALTER TABLE blacklist ADD COLUMN reason TEXT DEFAULT ''",
                "ALTER TABLE roles ADD COLUMN emoji TEXT DEFAULT ''",
                "ALTER TABLE chat_settings ADD COLUMN support_mode INTEGER DEFAULT 0",
                "ALTER TABLE chat_settings ADD COLUMN chat_closed INTEGER DEFAULT 0"
            ]:
                try:
                    self.cursor.execute(sql)
                    self.conn.commit()
                except sqlite3.OperationalError:
                    pass
            for sql in [
                """CREATE TABLE IF NOT EXISTS role_aliases (
                    peer_id INTEGER NOT NULL, priority INTEGER NOT NULL,
                    alias_name TEXT NOT NULL, alias_emoji TEXT DEFAULT '',
                    PRIMARY KEY(peer_id, priority))""",
                """CREATE TABLE IF NOT EXISTS chat_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    peer_id INTEGER NOT NULL, note_name TEXT NOT NULL,
                    note_text TEXT DEFAULT '', attachments TEXT DEFAULT '',
                    created_by INTEGER NOT NULL, created_at REAL DEFAULT 0,
                    UNIQUE(peer_id, note_name))""",
                """CREATE TABLE IF NOT EXISTS cmd_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    peer_id INTEGER NOT NULL,
                    original_cmd TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    UNIQUE(peer_id, alias))""",
                """CREATE TABLE IF NOT EXISTS global_cmd_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_cmd TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    UNIQUE(alias))""",
                """CREATE TABLE IF NOT EXISTS nicknames (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    peer_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    nickname TEXT NOT NULL,
                    UNIQUE(peer_id, user_id))""",
                """CREATE TABLE IF NOT EXISTS global_nicknames (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    nickname TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS trusted_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    peer_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    min_punish_priority INTEGER NOT NULL DEFAULT 100,
                    set_by INTEGER NOT NULL,
                    created_at REAL DEFAULT 0,
                    UNIQUE(peer_id, user_id))""",
                """CREATE TABLE IF NOT EXISTS leaders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    peer_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    org_name TEXT NOT NULL,
                    position TEXT NOT NULL,
                    set_by INTEGER NOT NULL,
                    created_at REAL DEFAULT 0,
                    UNIQUE(peer_id, user_id))""",
                """CREATE TABLE IF NOT EXISTS msg_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    peer_id INTEGER NOT NULL UNIQUE,
                    chat_name TEXT DEFAULT '')"""
            ]:
                try:
                    self.cursor.execute(sql)
                    self.conn.commit()
                except sqlite3.OperationalError:
                    pass

    # ============ MSG LINKS ============

    def add_msg_link(self, peer_id, chat_name=""):
        with self.lock:
            try:
                self.cursor.execute(
                    "INSERT OR REPLACE INTO msg_links (peer_id, chat_name) VALUES (?, ?)",
                    (peer_id, chat_name)
                )
                self.conn.commit()
                return True
            except Exception:
                return False

    def remove_msg_link(self, peer_id):
        with self.lock:
            self.cursor.execute("DELETE FROM msg_links WHERE peer_id = ?", (peer_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_msg_links(self):
        with self.lock:
            self.cursor.execute("SELECT peer_id, chat_name FROM msg_links")
            return [dict(r) for r in self.cursor.fetchall()]

    def is_msg_linked(self, peer_id):
        with self.lock:
            self.cursor.execute("SELECT id FROM msg_links WHERE peer_id = ?", (peer_id,))
            return self.cursor.fetchone() is not None

    # ============ LEADERS ============

    def set_leader(self, peer_id, user_id, org_name, position, set_by):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO leaders (peer_id, user_id, org_name, position, set_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (peer_id, user_id, org_name, position, set_by, time.time())
            )
            self.conn.commit()

    def remove_leader(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM leaders WHERE peer_id = ? AND user_id = ?", (peer_id, user_id))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_leader(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM leaders WHERE peer_id = ? AND user_id = ?", (peer_id, user_id))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_leader_list(self, peer_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM leaders WHERE peer_id = ? ORDER BY org_name", (peer_id,))
            return [dict(r) for r in self.cursor.fetchall()]

    # ============ TRUSTED ============

    def set_trusted(self, peer_id, user_id, min_punish_priority, set_by):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO trusted_users (peer_id, user_id, min_punish_priority, set_by, created_at) VALUES (?, ?, ?, ?, ?)",
                (peer_id, user_id, min_punish_priority, set_by, time.time())
            )
            self.conn.commit()

    def remove_trusted(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM trusted_users WHERE peer_id = ? AND user_id = ?", (peer_id, user_id))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_trusted(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM trusted_users WHERE peer_id = ? AND user_id = ?", (peer_id, user_id))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_trusted_list(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM trusted_users WHERE peer_id = ? ORDER BY min_punish_priority DESC",
                (peer_id,)
            )
            return [dict(r) for r in self.cursor.fetchall()]

    # ============ ОСНОВНЫЕ МЕТОДЫ ============

    def set_chat_owner(self, peer_id, owner_id):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO chat_owners (peer_id, owner_id) VALUES (?, ?)",
                (peer_id, owner_id)
            )
            self.conn.commit()

    def get_chat_owner(self, peer_id):
        with self.lock:
            self.cursor.execute("SELECT owner_id FROM chat_owners WHERE peer_id = ?", (peer_id,))
            r = self.cursor.fetchone()
            return r["owner_id"] if r else None

    def _get_chat_owner_nolock(self, peer_id):
        self.cursor.execute("SELECT owner_id FROM chat_owners WHERE peer_id = ?", (peer_id,))
        r = self.cursor.fetchone()
        return r["owner_id"] if r else None

    def create_or_update_role(self, peer_id, role_name, priority, emoji=""):
        with self.lock:
            self.cursor.execute(
                "SELECT id FROM roles WHERE peer_id = ? AND priority = ?", (peer_id, priority)
            )
            r = self.cursor.fetchone()
            if r:
                try:
                    self.cursor.execute(
                        "UPDATE roles SET role_name = ?, emoji = ? WHERE peer_id = ? AND priority = ?",
                        (role_name, emoji, peer_id, priority)
                    )
                    self.conn.commit()
                    return True, "updated"
                except sqlite3.IntegrityError:
                    return False, "Роль с таким именем уже существует."
            else:
                try:
                    self.cursor.execute(
                        "INSERT INTO roles (peer_id, role_name, priority, emoji) VALUES (?, ?, ?, ?)",
                        (peer_id, role_name, priority, emoji)
                    )
                    self.conn.commit()
                    return True, "created"
                except sqlite3.IntegrityError:
                    return False, "Роль с таким именем или приоритетом уже существует."

    def delete_role(self, peer_id, priority):
        with self.lock:
            if priority >= 100:
                return False, "Нельзя удалить роль владельца."
            self.cursor.execute(
                "SELECT id FROM roles WHERE peer_id = ? AND priority = ?", (peer_id, priority)
            )
            r = self.cursor.fetchone()
            if not r:
                return False, "Роль не найдена."
            self.cursor.execute("DELETE FROM user_roles WHERE role_id = ?", (r["id"],))
            self.cursor.execute("DELETE FROM roles WHERE id = ?", (r["id"],))
            self.conn.commit()
            return True, "OK"

    def get_roles(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM roles WHERE peer_id = ? ORDER BY priority DESC", (peer_id,)
            )
            return self.cursor.fetchall()

    def get_role_by_priority(self, peer_id, priority):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM roles WHERE peer_id = ? AND priority = ?", (peer_id, priority)
            )
            return self.cursor.fetchone()

    def assign_role(self, peer_id, user_id, priority):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM roles WHERE peer_id = ? AND priority = ?", (peer_id, priority)
            )
            r = self.cursor.fetchone()
            if not r:
                return False, "Роль не существует."
            self.cursor.execute(
                "INSERT OR REPLACE INTO user_roles (peer_id, user_id, role_id) VALUES (?, ?, ?)",
                (peer_id, user_id, r["id"])
            )
            self.conn.commit()
            return True, dict(r)

    def remove_role(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM user_roles WHERE peer_id = ? AND user_id = ?", (peer_id, user_id)
            )
            if self.cursor.rowcount == 0:
                return False, "У пользователя нет роли."
            self.conn.commit()
            return True, "OK"

    def get_user_role(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT r.role_name, r.priority, r.emoji FROM user_roles ur "
                "JOIN roles r ON ur.role_id = r.id "
                "WHERE ur.peer_id = ? AND ur.user_id = ?",
                (peer_id, user_id)
            )
            row = self.cursor.fetchone()
            return dict(row) if row else None

    def get_chat_staff(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT ur.user_id, r.role_name, r.priority, r.emoji "
                "FROM user_roles ur JOIN roles r ON ur.role_id = r.id "
                "WHERE ur.peer_id = ? ORDER BY r.priority DESC",
                (peer_id,)
            )
            return [dict(row) for row in self.cursor.fetchall()]

    def get_user_priority(self, peer_id, user_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return 1000
            o = self._get_chat_owner_nolock(peer_id)
            if o and o == user_id:
                return 100
            self.cursor.execute(
                "SELECT r.priority FROM user_roles ur JOIN roles r ON ur.role_id = r.id "
                "WHERE ur.peer_id = ? AND ur.user_id = ?",
                (peer_id, user_id)
            )
            r = self.cursor.fetchone()
            return r["priority"] if r else 0

    def get_user_priority_pool(self, peer_id, user_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return 1000
            o = self._get_chat_owner_nolock(peer_id)
            if o and o == user_id:
                return 100
            self.cursor.execute(
                "SELECT r.priority FROM user_roles ur JOIN roles r ON ur.role_id = r.id "
                "WHERE ur.peer_id = ? AND ur.user_id = ?",
                (peer_id, user_id)
            )
            r = self.cursor.fetchone()
            p = r["priority"] if r else 0
            self.cursor.execute("SELECT pool_owner FROM chat_pool WHERE peer_id = ?", (peer_id,))
            pool_row = self.cursor.fetchone()
            if pool_row:
                owner = pool_row["pool_owner"]
                self.cursor.execute("SELECT peer_id FROM chat_pool WHERE pool_owner = ?", (owner,))
                peers = [x["peer_id"] for x in self.cursor.fetchall()]
                peers.append(owner)
            else:
                self.cursor.execute("SELECT peer_id FROM chat_pool WHERE pool_owner = ?", (peer_id,))
                pp = self.cursor.fetchall()
                peers = [x["peer_id"] for x in pp] + [peer_id] if pp else []
            for pp in peers:
                if pp != peer_id:
                    self.cursor.execute(
                        "SELECT r.priority FROM user_roles ur JOIN roles r ON ur.role_id = r.id "
                        "WHERE ur.peer_id = ? AND ur.user_id = ?",
                        (pp, user_id)
                    )
                    rr = self.cursor.fetchone()
                    if rr and rr["priority"] > p:
                        p = rr["priority"]
            return p

    def ban_user(self, peer_id, user_id, banned_by, reason, duration):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            bu = 0 if duration == 0 else time.time() + duration
            self.cursor.execute(
                "INSERT OR REPLACE INTO bans (peer_id, user_id, banned_by, reason, ban_until, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (peer_id, user_id, banned_by, reason, bu, time.time())
            )
            self.conn.commit()
            return True

    def unban_user(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM bans WHERE peer_id = ? AND user_id = ?", (peer_id, user_id)
            )
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def is_banned(self, peer_id, user_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "SELECT * FROM bans WHERE peer_id = ? AND user_id = ?", (peer_id, user_id)
            )
            r = self.cursor.fetchone()
            if not r:
                return False
            if r["ban_until"] == 0:
                return True
            if time.time() > r["ban_until"]:
                self.cursor.execute("DELETE FROM bans WHERE id = ?", (r["id"],))
                self.conn.commit()
                return False
            return True

    def get_ban_info(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM bans WHERE peer_id = ? AND user_id = ?", (peer_id, user_id)
            )
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def mute_user(self, peer_id, user_id, muted_by, reason, duration):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            mu = 0 if duration == 0 else time.time() + duration
            self.cursor.execute(
                "INSERT OR REPLACE INTO mutes (peer_id, user_id, muted_by, reason, mute_until, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (peer_id, user_id, muted_by, reason, mu, time.time())
            )
            self.conn.commit()
            return True

    def unmute_user(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM mutes WHERE peer_id = ? AND user_id = ?", (peer_id, user_id)
            )
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def is_muted(self, peer_id, user_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "SELECT * FROM mutes WHERE peer_id = ? AND user_id = ?", (peer_id, user_id)
            )
            r = self.cursor.fetchone()
            if not r:
                return False
            if r["mute_until"] == 0:
                return True
            if time.time() > r["mute_until"]:
                self.cursor.execute("DELETE FROM mutes WHERE id = ?", (r["id"],))
                self.conn.commit()
                return False
            return True

    def get_mute_info(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM mutes WHERE peer_id = ? AND user_id = ?", (peer_id, user_id)
            )
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def set_cmd_permission(self, peer_id, command, min_priority):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO cmd_permissions (peer_id, command, min_priority) VALUES (?, ?, ?)",
                (peer_id, command, min_priority)
            )
            self.conn.commit()

    def get_cmd_permission(self, peer_id, command):
        with self.lock:
            self.cursor.execute(
                "SELECT min_priority FROM cmd_permissions WHERE peer_id = ? AND command = ?",
                (peer_id, command)
            )
            r = self.cursor.fetchone()
            return r["min_priority"] if r else None

    def get_all_cmd_permissions(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT command, min_priority FROM cmd_permissions WHERE peer_id = ? ORDER BY command",
                (peer_id,)
            )
            return [dict(r) for r in self.cursor.fetchall()]

    def add_to_blacklist(self, user_id, peer_id, bl_type, added_by, reason):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "INSERT INTO blacklist (user_id, peer_id, bl_type, added_by, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, peer_id, bl_type, added_by, reason, time.time())
            )
            self.conn.commit()
            return True

    def remove_from_blacklist(self, user_id, peer_id, bl_type=None):
        with self.lock:
            if bl_type:
                self.cursor.execute(
                    "DELETE FROM blacklist WHERE user_id = ? AND peer_id = ? AND bl_type = ?",
                    (user_id, peer_id, bl_type)
                )
            else:
                self.cursor.execute(
                    "DELETE FROM blacklist WHERE user_id = ? AND peer_id = ?", (user_id, peer_id)
                )
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def remove_from_blacklist_global(self, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def is_blacklisted_in_chat(self, user_id, peer_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return []
            self.cursor.execute(
                "SELECT * FROM blacklist WHERE user_id = ? AND "
                "(peer_id = ? OR bl_type IN ('full_project', 'full_strict'))",
                (user_id, peer_id)
            )
            return [dict(r) for r in self.cursor.fetchall()]

    def get_user_blacklist_entries(self, user_id, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM blacklist WHERE user_id = ? AND "
                "(peer_id = ? OR bl_type IN ('full_project', 'full_strict'))",
                (user_id, peer_id)
            )
            return [dict(r) for r in self.cursor.fetchall()]

    def get_all_chat_peers(self):
        with self.lock:
            self.cursor.execute("SELECT peer_id FROM chat_owners")
            return [r["peer_id"] for r in self.cursor.fetchall()]

    def add_vig(self, peer_id, user_id, issued_by, vig_type, reason):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "INSERT INTO viglist (peer_id, user_id, issued_by, vig_type, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (peer_id, user_id, issued_by, vig_type, reason, time.time())
            )
            self.conn.commit()
            return True

    def remove_vig_by_id(self, vig_id):
        with self.lock:
            self.cursor.execute("DELETE FROM viglist WHERE id = ?", (vig_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def remove_vigs(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM viglist WHERE peer_id = ? AND user_id = ?", (peer_id, user_id)
            )
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_vigs(self, peer_id, user_id=None):
        with self.lock:
            if user_id:
                self.cursor.execute(
                    "SELECT * FROM viglist WHERE peer_id = ? AND user_id = ? ORDER BY created_at DESC",
                    (peer_id, user_id)
                )
            else:
                self.cursor.execute(
                    "SELECT * FROM viglist WHERE peer_id = ? ORDER BY created_at DESC", (peer_id,)
                )
            return [dict(r) for r in self.cursor.fetchall()]

    def get_vig_by_id(self, vig_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM viglist WHERE id = ?", (vig_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_vig_issuer_max_priority(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT issued_by FROM viglist WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            )
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
                        "SELECT r.priority FROM user_roles ur JOIN roles r ON ur.role_id = r.id "
                        "WHERE ur.peer_id = ? AND ur.user_id = ?",
                        (peer_id, iid)
                    )
                    rr = self.cursor.fetchone()
                    p = rr["priority"] if rr else 0
                if p > mx:
                    mx = p
            return mx

    def increment_msg(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "INSERT INTO msg_count (peer_id, user_id, count) VALUES (?, ?, 1) "
                "ON CONFLICT(peer_id, user_id) DO UPDATE SET count = count + 1",
                (peer_id, user_id)
            )
            self.conn.commit()

    def get_top_msg(self, peer_id, limit=10):
        with self.lock:
            self.cursor.execute(
                "SELECT user_id, count FROM msg_count WHERE peer_id = ? ORDER BY count DESC LIMIT ?",
                (peer_id, limit)
            )
            return [dict(r) for r in self.cursor.fetchall()]

    def get_settings(self, peer_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM chat_settings WHERE peer_id = ?", (peer_id,))
            r = self.cursor.fetchone()
            if not r:
                self.cursor.execute("INSERT INTO chat_settings (peer_id) VALUES (?)", (peer_id,))
                self.conn.commit()
                self.cursor.execute("SELECT * FROM chat_settings WHERE peer_id = ?", (peer_id,))
                r = self.cursor.fetchone()
            return dict(r)

    def update_setting(self, peer_id, key, value):
        if key not in ALLOWED_SETTINGS:
            return
        with self.lock:
            self.cursor.execute("INSERT OR IGNORE INTO chat_settings (peer_id) VALUES (?)", (peer_id,))
            self.cursor.execute(
                f"UPDATE chat_settings SET {key} = ? WHERE peer_id = ?", (value, peer_id)
            )
            self.conn.commit()

    def connect_to_pool(self, peer_id, owner_peer):
        with self.lock:
            try:
                self.cursor.execute(
                    "INSERT OR REPLACE INTO chat_pool (pool_owner, peer_id) VALUES (?, ?)",
                    (owner_peer, peer_id)
                )
                self.conn.commit()
                return True
            except Exception:
                return False

    def disconnect_from_pool(self, peer_id):
        with self.lock:
            self.cursor.execute("DELETE FROM chat_pool WHERE peer_id = ?", (peer_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0

    def get_pool_peers(self, peer_id):
        with self.lock:
            self.cursor.execute("SELECT pool_owner FROM chat_pool WHERE peer_id = ?", (peer_id,))
            r = self.cursor.fetchone()
            if not r:
                self.cursor.execute(
                    "SELECT peer_id FROM chat_pool WHERE pool_owner = ?", (peer_id,)
                )
                peers = [x["peer_id"] for x in self.cursor.fetchall()]
                return peers + [peer_id] if peers else []
            owner = r["pool_owner"]
            self.cursor.execute(
                "SELECT peer_id FROM chat_pool WHERE pool_owner = ?", (owner,)
            )
            peers = [x["peer_id"] for x in self.cursor.fetchall()]
            peers.append(owner)
            return peers

    def is_connected(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM chat_pool WHERE peer_id = ? OR pool_owner = ?",
                (peer_id, peer_id)
            )
            return self.cursor.fetchone() is not None

    def create_import_code(self, peer_id):
        with self.lock:
            code = hashlib.md5(
                f"{peer_id}{time.time()}{random.randint(0, 999999)}".encode()
            ).hexdigest()[:12].upper()
            self.cursor.execute("DELETE FROM import_codes WHERE peer_id = ?", (peer_id,))
            self.cursor.execute(
                "INSERT INTO import_codes (code, peer_id, created_at) VALUES (?, ?, ?)",
                (code, peer_id, time.time())
            )
            self.conn.commit()
            return code

    def get_import_source(self, code):
        with self.lock:
            self.cursor.execute("SELECT * FROM import_codes WHERE code = ?", (code,))
            r = self.cursor.fetchone()
            if not r:
                return None
            if time.time() - r["created_at"] > 600:
                self.cursor.execute("DELETE FROM import_codes WHERE code = ?", (code,))
                self.conn.commit()
                return None
            return r["peer_id"]

    def import_settings(self, from_peer, to_peer):
        with self.lock:
            self.cursor.execute("SELECT * FROM chat_settings WHERE peer_id = ?", (from_peer,))
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
                f"INSERT OR REPLACE INTO chat_settings (peer_id, {keys}) VALUES (?, {ph})",
                [to_peer] + vals
            )
            self.cursor.execute("DELETE FROM roles WHERE peer_id = ?", (to_peer,))
            self.cursor.execute("SELECT * FROM roles WHERE peer_id = ?", (from_peer,))
            for role in self.cursor.fetchall():
                rd = dict(role)
                try:
                    self.cursor.execute(
                        "INSERT INTO roles (peer_id, role_name, priority, emoji) VALUES (?, ?, ?, ?)",
                        (to_peer, rd["role_name"], rd["priority"], rd.get("emoji", ""))
                    )
                except sqlite3.IntegrityError:
                    pass
            self.cursor.execute("DELETE FROM cmd_permissions WHERE peer_id = ?", (to_peer,))
            self.cursor.execute("SELECT * FROM cmd_permissions WHERE peer_id = ?", (from_peer,))
            for cp in self.cursor.fetchall():
                cpd = dict(cp)
                self.cursor.execute(
                    "INSERT INTO cmd_permissions (peer_id, command, min_priority) VALUES (?, ?, ?)",
                    (to_peer, cpd["command"], cpd["min_priority"])
                )
            self.conn.commit()
            return True

    def set_role_alias(self, peer_id, priority, alias_name, alias_emoji=""):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO role_aliases (peer_id, priority, alias_name, alias_emoji) "
                "VALUES (?, ?, ?, ?)",
                (peer_id, priority, alias_name, alias_emoji)
            )
            self.conn.commit()

    def get_role_alias(self, peer_id, priority):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM role_aliases WHERE peer_id = ? AND priority = ?",
                (peer_id, priority)
            )
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def create_note(self, peer_id, note_name, note_text, attachments, created_by):
        with self.lock:
            try:
                self.cursor.execute(
                    "INSERT INTO chat_notes (peer_id, note_name, note_text, attachments, created_by, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (peer_id, note_name.lower().strip(), note_text, attachments, created_by, time.time())
                )
                self.conn.commit()
                return True, "OK"
            except sqlite3.IntegrityError:
                return False, "Заметка с таким названием уже существует."

    def update_note(self, peer_id, note_name, note_text, attachments, created_by):
        with self.lock:
            self.cursor.execute(
                "UPDATE chat_notes SET note_text = ?, attachments = ?, created_by = ?, created_at = ? "
                "WHERE peer_id = ? AND note_name = ?",
                (note_text, attachments, created_by, time.time(), peer_id, note_name.lower().strip())
            )
            if self.cursor.rowcount == 0:
                return False, "Заметка не найдена."
            self.conn.commit()
            return True, "OK"

    def delete_note(self, peer_id, note_name):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM chat_notes WHERE peer_id = ? AND note_name = ?",
                (peer_id, note_name.lower().strip())
            )
            if self.cursor.rowcount == 0:
                return False, "Заметка не найдена."
            self.conn.commit()
            return True, "OK"

    def get_note(self, peer_id, note_name):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM chat_notes WHERE peer_id = ? AND note_name = ?",
                (peer_id, note_name.lower().strip())
            )
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_all_notes(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM chat_notes WHERE peer_id = ? ORDER BY note_name", (peer_id,)
            )
            return [dict(r) for r in self.cursor.fetchall()]

    def add_cmd_alias(self, peer_id, original_cmd, alias):
        with self.lock:
            try:
                self.cursor.execute(
                    "INSERT OR REPLACE INTO cmd_aliases (peer_id, original_cmd, alias) VALUES (?, ?, ?)",
                    (peer_id, original_cmd.lower(), alias.lower())
                )
                self.conn.commit()
                return True
            except Exception:
                return False

    def remove_cmd_alias(self, peer_id, alias):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM cmd_aliases WHERE peer_id = ? AND alias = ?",
                (peer_id, alias.lower())
            )
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_cmd_aliases(self, peer_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM cmd_aliases WHERE peer_id = ? ORDER BY original_cmd", (peer_id,)
            )
            return [dict(r) for r in self.cursor.fetchall()]

    def resolve_alias(self, peer_id, text):
        with self.lock:
            self.cursor.execute("SELECT * FROM global_cmd_aliases")
            global_aliases = self.cursor.fetchall()
            tl = text.lower().strip()
            for a in global_aliases:
                al = a["alias"]
                if tl == al or tl.startswith(al + " "):
                    rest = text[len(al):].strip()
                    return "/" + a["original_cmd"] + (" " + rest if rest else "")
            self.cursor.execute("SELECT * FROM cmd_aliases WHERE peer_id = ?", (peer_id,))
            aliases = self.cursor.fetchall()
            for a in aliases:
                al = a["alias"]
                if tl == al or tl.startswith(al + " "):
                    rest = text[len(al):].strip()
                    return "/" + a["original_cmd"] + (" " + rest if rest else "")
            return None

    def add_global_cmd_alias(self, original_cmd, alias):
        with self.lock:
            try:
                self.cursor.execute(
                    "INSERT OR REPLACE INTO global_cmd_aliases (original_cmd, alias) VALUES (?, ?)",
                    (original_cmd.lower(), alias.lower())
                )
                self.conn.commit()
                return True
            except Exception:
                return False

    def remove_global_cmd_alias(self, alias):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM global_cmd_aliases WHERE alias = ?", (alias.lower(),)
            )
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_global_cmd_aliases(self):
        with self.lock:
            self.cursor.execute("SELECT * FROM global_cmd_aliases ORDER BY original_cmd")
            return [dict(r) for r in self.cursor.fetchall()]

    def set_nickname(self, peer_id, user_id, nickname):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO nicknames (peer_id, user_id, nickname) VALUES (?, ?, ?)",
                (peer_id, user_id, nickname)
            )
            self.conn.commit()

    def remove_nickname(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM nicknames WHERE peer_id = ? AND user_id = ?", (peer_id, user_id)
            )
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def set_global_nickname(self, user_id, nickname):
        with self.lock:
            self.cursor.execute(
                "INSERT OR REPLACE INTO global_nicknames (user_id, nickname) VALUES (?, ?)",
                (user_id, nickname)
            )
            self.conn.commit()

    def remove_global_nickname(self, user_id):
        with self.lock:
            self.cursor.execute(
                "DELETE FROM global_nicknames WHERE user_id = ?", (user_id,)
            )
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_display_nickname(self, peer_id, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT nickname FROM nicknames WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            )
            r = self.cursor.fetchone()
            if r:
                return r["nickname"]
            self.cursor.execute(
                "SELECT nickname FROM global_nicknames WHERE user_id = ?", (user_id,)
            )
            r = self.cursor.fetchone()
            return r["nickname"] if r else None

    def global_ban_user(self, user_id, banned_by, reason, duration):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            bu = 0 if duration == 0 else time.time() + duration
            self.cursor.execute(
                "INSERT OR REPLACE INTO global_bans (user_id, banned_by, reason, ban_until, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, banned_by, reason, bu, time.time())
            )
            self.conn.commit()
            return True

    def global_unban_user(self, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM global_bans WHERE user_id = ?", (user_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def is_globally_banned(self, user_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute("SELECT * FROM global_bans WHERE user_id = ?", (user_id,))
            r = self.cursor.fetchone()
            if not r:
                return False
            if r["ban_until"] == 0:
                return True
            if time.time() > r["ban_until"]:
                self.cursor.execute("DELETE FROM global_bans WHERE user_id = ?", (user_id,))
                self.conn.commit()
                return False
            return True

    def get_global_ban_info(self, user_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM global_bans WHERE user_id = ?", (user_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def global_mute_user(self, user_id, muted_by, reason, duration):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            mu = 0 if duration == 0 else time.time() + duration
            self.cursor.execute(
                "INSERT OR REPLACE INTO global_mutes (user_id, muted_by, reason, mute_until, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, muted_by, reason, mu, time.time())
            )
            self.conn.commit()
            return True

    def global_unmute_user(self, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM global_mutes WHERE user_id = ?", (user_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def is_globally_muted(self, user_id):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute("SELECT * FROM global_mutes WHERE user_id = ?", (user_id,))
            r = self.cursor.fetchone()
            if not r:
                return False
            if r["mute_until"] == 0:
                return True
            if time.time() > r["mute_until"]:
                self.cursor.execute("DELETE FROM global_mutes WHERE user_id = ?", (user_id,))
                self.conn.commit()
                return False
            return True

    def get_global_mute_info(self, user_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM global_mutes WHERE user_id = ?", (user_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def add_global_vig(self, user_id, issued_by, vig_type, reason):
        with self.lock:
            if user_id in GLOBAL_ADMINS:
                return False
            self.cursor.execute(
                "INSERT INTO global_vigs (user_id, issued_by, vig_type, reason, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, issued_by, vig_type, reason, time.time())
            )
            self.conn.commit()
            return True

    def remove_global_vigs(self, user_id):
        with self.lock:
            self.cursor.execute("DELETE FROM global_vigs WHERE user_id = ?", (user_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def remove_global_vig_by_id(self, vig_id):
        with self.lock:
            self.cursor.execute("DELETE FROM global_vigs WHERE id = ?", (vig_id,))
            r = self.cursor.rowcount > 0
            self.conn.commit()
            return r

    def get_global_vigs(self, user_id=None):
        with self.lock:
            if user_id:
                self.cursor.execute(
                    "SELECT * FROM global_vigs WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,)
                )
            else:
                self.cursor.execute("SELECT * FROM global_vigs ORDER BY created_at DESC")
            return [dict(r) for r in self.cursor.fetchall()]

    def get_global_vig_by_id(self, vig_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM global_vigs WHERE id = ?", (vig_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def create_ticket(self, user_id, problem_text, problem_type):
        with self.lock:
            self.cursor.execute(
                "INSERT INTO support_tickets (user_id, problem_text, problem_type, status, created_at) "
                "VALUES (?, ?, ?, 'open', ?)",
                (user_id, problem_text, problem_type, time.time())
            )
            self.conn.commit()
            return self.cursor.lastrowid

    def get_open_ticket(self, user_id):
        with self.lock:
            self.cursor.execute(
                "SELECT * FROM support_tickets WHERE user_id = ? AND status = 'open' "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            )
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def close_ticket(self, ticket_id, closed_by):
        with self.lock:
            self.cursor.execute(
                "UPDATE support_tickets SET status = 'closed', closed_at = ?, closed_by = ? WHERE id = ?",
                (time.time(), closed_by, ticket_id)
            )
            self.conn.commit()
            return self.cursor.rowcount > 0

    def get_ticket_by_id(self, ticket_id):
        with self.lock:
            self.cursor.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))
            r = self.cursor.fetchone()
            return dict(r) if r else None

    def get_all_chats_with_info(self):
        with self.lock:
            self.cursor.execute("SELECT peer_id, owner_id FROM chat_owners")
            return [dict(r) for r in self.cursor.fetchall()]


DEFAULT_CMD_PERMISSIONS = {
    "drbl": 80, "drnewrole": 90, "drdelrole": 90, "drrole": 80,
    "drroles": 0, "drhelp": 0, "drcmd": 100, "drban": 60,
    "drunban": 60, "drmute": 50, "drunmute": 50, "drkick": 50,
    "drvig": 50, "drunvig": 50, "drunbl": 80, "drtop": 0,
    "drconnect": 100, "drimport": 100, "drdelmsg": 50,
    "drstaff": 0, "drmsg": 1000,
    "drgban": 90, "drgunban": 90,
    "drgmute": 90, "drgunmute": 90, "drgkick": 90, "drgvig": 90,
    "drgunvig": 90, "drgrole": 90,
    "drlistchat": 1000, "drstart": 100,
    "drstats": 0, "drvlads": 1000, "drrenamrole": 1000,
    "drnotes": 50, "drcmdname": 90,
    "drgcmdname": 1000, "drchat": 80,
    "drnick": 0, "drgnick": 90,
    "drtrusted": 90, "drleader": 80,
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
        return self.get(key) is not None

    def __contains__(self, key):
        return self.has(key)


bl_pending = PendingStore(60)
vig_pending = PendingStore(60)
unbl_pending = PendingStore(60)
gvig_pending = PendingStore(60)
support_pending = PendingStore(300)
unvig_pending = PendingStore(120)
gunvig_pending = PendingStore(120)


class Handlers:
    def __init__(self, vk, db, group_id):
        self.vk = vk
        self.db = db
        self.group_id = group_id
        self._nc = {}

    def send(self, pid, msg, keyboard=None, attachment=None):
        p = {"peer_id": pid, "message": msg, "random_id": random.randint(0, 2 ** 31)}
        if keyboard:
            p["keyboard"] = keyboard.get_keyboard()
        if attachment:
            p["attachment"] = attachment
        try:
            self.vk.messages.send(**p)
        except Exception as e:
            logger.error(f"Send err: {e}")

    def get_vk_name(self, uid):
        if uid in self._nc:
            return self._nc[uid]
        try:
            i = self.vk.users.get(user_ids=uid)
            if i:
                n = f"{i[0]['first_name']} {i[0]['last_name']}"
                self._nc[uid] = n
                return n
        except Exception:
            pass
        return str(uid)

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
            if att_type in ("photo", "video", "doc", "audio", "audio_message", "wall", "graffiti"):
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
        return uid in GLOBAL_ADMINS

    def get_prio(self, pid, uid):
        s = self.db.get_settings(pid)
        if s.get("connected"):
            return self.db.get_user_priority_pool(pid, uid)
        return self.db.get_user_priority(pid, uid)

    def min_prio(self, pid, cmd):
        p = self.db.get_cmd_permission(pid, cmd)
        return p if p is not None else DEFAULT_CMD_PERMISSIONS.get(cmd, 100)

    def has_perm(self, pid, uid, cmd):
        return self.get_prio(pid, uid) >= self.min_prio(pid, cmd)

    def format_role(self, pid, uid):
        if self.is_ga(uid):
            return "⭐ Глобальный Администратор (1000)"
        if self.get_prio(pid, uid) >= 100 and self.db.get_chat_owner(pid) == uid:
            alias = self.db.get_role_alias(pid, 100)
            if alias:
                emoji = alias.get("alias_emoji", "") or ""
                name = alias.get("alias_name", "Владелец")
                return f"{emoji} {name} (100)" if emoji else f"👑 {name} (100)"
            return "👑 Владелец (100)"
        ri = self.db.get_user_role(pid, uid)
        if ri:
            emoji = ri.get("emoji", "") or ""
            return f"{emoji} {ri['role_name']} ({ri['priority']})" if emoji else f"{ri['role_name']} ({ri['priority']})"
        alias = self.db.get_role_alias(pid, 0)
        if alias:
            emoji = alias.get("alias_emoji", "") or ""
            name = alias.get("alias_name", "Пользователь")
            return f"{emoji} {name} (0)" if emoji else f"{name} (0)"
        return "Пользователь (0)"

    def auto_owner(self, pid, event):
        if self.db.get_chat_owner(pid) is not None:
            return
        try:
            ci = self.vk.messages.getConversationsById(peer_ids=pid, group_id=self.group_id)
            items = ci.get("items", [])
            if items:
                ow = items[0].get("chat_settings", {}).get("owner_id")
                if ow:
                    self.db.set_chat_owner(pid, ow)
                    return
        except Exception:
            pass
        fid = event.get("from_id", 0)
        if fid > 0:
            self.db.set_chat_owner(pid, fid)

    def parse_dur(self, t):
        t = t.strip().lower()
        if t in ('n', 'навсегда'):
            return 0, "навсегда"
        m = re.match(r'^(\d+)([smhd])$', t)
        if not m:
            return None, None
        a, u = int(m.group(1)), m.group(2)
        mul = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        nm = {'s': 'сек.', 'm': 'мин.', 'h': 'ч.', 'd': 'дн.'}
        return a * mul[u], f"{a} {nm[u]}"

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

    def fmt_time(self, ts):
        if ts == 0:
            return "навсегда"
        left = ts - time.time()
        if left <= 0:
            return "истекло"
        if left < 60:
            return f"{int(left)}с"
        if left < 3600:
            return f"{int(left / 60)}м"
        if left < 86400:
            return f"{int(left / 3600)}ч"
        return f"{int(left / 86400)}д"

    # ============ АНТИЧИТ РОЛЕЙ ============

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
            return False, f"🛡 Античит: приоритет цели ({tp}) ≥ вашего ({up}). Вы не можете это сделать."
        trusted = self.db.get_trusted(pid, tid)
        if trusted:
            min_p = trusted["min_punish_priority"]
            if up < min_p:
                return False, (
                    f"🛡 Античит: {self.mention(tid)} защищён. "
                    f"Наказать можно только с приоритетом ≥ {min_p}, ваш — {up}."
                )
        return True, ""

    def anticheat_check_unpunish(self, pid, fid, punisher_id):
        if self.is_ga(fid):
            return True, ""
        pp = self.get_prio(pid, punisher_id)
        up = self.get_prio(pid, fid)
        if pp > up:
            return False, (
                f"🛡 Античит: наказание выдал человек с приоритетом {pp}, "
                f"ваш — {up}. Вы не можете это снять."
            )
        return True, ""

    def anticheat_check_role_assign(self, pid, fid, tid, new_priority):
        if self.is_ga(fid):
            return True, ""
        up = self.get_prio(pid, fid)
        tcp = self.get_prio(pid, tid)
        if tcp >= up:
            return False, (
                f"🛡 Античит: приоритет цели ({tcp}) ≥ вашего ({up}). "
                f"Вы не можете менять роль этому пользователю."
            )
        if new_priority >= up:
            return False, f"🛡 Античит: нельзя выдать роль с приоритетом ({new_priority}) ≥ вашего ({up})."
        owner = self.db.get_chat_owner(pid)
        if owner and tid == owner:
            return False, "🛡 Античит: нельзя менять роль владельцу чата. Только ГА может это сделать."
        return True, ""

    def anticheat_check_role_remove(self, pid, fid, tid):
        if self.is_ga(fid):
            return True, ""
        up = self.get_prio(pid, fid)
        tcp = self.get_prio(pid, tid)
        if tcp >= up:
            return False, f"🛡 Античит: приоритет цели ({tcp}) ≥ вашего ({up}). Вы не можете снять роль."
        owner = self.db.get_chat_owner(pid)
        if owner and tid == owner:
            return False, "🛡 Античит: нельзя снять роль у владельца чата. Только ГА может это сделать."
        return True, ""

    def anticheat_check_role_create(self, pid, fid, priority):
        if self.is_ga(fid):
            return True, ""
        up = self.get_prio(pid, fid)
        if priority >= up:
            return False, (
                f"🛡 Античит: нельзя создать/изменить роль с приоритетом ({priority}) ≥ вашего ({up})."
            )
        return True, ""

    def anticheat_check_role_delete(self, pid, fid, priority):
        if self.is_ga(fid):
            return True, ""
        up = self.get_prio(pid, fid)
        if priority >= up:
            return False, f"🛡 Античит: нельзя удалить роль с приоритетом ({priority}) ≥ вашего ({up})."
        if priority >= 100:
            return False, "🛡 Античит: нельзя удалить роль владельца."
        return True, ""

    def anticheat_check_owner_change(self, pid, fid):
        if self.is_ga(fid):
            return True, ""
        return False, "🛡 Античит: сменить владельца чата может только Глобальный Администратор."

    # ============ ОБРАБОТКА СООБЩЕНИЙ ============

    def handle_chat_invite(self, pid, uid, inviter):
        if self.db.is_globally_banned(uid):
            gi = self.db.get_global_ban_info(uid)
            self.send(
                pid,
                f"⛔ {self.mention(uid)} в глобальном бане!\n"
                f"🛡 Забанил: {self.mention(gi['banned_by'])}\n"
                f"📌 Причина: {gi.get('reason', '')}\n"
                f"⏰ До: {self.fmt_time(gi.get('ban_until', 0))}"
            )
            self.kick(pid, uid)
            return
        bi = self.db.get_ban_info(pid, uid)
        if not bi:
            return
        banner_prio = self.get_prio(pid, bi["banned_by"])
        inviter_prio = self.get_prio(pid, inviter)
        if banner_prio > inviter_prio:
            self.send(
                pid,
                f"⛔ {self.mention(uid)} забанен!\n"
                f"🛡 Забанил: {self.mention(bi['banned_by'])}\n"
                f"📌 Причина: {bi.get('reason', '')}\n"
                f"⏰ До: {self.fmt_time(bi.get('ban_until', 0))}\n\n"
                f"❌ Приоритет забанившего ({banner_prio}) > вашего ({inviter_prio})"
            )
            self.kick(pid, uid)
        else:
            self.db.unban_user(pid, uid)
            self.send(pid, f"✅ {self.mention(uid)} разбанен автоматически.\n🛡 Добавил: {self.mention(inviter)}")

    def handle_message(self, msg):
        text = msg.get("text", "").strip()
        pid = msg.get("peer_id")
        fid = msg.get("from_id")
        action = msg.get("action")
        if not pid or not fid:
            return
        if action:
            if action.get("type") == "chat_invite_user":
                mid = action.get("member_id")
                if mid and mid > 0:
                    self.handle_chat_invite(pid, mid, fid)
                    return
        self.auto_owner(pid, msg)
        self.db.get_settings(pid)

        if not self.is_ga(fid):
            if self.db.is_globally_banned(fid):
                gi = self.db.get_global_ban_info(fid)
                self.send(pid, f"⛔ {self.mention(fid)} в глобальном бане!\n📌 {gi.get('reason', '')}")
                self.kick(pid, fid)
                return
            if self.db.is_globally_muted(fid):
                try:
                    cmid = msg.get("conversation_message_id")
                    if cmid:
                        self.vk.messages.delete(
                            cmids=cmid, peer_id=pid, delete_for_all=1, group_id=self.group_id
                        )
                except Exception:
                    pass
                return
            if self.db.is_muted(pid, fid):
                try:
                    cmid = msg.get("conversation_message_id")
                    if cmid:
                        self.vk.messages.delete(
                            cmids=cmid, peer_id=pid, delete_for_all=1, group_id=self.group_id
                        )
                except Exception:
                    pass
                return
            if self.db.is_banned(pid, fid):
                self.send(pid, f"{self.mention(fid)} в бане.")
                self.kick(pid, fid)
                return
            bl = self.db.is_blacklisted_in_chat(fid, pid)
            if bl:
                self.send(pid, f"{self.mention(fid)} в ЧС.")
                self.kick(pid, fid)
                return

        settings = self.db.get_settings(pid)
        if settings.get("chat_closed") and not self.is_ga(fid):
            if self.get_prio(pid, fid) < 80:
                try:
                    cmid = msg.get("conversation_message_id")
                    if cmid:
                        self.vk.messages.delete(
                            cmids=cmid, peer_id=pid, delete_for_all=1, group_id=self.group_id
                        )
                except Exception:
                    pass
                return

        if not text:
            return
        if fid > 0:
            self.db.increment_msg(pid, fid)

        tl = text.lower().strip()

        # Pending обработка
        if fid in support_pending:
            self.process_support_problem(pid, fid, text)
            return
        if fid in vig_pending and tl in ("грубый выговор", "выговор", "устный выговор"):
            self.process_vig_choice(pid, fid, tl)
            return
        if fid in gvig_pending and tl in ("грубый выговор", "выговор", "устный выговор"):
            self.process_gvig_choice(pid, fid, tl)
            return
        if fid in bl_pending and tl in ("чса", "чсл", "чсп", "чсс"):
            self.process_bl_choice(pid, fid, tl)
            return
        if fid in unbl_pending and tl in ("чса", "чсл", "чсп", "чсс", "все"):
            self.process_unbl_choice(pid, fid, tl)
            return

        # Заметки по #название
        if tl.startswith("#") and len(tl) > 1:
            note_name = tl[1:].strip()
            if note_name:
                note = self.db.get_note(pid, note_name)
                if note:
                    att = note.get("attachments", "") or None
                    note_text = note.get("note_text", "")
                    self.send(
                        pid,
                        note_text if note_text else f"📝 #{note_name}",
                        attachment=att if att else None
                    )
                    return

        # Приветствие The Sander
        if "the sander" in tl or "sander" in tl:
            self.send(
                pid,
                f"Привет, {self.mention(fid)}!\n"
                f"Я — бот DarknessRussia (CRMP).\n"
                f"Ваша роль » {self.format_role(pid, fid)}\n"
                f"Команды: /drhelp или !помощь"
            )
            return

        # Системные команды без тега
        if tl == "!id":
            r = f"🆔 Peer ID: {pid}"
            if pid > 2000000000:
                r += f"\n✅ Chat ID: {pid - 2000000000}"
            self.send(pid, r)
            return
        if tl == "!test":
            self.send(pid, "Бот работает! | DarknessRussia")
            return

        # Резолв алиасов
        resolved = self.db.resolve_alias(pid, text)
        if resolved:
            msg = dict(msg)
            msg["text"] = resolved
            text = resolved
            tl = text.lower().strip()

        # Разбор команды
        cmd_key, rest_text = resolve_command(text)
        if not cmd_key:
            # Попробуем после резолва алиаса
            return

        # Передаём управление нужному обработчику
        # Подставляем rest в текст для совместимости parse_target
        fake_msg = dict(msg)
        fake_msg["text"] = text  # оригинальный текст с тегом и командой

        dispatch = {
            "drhelp": self.cmd_help,
            "drnewrole": self.cmd_newrole,
            "drdelrole": self.cmd_delrole,
            "drroles": self.cmd_roles,
            "drrole": self.cmd_role,
            "drcmdname": self.cmd_cmdname,
            "drgcmdname": self.cmd_gcmdname,
            "drcmd": self.cmd_cmd,
            "drban": self.cmd_ban,
            "drunban": self.cmd_unban,
            "drmute": self.cmd_mute,
            "drunmute": self.cmd_unmute,
            "drkick": self.cmd_kick,
            "drbl": self.cmd_bl,
            "drunbl": self.cmd_unbl,
            "drvig": self.cmd_vig,
            "drunvig": self.cmd_unvig,
            "drtop": self.cmd_top,
            "drconnect": self.cmd_connect,
            "drimport": self.cmd_import,
            "drdelmsg": self.cmd_delmsg,
            "drstaff": self.cmd_staff,
            "drmsg": self.cmd_msg,
            "drgban": self.cmd_gban,
            "drgunban": self.cmd_gunban,
            "drgmute": self.cmd_gmute,
            "drgunmute": self.cmd_gunmute,
            "drgkick": self.cmd_gkick,
            "drgvig": self.cmd_gvig,
            "drgunvig": self.cmd_gunvig,
            "drlistchat": self.cmd_listchat,
            "drgrole": self.cmd_grole,
            "drstart": self.cmd_start,
            "drstats": self.cmd_stats,
            "drvlads": self.cmd_vlads,
            "drrenamrole": self.cmd_renamrole,
            "drnotes": self.cmd_notes,
            "drchat": self.cmd_chat,
            "drnick": self.cmd_nick,
            "drgnick": self.cmd_gnick,
            "drtrusted": self.cmd_trusted,
            "drleader": self.cmd_leader,
        }

        handler = dispatch.get(cmd_key)
        if handler:
            handler(fake_msg, pid, fid)

    # ============ КОМАНДЫ ============

    def cmd_help(self, e, pid, fid):
        self.send(
            pid,
            f"📖 Команды DarknessRussia (CRMP)\n"
            f"{self.mention(fid)} | {self.format_role(pid, fid)}\n\n"
            f"Теги команд:\n"
            f"  / — английские команды (/drban, /drhelp ...)\n"
            f"  ! — русские и английские команды (!бан, !drban ...)\n"
            f"  [пробел] — русские команды ( бан, помощь ...)\n\n"
            f"Модерация:\n"
            f"  /drban | !бан | бан\n"
            f"  /drunban | !разбан | разбан\n"
            f"  /drmute | !мут | мут\n"
            f"  /drunmute | !размут | размут\n"
            f"  /drkick | !кик | кик\n"
            f"  /drbl | !чс | чс\n"
            f"  /drunbl | !снятьчс | снятьчс\n"
            f"  /drvig | !выговор | выговор\n"
            f"  /drunvig | !снятьвыговор | снятьвыговор\n"
            f"  /drdelmsg | /drchat\n\n"
            f"Организации (CRMP):\n"
            f"  /drleader set [юзер] Организация | Должность\n"
            f"  /drleader rem [юзер]\n"
            f"  !лидер set ... | лидер set ...\n\n"
            f"Защита:\n"
            f"  /drtrusted [юзер] [приоритет] — защитить\n"
            f"  /drtrusted [юзер] off — снять\n"
            f"  !довер | довер\n\n"
            f"Ники:\n"
            f"  /drnick set [ник] | !ник set [ник] | ник set [ник]\n"
            f"  /drnick remove | !ник remove | ник remove\n"
            f"  /drgnick set [юзер] [ник] (90+)\n\n"
            f"Роли:\n"
            f"  /drnewrole /drdelrole /drrole /drroles /drstaff\n"
            f"  !новаяроль | !роль | !роли | !персонал\n\n"
            f"Глобальные (ГА/90+):\n"
            f"  /drgban /drgunban /drgmute /drgunmute\n"
            f"  /drgkick /drgvig /drgunvig /drgrole\n"
            f"  /drlistchat /drvlads /drrenamrole\n\n"
            f"Заметки:\n"
            f"  /drnotes list|create|del|[имя]\n"
            f"  !заметки | #название — быстрый вызов\n\n"
            f"Алиасы:\n"
            f"  /drcmdname /drban /бан !бан\n"
            f"  /drcmdname list | /drcmdname del [алиас]\n\n"
            f"Статистика:\n"
            f"  /drstats | !стата | стата\n\n"
            f"Рассылка (только привязанные чаты):\n"
            f"  /drmsg [текст]\n\n"
            f"Прочее:\n"
            f"  /drtop | !топ | топ\n"
            f"  /drconnect /drimport /drcmd\n\n"
            f"🛡 Античит ролей активен\n"
            f"⏱ Время: 1s/5m/2h/3d/n"
        )

    def cmd_chat(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drchat"):
            return self.send(pid, "❌ Нет прав (мин. 80).")
        text = e.get("text", "").strip()
        parts = text.split(maxsplit=2)
        # parts[0] — тег+команда, parts[1] — аргумент
        arg = parts[2].strip().lower() if len(parts) > 2 else (parts[1].strip().lower() if len(parts) > 1 else "")
        # Убираем саму команду из arg если она там есть
        for cmd_w in list(EN_CMDS.keys()) + list(RU_CMDS.keys()):
            if arg == cmd_w:
                arg = ""
                break

        if not arg:
            settings = self.db.get_settings(pid)
            status = "🔴 ЗАКРЫТ" if settings.get("chat_closed") else "🟢 ОТКРЫТ"
            return self.send(
                pid,
                f"💬 Статус чата: {status}\n\n"
                f"/drchat open — открыть чат\n"
                f"/drchat close — закрыть чат\n\n"
                f"Когда чат закрыт, писать могут только пользователи с ролью ≥ 80."
            )
        # Убираем имя команды из arg
        for prefix in ["/drchat ", "!drchat ", "!чат ", " чат "]:
            if arg.startswith(prefix.strip().lower()):
                arg = arg[len(prefix.strip()):].strip()
                break

        # Получаем последнее слово — аргумент
        raw = text.split()
        arg = raw[-1].lower() if raw else ""

        if arg == "close":
            self.db.update_setting(pid, "chat_closed", 1)
            self.send(
                pid,
                f"🔴 Чат закрыт!\n🛡 Закрыл: {self.mention(fid)}\n\n"
                f"💬 Писать могут только пользователи с ролью ≥ 80."
            )
        elif arg == "open":
            self.db.update_setting(pid, "chat_closed", 0)
            self.send(pid, f"🟢 Чат открыт!\n🛡 Открыл: {self.mention(fid)}")
        else:
            self.send(pid, "❌ /drchat open|close")

    def cmd_nick(self, e, pid, fid):
        text = e.get("text", "").strip()
        raw = text.split()
        # Находим позицию после команды
        # raw[0] = тег+команда или тег, raw[1] = команда если тег отдельный
        # Проще: ищем set/remove в токенах
        args_str = ""
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl in ("drnick", "ник"):
                args_str = " ".join(raw[i + 1:])
                break

        if not args_str:
            nick = self.db.get_display_nickname(pid, fid)
            if nick:
                return self.send(
                    pid,
                    f"🖲️ Ваш ник: {nick}\n\n"
                    f"/drnick set [ник] — установить\n"
                    f"/drnick remove — убрать\n"
                    f"/drnick set [юзер] [ник] — другому (80+)\n"
                    f"/drnick remove [юзер] — убрать другому (80+)"
                )
            return self.send(
                pid,
                f"🖲️ У вас нет ника.\n\n"
                f"/drnick set [ник] — установить\n"
                f"/drnick set [юзер] [ник] — другому (80+)\n"
                f"/drnick remove [юзер] — убрать другому (80+)"
            )

        al = args_str.lower()
        if al.startswith("set"):
            sr = args_str[3:].strip()
            if not sr:
                return self.send(pid, "❌ /drnick set [ник]\n/drnick set [юзер] [ник]")
            tid = self.parse_target_from_rest(sr, e)
            if tid and tid != fid:
                if self.get_prio(pid, fid) < 80:
                    return self.send(pid, "❌ Для смены ника другому нужен приоритет 80+.")
                nt = re.sub(r'\[id\d+\|[^\]]*\]', '', sr).strip()
                np = nt.split()
                if np:
                    try:
                        int(np[0])
                        np = np[1:]
                    except ValueError:
                        pass
                nick = " ".join(np).strip()
                if not nick:
                    return self.send(pid, "❌ Укажите ник.")
                if len(nick) > 32:
                    return self.send(pid, "❌ Ник не более 32 символов.")
                self.db.set_nickname(pid, tid, nick)
                self.send(pid, f"🖲️ Ник {self.mention(tid)} -> «{nick}»\n🛡 Установил: {self.mention(fid)}")
            else:
                if tid == fid:
                    nt = re.sub(r'\[id\d+\|[^\]]*\]', '', sr).strip()
                    np = nt.split()
                    if np:
                        try:
                            int(np[0])
                            np = np[1:]
                        except ValueError:
                            pass
                    nick = " ".join(np).strip()
                else:
                    nick = sr.strip()
                if not nick:
                    return self.send(pid, "❌ Укажите ник.")
                if len(nick) > 32:
                    return self.send(pid, "❌ Ник не более 32 символов.")
                self.db.set_nickname(pid, fid, nick)
                self.send(pid, f"🖲️ Ваш ник -> «{nick}»")
            return

        if al.startswith("remove"):
            rr = args_str[6:].strip()
            if rr:
                tid = self.parse_target_from_rest(rr, e)
                if tid and tid != fid:
                    if self.get_prio(pid, fid) < 80:
                        return self.send(pid, "❌ 80+.")
                    self.send(
                        pid,
                        f"🖲️ Ник {self.mention(tid)} убран.\n🛡 Снял: {self.mention(fid)}"
                        if self.db.remove_nickname(pid, tid) else "❌ Нет ника."
                    )
                else:
                    self.send(
                        pid,
                        "🖲️ Ваш ник убран." if self.db.remove_nickname(pid, fid) else "❌ Нет ника."
                    )
            else:
                reply = e.get("reply_message")
                fwd = e.get("fwd_messages", [])
                tid = None
                if reply:
                    tid = reply.get("from_id")
                elif fwd:
                    tid = fwd[0].get("from_id")
                if tid and tid > 0 and tid != fid:
                    if self.get_prio(pid, fid) < 80:
                        return self.send(pid, "❌ 80+.")
                    self.send(
                        pid,
                        f"🖲️ Ник {self.mention(tid)} убран.\n🛡 Снял: {self.mention(fid)}"
                        if self.db.remove_nickname(pid, tid) else "❌ Нет ника."
                    )
                else:
                    self.send(
                        pid,
                        "🖲️ Ваш ник убран." if self.db.remove_nickname(pid, fid) else "❌ Нет ника."
                    )
            return

        self.send(pid, "❌ /drnick set [ник] | /drnick remove")

    def cmd_gnick(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drgnick"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        text = e.get("text", "").strip()
        raw = text.split()
        args_str = ""
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl in ("drgnick",):
                args_str = " ".join(raw[i + 1:])
                break
        if not args_str:
            return self.send(
                pid,
                "🖲️ Глобальные ники:\n  /drgnick set [юзер] [ник]\n  /drgnick remove [юзер]"
            )
        al = args_str.lower()
        if al.startswith("set"):
            sr = args_str[3:].strip()
            if not sr:
                return self.send(pid, "❌ /drgnick set [юзер] [ник]")
            tid = self.parse_target_from_rest(sr, e)
            if not tid:
                return self.send(pid, "❌ Укажите юзера.")
            nt = re.sub(r'\[id\d+\|[^\]]*\]', '', sr).strip()
            np = nt.split()
            if np:
                try:
                    int(np[0])
                    np = np[1:]
                except ValueError:
                    pass
            nick = " ".join(np).strip()
            if not nick:
                return self.send(pid, "❌ Укажите ник.")
            if len(nick) > 32:
                return self.send(pid, "❌ Ник не более 32 символов.")
            self.db.set_global_nickname(tid, nick)
            self.send(
                pid,
                f"🌐🖲️ Глобальный ник {self.mention(tid)} -> «{nick}»\n🛡 Установил: {self.mention(fid)}"
            )
            return
        if al.startswith("remove"):
            rr = args_str[6:].strip()
            tid = self.parse_target_from_rest(rr, e)
            if not tid:
                reply = e.get("reply_message")
                if reply:
                    tid = reply.get("from_id")
                fwd = e.get("fwd_messages", [])
                if not tid and fwd:
                    tid = fwd[0].get("from_id")
            if not tid or tid <= 0:
                return self.send(pid, "❌ Укажите юзера.")
            self.send(
                pid,
                f"🌐🖲️ Глобальный ник {self.mention(tid)} убран.\n🛡 Снял: {self.mention(fid)}"
                if self.db.remove_global_nickname(tid) else "❌ Нет глобального ника."
            )
            return
        self.send(pid, "❌ /drgnick set [юзер] [ник] | /drgnick remove [юзер]")

    def cmd_stats(self, e, pid, fid):
        tid, _ = self.parse_target(e)
        target = tid if tid else fid
        name = self.mention(target)
        role_str = self.format_role(pid, target)
        nick = self.db.get_display_nickname(pid, target)
        nick_str = nick if nick else "Не установлен"
        trusted = self.db.get_trusted(pid, target)
        trusted_str = f"Защищён (≥ {trusted['min_punish_priority']})" if trusted else "Нет"

        leader_info = self.db.get_leader(pid, target)
        org_str = f"{leader_info['org_name']} | {leader_info['position']}" if leader_info else "Отсутствует"

        punishments = []
        ban_info = self.db.get_ban_info(pid, target)
        if ban_info and self.db.is_banned(pid, target):
            punishments.append(f"  🔴 Бан -> {self.fmt_time(ban_info.get('ban_until', 0))}")
        mute_info = self.db.get_mute_info(pid, target)
        if mute_info and self.db.is_muted(pid, target):
            punishments.append(f"  🟡 Мут -> {self.fmt_time(mute_info.get('mute_until', 0))}")
        vigs = self.db.get_vigs(pid, target)
        vig_icons = {"грубый выговор": "🔴", "выговор": "🟡", "устный выговор": "🟢"}
        for v in vigs:
            punishments.append(f"  {vig_icons.get(v['vig_type'], '⚠️')} {v['vig_type'].title()}")
        gban_info = self.db.get_global_ban_info(target)
        if gban_info and self.db.is_globally_banned(target):
            punishments.append(f"  🌐🔴 Глобальный бан -> {self.fmt_time(gban_info.get('ban_until', 0))}")
        gmute_info = self.db.get_global_mute_info(target)
        if gmute_info and self.db.is_globally_muted(target):
            punishments.append(f"  🌐🟡 Глобальный мут -> {self.fmt_time(gmute_info.get('mute_until', 0))}")
        punishments_str = "\n".join(punishments) if punishments else "  Нет"
        bl_entries = self.db.get_user_blacklist_entries(target, pid)
        bl_types_map = {"chat_admin": "ЧСА", "chat_local": "ЧСЛ", "full_project": "ЧСП", "full_strict": "ЧСС"}
        bl_str = (
            ", ".join(list(set([bl_types_map.get(b["bl_type"], b["bl_type"]) for b in bl_entries])))
            if bl_entries else "Нет"
        )
        self.send(
            pid,
            f"⚙️ Имя: {name}\n"
            f"🖲️ Ник в боте: {nick_str}\n"
            f"👾 Роль: {role_str}\n"
            f"📍 Организация и должность: {org_str}\n"
            f"🛡 Защита: {trusted_str}\n"
            f"🛡 Активные наказания:\n{punishments_str}\n"
            f"❇️ Активный чёрный список: {bl_str}"
        )

    def cmd_leader(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drleader"):
            return self.send(pid, "❌ Нет прав (мин. 80).")
        text = e.get("text", "").strip()
        raw = text.split()
        args_str = ""
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl in ("drleader", "лидер"):
                args_str = " ".join(raw[i + 1:])
                break

        if not args_str:
            leaders = self.db.get_leader_list(pid)
            if not leaders:
                txt = "📍 Организации: пусто\n\n"
            else:
                txt = "📍 Организации и должности:\n\n"
                for i, l in enumerate(leaders, 1):
                    txt += (
                        f"{i}. {self.mention(l['user_id'])}\n"
                        f"   📍 {l['org_name']} | {l['position']}\n"
                        f"   🛡 Назначил: {self.mention(l['set_by'])}\n"
                    )
                txt += f"\n📊 Всего: {len(leaders)}\n\n"
            txt += (
                "Использование:\n"
                "  /drleader set [юзер] Организация | Должность\n"
                "  /drleader rem [юзер] — снять должность\n\n"
                "Пример:\n"
                "  /drleader set @user МВД | Нч. УМВД"
            )
            return self.send(pid, txt)

        al = args_str.lower()

        if al.startswith("set"):
            sr = args_str[3:].strip()
            if not sr:
                return self.send(
                    pid,
                    "❌ /drleader set [юзер] Организация | Должность\n\nПример: /drleader set @user МВД | Нч. УМВД"
                )
            tid = self.parse_target_from_rest(sr, e)
            if not tid:
                return self.send(
                    pid,
                    "❌ Укажите пользователя.\n\n/drleader set [юзер] Организация | Должность"
                )
            clean = re.sub(r'\[id\d+\|[^\]]*\]', '', sr).strip()
            clean_parts = clean.split()
            if clean_parts:
                try:
                    int(clean_parts[0])
                    clean = " ".join(clean_parts[1:])
                except ValueError:
                    pass
            if "|" not in clean:
                return self.send(
                    pid,
                    "❌ Формат: Организация | Должность\n\nПример: /drleader set @user МВД | Нч. УМВД"
                )
            org_parts = clean.split("|", 1)
            org_name = org_parts[0].strip()
            position = org_parts[1].strip()
            if not org_name or not position:
                return self.send(
                    pid,
                    "❌ Укажите организацию и должность.\n\nПример: /drleader set @user МВД | Нч. УМВД"
                )
            if len(org_name) > 50:
                return self.send(pid, "❌ Название организации не более 50 символов.")
            if len(position) > 50:
                return self.send(pid, "❌ Должность не более 50 символов.")
            self.db.set_leader(pid, tid, org_name, position, fid)
            self.send(
                pid,
                f"📍 Назначение:\n"
                f"👾 {self.mention(tid)}\n"
                f"📍 {org_name} | {position}\n"
                f"🛡 Назначил: {self.mention(fid)}"
            )
            return

        if al.startswith("rem"):
            rr = args_str[3:].strip()
            if not rr:
                tid = self.parse_target_from_rest("", e)
                if not tid:
                    return self.send(pid, "❌ /drleader rem [юзер]")
            else:
                tid = self.parse_target_from_rest(rr, e)
                if not tid:
                    return self.send(pid, "❌ Укажите пользователя.\n\n/drleader rem [юзер]")
            if self.db.remove_leader(pid, tid):
                self.send(pid, f"📍 Должность {self.mention(tid)} снята.\n🛡 Снял: {self.mention(fid)}")
            else:
                self.send(pid, f"❌ У {self.mention(tid)} нет должности.")
            return

        self.send(pid, "❌ /drleader set [юзер] Организация | Должность\n/drleader rem [юзер]")

    def cmd_trusted(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drtrusted"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        text = e.get("text", "").strip()
        raw = text.split()
        args_str = ""
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl in ("drtrusted", "довер"):
                args_str = " ".join(raw[i + 1:])
                break

        if not args_str:
            tl = self.db.get_trusted_list(pid)
            if not tl:
                txt = "🛡 Доверенных пользователей нет.\n\n"
            else:
                txt = "🛡 Доверенные пользователи:\n\n"
                for i, t in enumerate(tl, 1):
                    txt += (
                        f"{i}. {self.mention(t['user_id'])} — мин. {t['min_punish_priority']}+\n"
                        f"   🛡 Установил: {self.mention(t['set_by'])}\n"
                    )
                txt += f"\n📊 Всего: {len(tl)}\n\n"
            txt += (
                "Использование:\n"
                "  /drtrusted [юзер] [мин.приоритет] — защитить\n"
                "  /drtrusted [юзер] off — снять защиту\n\n"
                "Пример: /drtrusted @user 90\n"
                "Только люди с приоритетом ≥ 90 смогут наказать этого юзера."
            )
            return self.send(pid, txt)

        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drtrusted [юзер] [мин.приоритет/off]")
        if self.is_ga(tid):
            return self.send(pid, "⛔ ГА уже защищён на максимальном уровне.")

        rest = rest.strip()
        if not rest:
            trusted = self.db.get_trusted(pid, tid)
            if trusted:
                self.send(
                    pid,
                    f"🛡 {self.mention(tid)} защищён.\n"
                    f"📌 Наказать можно только с приоритетом ≥ {trusted['min_punish_priority']}\n"
                    f"🛡 Установил: {self.mention(trusted['set_by'])}"
                )
            else:
                self.send(
                    pid,
                    f"🛡 {self.mention(tid)} не защищён.\n\n"
                    f"/drtrusted {tid} [мин.приоритет] — защитить\n"
                    f"/drtrusted {tid} off — снять"
                )
            return

        if rest.lower() == "off":
            if self.db.remove_trusted(pid, tid):
                self.send(pid, f"🛡 Защита {self.mention(tid)} снята.\n🛡 Снял: {self.mention(fid)}")
            else:
                self.send(pid, f"❌ {self.mention(tid)} не был защищён.")
            return

        try:
            min_p = int(rest.split()[0])
        except (ValueError, IndexError):
            return self.send(pid, "❌ Укажите число (1-1000) или off.\n\nПример: /drtrusted @user 90")
        if min_p < 1 or min_p > 1000:
            return self.send(pid, "❌ Диапазон: 1-1000.")

        up = self.get_prio(pid, fid)
        if min_p > up and not self.is_ga(fid):
            return self.send(
                pid,
                f"🛡 Античит: нельзя установить защиту ({min_p}) выше вашего приоритета ({up})."
            )

        self.db.set_trusted(pid, tid, min_p, fid)
        self.send(
            pid,
            f"🛡 {self.mention(tid)} защищён!\n"
            f"📌 Наказать можно только с приоритетом ≥ {min_p}\n"
            f"🛡 Установил: {self.mention(fid)}"
        )

    def cmd_cmdname(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drcmdname"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        text = e.get("text", "").strip()
        raw = text.split()
        args_str = ""
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl == "drcmdname":
                args_str = " ".join(raw[i + 1:])
                break
        if not args_str:
            return self.send(
                pid,
                "📝 Использование:\n"
                "  /drcmdname /drban /бан !бан\n"
                "  /drcmdname list — список алиасов\n"
                "  /drcmdname del [алиас] — удалить алиас"
            )
        al = args_str.lower()
        if al == "list":
            aliases = self.db.get_cmd_aliases(pid)
            if not aliases:
                return self.send(pid, "📝 Алиасов нет.\n\nСоздать: /drcmdname /drban /бан !бан")
            txt = "📝 Алиасы команд:\n\n"
            for a in aliases:
                txt += f"  /{a['original_cmd']} -> {a['alias']}\n"
            return self.send(pid, txt)
        if al.startswith("del "):
            atd = args_str[4:].strip().lower()
            if not atd:
                return self.send(pid, "❌ Укажите алиас.")
            self.send(
                pid,
                f"🗑 Алиас «{atd}» удалён." if self.db.remove_cmd_alias(pid, atd) else f"❌ Не найден."
            )
            return
        tokens = args_str.split()
        if len(tokens) < 2:
            return self.send(pid, "❌ Укажите команду и алиасы.")
        original = tokens[0].lower().replace("/", "").strip()
        if original not in DEFAULT_CMD_PERMISSIONS:
            return self.send(pid, f"❌ Неизвестная: {original}")
        added = [
            alias for t in tokens[1:]
            if (alias := t.strip().lower()) and self.db.add_cmd_alias(pid, original, alias)
        ]
        self.send(
            pid,
            f"✅ Алиасы для /{original}:\n  " + "\n  ".join(added) if added else "❌ Не удалось."
        )

    def cmd_gcmdname(self, e, pid, fid):
        if not self.is_ga(fid):
            return self.send(pid, "❌ Только ГА.")
        text = e.get("text", "").strip()
        raw = text.split()
        args_str = ""
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl == "drgcmdname":
                args_str = " ".join(raw[i + 1:])
                break
        if not args_str:
            return self.send(
                pid,
                "📝 Глобальные алиасы:\n  /drgcmdname /drban /бан !бан\n  /drgcmdname list\n  /drgcmdname del [алиас]"
            )
        al = args_str.lower()
        if al == "list":
            aliases = self.db.get_global_cmd_aliases()
            if not aliases:
                return self.send(pid, "📝 Глобальных алиасов нет.")
            txt = "📝 Глобальные алиасы:\n\n"
            for a in aliases:
                txt += f"  /{a['original_cmd']} -> {a['alias']}\n"
            return self.send(pid, txt)
        if al.startswith("del "):
            atd = args_str[4:].strip().lower()
            if not atd:
                return self.send(pid, "❌ Укажите алиас.")
            self.send(
                pid,
                f"🗑 Глобальный алиас «{atd}» удалён."
                if self.db.remove_global_cmd_alias(atd) else f"❌ Не найден."
            )
            return
        tokens = args_str.split()
        if len(tokens) < 2:
            return self.send(pid, "❌ Укажите команду и алиасы.")
        original = tokens[0].lower().replace("/", "").strip()
        if original not in DEFAULT_CMD_PERMISSIONS:
            return self.send(pid, f"❌ Неизвестная: {original}")
        added = [
            alias for t in tokens[1:]
            if (alias := t.strip().lower()) and self.db.add_global_cmd_alias(original, alias)
        ]
        self.send(
            pid,
            f"🌐 Глобальные алиасы для /{original}:\n  " + "\n  ".join(added) if added else "❌ Не удалось."
        )

    def cmd_grole(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drgrole"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drgrole [юзер] [приоритет]")
        if self.is_ga(tid) and not self.is_ga(fid):
            return self.send(pid, "⛔ ГА защищён.")
        try:
            pa = int(rest.strip().split()[0])
        except (ValueError, IndexError):
            return self.send(pid, "❌ Укажите приоритет.")
        all_peers = self.db.get_all_chat_peers()
        assigned = 0
        removed = 0
        if pa == 0:
            for peer in all_peers:
                ok, _ = self.db.remove_role(peer, tid)
                if ok:
                    removed += 1
                    if peer != pid:
                        self.send(peer, f"🌐 ГЛОБАЛЬНАЯ СМЕНА РОЛИ\n👾 {self.mention(tid)} -> Без роли (0)\n🛡 Выдал: {self.mention(fid)}")
            return self.send(
                pid,
                f"🌐 ГЛОБАЛЬНАЯ СМЕНА РОЛИ\n"
                f"👾 {self.mention(tid)} -> Без роли (0)\n"
                f"🛡 Выдал: {self.mention(fid)}\n"
                f"🌍 Снято в {removed}/{len(all_peers)} чатах"
            )
        for peer in all_peers:
            role = self.db.get_role_by_priority(peer, pa)
            if role:
                old_role = self.format_role(peer, tid)
                ok, _ = self.db.assign_role(peer, tid, pa)
                if ok:
                    assigned += 1
                    if peer != pid:
                        self.send(
                            peer,
                            f"🌐 ГЛОБАЛЬНАЯ СМЕНА РОЛИ\n"
                            f"👾 {self.mention(tid)}\n"
                            f"{old_role} -> {self.format_role(peer, tid)}\n"
                            f"🛡 Выдал: {self.mention(fid)}"
                        )
        self.send(
            pid,
            f"🌐 ГЛОБАЛЬНАЯ СМЕНА РОЛИ\n"
            f"👾 {self.mention(tid)} -> приоритет {pa}\n"
            f"🛡 Выдал: {self.mention(fid)}\n"
            f"🌍 Назначено в {assigned}/{len(all_peers)} чатах"
        )

    def cmd_notes(self, e, pid, fid):
        text = e.get("text", "").strip()
        raw = text.split()
        args_str = ""
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl in ("drnotes", "заметки"):
                args_str = " ".join(raw[i + 1:])
                break
        if not args_str:
            return self.send(
                pid,
                "📝 Использование:\n"
                "  /drnotes list — список\n"
                "  /drnotes create [название] [текст] — создать\n"
                "  /drnotes [название] — показать\n"
                "  /drnotes del [название] — удалить\n"
                "  #название — быстрый вызов"
            )
        al = args_str.lower()
        if al == "list":
            notes = self.db.get_all_notes(pid)
            if not notes:
                return self.send(pid, "📝 Заметок нет.")
            txt = "📝 Заметки чата:\n\n"
            for i, n in enumerate(notes, 1):
                txt += f"{i}. #{n['note_name']}{'📎' if n.get('attachments') else ''}\n"
            return self.send(pid, txt + f"\n📊 Всего: {len(notes)}")
        if al.startswith("create "):
            if not self.has_perm(pid, fid, "drnotes"):
                return self.send(pid, "❌ Нет прав.")
            cr = args_str[7:].strip()
            if not cr:
                return self.send(pid, "❌ /drnotes create [название] [текст]")
            cp = cr.split(maxsplit=1)
            nn = cp[0].strip().lower()
            nt = cp[1].strip() if len(cp) > 1 else ""
            if not re.match(r'^[a-zа-яё0-9_\-]+$', nn):
                return self.send(pid, "❌ Название: буквы, цифры, _ и -")
            att = self.extract_attachments(e)
            if not nt and not att:
                return self.send(pid, "❌ Укажите текст и/или прикрепите файлы.")
            if self.db.get_note(pid, nn):
                ok, mr = self.db.update_note(pid, nn, nt, att, fid)
                self.send(pid, f"✅ Заметка #{nn} обновлена." if ok else f"❌ {mr}")
            else:
                ok, mr = self.db.create_note(pid, nn, nt, att, fid)
                self.send(pid, f"✅ Заметка #{nn} создана.\nВызов: #{nn}" if ok else f"❌ {mr}")
            return
        if al.startswith("del "):
            if not self.has_perm(pid, fid, "drnotes"):
                return self.send(pid, "❌ Нет прав.")
            nn = args_str[4:].strip().lower()
            if not nn:
                return self.send(pid, "❌ /drnotes del [название]")
            ok, mr = self.db.delete_note(pid, nn)
            self.send(pid, f"🗑 Заметка #{nn} удалена." if ok else f"❌ {mr}")
            return
        note = self.db.get_note(pid, al.strip())
        if note:
            att = note.get("attachments", "") or None
            self.send(pid, note.get("note_text", "") or f"📝 #{al.strip()}", attachment=att if att else None)
        else:
            self.send(pid, f"❌ Заметка #{al.strip()} не найдена.")

    def cmd_vlads(self, e, pid, fid):
        ok, err = self.anticheat_check_owner_change(pid, fid)
        if not ok:
            return self.send(pid, err)
        tid, _ = self.parse_target(e)
        if not tid or tid <= 0:
            return self.send(pid, "❌ /drvlads [юзер]")
        old_owner = self.db.get_chat_owner(pid)
        if old_owner and old_owner != tid:
            self.db.remove_role(pid, old_owner)
        self.db.set_chat_owner(pid, tid)
        self.send(pid, f"〽️ Новый владелец чата -> {self.mention(tid)}")

    def cmd_renamrole(self, e, pid, fid):
        if not self.is_ga(fid):
            return self.send(pid, "❌ Только ГА.")
        parts = e.get("text", "").split(maxsplit=2)
        if len(parts) < 3:
            return self.send(pid, "❌ /drrenamrole [0|100] [Эмодзи Название]")
        try:
            priority = int(parts[1])
        except ValueError:
            return self.send(pid, "❌ Число (0 или 100).")
        if priority not in (0, 100):
            return self.send(pid, "❌ Только 0 или 100.")
        rt = parts[2].strip()
        emoji, rn = "", rt
        ep = re.match(
            r'^([\U0001F000-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\u2600-\u26FF\u2700-\u27BF])\s*(.+)$',
            rt
        )
        if ep:
            emoji, rn = ep.group(1), ep.group(2).strip()
        self.db.set_role_alias(pid, priority, rn, emoji)
        d = f"{emoji} {rn} ({priority})" if emoji else f"{rn} ({priority})"
        self.send(
            pid,
            f"✅ «{'Пользователь' if priority == 0 else 'Владелец'} ({priority})» -> «{d}»"
        )

    def cmd_ban(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drban"):
            return self.send(pid, "❌ Нет прав.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drban [юзер] [время] [причина]")
        ok, err = self.anticheat_check_punish(pid, fid, tid)
        if not ok:
            return self.send(pid, err)
        parts = rest.split(maxsplit=1)
        if not parts:
            return self.send(pid, "❌ Укажите время.")
        dur, ht = self.parse_dur(parts[0])
        if dur is None:
            return self.send(pid, "❌ Неверное время.")
        reason = parts[1].strip() if len(parts) > 1 else "Не указана"
        self.db.ban_user(pid, tid, fid, reason, dur)
        self.kick(pid, tid)
        self.send(
            pid,
            f"👾 Бан: {self.mention(tid)}\n"
            f"🛡 Выдал: {self.mention(fid)}\n"
            f"〽️ Роль: {self.format_role(pid, fid)}\n"
            f"🌹 Роль нарушителя: {self.format_role(pid, tid)}\n"
            f"📌 {reason} | {ht}"
        )

    def cmd_unban(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drunban"):
            return self.send(pid, "❌ Нет прав.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drunban [юзер]")
        bi = self.db.get_ban_info(pid, tid)
        if bi:
            ok, err = self.anticheat_check_unpunish(pid, fid, bi["banned_by"])
            if not ok:
                return self.send(pid, err)
        self.send(
            pid,
            f"👾 Разбан: {self.mention(tid)}\n🛡 Снял: {self.mention(fid)}"
            if self.db.unban_user(pid, tid) else f"❌ {self.mention(tid)} не в бане."
        )

    def cmd_mute(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drmute"):
            return self.send(pid, "❌ Нет прав.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drmute [юзер] [время] [причина]")
        ok, err = self.anticheat_check_punish(pid, fid, tid)
        if not ok:
            return self.send(pid, err)
        parts = rest.split(maxsplit=1)
        if not parts:
            return self.send(pid, "❌ Укажите время.")
        dur, ht = self.parse_dur(parts[0])
        if dur is None:
            return self.send(pid, "❌ Неверное время.")
        reason = parts[1].strip() if len(parts) > 1 else "Не указана"
        self.db.mute_user(pid, tid, fid, reason, dur)
        self.send(
            pid,
            f"👾 Мут: {self.mention(tid)}\n"
            f"🛡 Выдал: {self.mention(fid)}\n"
            f"〽️ Роль: {self.format_role(pid, fid)}\n"
            f"🌹 Роль нарушителя: {self.format_role(pid, tid)}\n"
            f"📌 {reason} | {ht}"
        )

    def cmd_unmute(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drunmute"):
            return self.send(pid, "❌ Нет прав.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drunmute [юзер]")
        mi = self.db.get_mute_info(pid, tid)
        if mi:
            ok, err = self.anticheat_check_unpunish(pid, fid, mi["muted_by"])
            if not ok:
                return self.send(pid, err)
        self.send(
            pid,
            f"👾 Размут: {self.mention(tid)}\n🛡 Снял: {self.mention(fid)}"
            if self.db.unmute_user(pid, tid) else f"❌ {self.mention(tid)} не в муте."
        )

    def cmd_kick(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drkick"):
            return self.send(pid, "❌ Нет прав.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drkick [юзер] [причина]")
        ok, err = self.anticheat_check_punish(pid, fid, tid)
        if not ok:
            return self.send(pid, err)
        reason = rest.strip() or "Не указана"
        self.send(
            pid,
            f"👾 Кик: {self.mention(tid)}\n"
            f"🛡 Выдал: {self.mention(fid)}\n"
            f"〽️ Роль: {self.format_role(pid, fid)}\n"
            f"🌹 Роль нарушителя: {self.format_role(pid, tid)}\n"
            f"📌 {reason}"
            if self.kick(pid, tid) else "❌ Не удалось кикнуть."
        )

    def cmd_vig(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drvig"):
            return self.send(pid, "❌ Нет прав.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drvig [юзер] [причина]")
        ok, err = self.anticheat_check_punish(pid, fid, tid)
        if not ok:
            return self.send(pid, err)
        reason = rest.strip() or "Не указана"
        vig_pending.set(fid, {"target_id": tid, "peer_id": pid, "reason": reason})
        kb = VkKeyboard(inline=True)
        kb.add_callback_button(
            "Грубый выговор", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button": "vig_грубый выговор"})
        )
        kb.add_line()
        kb.add_callback_button(
            "Выговор", color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button": "vig_выговор"})
        )
        kb.add_line()
        kb.add_callback_button(
            "Устный выговор", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button": "vig_устный выговор"})
        )
        self.send(pid, f"⚠️ Выговор для {self.mention(tid)}\n📋 {reason}\n\nВыберите тип:", keyboard=kb)

    def process_vig_choice(self, pid, fid, choice):
        p = vig_pending.pop(fid)
        if not p:
            return self.send(pid, "❌ Нет запроса.")
        if time.time() - p["_created"] > 60:
            return self.send(pid, "⏰ Истекло.")
        tid, reason = p["target_id"], p["reason"]
        icons = {"грубый выговор": "🔴", "выговор": "🟡", "устный выговор": "🟢"}
        self.db.add_vig(pid, tid, fid, choice, reason)
        total = len(self.db.get_vigs(pid, tid))
        self.send(
            pid,
            f"👾 {icons.get(choice, '')} {choice.title()}: {self.mention(tid)}\n"
            f"🛡 Выдал: {self.mention(fid)}\n"
            f"〽️ Роль: {self.format_role(pid, fid)}\n"
            f"🌹 {self.format_role(pid, tid)}\n"
            f"📌 {reason}\n"
            f"📊 Всего: {total}"
        )

    def cmd_unvig(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drunvig"):
            return self.send(pid, "❌ Нет прав.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drunvig [юзер]")
        mx = self.db.get_vig_issuer_max_priority(pid, tid)
        mp = self.get_prio(pid, fid)
        if mx > mp and not self.is_ga(fid):
            return self.send(
                pid,
                f"🛡 Античит: наказание выдал человек с приоритетом {mx}, ваш — {mp}. Вы не можете это снять."
            )
        vigs = self.db.get_vigs(pid, tid)
        if not vigs:
            return self.send(pid, f"❌ У {self.mention(tid)} нет выговоров.")
        icons = {"грубый выговор": "🔴", "выговор": "🟡", "устный выговор": "🟢"}
        txt = f"📋 Выговоры {self.mention(tid)}:\n\n"
        kb = VkKeyboard(inline=True)
        for i, v in enumerate(vigs[:5], 1):
            txt += (
                f"{i}. {icons.get(v['vig_type'], '')} {v['vig_type'].title()}\n"
                f"   📌 {v['reason']}\n"
                f"   🛡 Выдал: {self.mention(v['issued_by'])}\n"
            )
            kb.add_callback_button(
                f"❌ #{i}", color=VkKeyboardColor.NEGATIVE,
                payload=json.dumps({"button": f"unvig_{v['id']}"})
            )
            if i < len(vigs[:5]):
                kb.add_line()
        kb.add_line()
        kb.add_callback_button(
            "🗑 Снять все", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button": f"unvig_all_{tid}_{pid}"})
        )
        unvig_pending.set(fid, {"target_id": tid, "peer_id": pid})
        self.send(pid, txt + "\nВыберите выговор для снятия или снимите все:", keyboard=kb)

    def process_unvig_single(self, pid, fid, vig_id):
        p = unvig_pending.pop(fid)
        if not p:
            return self.send(pid, "❌ Нет запроса.")
        vig = self.db.get_vig_by_id(vig_id)
        if not vig:
            return self.send(pid, "❌ Выговор не найден.")
        icons = {"грубый выговор": "🔴", "выговор": "🟡", "устный выговор": "🟢"}
        self.send(
            pid,
            f"✅ Выговор снят: {icons.get(vig['vig_type'], '')} {vig['vig_type'].title()}\n"
            f"👾 {self.mention(vig['user_id'])}\n"
            f"🛡 Снял: {self.mention(fid)}"
            if self.db.remove_vig_by_id(vig_id) else "❌ Не удалось."
        )

    def process_unvig_all(self, pid, fid, tid):
        p = unvig_pending.pop(fid)
        if not p:
            return self.send(pid, "❌ Нет запроса.")
        self.send(
            pid,
            f"👾 Все выговоры сняты: {self.mention(tid)}\n🛡 Снял: {self.mention(fid)}"
            if self.db.remove_vigs(pid, tid) else f"❌ Нет выговоров."
        )

    def cmd_bl(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drbl"):
            return self.send(pid, "❌ Нет прав.")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drbl [юзер] [причина]")
        ok, err = self.anticheat_check_punish(pid, fid, tid)
        if not ok:
            return self.send(pid, err)
        reason = rest.strip() or "Не указана"
        bl_pending.set(fid, {"target_id": tid, "peer_id": pid, "reason": reason})
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("ЧСА", color=VkKeyboardColor.PRIMARY, payload=json.dumps({"button": "ЧСА"}))
        kb.add_callback_button("ЧСЛ", color=VkKeyboardColor.PRIMARY, payload=json.dumps({"button": "ЧСЛ"}))
        kb.add_line()
        kb.add_callback_button("ЧСП", color=VkKeyboardColor.NEGATIVE, payload=json.dumps({"button": "ЧСП"}))
        kb.add_callback_button("ЧСС", color=VkKeyboardColor.NEGATIVE, payload=json.dumps({"button": "ЧСС"}))
        self.send(
            pid,
            f"⛔ ЧС для {self.mention(tid)}\n📋 {reason}\n\n"
            f"🔹 ЧСА/ЧСЛ — этот чат\n🔴 ЧСП/ЧСС — все чаты\n⏰ 60с",
            keyboard=kb
        )

    def process_bl_choice(self, pid, fid, choice):
        p = bl_pending.pop(fid)
        if not p:
            return self.send(pid, "❌ Нет запроса.")
        if time.time() - p["_created"] > 60:
            return self.send(pid, "⏰ Истекло.")
        tid, op, reason = p["target_id"], p["peer_id"], p["reason"]
        tr = self.format_role(pid, tid)
        tm = {"чса": "chat_admin", "чсл": "chat_local", "чсп": "full_project", "чсс": "full_strict"}
        tn = {"чса": "ЧСА", "чсл": "ЧСЛ", "чсп": "ЧСП", "чсс": "ЧСС"}
        if not self.db.add_to_blacklist(tid, op, tm[choice], fid, reason):
            return self.send(pid, "⛔ Защита ГА.")
        name = tn[choice]
        if choice in ("чса", "чсл"):
            self.db.ban_user(op, tid, fid, f"{name}: {reason}", 0)
            self.kick(op, tid)
            self.send(op, f"⛔ {self.mention(tid)}\n🌹 {tr} → {name}\n📋 {reason}")
        else:
            ap = self.db.get_all_chat_peers()
            for cp in ap:
                self.db.ban_user(cp, tid, fid, f"{name}: {reason}", 0)
                if self.kick(cp, tid) and cp != op:
                    self.send(cp, f"⛔ {self.mention(tid)} → {name}\n📋 {reason}")
            self.send(op, f"⛔ {self.mention(tid)}\n🌹 {tr} → {name}\n📋 {reason}\n🌐 Во всех ({len(ap)}).")

    def cmd_unbl(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drunbl"):
            return self.send(pid, "❌ Нет прав.")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drunbl [юзер]")
        unbl_pending.set(fid, {"target_id": tid, "peer_id": pid})
        kb = VkKeyboard(inline=True)
        kb.add_callback_button("ЧСА", color=VkKeyboardColor.PRIMARY, payload=json.dumps({"button": "unbl_ЧСА"}))
        kb.add_callback_button("ЧСЛ", color=VkKeyboardColor.PRIMARY, payload=json.dumps({"button": "unbl_ЧСЛ"}))
        kb.add_line()
        kb.add_callback_button("ЧСП", color=VkKeyboardColor.NEGATIVE, payload=json.dumps({"button": "unbl_ЧСП"}))
        kb.add_callback_button("ЧСС", color=VkKeyboardColor.NEGATIVE, payload=json.dumps({"button": "unbl_ЧСС"}))
        kb.add_line()
        kb.add_callback_button("ВСЕ", color=VkKeyboardColor.POSITIVE, payload=json.dumps({"button": "unbl_ВСЕ"}))
        self.send(pid, f"🔓 Убрать {self.mention(tid)} из ЧС:", keyboard=kb)

    def process_unbl_choice(self, pid, fid, choice):
        p = unbl_pending.pop(fid)
        if not p:
            return self.send(pid, "❌ Нет запроса.")
        if time.time() - p["_created"] > 60:
            return self.send(pid, "⏰ Истекло.")
        tid = p["target_id"]
        tm = {"чса": "chat_admin", "чсл": "chat_local", "чсп": "full_project", "чсс": "full_strict"}
        if choice == "все":
            self.send(
                pid,
                f"✅ {self.mention(tid)} убран из всех ЧС."
                if self.db.remove_from_blacklist_global(tid) else f"❌ Не в ЧС."
            )
        else:
            self.send(
                pid,
                f"✅ Убран из {choice.upper()}."
                if self.db.remove_from_blacklist(tid, p["peer_id"], tm[choice]) else f"❌ Не найден."
            )

    def cmd_newrole(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drnewrole"):
            return self.send(pid, "❌ Нет прав.")
        parts = e.get("text", "").split(maxsplit=3)
        # parts[0]=тег+cmd или тег, parts[1]=приоритет, parts[2]=название
        # Найдём приоритет и название
        pr_str = ""
        rname_str = ""
        raw = e.get("text", "").split()
        cmd_found = False
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl in ("drnewrole", "новаяроль"):
                if i + 1 < len(raw):
                    pr_str = raw[i + 1]
                if i + 2 < len(raw):
                    rname_str = " ".join(raw[i + 2:])
                cmd_found = True
                break
        if not cmd_found or not pr_str:
            return self.send(pid, "❌ /drnewrole [приоритет] [Эмодзи Название]")
        try:
            pr = int(pr_str)
        except ValueError:
            return self.send(pid, "❌ Приоритет — число.")
        if pr < 1 or pr > 99:
            return self.send(pid, "❌ 1-99.")
        ok, err = self.anticheat_check_role_create(pid, fid, pr)
        if not ok:
            return self.send(pid, err)
        if not rname_str:
            return self.send(pid, "❌ /drnewrole [приоритет] [Эмодзи Название]")
        rt = rname_str.strip()
        emoji, rn = "", rt
        ep = re.match(
            r'^([\U0001F000-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\u2600-\u26FF\u2700-\u27BF])\s*(.+)$',
            rt
        )
        if ep:
            emoji, rn = ep.group(1), ep.group(2).strip()
        ok, status = self.db.create_or_update_role(pid, rn, pr, emoji)
        if ok:
            d = f"{emoji} {rn} ({pr})" if emoji else f"{rn} ({pr})"
            self.send(
                pid,
                f"✅ Роль ({pr}) обновлена -> «{d}»" if status == "updated" else f"✅ Роль «{d}» создана."
            )
        else:
            self.send(pid, f"❌ {status}")

    def cmd_delrole(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drdelrole"):
            return self.send(pid, "❌ Нет прав.")
        raw = e.get("text", "").split()
        pr_str = ""
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl in ("drdelrole", "удалитьроль"):
                if i + 1 < len(raw):
                    pr_str = raw[i + 1]
                break
        if not pr_str:
            return self.send(pid, "❌ /drdelrole [приоритет]")
        try:
            pr = int(pr_str)
        except ValueError:
            return self.send(pid, "❌ Число.")
        ok, err = self.anticheat_check_role_delete(pid, fid, pr)
        if not ok:
            return self.send(pid, err)
        r = self.db.get_role_by_priority(pid, pr)
        d = (
            f"{(dict(r).get('emoji', '') or '')} {dict(r)['role_name']} ({pr})"
            if r else f"? ({pr})"
        )
        ok, mr = self.db.delete_role(pid, pr)
        self.send(pid, f"🗑 Роль «{d.strip()}» удалена." if ok else f"❌ {mr}")

    def cmd_role(self, e, pid, fid):
        text = e.get("text", "")
        tid, rest = self.parse_target(e)
        raw = text.split()
        # Если нет аргументов — показать свою роль
        cmd_idx = None
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl in ("drrole", "роль"):
                cmd_idx = i
                break
        args_after_cmd = raw[cmd_idx + 1:] if cmd_idx is not None else []

        if not args_after_cmd:
            return self.send(pid, f"Ваша роль » {self.format_role(pid, fid)}")
        if tid and not rest.strip():
            return self.send(pid, f"Роль {self.mention(tid)} » {self.format_role(pid, tid)}")
        if not self.has_perm(pid, fid, "drrole"):
            return self.send(pid, "❌ Нет прав.")
        if not tid:
            return self.send(pid, "❌ /drrole [юзер] [приоритет/0]")
        try:
            pa = int(rest.strip().split()[0])
        except (ValueError, IndexError):
            return self.send(pid, "❌ Укажите приоритет.")
        if pa == 0:
            ok, err = self.anticheat_check_role_remove(pid, fid, tid)
            if not ok:
                return self.send(pid, err)
            old = self.format_role(pid, tid)
            ok, mr = self.db.remove_role(pid, tid)
            return self.send(
                pid,
                f"👾 {self.mention(tid)}\n{old} -> {self.format_role(pid, tid)}\n📌 Сменил: {self.mention(fid)}"
                if ok else f"❌ {mr}"
            )
        if pa < 1 or pa > 99:
            return self.send(pid, "❌ 1-99.")
        ok, err = self.anticheat_check_role_assign(pid, fid, tid, pa)
        if not ok:
            return self.send(pid, err)
        old = self.format_role(pid, tid)
        ok, res = self.db.assign_role(pid, tid, pa)
        self.send(
            pid,
            f"👾 {self.mention(tid)}\n{old} -> {self.format_role(pid, tid)}\n📌 Сменил: {self.mention(fid)}"
            if ok else f"❌ {res}"
        )

    def cmd_roles(self, e, pid, fid):
        roles = self.db.get_roles(pid)
        oid = self.db.get_chat_owner(pid)
        txt = "📋 Роли чата\n\n⭐ Глобальный Администратор (1000)\n"
        if oid:
            a100 = self.db.get_role_alias(pid, 100)
            if a100:
                em = a100.get("alias_emoji", "") or ""
                nm = a100.get("alias_name", "Владелец")
                txt += f"{em} {nm} (100)\n" if em else f"👑 {nm} (100)\n"
            else:
                txt += "👑 Владелец (100)\n"
        if roles:
            txt += "\n"
            for r in roles:
                rd = dict(r)
                em = rd.get("emoji", "") or ""
                txt += f"{em} {rd['role_name']} ({rd['priority']})\n" if em else f"{rd['role_name']} ({rd['priority']})\n"
        a0 = self.db.get_role_alias(pid, 0)
        if a0:
            em = a0.get("alias_emoji", "") or ""
            nm = a0.get("alias_name", "Пользователь")
            txt += f"\n{em} {nm} (0)\n" if em else f"\n{nm} (0)\n"
        else:
            txt += f"\nПользователь (0)\n"
        self.send(pid, txt + f"\n📌 Всего: {len(roles) + 2}")

    def cmd_staff(self, e, pid, fid):
        staff = self.db.get_chat_staff(pid)
        oid = self.db.get_chat_owner(pid)
        rg = {}
        gm = [self.mention_nick(pid, g) for g in GLOBAL_ADMINS]
        if gm:
            rg[1001] = {"d": "⭐ Глобальный Администратор (1000)", "u": gm}
        if oid and oid not in GLOBAL_ADMINS:
            a100 = self.db.get_role_alias(pid, 100)
            if a100:
                em = a100.get("alias_emoji", "") or ""
                nm = a100.get("alias_name", "Владелец")
                d = f"{em} {nm} (100)" if em else f"👑 {nm} (100)"
            else:
                d = "👑 Владелец (100)"
            rg[100] = {"d": d, "u": [self.mention_nick(pid, oid)]}
        for s in (staff or []):
            uid = s["user_id"]
            if uid == oid or uid in GLOBAL_ADMINS:
                continue
            p = s["priority"]
            em = s.get("emoji", "") or ""
            d = f"{em} {s['role_name']} ({p})" if em else f"{s['role_name']} ({p})"
            if p not in rg:
                rg[p] = {"d": d, "u": []}
            rg[p]["u"].append(self.mention_nick(pid, uid))
        if not rg:
            return self.send(pid, "👮 Пусто.")
        txt = "👮 Персонал\n\n"
        for p in sorted(rg.keys(), reverse=True):
            txt += f"{rg[p]['d']} -> {', '.join(rg[p]['u'])}\n"
        self.send(pid, txt)

    def cmd_cmd(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drcmd"):
            return self.send(pid, "❌ Только владелец.")
        raw = e.get("text", "").split()
        args = []
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl == "drcmd":
                args = raw[i + 1:]
                break
        if not args:
            perms = self.db.get_all_cmd_permissions(pid)
            pt = "".join([f"  /{p['command']} — {p['min_priority']}\n" for p in perms]) or "  По умолчанию.\n"
            dt = "".join(
                [f"  /{c} — {p}\n" for c, p in sorted(DEFAULT_CMD_PERMISSIONS.items(), key=lambda x: -x[1])]
            )
            return self.send(pid, f"⚙️ Права\n\nНастроенные:\n{pt}\nПо умолчанию:\n{dt}\n/drcmd [cmd] [prio]")
        if len(args) < 2:
            return self.send(pid, "❌ /drcmd [команда] [приоритет]")
        cn = args[0].lower().replace("/", "")
        try:
            mp = int(args[1])
        except ValueError:
            return self.send(pid, "❌ Число.")
        if mp < 0 or mp > 1000:
            return self.send(pid, "❌ 0-1000.")
        if cn not in DEFAULT_CMD_PERMISSIONS:
            return self.send(pid, f"❌ Неизвестная: {cn}")
        self.db.set_cmd_permission(pid, cn, mp)
        self.send(pid, f"✅ /{cn} — мин: {mp}")

    def cmd_top(self, e, pid, fid):
        top = self.db.get_top_msg(pid, 15)
        if not top:
            return self.send(pid, "📊 Пусто.")
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        txt = "📊 Топ\n\n"
        for i, t in enumerate(top, 1):
            txt += f"{medals.get(i, f'{i}.')} {self.mention(t['user_id'])} — {t['count']}\n"
        self.send(pid, txt)

    def cmd_connect(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drconnect"):
            return self.send(pid, "❌ Только владелец.")
        raw = e.get("text", "").split()
        args = []
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl == "drconnect":
                args = raw[i + 1:]
                break
        if not args:
            if self.db.is_connected(pid):
                pool = self.db.get_pool_peers(pid)
                return self.send(
                    pid,
                    f"🔗 Пул\n\n" + "\n".join([f"  • {p}" for p in pool]) +
                    f"\n\n/drconnect off\n/drconnect [peer_id]"
                )
            return self.send(pid, "🔗 /drconnect create|[peer_id]|off")
        arg = args[0].lower()
        if arg == "create":
            self.db.connect_to_pool(pid, pid)
            self.db.update_setting(pid, "connected", 1)
            self.send(pid, f"✅ Пул создан. /drconnect {pid}")
        elif arg == "off":
            self.db.disconnect_from_pool(pid)
            self.db.update_setting(pid, "connected", 0)
            self.send(pid, "✅ Отключён.")
        else:
            try:
                op = int(arg)
            except ValueError:
                return self.send(pid, "❌ Число.")
            self.db.connect_to_pool(pid, op)
            self.db.update_setting(pid, "connected", 1)
            self.send(pid, f"✅ Подключён к {op}.")

    def cmd_import(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drimport"):
            return self.send(pid, "❌ Только владелец.")
        raw = e.get("text", "").split()
        args = []
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl == "drimport":
                args = raw[i + 1:]
                break
        if not args:
            code = self.db.create_import_code(pid)
            return self.send(pid, f"📦 Код: {code}\n/drimport {code}\n⏰ 10 мин.")
        code = args[0].strip().upper()
        src = self.db.get_import_source(code)
        if not src:
            return self.send(pid, "❌ Код не найден.")
        if src == pid:
            return self.send(pid, "❌ Тот же чат.")
        self.send(
            pid,
            f"✅ Импортировано из {src}." if self.db.import_settings(src, pid) else "❌ Ошибка."
        )

    def cmd_delmsg(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drdelmsg"):
            return self.send(pid, "❌ Нет прав.")
        raw = e.get("text", "").split()
        count_str = ""
        for i, tok in enumerate(raw):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl == "drdelmsg":
                if i + 1 < len(raw):
                    count_str = raw[i + 1]
                break
        if not count_str:
            return self.send(pid, "❌ /drdelmsg [1-100]")
        try:
            count = int(count_str)
            if not (1 <= count <= 100):
                return self.send(pid, "❌ 1-100.")
        except ValueError:
            return self.send(pid, "❌ 1-100.")
        try:
            msgs = self.vk.messages.getHistory(peer_id=pid, count=count + 1).get("items", [])
            cmids = [
                m["conversation_message_id"]
                for m in msgs
                if m.get("from_id", 0) != -self.group_id and m.get("conversation_message_id")
            ]
            if cmids:
                for i in range(0, len(cmids), 24):
                    batch = cmids[i:i + 24]
                    try:
                        self.vk.messages.delete(
                            cmids=",".join(map(str, batch)),
                            peer_id=pid,
                            delete_for_all=1,
                            group_id=self.group_id
                        )
                    except Exception as ex:
                        logger.error(f"delmsg batch err: {ex}")
                self.send(pid, f"🗑 Удалено {len(cmids)} сообщений.")
            else:
                self.send(pid, "❌ Нечего удалять.")
        except Exception as ex:
            logger.error(f"delmsg err: {ex}")
            self.send(pid, "❌ Ошибка удаления сообщений.")

    def cmd_msg(self, e, pid, fid):
        """
        Рассылка только в привязанные чаты (msg_links).
        ГА может управлять привязкой и делать рассылку.
        """
        if not self.is_ga(fid):
            return self.send(pid, "❌ Только ГА.")
        raw = e.get("text", "").split(maxsplit=2)
        # raw[0] = тег+команда, raw[1] = подкоманда или текст
        args_str = ""
        for i, tok in enumerate(e.get("text", "").split()):
            tl = tok.lower().lstrip("/!").lstrip()
            if tl == "drmsg":
                args_str = " ".join(e.get("text", "").split()[i + 1:])
                break

        if not args_str:
            links = self.db.get_msg_links()
            if not links:
                return self.send(
                    pid,
                    "📨 Рассылка DarknessRussia\n\n"
                    "Привязанных чатов нет.\n\n"
                    "Управление:\n"
                    "  /drmsg add [peer_id] [название] — привязать чат\n"
                    "  /drmsg rem [peer_id] — отвязать чат\n"
                    "  /drmsg list — список привязанных\n"
                    "  /drmsg [текст] — рассылка во все привязанные чаты"
                )
            txt = "📨 Привязанные чаты для рассылки:\n\n"
            for i, l in enumerate(links, 1):
                name = l.get("chat_name") or "—"
                txt += f"{i}. {l['peer_id']} | {name}\n"
            txt += (
                f"\n📊 Всего: {len(links)}\n\n"
                "  /drmsg add [peer_id] [название] — привязать\n"
                "  /drmsg rem [peer_id] — отвязать\n"
                "  /drmsg list — список\n"
                "  /drmsg [текст] — рассылка"
            )
            return self.send(pid, txt)

        al = args_str.lower()

        if al == "list":
            links = self.db.get_msg_links()
            if not links:
                return self.send(pid, "📨 Привязанных чатов нет.")
            txt = "📨 Привязанные чаты:\n\n"
            for i, l in enumerate(links, 1):
                name = l.get("chat_name") or "—"
                txt += f"{i}. {l['peer_id']} | {name}\n"
            return self.send(pid, txt + f"\n📊 Всего: {len(links)}")

        if al.startswith("add"):
            rest = args_str[3:].strip()
            if not rest:
                return self.send(pid, "❌ /drmsg add [peer_id] [название]")
            parts = rest.split(maxsplit=1)
            try:
                link_peer = int(parts[0])
            except ValueError:
                return self.send(pid, "❌ peer_id — число.")
            chat_name = parts[1].strip() if len(parts) > 1 else ""
            self.db.add_msg_link(link_peer, chat_name)
            self.send(
                pid,
                f"✅ Чат {link_peer} привязан для рассылки."
                + (f" Название: «{chat_name}»" if chat_name else "")
            )
            return

        if al.startswith("rem"):
            rest = args_str[3:].strip()
            if not rest:
                return self.send(pid, "❌ /drmsg rem [peer_id]")
            try:
                link_peer = int(rest.split()[0])
            except ValueError:
                return self.send(pid, "❌ peer_id — число.")
            self.send(
                pid,
                f"✅ Чат {link_peer} отвязан."
                if self.db.remove_msg_link(link_peer) else f"❌ Чат {link_peer} не найден."
            )
            return

        # Рассылка текста
        msg_text = args_str.strip()
        if not msg_text:
            return self.send(pid, "❌ Укажите текст для рассылки.")
        links = self.db.get_msg_links()
        if not links:
            return self.send(pid, "❌ Нет привязанных чатов. Используйте /drmsg add [peer_id]")
        sent = 0
        for link in links:
            lp = link["peer_id"]
            try:
                self.vk.messages.send(
                    peer_id=lp,
                    message=f"📨 Сообщение от Администрации DarknessRussia:\n{msg_text}",
                    random_id=random.randint(0, 2 ** 31)
                )
                sent += 1
                time.sleep(0.1)
            except Exception as ex:
                logger.error(f"msg send err to {lp}: {ex}")
        self.send(pid, f"✅ Отправлено в {sent}/{len(links)} привязанных чатов.")

    def cmd_gban(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drgban"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drgban [юзер] [время] [причина]")
        if self.is_ga(tid):
            return self.send(pid, "⛔ Нельзя наказать ГА.")
        parts = rest.split(maxsplit=1)
        if not parts:
            return self.send(pid, "❌ Укажите время.")
        dur, ht = self.parse_dur(parts[0])
        if dur is None:
            return self.send(pid, "❌ Неверное время.")
        reason = parts[1].strip() if len(parts) > 1 else "Не указана"
        self.db.global_ban_user(tid, fid, reason, dur)
        all_peers = self.db.get_all_chat_peers()
        kicked = 0
        for peer in all_peers:
            self.db.ban_user(peer, tid, fid, f"[Глобал] {reason}", dur)
            kicked += 1 if self.kick(peer, tid) else 0
        self.send(
            pid,
            f"🌐 ГЛОБАЛЬНЫЙ БАН\n"
            f"👾 {self.mention(tid)}\n"
            f"🛡 {self.mention(fid)}\n"
            f"〽️ {self.format_role(pid, fid)}\n"
            f"📌 {reason} | {ht}\n"
            f"🌍 {kicked}/{len(all_peers)}"
        )

    def cmd_gunban(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drgunban"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drgunban [юзер]")
        if self.db.global_unban_user(tid):
            for peer in self.db.get_all_chat_peers():
                self.db.unban_user(peer, tid)
            self.send(pid, f"🌐 РАЗБАН: {self.mention(tid)}\n🛡 {self.mention(fid)}")
        else:
            self.send(pid, f"❌ Не в глобальном бане.")

    def cmd_gmute(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drgmute"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drgmute [юзер] [время] [причина]")
        if self.is_ga(tid):
            return self.send(pid, "⛔ Нельзя наказать ГА.")
        parts = rest.split(maxsplit=1)
        if not parts:
            return self.send(pid, "❌ Укажите время.")
        dur, ht = self.parse_dur(parts[0])
        if dur is None:
            return self.send(pid, "❌ Неверное время.")
        reason = parts[1].strip() if len(parts) > 1 else "Не указана"
        self.db.global_mute_user(tid, fid, reason, dur)
        all_peers = self.db.get_all_chat_peers()
        for peer in all_peers:
            self.db.mute_user(peer, tid, fid, f"[Глобал] {reason}", dur)
        self.send(
            pid,
            f"🌐 ГЛОБАЛЬНЫЙ МУТ\n"
            f"👾 {self.mention(tid)}\n"
            f"🛡 {self.mention(fid)}\n"
            f"〽️ {self.format_role(pid, fid)}\n"
            f"📌 {reason} | {ht}\n"
            f"🌍 {len(all_peers)}"
        )

    def cmd_gunmute(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drgunmute"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drgunmute [юзер]")
        if self.db.global_unmute_user(tid):
            for peer in self.db.get_all_chat_peers():
                self.db.unmute_user(peer, tid)
            self.send(pid, f"🌐 РАЗМУТ: {self.mention(tid)}\n🛡 {self.mention(fid)}")
        else:
            self.send(pid, f"❌ Не в глобальном муте.")

    def cmd_gkick(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drgkick"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drgkick [юзер] [причина]")
        if self.is_ga(tid):
            return self.send(pid, "⛔ Нельзя наказать ГА.")
        reason = rest.strip() or "Не указана"
        all_peers = self.db.get_all_chat_peers()
        kicked = sum(1 for p in all_peers if self.kick(p, tid))
        self.send(
            pid,
            f"🌐 ГЛОБАЛЬНЫЙ КИК\n"
            f"👾 {self.mention(tid)}\n"
            f"🛡 {self.mention(fid)}\n"
            f"📌 {reason}\n"
            f"🌍 {kicked}/{len(all_peers)}"
        )

    def cmd_gvig(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drgvig"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        tid, rest = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drgvig [юзер] [причина]")
        if self.is_ga(tid):
            return self.send(pid, "⛔ Нельзя наказать ГА.")
        reason = rest.strip() or "Не указана"
        gvig_pending.set(fid, {"target_id": tid, "peer_id": pid, "reason": reason})
        kb = VkKeyboard(inline=True)
        kb.add_callback_button(
            "Грубый выговор", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button": "gvig_грубый выговор"})
        )
        kb.add_line()
        kb.add_callback_button(
            "Выговор", color=VkKeyboardColor.PRIMARY,
            payload=json.dumps({"button": "gvig_выговор"})
        )
        kb.add_line()
        kb.add_callback_button(
            "Устный выговор", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button": "gvig_устный выговор"})
        )
        self.send(
            pid,
            f"🌐 ВЫГОВОР для {self.mention(tid)}\n📋 {reason}\n\nВыберите тип:",
            keyboard=kb
        )

    def process_gvig_choice(self, pid, fid, choice):
        p = gvig_pending.pop(fid)
        if not p:
            return self.send(pid, "❌ Нет запроса.")
        if time.time() - p["_created"] > 60:
            return self.send(pid, "⏰ Истекло.")
        tid, reason = p["target_id"], p["reason"]
        icons = {"грубый выговор": "🔴", "выговор": "🟡", "устный выговор": "🟢"}
        self.db.add_global_vig(tid, fid, choice, reason)
        self.send(
            pid,
            f"🌐 {icons.get(choice, '')} {choice.title()}: {self.mention(tid)}\n"
            f"🛡 {self.mention(fid)}\n"
            f"📌 {reason}\n"
            f"📊 Всего: {len(self.db.get_global_vigs(tid))}"
        )

    def cmd_gunvig(self, e, pid, fid):
        if not self.has_perm(pid, fid, "drgunvig"):
            return self.send(pid, "❌ Нет прав (мин. 90).")
        tid, _ = self.parse_target(e)
        if not tid:
            return self.send(pid, "❌ /drgunvig [юзер]")
        gvigs = self.db.get_global_vigs(tid)
        if not gvigs:
            return self.send(pid, f"❌ У {self.mention(tid)} нет глобальных выговоров.")
        icons = {"грубый выговор": "🔴", "выговор": "🟡", "устный выговор": "🟢"}
        txt = f"🌐 Глобальные выговоры {self.mention(tid)}:\n\n"
        kb = VkKeyboard(inline=True)
        for i, v in enumerate(gvigs[:5], 1):
            txt += (
                f"{i}. {icons.get(v['vig_type'], '')} {v['vig_type'].title()}\n"
                f"   📌 {v['reason']}\n"
                f"   🛡 Выдал: {self.mention(v['issued_by'])}\n"
            )
            kb.add_callback_button(
                f"❌ #{i}", color=VkKeyboardColor.NEGATIVE,
                payload=json.dumps({"button": f"gunvig_{v['id']}"})
            )
            if i < len(gvigs[:5]):
                kb.add_line()
        kb.add_line()
        kb.add_callback_button(
            "🗑 Снять все", color=VkKeyboardColor.POSITIVE,
            payload=json.dumps({"button": f"gunvig_all_{tid}"})
        )
        gunvig_pending.set(fid, {"target_id": tid, "peer_id": pid})
        self.send(pid, txt + "\nВыберите выговор для снятия или снимите все:", keyboard=kb)

    def process_gunvig_single(self, pid, fid, vig_id):
        p = gunvig_pending.pop(fid)
        if not p:
            return self.send(pid, "❌ Нет запроса.")
        vig = self.db.get_global_vig_by_id(vig_id)
        if not vig:
            return self.send(pid, "❌ Выговор не найден.")
        icons = {"грубый выговор": "🔴", "выговор": "🟡", "устный выговор": "🟢"}
        self.send(
            pid,
            f"🌐 Выговор снят: {icons.get(vig['vig_type'], '')} {vig['vig_type'].title()}\n"
            f"👾 {self.mention(vig['user_id'])}\n"
            f"🛡 Снял: {self.mention(fid)}"
            if self.db.remove_global_vig_by_id(vig_id) else "❌ Не удалось."
        )

    def process_gunvig_all(self, pid, fid, tid):
        p = gunvig_pending.pop(fid)
        if not p:
            return self.send(pid, "❌ Нет запроса.")
        self.send(
            pid,
            f"🌐 Все глобальные выговоры сняты: {self.mention(tid)}\n🛡 Снял: {self.mention(fid)}"
            if self.db.remove_global_vigs(tid) else f"❌ Нет выговоров."
        )

    def cmd_listchat(self, e, pid, fid):
        if not self.is_ga(fid):
            return self.send(pid, "❌ Только ГА.")
        chats = self.db.get_all_chats_with_info()
        if not chats:
            return self.send(pid, "📋 Нет чатов.")
        txt = "📋 ВСЕ ЧАТЫ\n\n"
        for i, chat in enumerate(chats[:50], 1):
            peer, owner = chat['peer_id'], chat['owner_id']
            try:
                ci = self.vk.messages.getConversationsById(peer_ids=peer, group_id=self.group_id)
                items = ci.get("items", [])
                title = items[0].get("chat_settings", {}).get("title", "?") if items else "?"
                txt += f"{i}. {title}\n   👑 {self.mention(owner)} | 🆔 {peer}\n\n"
            except Exception:
                txt += f"{i}. Беседа {peer}\n   👑 {self.mention(owner)}\n\n"
        self.send(pid, txt + f"📊 Всего: {len(chats)}")

    def cmd_start(self, e, pid, fid):
        if pid != fid:
            return
        ot = self.db.get_open_ticket(fid)
        if ot:
            kb = VkKeyboard(inline=True)
            kb.add_callback_button(
                "❌ Закрыть", color=VkKeyboardColor.NEGATIVE,
                payload=json.dumps({"button": f"close_ticket_{ot['id']}"})
            )
            return self.send(pid, f"⚠️ Обращение #{ot['id']} уже открыто.", keyboard=kb)
        support_pending.set(fid, {"stage": "waiting_problem"})
        self.send(
            pid,
            "👋 Здравствуйте!\n🔧 Техподдержка DarknessRussia.\n📝 Опишите проблему одним сообщением."
        )

    def process_support_problem(self, pid, fid, text):
        pending = support_pending.get(fid)
        if not pending:
            return
        if pending.get("stage") == "waiting_problem":
            support_pending.set(fid, {"stage": "waiting_type", "problem_text": text})
            kb = VkKeyboard(inline=True)
            kb.add_callback_button(
                "🖥 Сервер", color=VkKeyboardColor.PRIMARY,
                payload=json.dumps({"button": "support_server"})
            )
            kb.add_line()
            kb.add_callback_button(
                "🤖 Бот", color=VkKeyboardColor.PRIMARY,
                payload=json.dumps({"button": "support_bot"})
            )
            kb.add_line()
            kb.add_callback_button(
                "💳 Донат", color=VkKeyboardColor.PRIMARY,
                payload=json.dumps({"button": "support_donate"})
            )
            self.send(pid, "✅ Выберите категорию:", keyboard=kb)

    def handle_support_type_choice(self, pid, fid, problem_type):
        pending = support_pending.pop(fid)
        if not pending or pending.get("stage") != "waiting_type":
            return self.send(pid, "❌ Нет запроса.")
        problem_text = pending.get("problem_text", "")
        type_names = {"server": "🖥 Сервер", "bot": "🤖 Бот", "donate": "💳 Донат"}
        ticket_id = self.db.create_ticket(fid, problem_text, problem_type)
        kb = VkKeyboard(inline=True)
        kb.add_callback_button(
            "❌ Закрыть", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button": f"close_ticket_{ticket_id}"})
        )
        self.send(
            pid,
            f"✅ Обращение #{ticket_id} принято!\n"
            f"📂 {type_names.get(problem_type, '?')}\n"
            f"📝 {problem_text}\n⏳ Ожидайте.",
            keyboard=kb
        )
        try:
            sk = VkKeyboard(inline=True)
            sk.add_callback_button(
                "✅ Закрыть", color=VkKeyboardColor.POSITIVE,
                payload=json.dumps({"button": f"support_close_{ticket_id}"})
            )
            self.vk.messages.send(
                peer_id=SUPPORT_PEER,
                message=(
                    f"🆘 ОБРАЩЕНИЕ #{ticket_id}\n"
                    f"👤 {self.mention(fid)}\n"
                    f"📂 {type_names.get(problem_type, '?')}\n"
                    f"📝 {problem_text}\n"
                    f"💬 Ответьте на это сообщение."
                ),
                keyboard=sk.get_keyboard(),
                random_id=random.randint(0, 2 ** 31)
            )
        except Exception as ex:
            logger.error(f"Support send err: {ex}")

    def handle_support_reply(self, msg):
        reply = msg.get("reply_message")
        if not reply:
            return
        match = re.search(r'ОБРАЩЕНИЕ #(\d+)', reply.get("text", ""))
        if not match:
            return
        ticket_id = int(match.group(1))
        ticket = self.db.get_ticket_by_id(ticket_id)
        if not ticket or ticket['status'] != 'open':
            return self.send(msg['peer_id'], f"❌ #{ticket_id} закрыто/не найдено.")
        user_id = ticket['user_id']
        kb = VkKeyboard(inline=True)
        kb.add_callback_button(
            "❌ Закрыть", color=VkKeyboardColor.NEGATIVE,
            payload=json.dumps({"button": f"close_ticket_{ticket_id}"})
        )
        try:
            self.vk.messages.send(
                peer_id=user_id,
                message=f"💬 ОТВЕТ #{ticket_id}\n\n{msg.get('text', '')}",
                keyboard=kb.get_keyboard(),
                random_id=random.randint(0, 2 ** 31)
            )
            self.send(msg['peer_id'], f"✅ Ответ отправлен {self.mention(user_id)}")
        except Exception as ex:
            self.send(msg['peer_id'], f"❌ {ex}")

    def handle_close_ticket(self, ticket_id, closed_by, peer_id):
        ticket = self.db.get_ticket_by_id(ticket_id)
        if not ticket:
            return self.send(peer_id, f"❌ #{ticket_id} не найдено.")
        if ticket['status'] == 'closed':
            return self.send(peer_id, f"❌ #{ticket_id} уже закрыто.")
        self.db.close_ticket(ticket_id, closed_by)
        user_id = ticket['user_id']
        if peer_id != user_id:
            try:
                self.vk.messages.send(
                    peer_id=user_id,
                    message=f"✅ Обращение #{ticket_id} закрыто. Спасибо!",
                    random_id=random.randint(0, 2 ** 31)
                )
            except Exception:
                pass
            self.send(peer_id, f"✅ #{ticket_id} закрыто. {self.mention(user_id)} уведомлён.")
        else:
            self.send(peer_id, f"✅ Обращение #{ticket_id} закрыто.")
            try:
                self.vk.messages.send(
                    peer_id=SUPPORT_PEER,
                    message=f"ℹ️ #{ticket_id} закрыто {self.mention(user_id)}",
                    random_id=random.randint(0, 2 ** 31)
                )
            except Exception:
                pass


def main():
    print("=" * 55)
    print("  🎮 DarknessRussia Bot v2.8.1 (CRMP)")
    print("=" * 55)
    try:
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        longpoll = VkBotLongPoll(vk_session, GROUP_ID)
        try:
            gi = vk.groups.getById(group_id=GROUP_ID)
            print(f"  ✅ Сообщество: {gi[0]['name']}")
        except Exception as ex:
            print(f"  ❌ {ex}")
            return
        db = Database()
        handlers = Handlers(vk, db, GROUP_ID)
        print(f"  ✅ БД | ГА: {len(GLOBAL_ADMINS)} | Поддержка: {SUPPORT_PEER}")
        print("  🟢 Бот запущен! | 🛡 Античит активен")
        print("=" * 55)

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
                    eo = event.object
                    uid = eo.get("user_id")
                    pid = eo.get("peer_id")
                    eid = eo.get("event_id")
                    payload = eo.get("payload", {})
                    try:
                        vk.messages.sendMessageEventAnswer(
                            event_id=eid, user_id=uid, peer_id=pid,
                            event_data=json.dumps({"type": "show_snackbar", "text": "✅"})
                        )
                    except Exception:
                        pass
                    bt = ""
                    if isinstance(payload, dict):
                        bt = payload.get("button", "")
                    elif isinstance(payload, str):
                        try:
                            bt = json.loads(payload).get("button", "")
                        except Exception:
                            pass
                    if not bt or not uid or not pid:
                        continue
                    btl = bt.lower().strip()

                    if bt.startswith("support_") and not bt.startswith("support_close_"):
                        handlers.handle_support_type_choice(pid, uid, bt.split("_")[1])
                    elif bt.startswith("close_ticket_"):
                        handlers.handle_close_ticket(int(bt.split("_")[2]), uid, pid)
                    elif bt.startswith("support_close_"):
                        handlers.handle_close_ticket(int(bt.split("_")[2]), uid, pid)
                    elif btl in ("чса", "чсл", "чсп", "чсс"):
                        if uid in bl_pending:
                            handlers.process_bl_choice(pid, uid, btl)
                        else:
                            handlers.send(pid, "❌ Нет запроса.")
                    elif bt.startswith("unbl_"):
                        if uid in unbl_pending:
                            handlers.process_unbl_choice(pid, uid, bt[5:].lower().strip())
                        else:
                            handlers.send(pid, "❌ Нет запроса.")
                    elif bt.startswith("vig_"):
                        if uid in vig_pending:
                            handlers.process_vig_choice(pid, uid, bt[4:].lower().strip())
                        else:
                            handlers.send(pid, "❌ Нет запроса.")
                    elif bt.startswith("gvig_"):
                        if uid in gvig_pending:
                            handlers.process_gvig_choice(pid, uid, bt[5:].lower().strip())
                        else:
                            handlers.send(pid, "❌ Нет запроса.")
                    elif bt.startswith("unvig_"):
                        rest = bt[6:]
                        if rest.startswith("all_"):
                            parts = rest[4:].split("_")
                            if len(parts) >= 2:
                                if uid in unvig_pending:
                                    handlers.process_unvig_all(int(parts[1]), uid, int(parts[0]))
                                else:
                                    handlers.send(pid, "❌ Нет запроса.")
                        else:
                            try:
                                if uid in unvig_pending:
                                    handlers.process_unvig_single(pid, uid, int(rest))
                                else:
                                    handlers.send(pid, "❌ Нет запроса.")
                            except ValueError:
                                pass
                    elif bt.startswith("gunvig_"):
                        rest = bt[7:]
                        if rest.startswith("all_"):
                            try:
                                if uid in gunvig_pending:
                                    handlers.process_gunvig_all(pid, uid, int(rest[4:]))
                                else:
                                    handlers.send(pid, "❌ Нет запроса.")
                            except ValueError:
                                pass
                        else:
                            try:
                                if uid in gunvig_pending:
                                    handlers.process_gunvig_single(pid, uid, int(rest))
                                else:
                                    handlers.send(pid, "❌ Нет запроса.")
                            except ValueError:
                                pass
                except Exception as ex:
                    logger.error(f"CB err: {ex}")
                    traceback.print_exc()

    except KeyboardInterrupt:
        print("\nСтоп.")
    except Exception as ex:
        logger.critical(f"Fatal: {ex}")
        traceback.print_exc()


if __name__ == "__main__":
    main()