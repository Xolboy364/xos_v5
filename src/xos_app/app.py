"""
xOS v3.2 — Android APK
Tablar: Shell | xASM | Hamza | Zafar | Brain | RL | Devices | CPU | Qo'llanma

Tuzatishlar (APK uchun):
 - toga.style.Pack to'g'ri ishlatiladi
 - Barcha background_color olib tashlandi (Android Toga da ishlamaydi)
 - MultilineTextInput.readonly=True sintaksisi tuzatildi
 - Lambda closurelar tuzatildi
 - threading.Thread daemon=True qo'shildi
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
_lock = threading.Lock()
_rl_lock = threading.Lock()
_brain_file = os.path.join(os.path.expanduser('~'), '.xos_v32_brain.json')
try:
    _machine.brain_load(_brain_file)
except Exception:
    pass

# ── Stil yordamchilari ──────────────────────────────────────────
def _col(pad=4, flex=1):
    return Pack(direction=COLUMN, padding=pad, flex=flex)

def _row(pad=4, flex=0):
    kw = dict(direction=ROW, padding=pad)
    if flex: kw['flex'] = flex
    return Pack(**kw)

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
    """Read-only multiline output"""
    kw = dict(padding=4, font_family='monospace', font_size=11)
    if h: kw['height'] = h
    if flex: kw['flex'] = flex
    return toga.MultilineTextInput(
        value=value,
        readonly=True,
        style=Pack(**kw)
    )

def _inp(placeholder='', h=200, flex=0, value=''):
    """Editable multiline input"""
    kw = dict(padding=4, font_family='monospace', font_size=11)
    if h: kw['height'] = h
    if flex: kw['flex'] = flex
    w = toga.MultilineTextInput(style=Pack(**kw))
    if value:
        w.value = value
    if placeholder:
        w.placeholder = placeholder
    return w

def _sep():
    return toga.Divider()

# ══════════════════════════════════════════════════════════════════
class xOSApp(toga.App):

    def startup(self):
        self.main_window = toga.MainWindow(title="xOS v3.2")

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

    # ══════════════════════════════════════════════════════════════
    # SHELL TAB
    # ══════════════════════════════════════════════════════════════
    def _tab_shell(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("⬡ xOS v3.2 Shell", size=14, bold=True, pad=8))
        root.add(_sep())

        self._sh_out = _out(
            value="xOS v3.2 — tayyor\n'help' — yordam\n",
            flex=1
        )
        root.add(self._sh_out)
        root.add(_sep())

        inp_row = _box(ROW, pad=4)
        self._sh_inp = toga.TextInput(
            placeholder="buyruq kiriting...",
            style=Pack(flex=1, padding=4, font_family='monospace', font_size=12)
        )
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
        if not cmd:
            return
        self._sh_inp.value = ''
        self._sh_out.value += f"\n$ {cmd}\n"
        try:
            result = _machine.shell.run(cmd)
            self._sh_out.value += str(result) + "\n"
        except Exception as e:
            self._sh_out.value += f"❌ Xato: {e}\n"

    def _sh_clear(self, widget):
        self._sh_out.value = "Tozalandi.\n"

    def _sh_help(self, widget):
        self._sh_out.value += "\n$ help\n"
        self._sh_out.value += _machine.shell.run("help") + "\n"

    def _sh_demos(self, widget):
        self._sh_out.value += "\n$ demos\n"
        self._sh_out.value += _machine.shell.run("demos") + "\n"

    # ══════════════════════════════════════════════════════════════
    # xASM EDITOR TAB
    # ══════════════════════════════════════════════════════════════
    def _tab_editor(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("📝 xASM Editor", size=14, bold=True, pad=8))
        root.add(_sep())

        self._ed_inp = _inp(
            placeholder="xASM kodi...",
            h=280,
            value="; xOS Assembly\n.section text\n    LOAD X0, #10\n    LOAD X1, #20\n    ADD  X2, X0, X1\n    PRINT X2\n    HALT\n"
        )
        root.add(self._ed_inp)

        brow = _box(ROW, pad=4)
        brow.add(_btn("▶ Ishlatish",  self._ed_run,     pad=6, flex=1))
        brow.add(_btn("⚙ Assemble",  self._ed_assemble, pad=6, flex=1))
        brow.add(_btn("📦 xELF",     self._ed_elf,      pad=6, flex=1))
        brow.add(_btn("🗑 Tozala",   self._ed_clear,    pad=6, flex=1))
        root.add(brow)

        root.add(_sep())
        root.add(_lbl("Natija:", size=11, bold=True, pad=4))
        self._ed_out = _out(flex=1)
        root.add(self._ed_out)
        return root

    def _ed_run(self, widget):
        code = self._ed_inp.value.strip()
        if not code:
            self._ed_out.value = "❌ Kod kiriting"
            return
        def run():
            try:
                with _lock:
                    r = _machine.run_source(code)
                out = r.get('output', '')
                instr = r.get('instr', 0)
                halted = r.get('halted', False)
                self._ed_out.value = (
                    f"✅ Muvaffaqiyatli\n"
                    f"Chiqish : {out}\n"
                    f"Buyruqlar: {instr}\n"
                    f"Holat   : {'HALT ✅' if halted else 'Limit ⏸'}"
                )
            except Exception as e:
                self._ed_out.value = f"❌ Xato: {e}"
        threading.Thread(target=run, daemon=True).start()
        self._ed_out.value = "⏳ Ishlamoqda..."

    def _ed_assemble(self, widget):
        code = self._ed_inp.value.strip()
        if not code:
            return
        try:
            from compiler.assembler import Assembler
            asm = Assembler()
            bc = asm.assemble(code)
            self._ed_out.value = f"✅ Assemble\nBaytlar: {len(bc)}\nHex: {bc[:32].hex()}"
        except Exception as e:
            self._ed_out.value = f"❌ Assemble xatosi: {e}"

    def _ed_elf(self, widget):
        code = self._ed_inp.value.strip()
        if not code:
            return
        try:
            r = _machine.shell.run(f'elf "{code}"')
            self._ed_out.value = str(r)
        except Exception as e:
            self._ed_out.value = f"❌ {e}"

    def _ed_clear(self, widget):
        self._ed_inp.value = ''
        self._ed_out.value = ''

    # ══════════════════════════════════════════════════════════════
    # HAMZA TAB
    # ══════════════════════════════════════════════════════════════
    def _tab_hamza(self):
        root = _box(COLUMN, pad=0, flex=1)
        status = "✅ Faol" if HAMZA_BOR else "❌ Yuklanmadi"
        root.add(_lbl(f"⚡ Hamza O'zbek Tili — {status}", size=13, bold=True, pad=8))
        root.add(_sep())

        self._hz_inp = _inp(
            h=220,
            value='son x = 10\nson y = 20\nchiqar x + y\n'
        )
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
        if not HAMZA_BOR:
            self._hz_out.value = "❌ Hamza moduli yuklanmadi"
            return
        code = self._hz_inp.value.strip()
        if not code:
            return
        def run():
            try:
                r = _hamza_til.run(code)
                if r.get('muvaffaqiyat'):
                    self._hz_out.value = (
                        f"✅ Muvaffaqiyatli\n"
                        f"Chiqish  : {r.get('chiqish', '')}\n"
                        f"Buyruqlar: {r.get('buyruqlar', 0)}\n"
                        f"Baytlar  : {r.get('baytlar', 0)}"
                    )
                else:
                    self._hz_out.value = f"❌ Xato: {r.get('xato', 'Noma\'lum')}"
            except Exception as e:
                self._hz_out.value = f"❌ {e}"
        threading.Thread(target=run, daemon=True).start()
        self._hz_out.value = "⏳ Kompilyatsiya..."

    def _hz_compile(self, widget):
        if not HAMZA_BOR:
            return
        code = self._hz_inp.value.strip()
        if not code:
            return
        xasm, xato = _hamza_til.compile(code)
        if xato:
            self._hz_out.value = f"❌ {xato}"
        else:
            self._hz_out.value = f"✅ xASM kodi:\n{xasm}"

    def _hz_example(self, widget):
        self._hz_inp.value = (
            "ish fibonacci(n):\n"
            "    agar n < 2:\n"
            "        qayt n\n"
            "    qayt fibonacci(n - 1) + fibonacci(n - 2)\n\n"
            "chiqar fibonacci(10)\n"
        )

    def _hz_clear(self, widget):
        self._hz_inp.value = ''
        self._hz_out.value = ''

    # ══════════════════════════════════════════════════════════════
    # ZAFAR TAB
    # ══════════════════════════════════════════════════════════════
    def _tab_zafar(self):
        root = _box(COLUMN, pad=0, flex=1)
        status = "✅ Faol" if ZAFAR_BOR else "❌ Yuklanmadi"
        root.add(_lbl(f"🌟 Zafar O'zbek Tili — {status}", size=13, bold=True, pad=8))
        root.add(_sep())

        self._zf_inp = _inp(
            h=220,
            value='son a = 5\nson b = 3\nchiqar a * b\n'
        )
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
        if not ZAFAR_BOR:
            self._zf_out.value = "❌ Zafar moduli yuklanmadi"
            return
        code = self._zf_inp.value.strip()
        if not code:
            return
        def run():
            try:
                r = _zafar_til.run(code)
                if r.get('muvaffaqiyat'):
                    self._zf_out.value = (
                        f"✅ Muvaffaqiyatli\n"
                        f"Chiqish  : {r.get('chiqish', '')}\n"
                        f"Buyruqlar: {r.get('buyruqlar', 0)}\n"
                        f"Baytlar  : {r.get('baytlar', 0)}"
                    )
                else:
                    self._zf_out.value = f"❌ Xato: {r.get('xato', 'Noma\'lum')}"
            except Exception as e:
                self._zf_out.value = f"❌ {e}"
        threading.Thread(target=run, daemon=True).start()
        self._zf_out.value = "⏳ Kompilyatsiya..."

    def _zf_compile(self, widget):
        if not ZAFAR_BOR:
            return
        code = self._zf_inp.value.strip()
        if not code:
            return
        xasm, xato = _zafar_til.compile(code)
        if xato:
            self._zf_out.value = f"❌ {xato}"
        else:
            self._zf_out.value = f"✅ xASM kodi:\n{xasm}"

    def _zf_example(self, widget):
        self._zf_inp.value = (
            "ish kvadrat(n):\n"
            "    qayt n * n\n\n"
            "takror i = 1, 6:\n"
            "    chiqar kvadrat(i)\n"
        )

    def _zf_clear(self, widget):
        self._zf_inp.value = ''
        self._zf_out.value = ''

    # ══════════════════════════════════════════════════════════════
    # BRAIN TAB
    # ══════════════════════════════════════════════════════════════
    def _tab_brain(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("🧠 Brain AI — Neyron Tarmoq", size=13, bold=True, pad=8))
        root.add(_sep())

        self._br_out = _out(
            value="Brain AI tayyor. Xabar yuboring...\nMisol: 'fibonacci kodi', 'xos nima', 'yordam'\n",
            flex=1
        )
        root.add(self._br_out)
        root.add(_sep())

        inp_row = _box(ROW, pad=4)
        self._br_inp = toga.TextInput(
            placeholder="xabar yoki 'status', 'gen <vazifa>'...",
            style=Pack(flex=1, padding=4, font_size=12)
        )
        inp_row.add(self._br_inp)
        inp_row.add(_btn("📨 Yuborish", self._br_send, pad=6))
        root.add(inp_row)

        brow = _box(ROW, pad=4)
        brow.add(_btn("📊 Status",  self._br_status,  pad=6, flex=1))
        brow.add(_btn("💾 Saqlash", self._br_save,    pad=6, flex=1))
        brow.add(_btn("🗑 Tozala",  self._br_clear,   pad=6, flex=1))
        root.add(brow)
        return root

    def _br_send(self, widget):
        msg = self._br_inp.value.strip()
        if not msg:
            return
        self._br_inp.value = ''
        self._br_out.value += f"\n👤 {msg}\n"
        def run():
            try:
                # Avval ai_core dan real javob
                from ai_core import AIYordamchi
                if not hasattr(self, '_ai_yordamchi'):
                    self._ai_yordamchi = AIYordamchi()
                ai_javob = self._ai_yordamchi.javob(msg)

                # Agar ai_core aniq javob bersa — uni ishlatamiz
                # Agar "Tushundim" (noaniq) bo'lsa — machine.brain_chat ga o'tamiz
                if "Tushundim:" in ai_javob or "Savolingiz:" in ai_javob:
                    with _lock:
                        r = _machine.brain_chat(msg)
                    self._br_out.value += f"🧠 {r}\n"
                else:
                    self._br_out.value += f"🧠 {ai_javob}\n"
            except Exception as e:
                self._br_out.value += f"❌ {e}\n"
        threading.Thread(target=run, daemon=True).start()

    def _br_status(self, widget):
        try:
            with _lock:
                r = _machine.brain_status()
            self._br_out.value += f"\n📊 Status:\n{r}\n"
        except Exception as e:
            self._br_out.value += f"❌ {e}\n"

    def _br_save(self, widget):
        try:
            _machine.brain_save(_brain_file)
            self._br_out.value += "✅ Brain saqlandi\n"
        except Exception as e:
            self._br_out.value += f"❌ {e}\n"

    def _br_clear(self, widget):
        self._br_out.value = "Tozalandi.\n"

    # ══════════════════════════════════════════════════════════════
    # RL TAB
    # ══════════════════════════════════════════════════════════════
    def _tab_rl(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("🤖 Reinforcement Learning", size=13, bold=True, pad=8))
        root.add(_sep())

        self._rl_out = _out(
            value="RL Engine tayyor.\nEpizod sonini tanlang va trening boshlang.\n",
            flex=1
        )
        root.add(self._rl_out)
        root.add(_sep())

        erow = _box(ROW, pad=8)
        erow.add(_lbl("Epizodlar:", size=12, pad=4))
        # NumberInput Android da mavjud emas → TextInput
        self._rl_episodes = toga.TextInput(
            value="10",
            style=Pack(flex=1, padding=4, font_size=14)
        )
        erow.add(self._rl_episodes)
        root.add(erow)

        brow = _box(ROW, pad=4)
        brow.add(_btn("🚀 Trening boshlash", self._rl_train,  pad=8, flex=2))
        brow.add(_btn("📊 Status",           self._rl_status, pad=8, flex=1))
        root.add(brow)
        return root

    def _rl_train(self, widget):
        try:
            n = max(1, int(str(self._rl_episodes.value or "10").strip()))
        except (ValueError, TypeError):
            n = 10
        self._rl_out.value += f"\n🚀 {n} ta epizod boshlanmoqda...\n"
        def run():
            try:
                with _rl_lock:
                    results = _machine.brain.rl_train(n)
                self._rl_out.value += (
                    f"✅ Trening tugadi\n"
                    f"  Epizodlar    : {results.get('episodes', 0)}\n"
                    f"  O'rt mukofot : {results.get('avg_reward', 0)}\n"
                    f"  Maks mukofot : {results.get('max_reward', 0)}\n"
                    f"  Muvaffaqiyat : {results.get('success_rate', 0)}%\n"
                )
            except Exception as e:
                self._rl_out.value += f"❌ {e}\n"
        threading.Thread(target=run, daemon=True).start()

    def _rl_status(self, widget):
        try:
            with _lock:
                r = _machine.brain_chat("rl status")
            self._rl_out.value += f"\n📊 {r}\n"
        except Exception as e:
            self._rl_out.value += f"❌ {e}\n"

    # ══════════════════════════════════════════════════════════════
    # DEVICES TAB
    # ══════════════════════════════════════════════════════════════
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
            with _lock:
                st = _machine.status()
            dev = st.get('devices', {})
            mem = st.get('memory', {})
            cpu_st = st.get('cpu', {})
            lines = [
                "╔══════════════════════════════════════╗",
                "║  xOS v3.2 — Qurilmalar holati        ║",
                "╠══════════════════════════════════════╣",
                f"║  🧮 CPU    ● {cpu_st.get('mips',0):.4f} MIPS          ║",
                f"║  💾 RAM    ● {mem.get('total_mb',1)} MB                ║",
                f"║  📟 UART   ● Faol                    ║",
                f"║  ⚡ GPIO   ● 8 pin                   ║",
                f"║  🕐 Timer  ● Faol                    ║",
                f"║  🖥  Display● 320x240 px              ║",
                f"║  ⚡ Hamza  ● {'Faol' if HAMZA_BOR else 'Yo\'q'}                  ║",
                f"║  🌟 Zafar  ● {'Faol' if ZAFAR_BOR else 'Yo\'q'}                  ║",
                "╠══════════════════════════════════════╣",
                f"║  🕐 {time.strftime('%Y-%m-%d %H:%M:%S')}           ║",
                "╚══════════════════════════════════════╝",
            ]
            self._dev_out.value = '\n'.join(lines)
        except Exception as e:
            self._dev_out.value = f"❌ {e}"

    def _dev_reset(self, widget):
        try:
            with _lock:
                _machine.reset()
            self._dev_out.value = "✅ Barcha qurilmalar qayta boshlandi.\n"
        except Exception as e:
            self._dev_out.value = f"❌ {e}"

    # ══════════════════════════════════════════════════════════════
    # CPU TAB
    # ══════════════════════════════════════════════════════════════
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
                halt = cpu.halted
                cyc = cpu.cycles
                instr = cpu.instr_count
            fl = f"{'N' if fn else '-'}{'Z' if fz else '-'}{'C' if fc else '-'}{'V' if fv else '-'}"
            lines = [
                "╔══════════════════════════════════════╗",
                f"║  xCPU-1  {'HALTED' if halt else 'RUNNING':<8}  Flaglar:{fl}  ║",
                "╠══════════════════════════════════════╣",
            ]
            for i in range(0, 12, 2):
                lines.append(
                    f"║  X{i:02d}={regs[i]:>10d}  X{i+1:02d}={regs[i+1]:>10d}  ║"
                )
            lines += [
                "╠══════════════════════════════════════╣",
                f"║  SP={sp:#010x}  (Stack Pointer)  ║",
                f"║  LR={lr:#010x}  (Link Register)  ║",
                f"║  PC={pc:#010x}  (Prog Counter)   ║",
                "╠══════════════════════════════════════╣",
                f"║  Tsikllar  : {cyc:>12,}          ║",
                f"║  Buyruqlar : {instr:>12,}          ║",
                "╚══════════════════════════════════════╝",
            ]
            self._cpu_out.value = '\n'.join(lines)
        except Exception as e:
            self._cpu_out.value = f"❌ {e}"

    def _cpu_dump(self, widget):
        try:
            with _lock:
                from memory.memory import RAM_START
                dump = _machine.memory.dump(RAM_START, 64)
            self._cpu_out.value = dump
        except Exception as e:
            self._cpu_out.value = f"❌ {e}"

    # ══════════════════════════════════════════════════════════════
    # QO'LLANMA TAB
    # ══════════════════════════════════════════════════════════════
    def _tab_qollanma(self):
        root = _box(COLUMN, pad=0, flex=1)
        root.add(_lbl("📖 xOS v3.2 Qo'llanma", size=14, bold=True, pad=8))
        root.add(_sep())

        # ScrollContainer + Label Android da ishlamasligi mumkin
        # MultilineTextInput(readonly=True) ishonchli variant
        text = toga.MultilineTextInput(
            value=QOLLANMA_MATNI,
            readonly=True,
            style=Pack(flex=1, padding=8, font_size=11, font_family='monospace')
        )
        root.add(text)
        return root


QOLLANMA_MATNI = """
⬡ xOS v3.2 — To'liq Qo'llanma
================================

📱 TABLAR:
  💻 Shell    — Interaktiv buyruq qatori
  📝 xASM     — Assembly editor
  ⚡ Hamza    — O'zbek dasturlash tili (YANGI!)
  🌟 Zafar    — O'zbek dasturlash tili (YANGI!)
  🧠 Brain    — AI suhbat va kod generatsiya
  🤖 RL       — Reinforcement Learning trening
  🔌 Devices  — Qurilmalar holati
  📊 CPU      — Registrlar va flaglar
  📖 Qo'llanma— Shu sahifa

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ HAMZA TILI SINTAKSISI:
  son x = 5        → o'zgaruvchi
  matn s = "Salom" → matn
  agar x > 3:      → shart
      chiqar x
  aks:
      chiqar 0
  takror i = 0, 10:→ tsikl
      chiqar i
  ish f(a, b):     → funksiya
      qayt a + b
  chiqar f(3, 4)   → natija: 7

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 xASM INSTRUKSIYALAR:
  LOAD X0, #100    → X0 = 100
  ADD  X2, X0, X1  → X2 = X0 + X1
  SUB  X2, X0, X1  → X2 = X0 - X1
  MUL  X2, X0, X1  → X2 = X0 * X1
  CMP  X0, X1      → taqqoslash
  JEQ  label       → teng bo'lsa sakra
  JNE  label       → teng bo'lmasa sakra
  JLT  label       → kichik bo'lsa sakra
  JGT  label       → katta bo'lsa sakra
  CALL func        → funksiya chaqir
  RET              → qayt
  PRINT X0         → raqam chiqar
  PUTC  X0         → belgi chiqar
  HALT             → to'xtat

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 BRAIN AI:
  status           → holat ko'rish
  gen <vazifa>     → kod generatsiya
  learn            → o'rganish tsikli
  patterns         → patternlar soni
  rules            → qoidalar soni

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 MISOL — Fibonacci (Hamza):
  ish fib(n):
      agar n < 2:
          qayt n
      qayt fib(n-1) + fib(n-2)
  chiqar fib(10)
  → Natija: 55

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  xOS Team — 2026 | v3.2.0
  100% Offline | 100% O'zbek
"""


def main():
    return xOSApp("xOS v3.2", "uz.xos.app")
