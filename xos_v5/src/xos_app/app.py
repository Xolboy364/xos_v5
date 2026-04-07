"""
xOS v5.0 — Android APK (Toga UI)
===================================
v5.0: Brain persistent, fon o'rganish, aqlli chat, versiya yangilandi
"""
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
import threading, time, os, sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from kernel.machine import Machine

try:
    from hamza.hamza import Hamza as _HamzaLang
    _hamza_til = _HamzaLang()
    HAMZA_BOR = True
except Exception:
    _hamza_til = None
    HAMZA_BOR = False

try:
    from zafar.zafar import Zafar as _ZafarLang
    _zafar_til = _ZafarLang()
    ZAFAR_BOR = True
except Exception:
    _zafar_til = None
    ZAFAR_BOR = False

_machine = Machine()
_lock    = threading.Lock()
_rl_lock = threading.Lock()

def _box(direction=COLUMN, pad=4, flex=0):
    kw = dict(direction=direction, padding=pad)
    if flex: kw['flex'] = flex
    return toga.Box(style=Pack(**kw))

def _lbl(text, size=12, bold=False, pad=4):
    kw = dict(font_size=size, padding=pad)
    if bold: kw['font_weight'] = 'bold'
    return toga.Label(text, style=Pack(**kw))

def _btn(label, fn, pad=6, flex=0):
    kw = dict(padding=pad)
    if flex: kw['flex'] = flex
    return toga.Button(label, on_press=fn, style=Pack(**kw))

def _out(value='', h=300, flex=0):
    kw = dict(padding=4, font_family='monospace', font_size=11)
    if h:    kw['height'] = h
    if flex: kw['flex']   = flex
    return toga.MultilineTextInput(value=value, readonly=True, style=Pack(**kw))

def _inp(placeholder='', h=200, flex=0, value=''):
    kw = dict(padding=4, font_family='monospace', font_size=11)
    if h:    kw['height'] = h
    if flex: kw['flex']   = flex
    w = toga.MultilineTextInput(style=Pack(**kw))
    if value:       w.value       = value
    if placeholder: w.placeholder = placeholder
    return w

def _sep(): return toga.Divider()

class xOSApp(toga.App):

    def startup(self):
        self.main_window = toga.MainWindow(title="xOS v5.0")
        tabs = toga.OptionContainer(content=[
            toga.OptionItem("💻 Shell",      self._tab_shell()),
            toga.OptionItem("📝 xASM",       self._tab_editor()),
            toga.OptionItem("⚡ Hamza",      self._tab_hamza()),
            toga.OptionItem("🌟 Zafar",      self._tab_zafar()),
            toga.OptionItem("🧠 Brain",      self._tab_brain()),
            toga.OptionItem("🤖 RL",         self._tab_rl()),
            toga.OptionItem("🔌 Devices",    self._tab_devices()),
            toga.OptionItem("📊 CPU",        self._tab_cpu()),
            toga.OptionItem("📖 Qo'llanma", self._tab_qollanma()),
        ])
        self.main_window.content = tabs
        self.main_window.show()

    # ─── SHELL ────────────────────────────────────────────────────
    def _tab_shell(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("⬡ xOS v5.0 Shell", size=14, bold=True, pad=8))
        root.add(_sep())
        self._sh_out = _out(value="xOS v5.0 — tayyor\n'help' — yordam\n", flex=1)
        root.add(self._sh_out)
        root.add(_sep())
        inp_row = _box(ROW, pad=4)
        self._sh_inp = toga.TextInput(
            placeholder="buyruq kiriting...",
            style=Pack(flex=1, padding=4, font_family='monospace', font_size=12))
        inp_row.add(self._sh_inp)
        inp_row.add(_btn("▶ Yuborish", self._sh_send, pad=6))
        root.add(inp_row)
        qrow = _box(ROW, pad=4)
        qrow.add(_btn("🗑 Tozalash", self._sh_clear, pad=6, flex=1))
        qrow.add(_btn("❓ Yordam",   self._sh_help,  pad=6, flex=1))
        qrow.add(_btn("📋 Demolar",  self._sh_demos, pad=6, flex=1))
        root.add(qrow)
        return root

    def _sh_send(self, widget):
        cmd = self._sh_inp.value.strip()
        if not cmd: return
        self._sh_inp.value = ''
        self._sh_out.value += f"\n$ {cmd}\n"
        try:
            self._sh_out.value += str(_machine.shell.run(cmd)) + "\n"
        except Exception as e:
            self._sh_out.value += f"❌ {e}\n"

    def _sh_clear(self, w): self._sh_out.value = "Tozalandi.\n"
    def _sh_help(self, w):
        self._sh_out.value += "\n$ help\n" + _machine.shell.run("help") + "\n"
    def _sh_demos(self, w):
        self._sh_out.value += "\n$ demos\n" + _machine.shell.run("demos") + "\n"

    # ─── xASM ─────────────────────────────────────────────────────
    def _tab_editor(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("📝 xASM Editor", size=14, bold=True, pad=8))
        root.add(_sep())
        self._ed_inp = _inp(h=280,
            value="; xOS v5.0\n.section text\n    LOAD X0, #10\n    LOAD X1, #20\n    ADD  X2, X0, X1\n    PRINT X2\n    HALT\n")
        root.add(self._ed_inp)
        brow = _box(ROW, pad=4)
        brow.add(_btn("▶ Ishlatish", self._ed_run,     pad=6, flex=1))
        brow.add(_btn("⚙ Assemble", self._ed_assemble, pad=6, flex=1))
        brow.add(_btn("📦 xELF",    self._ed_elf,      pad=6, flex=1))
        brow.add(_btn("🗑 Tozala",  self._ed_clear,    pad=6, flex=1))
        root.add(brow)
        root.add(_sep())
        root.add(_lbl("Natija:", size=11, bold=True, pad=4))
        self._ed_out = _out(flex=1)
        root.add(self._ed_out)
        return root

    def _ed_run(self, widget):
        code = self._ed_inp.value.strip()
        if not code: self._ed_out.value = "❌ Kod kiriting"; return
        def run():
            try:
                with _lock: r = _machine.run_source(code)
                self._ed_out.value = (
                    f"✅ Muvaffaqiyatli\nChiqish  : {r.get('output','')}\n"
                    f"Buyruqlar: {r.get('instr',0)}\nTezlik   : {r.get('mips',0)} MIPS\n"
                    f"Holat    : {'HALT ✅' if r.get('halted') else 'Limit ⏸'}")
            except Exception as e: self._ed_out.value = f"❌ {e}"
        threading.Thread(target=run, daemon=True).start()
        self._ed_out.value = "⏳ Ishlamoqda..."

    def _ed_assemble(self, widget):
        code = self._ed_inp.value.strip()
        if not code: return
        try:
            from compiler.assembler import Assembler
            bc = Assembler().assemble(code)
            self._ed_out.value = f"✅ Assemble\nBaytlar: {len(bc)}\nHex: {bc[:32].hex()}"
        except Exception as e: self._ed_out.value = f"❌ {e}"

    def _ed_elf(self, widget):
        code = self._ed_inp.value.strip()
        if not code: return
        try:
            self._ed_out.value = _machine.dump_elf(_machine.compile_to_elf(code))
        except Exception as e: self._ed_out.value = f"❌ {e}"

    def _ed_clear(self, w): self._ed_inp.value = ''; self._ed_out.value = ''

    # ─── HAMZA ────────────────────────────────────────────────────
    def _tab_hamza(self):
        root = _box(COLUMN, pad=0, flex=1)
        st = "✅ Faol" if HAMZA_BOR else "❌ Yuklanmadi"
        root.add(_lbl(f"⚡ Hamza O'zbek Tili — {st}", size=13, bold=True, pad=8))
        root.add(_sep())
        self._hz_inp = _inp(h=220, value='son x = 10\nson y = 20\nchiqar x + y\n')
        root.add(self._hz_inp)
        brow = _box(ROW, pad=4)
        brow.add(_btn("▶ Ishlatish", self._hz_run,     pad=6, flex=1))
        brow.add(_btn("📋 xASM",     self._hz_compile, pad=6, flex=1))
        brow.add(_btn("💡 Misol",    self._hz_example, pad=6, flex=1))
        brow.add(_btn("🗑 Tozala",   self._hz_clear,   pad=6, flex=1))
        root.add(brow)
        root.add(_sep())
        self._hz_out = _out(flex=1)
        root.add(self._hz_out)
        return root

    def _hz_run(self, widget):
        if not HAMZA_BOR: self._hz_out.value = "❌ Hamza yuklanmadi"; return
        code = self._hz_inp.value.strip()
        if not code: return
        def run():
            try:
                r = _hamza_til.run(code)
                if r.get('muvaffaqiyat'):
                    self._hz_out.value = (f"✅ Muvaffaqiyatli\n"
                        f"Chiqish  : {r.get('chiqish','')}\n"
                        f"Buyruqlar: {r.get('buyruqlar',0)}\nBaytlar  : {r.get('baytlar',0)}")
                else: self._hz_out.value = f"❌ {r.get('xato','Xato')}"
            except Exception as e: self._hz_out.value = f"❌ {e}"
        threading.Thread(target=run, daemon=True).start()
        self._hz_out.value = "⏳ Kompilyatsiya..."

    def _hz_compile(self, widget):
        if not HAMZA_BOR: return
        xasm, xato = _hamza_til.compile(self._hz_inp.value.strip())
        self._hz_out.value = f"❌ {xato}" if xato else f"✅ xASM:\n{xasm}"

    def _hz_example(self, widget):
        self._hz_inp.value = ("ish fibonacci(n):\n    agar n < 2:\n        qayt n\n"
                              "    qayt fibonacci(n - 1) + fibonacci(n - 2)\n\nchiqar fibonacci(10)\n")

    def _hz_clear(self, w): self._hz_inp.value = ''; self._hz_out.value = ''

    # ─── ZAFAR ────────────────────────────────────────────────────
    def _tab_zafar(self):
        root = _box(COLUMN, pad=0, flex=1)
        st = "✅ Faol" if ZAFAR_BOR else "❌ Yuklanmadi"
        root.add(_lbl(f"🌟 Zafar O'zbek Tili — {st}", size=13, bold=True, pad=8))
        root.add(_sep())
        self._zf_inp = _inp(h=220, value='son a = 5\nson b = 3\nchiqar a * b\n')
        root.add(self._zf_inp)
        brow = _box(ROW, pad=4)
        brow.add(_btn("▶ Ishlatish", self._zf_run,     pad=6, flex=1))
        brow.add(_btn("📋 xASM",     self._zf_compile, pad=6, flex=1))
        brow.add(_btn("💡 Misol",    self._zf_example, pad=6, flex=1))
        brow.add(_btn("🗑 Tozala",   self._zf_clear,   pad=6, flex=1))
        root.add(brow)
        root.add(_sep())
        self._zf_out = _out(flex=1)
        root.add(self._zf_out)
        return root

    def _zf_run(self, widget):
        if not ZAFAR_BOR: self._zf_out.value = "❌ Zafar yuklanmadi"; return
        code = self._zf_inp.value.strip()
        if not code: return
        def run():
            try:
                r = _zafar_til.run(code)
                if r.get('muvaffaqiyat'):
                    self._zf_out.value = (f"✅ Muvaffaqiyatli\n"
                        f"Chiqish  : {r.get('chiqish','')}\n"
                        f"Buyruqlar: {r.get('buyruqlar',0)}\nBaytlar  : {r.get('baytlar',0)}")
                else: self._zf_out.value = f"❌ {r.get('xato','Xato')}"
            except Exception as e: self._zf_out.value = f"❌ {e}"
        threading.Thread(target=run, daemon=True).start()
        self._zf_out.value = "⏳ Kompilyatsiya..."

    def _zf_compile(self, widget):
        if not ZAFAR_BOR: return
        xasm, xato = _zafar_til.compile(self._zf_inp.value.strip())
        self._zf_out.value = f"❌ {xato}" if xato else f"✅ xASM:\n{xasm}"

    def _zf_example(self, widget):
        self._zf_inp.value = "ish kvadrat(n):\n    qayt n * n\n\ntakror i = 1, 6:\n    chiqar kvadrat(i)\n"

    def _zf_clear(self, w): self._zf_inp.value = ''; self._zf_out.value = ''

    # ─── BRAIN v5.0 ───────────────────────────────────────────────
    def _tab_brain(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("🧠 Brain AI v5.0 — Persistent + Fon O'rganish", size=13, bold=True, pad=8))
        root.add(_sep())
        brain = _machine.brain
        store = getattr(brain, 'store', None)
        age   = store.brain_age() if store else 'yangi'
        chat_n = store.chat.total_count() if store else 0
        self._br_out = _out(
            value=f"Brain v5.0 tayyor.\nYosh: {age} | Suhbatlar: {chat_n}\n"
                  f"'fibonacci kodi', 'xos nima', 'yordam'\n", flex=1)
        root.add(self._br_out)
        root.add(_sep())
        inp_row = _box(ROW, pad=4)
        self._br_inp = toga.TextInput(
            placeholder="xabar yozing...",
            style=Pack(flex=1, padding=4, font_size=12))
        inp_row.add(self._br_inp)
        inp_row.add(_btn("📨 Yuborish", self._br_send, pad=6))
        root.add(inp_row)
        brow = _box(ROW, pad=4)
        brow.add(_btn("📊 Status",  self._br_status, pad=6, flex=1))
        brow.add(_btn("💾 Saqlash", self._br_save,   pad=6, flex=1))
        brow.add(_btn("🤖 Fon",     self._br_bg,     pad=6, flex=1))
        brow.add(_btn("🗑 Tozala",  self._br_clear,  pad=6, flex=1))
        root.add(brow)
        return root

    def _br_send(self, widget):
        msg = self._br_inp.value.strip()
        if not msg: return
        self._br_inp.value = ''
        self._br_out.value += f"\n👤 {msg}\n"
        def run():
            try:
                with _lock: r = _machine.brain_chat(msg)
                self._br_out.value += f"🧠 {r}\n"
            except Exception as e: self._br_out.value += f"❌ {e}\n"
        threading.Thread(target=run, daemon=True).start()

    def _br_status(self, widget):
        try:
            with _lock: r = _machine.brain_status()
            self._br_out.value += f"\n📊 Status:\n{r}\n"
        except Exception as e: self._br_out.value += f"❌ {e}\n"

    def _br_save(self, widget):
        try:
            brain = _machine.brain
            store = getattr(brain, 'store', None)
            if store:
                ok = store.save_brain(brain)
                self._br_out.value += "✅ Persistent saqlash OK\n" if ok else "❌ Saqlash xato\n"
            else:
                _machine.brain_save(os.path.join(os.path.expanduser('~'), '.xos_brain.json'))
                self._br_out.value += "✅ Brain saqlandi\n"
        except Exception as e: self._br_out.value += f"❌ {e}\n"

    def _br_bg(self, widget):
        try:
            bg = getattr(_machine.brain, 'bg_learner', None)
            if bg: self._br_out.value += f"\n{bg.status()}\n"
            else:  self._br_out.value += "⏸ Fon o'rganish yuklanmagan\n"
        except Exception as e: self._br_out.value += f"❌ {e}\n"

    def _br_clear(self, w): self._br_out.value = "Tozalandi.\n"

    # ─── RL ───────────────────────────────────────────────────────
    def _tab_rl(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("🤖 Reinforcement Learning", size=13, bold=True, pad=8))
        root.add(_sep())
        self._rl_out = _out(value="RL Engine tayyor.\n", flex=1)
        root.add(self._rl_out)
        root.add(_sep())
        erow = _box(ROW, pad=8)
        erow.add(_lbl("Epizodlar:", size=12, pad=4))
        self._rl_ep = toga.TextInput(value="10", style=Pack(flex=1, padding=4, font_size=14))
        erow.add(self._rl_ep)
        root.add(erow)
        brow = _box(ROW, pad=4)
        brow.add(_btn("🚀 Trening", self._rl_train,  pad=8, flex=2))
        brow.add(_btn("📊 Status",  self._rl_status, pad=8, flex=1))
        brow.add(_btn("🗑 Tozala",  self._rl_clear,  pad=8, flex=1))
        root.add(brow)
        return root

    def _rl_train(self, widget):
        try: n = max(1, int(str(self._rl_ep.value or "10").strip()))
        except: n = 10
        self._rl_out.value += f"\n🚀 {n} epizod boshlanmoqda...\n"
        def run():
            try:
                with _rl_lock: r = _machine.brain.rl_train(n)
                self._rl_out.value += (
                    f"✅ Tugadi\n  Epizod: {r.get('episodes',0)}\n"
                    f"  O'rt mukofot: {r.get('avg_reward',0)}\n"
                    f"  Muvaffaqiyat: {r.get('success_rate',0)}%\n"
                    f"  Yangi shablon: {r.get('new_programs',0)}\n")
            except Exception as e: self._rl_out.value += f"❌ {e}\n"
        threading.Thread(target=run, daemon=True).start()

    def _rl_status(self, widget):
        try:
            with _lock: r = _machine.brain.rl_status()
            self._rl_out.value += f"\n📊 {r}\n"
        except Exception as e: self._rl_out.value += f"❌ {e}\n"

    def _rl_clear(self, w): self._rl_out.value = "Tozalandi.\n"

    # ─── DEVICES ──────────────────────────────────────────────────
    def _tab_devices(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("🔌 Qurilmalar Paneli", size=13, bold=True, pad=8))
        root.add(_sep())
        self._dev_out = _out(flex=1)
        root.add(self._dev_out)
        root.add(_sep())
        brow = _box(ROW, pad=4)
        brow.add(_btn("🔄 Yangilash", self._dev_refresh, pad=6, flex=1))
        brow.add(_btn("↺ Reset",      self._dev_reset,   pad=6, flex=1))
        root.add(brow)
        self._dev_refresh(None)
        return root

    def _dev_refresh(self, widget):
        try:
            with _lock: st = _machine.status()
            mem    = st.get('memory', {})
            cpu_st = st.get('cpu', {})
            brain  = _machine.brain
            store  = getattr(brain, 'store', None)
            bg     = getattr(brain, 'bg_learner', None)
            age    = store.brain_age() if store else 'yangi'
            chat_n = store.chat.total_count() if store else 0
            saves  = store._stats.get('total_saves', 0) if store else 0
            bg_s   = '🟢 Faol' if (bg and bg._running) else '⏸'
            bg_rl  = bg.total_rl_episodes if bg else 0
            lines = [
                "╔══════════════════════════════════════╗",
                "║  xOS v5.0 — Qurilmalar holati        ║",
                "╠══════════════════════════════════════╣",
                f"║  🧮 CPU    ● {cpu_st.get('mips',0):.4f} MIPS          ║",
                f"║  💾 RAM    ● {mem.get('total_mb',1)} MB                ║",
                f"║  📟 UART   ● Faol                    ║",
                f"║  ⚡ GPIO   ● 8 pin                   ║",
                f"║  ⚡ Hamza  ● {'Faol' if HAMZA_BOR else 'Yoq'}                  ║",
                f"║  🌟 Zafar  ● {'Faol' if ZAFAR_BOR else 'Yoq'}                  ║",
                "╠══════════════════════════════════════╣",
                f"║  🧠 Brain yoshi   : {age:<16} ║",
                f"║  💬 Suhbatlar     : {chat_n:<16} ║",
                f"║  💾 Saqlashlar    : {saves:<16} ║",
                f"║  🤖 Fon o'rganish : {bg_s:<14} ║",
                f"║  🚀 Fon RL ep     : {bg_rl:<16} ║",
                "╠══════════════════════════════════════╣",
                f"║  🕐 {time.strftime('%Y-%m-%d %H:%M:%S')}           ║",
                "╚══════════════════════════════════════╝",
            ]
            self._dev_out.value = '\n'.join(lines)
        except Exception as e: self._dev_out.value = f"❌ {e}"

    def _dev_reset(self, widget):
        try:
            with _lock: _machine.reset()
            self._dev_out.value = "✅ Qayta boshlandi.\n"
        except Exception as e: self._dev_out.value = f"❌ {e}"

    # ─── CPU ──────────────────────────────────────────────────────
    def _tab_cpu(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("📊 CPU — xCPU-1 Monitor", size=13, bold=True, pad=8))
        root.add(_sep())
        self._cpu_out = _out(flex=1)
        root.add(self._cpu_out)
        root.add(_sep())
        brow = _box(ROW, pad=4)
        brow.add(_btn("🔄 Yangilash", self._cpu_refresh, pad=6, flex=1))
        brow.add(_btn("📋 Mem Dump",  self._cpu_dump,    pad=6, flex=1))
        root.add(brow)
        self._cpu_refresh(None)
        return root

    def _cpu_refresh(self, widget):
        try:
            with _lock:
                cpu = _machine.cpu
                regs = list(cpu.regs)
                pc, sp, lr = cpu.pc, cpu.sp, cpu.lr
                fn, fz, fc, fv = cpu.flag_n, cpu.flag_z, cpu.flag_c, cpu.flag_v
                halt, cyc, instr = cpu.halted, cpu.cycles, cpu.instr_count
            fl = f"{'N' if fn else '-'}{'Z' if fz else '-'}{'C' if fc else '-'}{'V' if fv else '-'}"
            lines = ["╔══════════════════════════════════════╗",
                     f"║  xCPU-1  {'HALTED' if halt else 'RUNNING':<8}  Flaglar:{fl}  ║",
                     "╠══════════════════════════════════════╣"]
            for i in range(0, 12, 2):
                lines.append(f"║  X{i:02d}={regs[i]:>10d}  X{i+1:02d}={regs[i+1]:>10d}  ║")
            lines += ["╠══════════════════════════════════════╣",
                      f"║  SP={sp:#010x}  (Stack Pointer)  ║",
                      f"║  LR={lr:#010x}  (Link Register)  ║",
                      f"║  PC={pc:#010x}  (Prog Counter)   ║",
                      "╠══════════════════════════════════════╣",
                      f"║  Tsikllar  : {cyc:>12,}          ║",
                      f"║  Buyruqlar : {instr:>12,}          ║",
                      "╚══════════════════════════════════════╝"]
            self._cpu_out.value = '\n'.join(lines)
        except Exception as e: self._cpu_out.value = f"❌ {e}"

    def _cpu_dump(self, widget):
        try:
            with _lock: dump = _machine.dump_mem(0x00020000, 64)
            self._cpu_out.value = dump
        except Exception as e: self._cpu_out.value = f"❌ {e}"

    # ─── QO'LLANMA ────────────────────────────────────────────────
    def _tab_qollanma(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("📖 xOS v5.0 Qo'llanma", size=14, bold=True, pad=8))
        root.add(_sep())
        root.add(toga.MultilineTextInput(
            value=QOLLANMA, readonly=True,
            style=Pack(flex=1, padding=8, font_size=11, font_family='monospace')))
        return root


QOLLANMA = """
⬡ xOS v5.0 — To'liq Qo'llanma
================================

🆕 v5.0 YANGILIKLAR:
  💾 Persistent Xotira — diskda saqlanadi
  🤖 Fon O'rganish    — har vaqt ishlaydi
  🧠 Aqlli Chat       — "fibonacci kodi" tushunadi
  📖 Suhbat Tarixi    — saqlanadi

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 BRAIN SAVOLLARI:
  salom            → Brain holati
  xos nima         → Tizim haqida
  fibonacci kodi   → Hamza fibonacci
  factorial kodi   → Hamza factorial
  xasm misol       → Assembly namuna
  10 + 20          → Hisoblash
  status           → Brain statistika
  fon              → Fon o'rganish
  xotira           → Xotira holati
  yordam           → Barcha buyruqlar

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ HAMZA SINTAKSIS:
  son x = 5
  agar x > 3:
      chiqar x
  takror i = 0, 10:
      chiqar i
  ish f(a, b):
      qayt a + b
  chiqar f(3, 4)   → 7

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 xASM:
  LOAD X0, #10
  ADD  X2, X0, X1
  PRINT X2
  HALT

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Fibonacci (Hamza):
  ish fib(n):
      agar n < 2:
          qayt n
      qayt fib(n-1) + fib(n-2)
  chiqar fib(10)  → 55

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  xOS Team 2026 | v5.0.0 | MIT
"""


def main():
    return xOSApp("xOS v5.0", "uz.xos.app")
