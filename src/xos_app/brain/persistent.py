"""
xOS Brain — Persistent Xotira v1.0
=====================================
Brain o'rganganlarini diskka saqlaydi.
Ilova yopilsa ham, qayta ochilganda davom etadi.

Fayllar:
  brain_state.json   — asosiy holat (KB, NN, RL)
  brain_diary.jsonl  — o'rganish kundaligi
  brain_chat.jsonl   — suhbat tarixi
  brain_self.py      — o'zi yozgan kod (!)
"""

import json
import os
import time
import threading
from collections import deque


# ═══════════════════════════════════════════════
# SAQLASH YO'LLARI
# ═══════════════════════════════════════════════

def _get_data_dir():
    """
    Saqlash papkasini topadi.
    Android da: /data/user/0/.../files/xos_brain/
    Desktop da: ~/.xos_brain/
    """
    # Android Briefcase papkasi
    android_base = os.environ.get('ANDROID_DATA', '')
    if android_base:
        base = os.path.join(android_base, 'user', '0', 'xos_brain')
    else:
        base = os.path.join(os.path.expanduser('~'), '.xos_brain')

    os.makedirs(base, exist_ok=True)
    return base


DATA_DIR = _get_data_dir()
STATE_FILE  = os.path.join(DATA_DIR, 'brain_state.json')
DIARY_FILE  = os.path.join(DATA_DIR, 'brain_diary.jsonl')
CHAT_FILE   = os.path.join(DATA_DIR, 'brain_chat.jsonl')
SELF_FILE   = os.path.join(DATA_DIR, 'brain_self.py')
STATS_FILE  = os.path.join(DATA_DIR, 'brain_stats.json')


# ═══════════════════════════════════════════════
# KUNDALIK (Diary)
# ═══════════════════════════════════════════════

class Diary:
    """
    Brain o'rganish kundaligi.
    Har bir o'rganish hodisasini JSONL formatda saqlaydi.
    """

    def __init__(self, path=DIARY_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._cache = deque(maxlen=100)  # oxirgi 100 ta

    def log(self, event_type: str, data: dict):
        entry = {
            'ts': time.time(),
            'time_str': time.strftime('%Y-%m-%d %H:%M:%S'),
            'type': event_type,
            **data
        }
        self._cache.append(entry)
        # Diskka yoz (xato chiqarma)
        try:
            with self._lock:
                with open(self.path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception:
            pass
        return entry

    def recent(self, n=20) -> list:
        """Oxirgi N ta yozuvni qaytaradi."""
        result = []
        # Cache dan
        result.extend(list(self._cache)[-n:])
        if len(result) >= n:
            return result[-n:]
        # Diskdan o'qi
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            entries = []
            for line in lines[-n:]:
                try:
                    entries.append(json.loads(line.strip()))
                except Exception:
                    pass
            return entries[-n:]
        except Exception:
            return result

    def stats(self) -> dict:
        try:
            size = os.path.getsize(self.path)
            with open(self.path, 'r', encoding='utf-8') as f:
                count = sum(1 for _ in f)
            return {'entries': count, 'size_kb': round(size / 1024, 1)}
        except Exception:
            return {'entries': 0, 'size_kb': 0}


# ═══════════════════════════════════════════════
# SUHBAT TARIXI
# ═══════════════════════════════════════════════

class ChatHistory:
    """
    Barcha suhbatlarni diskka saqlaydi.
    Brain suhbat kontekstini eslaydi.
    """

    def __init__(self, path=CHAT_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._session = []  # joriy sessiya

    def add(self, role: str, message: str, context: dict = None):
        entry = {
            'ts': time.time(),
            'time_str': time.strftime('%Y-%m-%d %H:%M:%S'),
            'role': role,
            'msg': message,
            'ctx': context or {}
        }
        self._session.append(entry)
        try:
            with self._lock:
                with open(self.path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception:
            pass

    def session_context(self, n=10) -> list:
        """Joriy sessiyaning oxirgi N ta xabari."""
        return self._session[-n:]

    def total_count(self) -> int:
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception:
            return len(self._session)

    def search(self, keyword: str, limit=10) -> list:
        """Kalit so'z bo'yicha suhbat tarixidan qidirish."""
        results = []
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if keyword.lower() in entry.get('msg', '').lower():
                            results.append(entry)
                    except Exception:
                        pass
        except Exception:
            pass
        return results[-limit:]


# ═══════════════════════════════════════════════
# O'Z-O'ZI YOZGAN KOD
# ═══════════════════════════════════════════════

class SelfCode:
    """
    Brain o'zi yozgan Python kodini saqlaydi va boshqaradi.
    Bu - "self-hosting" ga birinchi qadam.
    """

    def __init__(self, path=SELF_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._generated = []

    def save_program(self, name: str, code: str, language: str = 'xasm',
                     reward: float = 0.0, description: str = ''):
        """Yaxshi dasturni saqlaydi."""
        entry = {
            'name': name,
            'language': language,
            'reward': reward,
            'description': description,
            'code': code,
            'ts': time.time(),
            'time_str': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        self._generated.append(entry)

        # Python fayliga qo'shish
        py_block = f'''
# ══════════════════════════════════════════════
# {name} | {language} | reward={reward:.1f} | {time.strftime('%Y-%m-%d %H:%M:%S')}
# {description}
# ══════════════════════════════════════════════
BRAIN_GENERATED["{name}"] = """{code}"""

'''
        try:
            with self._lock:
                # Fayl boshida BRAIN_GENERATED dict yo'q bo'lsa, yarat
                if not os.path.exists(self.path):
                    header = '"""Brain o\'zi yozgan dasturlar — avtomatik yangilanadi"""\nBRAIN_GENERATED = {}\n'
                    with open(self.path, 'w', encoding='utf-8') as f:
                        f.write(header)

                with open(self.path, 'a', encoding='utf-8') as f:
                    f.write(py_block)
        except Exception:
            pass
        return entry

    def load_all(self) -> dict:
        """Saqlangan barcha dasturlarni qaytaradi."""
        try:
            namespace = {'BRAIN_GENERATED': {}}
            with open(self.path, 'r', encoding='utf-8') as f:
                exec(f.read(), namespace)
            return namespace.get('BRAIN_GENERATED', {})
        except Exception:
            return {}

    def count(self) -> int:
        return len(self._generated)


# ═══════════════════════════════════════════════
# ASOSIY SAQLASH MENEJER
# ═══════════════════════════════════════════════

class PersistentStore:
    """
    Brain ni diskka saqlaydigan va yuklaydigan asosiy sinf.
    Brain.save() va Brain.load() ni to'ldiradi.

    Avtomatik saqlash: har N sessiyada (auto_save_every).
    """

    def __init__(self,
                 state_path: str = STATE_FILE,
                 auto_save_every: int = 5):
        self.state_path = state_path
        self.auto_save_every = auto_save_every
        self._save_count = 0
        self._lock = threading.Lock()

        self.diary    = Diary()
        self.chat     = ChatHistory()
        self.selfcode = SelfCode()

        # Statistika
        self._stats = {
            'total_saves':    0,
            'total_loads':    0,
            'last_save_ts':   None,
            'last_load_ts':   None,
            'first_boot_ts':  None,
        }
        self._load_stats()

    def _load_stats(self):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                self._stats.update(saved)
        except Exception:
            self._stats['first_boot_ts'] = time.time()

    def _save_stats(self):
        try:
            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._stats, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save_brain(self, brain) -> bool:
        """Brain holatini to'liq saqlaydi."""
        try:
            with self._lock:
                brain.save(self.state_path)
                self._stats['total_saves'] += 1
                self._stats['last_save_ts'] = time.time()
                self._save_stats()

            self.diary.log('save', {
                'sessions': brain.sessions,
                'patterns': brain.kb.stats()['patterns'],
                'rules': brain.kb.stats()['rules'],
                'programs': brain.kb.stats()['programs'],
                'nn_iter': brain.nn.iterations,
                'nn_loss': round(brain.nn.avg_loss(), 6),
            })
            return True
        except Exception as e:
            self.diary.log('save_error', {'error': str(e)})
            return False

    def load_brain(self, brain) -> bool:
        """Saqlangan Brain holatini yuklaydi."""
        if not os.path.exists(self.state_path):
            self.diary.log('first_boot', {'msg': 'Yangi Brain — hech narsa yuklanmadi'})
            return False
        try:
            brain.load(self.state_path)
            self._stats['total_loads'] += 1
            self._stats['last_load_ts'] = time.time()
            self._save_stats()

            # O'zi yozgan dasturlarni ham yukla
            saved_progs = self.selfcode.load_all()
            if saved_progs:
                brain.kb.programs.update(saved_progs)

            self.diary.log('load', {
                'sessions': brain.sessions,
                'patterns': brain.kb.stats()['patterns'],
                'programs': brain.kb.stats()['programs'],
            })
            return True
        except Exception as e:
            self.diary.log('load_error', {'error': str(e)})
            return False

    def maybe_auto_save(self, brain) -> bool:
        """Sessiyalar soniga qarab avtomatik saqlash."""
        self._save_count += 1
        if self._save_count % self.auto_save_every == 0:
            return self.save_brain(brain)
        return False

    def brain_age(self) -> str:
        """Brain necha kundan beri yashayapti."""
        first = self._stats.get('first_boot_ts')
        if not first:
            return "Yangi"
        days = (time.time() - first) / 86400
        if days < 1:
            hours = days * 24
            return f"{hours:.1f} soat"
        return f"{days:.1f} kun"

    def summary(self) -> str:
        age   = self.brain_age()
        saves = self._stats['total_saves']
        loads = self._stats['total_loads']
        diary = self.diary.stats()
        chat_n = self.chat.total_count()
        self_n = self.selfcode.count()
        last_save = ''
        if self._stats.get('last_save_ts'):
            ago = time.time() - self._stats['last_save_ts']
            last_save = f"{ago/60:.1f} daqiqa oldin saqlandi"

        return (f"💾 Persistent Xotira:\n"
                f"  Yoshi        : {age}\n"
                f"  Saqlashlar   : {saves} marta\n"
                f"  Yuklashlar   : {loads} marta\n"
                f"  Kundalik     : {diary['entries']} yozuv ({diary['size_kb']} KB)\n"
                f"  Suhbatlar    : {chat_n} xabar\n"
                f"  O'zi yozgan  : {self_n} dastur\n"
                f"  {last_save}")
