"""xOS v3.2 Shell — Interaktiv buyruq qatori (Hamza + Zafar tillari)"""
import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from kernel.machine import Machine

# Hamza tili integratsiyasi
try:
    from hamza.hamza import Hamza
    _hamza = Hamza()
    HAMZA_BOR = True
except ImportError:
    HAMZA_BOR = False

# Zafar tili integratsiyasi
try:
    from zafar.zafar import Zafar
    _zafar = Zafar()
    ZAFAR_BOR = True
except ImportError:
    ZAFAR_BOR = False

BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║   xOS v3.2 — O'z Operatsion Tizimi                             ║
║   xCPU-1  •  Brain AI  •  Devices  •  xELF                     ║
║   Hamza Tili  •  Zafar Tili  •  100% Offline                   ║
╚══════════════════════════════════════════════════════════════════╝
  'help' — buyruqlar  |  'quit' — chiqish
"""

HELP = """
╔══ xOS v3.2 Shell — Buyruqlar ══════════════════════════════╗
║  HAMZA TILI:                                                 ║
║    hamza \"KOD\"       → Hamza tilida kod ishlatish           ║
║    hamza fayl.hz    → Hamza faylini ishlatish               ║
║    hamza.tahlil \"KOD\"→ Token + xASM ko'rsatish              ║
║    hamza.demo       → Hamza misollarini ko'rsatish          ║
║                                                              ║
║  ZAFAR TILI:                                                 ║
║    zafar \"KOD\"       → Zafar tilida kod ishlatish           ║
║    zafar fayl.zf    → Zafar faylini ishlatish               ║
║    zafar.tahlil \"KOD\"→ Token + xASM ko'rsatish              ║
║    zafar.demo       → Zafar misollarini ko'rsatish          ║
║                                                              ║
║  xASM (assembly):                                            ║
║    run <fayl.xasm>  → faylni ishlatish                      ║
║    exec \"KOD\"        → kodni bevosita ishlatish              ║
║    demo <nom>       → tayyor demo                           ║
║    demos            → barcha demolar                        ║
║    asm \"KOD\"         → assembly → bytecode                   ║
║    elf \"KOD\"         → assembly → xELF binary                ║
║    dis <fayl>       → disassemble                           ║
║                                                              ║
║  BRAIN AI:                                                   ║
║    brain            → brain suhbat rejimi                   ║
║    gen <vazifa>     → kod generatsiya                       ║
║    bstatus          → brain holati                          ║
║    rl [N|status]    → RL trening                            ║
║                                                              ║
║  DEBUG:                                                      ║
║    regs             → registrlar                            ║
║    mem [addr]       → xotira dump                           ║
║    status           → mashina holati                        ║
║    reset            → qayta yuklash                         ║
╚══════════════════════════════════════════════════════════════╝"""


class Shell:
    def __init__(self):
        self.machine     = Machine()
        self.running     = True
        self.brain_mode  = False
        self.last_result = None
        self.brain_file  = os.path.expanduser('~/.xos_v32_brain.json')
        self.machine.brain_load(self.brain_file)
        self._hamza = _hamza if HAMZA_BOR else None
        self._zafar = _zafar if ZAFAR_BOR else None

    def run(self):
        print(BANNER)
        if HAMZA_BOR:
            print("  ✅ Hamza tili yuklandi — 'hamza \"kod\"' bilan ishlatish")
        else:
            print("  ⚠  Hamza tili topilmadi (hamza/hamza.py kerak)")
        if ZAFAR_BOR:
            print("  ✅ Zafar tili yuklandi — 'zafar \"kod\"' bilan ishlatish")
        else:
            print("  ⚠  Zafar tili topilmadi (zafar/zafar.py kerak)")
        demos = self.machine.available_demos()
        print(f"  Demolar ({len(demos)}): {', '.join(demos[:5])}...")
        print()

        while self.running:
            try:
                prompt = "🧠 brain> " if self.brain_mode else "xOS> "
                line = input(prompt).strip()
                if not line: continue
                self._dispatch(line)
            except KeyboardInterrupt:
                print("\n  Ctrl+C — chiqish uchun 'quit'")
            except EOFError:
                print("\nXayr!"); break
            except Exception as e:
                print(f"  ❌ Xato: {e}")

        self.machine.brain_save(self.brain_file)

    def _dispatch(self, line):
        # Brain rejimi
        if self.brain_mode:
            if line.lower() in ('exit', 'quit', 'q', 'chiq'):
                self.brain_mode = False
                print("  Shell rejiмига qaytildi.")
                return
            print(f"\n  🧠 {self.machine.brain_chat(line)}\n")
            return

        parts = line.split(None, 1)
        cmd   = parts[0].lower()
        args  = parts[1] if len(parts) > 1 else ''

        # ── Hamza tili buyruqlari ─────────────────────────────
        if cmd == 'hamza':
            self._hamza_run(args)
        elif cmd == 'hamza.tahlil':
            self._hamza_tahlil(args)
        elif cmd == 'hamza.demo':
            self._hamza_demo()

        # ── Zafar tili buyruqlari ─────────────────────────────
        elif cmd == 'zafar':
            self._zafar_run(args)
        elif cmd == 'zafar.tahlil':
            self._zafar_tahlil(args)
        elif cmd == 'zafar.demo':
            self._zafar_demo()

        # ── Umumiy buyruqlar ──────────────────────────────────
        elif cmd in ('quit', 'exit', 'q'):
            self.running = False
        elif cmd == 'help':
            print(HELP)
        elif cmd == 'clear':
            os.system('clear' if os.name == 'posix' else 'cls')
        elif cmd == 'brain':
            self.brain_mode = True
            print("  🧠 Brain rejimi. 'exit' bilan qaytish.\n")
            print(f"  🧠 {self.machine.brain_chat('salom')}\n")
        elif cmd == 'gen':
            if not args: print("  gen <vazifa>"); return
            print(f"\n{self.machine.brain_generate(args)}")
        elif cmd == 'bstatus':
            print(self.machine.brain_status())
        elif cmd == 'rl':
            if not self.machine.brain.rl_available():
                print("  ❌ RL Engine yuklanmagan"); return
            if not args or args == 'status':
                print(self.machine.brain.rl_status())
            elif args == 'episode':
                r = self.machine.brain.rl_episode()
                print(f"  Ep {r.get('episode','?')} | {r.get('action','?')} | "
                      f"R={r.get('reward',0):+.1f} | "
                      f"{'✅' if r.get('halted') else '❌'}")
            else:
                try: n = int(args.split()[0])
                except ValueError: n = 5
                print(f"  ⏳ RL {n} epizod...")
                r = self.machine.brain.rl_train(n, verbose=True)
                print(f"  ✅ avg={r['avg_reward']} success={r['success_rate']}%")
        elif cmd == 'blearn':
            self.machine.brain.force_learn()
            kb = self.machine.brain.kb.stats()
            print(f"  ✅ Pattern: {kb['patterns']}, Qoida: {kb['rules']}")
        elif cmd == 'bsave':
            path = args or self.brain_file
            self.machine.brain_save(path); print(f"  💾 {path}")
        elif cmd == 'bload':
            path = args or self.brain_file
            self.machine.brain_load(path); print(f"  📂 {path}")
        elif cmd == 'demos':
            for d in self.machine.available_demos(): print(f"  • {d}")
        elif cmd == 'demo':
            if not args:
                print(f"  demo <nom>. Mavjud: {', '.join(self.machine.available_demos())}"); return
            self._run_show(lambda: self.machine.run_demo(args), f"demo '{args}'")
        elif cmd == 'exec':
            if not args: print("  exec \"KOD\""); return
            self._run_show(
                lambda: self.machine.run_source(args.replace('\\n', '\n')), "exec")
        elif cmd == 'run':
            if not args: print("  run <fayl>"); return
            try:
                src = open(args, encoding='utf-8').read()
                ext = os.path.splitext(args)[1].lower()
                if ext == '.hz':
                    self._hamza_run(f'"{src}"')
                else:
                    self._run_show(lambda: self.machine.run_source(src), args)
            except FileNotFoundError:
                print(f"  ❌ Fayl topilmadi: {args}")
        elif cmd == 'asm':
            if not args: print("  asm \"KOD\""); return
            try:
                code = self.machine.compile(args.replace('\\n', '\n'))
                print(f"\n  Binary ({len(code)} byte):")
                for i in range(0, min(len(code), 64), 4):
                    w = int.from_bytes(code[i:i+4], 'little')
                    print(f"  0x{0x20000+i:08X}:  {w:08X}")
            except Exception as e:
                print(f"  ❌ {e}")
        elif cmd == 'elf':
            if not args: print("  elf \"KOD\""); return
            try:
                elf = self.machine.compile_to_elf(args.replace('\\n', '\n'))
                print(self.machine.dump_elf(elf))
            except Exception as e:
                print(f"  ❌ {e}")
        elif cmd == 'dis':
            if not args: print("  dis <fayl>"); return
            try:
                data = open(args, 'rb').read()
                print(self.machine.disassemble(data))
            except FileNotFoundError:
                print(f"  ❌ {args} topilmadi")
        elif cmd == 'analyze':
            if not args: print("  analyze <fayl.xasm>"); return
            try:
                src = open(args, encoding='utf-8').read()
                print(self.machine.brain_analyze(src))
            except FileNotFoundError:
                print(f"  ❌ {args} topilmadi")
        elif cmd == 'evaluate':
            if self.last_result:
                print(self.machine.brain_evaluate(self.last_result))
            else:
                print("  Avval dastur ishlatib ko'ring")
        elif cmd == 'devices':
            d = self.machine.bus.summary()
            print(f"  UART  : tx={d['uart']['tx_len']} rx={d['uart']['rx_len']}")
            print(f"  Timer0: val={d['timer0']['value']} fires={d['timer0']['fires']}")
            print(f"  GPIO  : dir={d['gpio']['dir']} out={d['gpio']['out']}")
            print(f"  Display: {d['display']['size']} {d['display']['bpp']}bpp")
        elif cmd == 'gpio':
            p2 = args.split()
            if len(p2) >= 2:
                self.machine.gpio_set(int(p2[0]), bool(int(p2[1])))
                print(f"  GPIO pin {p2[0]} = {p2[1]}")
            else:
                print("  gpio <pin> <0|1>")
        elif cmd == 'timer':
            if args:
                self.machine.timer_start(int(args))
                print(f"  Timer0 ishga tushdi: load={args}")
            else:
                print("  timer <load_value>")
        elif cmd == 'regs':
            print(self.machine.dump_regs())
        elif cmd == 'mem':
            addr = int(args, 16) if args else 0x20000
            print(self.machine.dump_mem(addr, 64))
        elif cmd == 'status':
            st  = self.machine.status()
            cpu = st['cpu']; mem = st['memory']; brn = st['brain']
            hamza_holat = "✅ Yuklangan" if HAMZA_BOR else "❌ Yuklanmagan"
            zafar_holat = "✅ Yuklangan" if ZAFAR_BOR else "❌ Yuklanmagan"
            print(f"""
  ╔══ xOS v3.2 Machine Status ══════════════════════╗
  ║  CPU    : {cpu['instr']} instr, {cpu['mips']} MIPS
  ║  Xotira : {mem['total_mb']} MB, heap={mem['heap_used']} byte
  ║  Brain  : {brn['patterns']} pattern, {brn['rules']} qoida
  ║  Hamza  : {hamza_holat}
  ║  Zafar  : {zafar_holat}
  ╚══════════════════════════════════════════════════╝""")
        elif cmd == 'reset':
            self.machine.reset()
            if self._hamza:
                self._hamza = Hamza()
            if self._zafar:
                self._zafar = Zafar()
            print("  ✅ Mashina qayta ishga tushirildi.")
        else:
            resp = self.machine.brain_chat(line)
            print(f"  🧠 {resp}")

    # ── Hamza tili metodlari ──────────────────────────────────────

    def _hamza_run(self, args):
        """hamza \"kod\" yoki hamza fayl.hz"""
        if not HAMZA_BOR:
            print("  ❌ Hamza tili yuklanmagan (hamza/hamza.py kerak)")
            return

        # Fayl yoki to'g'ridan kod?
        if args.endswith('.hz') and not args.startswith('"'):
            try:
                kod = open(args, encoding='utf-8').read()
            except FileNotFoundError:
                print(f"  ❌ Fayl topilmadi: {args}"); return
        else:
            # Qo'shtirnoqlarni olib tashlash
            kod = args.strip('"\'').replace('\\n', '\n')

        if not kod.strip():
            print("  hamza \"kod\"  yoki  hamza fayl.hz"); return

        print(f"  ⟳ Hamza → xASM → xCPU-1...")
        t0 = time.time()

        natija = self._hamza.run(kod, machine=self.machine)
        elapsed = time.time() - t0

        if not natija.get('muvaffaqiyat'):
            print(f"  ❌ Xato [{natija.get('bosqich','?')}]: {natija.get('xato','?')}")
            return

        self.last_result = natija
        chiqish = natija.get('chiqish', '')
        print(f"\n  ▶ Hamza dasturi")
        print(f"  {'─'*48}")
        if chiqish:
            print(f"  Chiqish     : {chiqish}")
        print(f"  Registrlar  : X0={natija['registrlar'][0]} X1={natija['registrlar'][1]} "
              f"X2={natija['registrlar'][2]}")
        print(f"  Buyruqlar   : {natija.get('buyruqlar', 0)}")
        print(f"  Baytlar     : {natija.get('baytlar', 0)}")
        print(f"  Vaqt        : {elapsed:.4f}s")
        holat_328 = "✅ To'xtadi" if natija.get('to_xtatildi') else "⏸ Limit"
        print(f"  Holat       : {holat_328}")
        print()

    def _hamza_tahlil(self, args):
        """Hamza kodi tokenlar + xASM ko'rsatish"""
        if not HAMZA_BOR:
            print("  ❌ Hamza tili yuklanmagan"); return
        kod = args.strip('"\'').replace('\\n', '\n')
        if not kod.strip():
            print("  hamza.tahlil \"kod\""); return
        print(self._hamza.tahlil(kod))

    def _hamza_demo(self):
        """Hamza namuna dasturlarini ko'rsatish"""
        if not HAMZA_BOR:
            print("  ❌ Hamza tili yuklanmagan"); return

        demolar = [
            ("Fibonacci", "son a = 0\nson b = 1\ntakror i = 0, 10:\n    son c = a + b\n    son a = b\n    son b = c\nchiqar b"),
            ("Faktorial", "son n = 7\nson f = 1\ntakror i = 1, 8:\n    son f = f * i\nchiqar f"),
            ("Juft sonlar", "son s = 0\ntakror i = 0, 11:\n    agar i % 2 == 0:\n        son s = s + i\nchiqar s"),
        ]

        print("\n  ═══ Hamza Tili — Namuna Dasturlar ═══")
        for nom, kod in demolar:
            print(f"\n  ▸ {nom}:")
            for satr in kod.split('\n'):
                print(f"    {satr}")
            natija = self._hamza.run(kod, machine=self.machine)
            if natija.get('muvaffaqiyat'):
                chiqish = natija.get('chiqish', '')
                regs = natija['registrlar']
                val = chiqish if chiqish else str(regs[0])
                print(f"    → Natija: {val}")
            else:
                print(f"    → Xato: {natija.get('xato','?')}")
        print()

    def _run_show(self, fn, label):
        try:
            t0 = time.time()
            result = fn()
            elapsed = time.time() - t0
            self.last_result = result
            out = result.get('output', '')
            print(f"\n  ▶ {label}")
            print(f"  {'─'*48}")
            if out: print(f"  Chiqish     : {out}")
            print(f"  Instruksiya : {result['instr']}")
            print(f"  Tezlik      : {result['mips']} MIPS")
            print(f"  Vaqt        : {elapsed:.4f}s")
            holat_379 = "✅ To'xtadi" if result['halted'] else "⏸ Limit"
            print(f"  Holat       : {holat_379}")
            ev = self.machine.brain_evaluate(result)
            print(f"  {ev.splitlines()[0]}")
            print()
        except Exception as e:
            print(f"  ❌ Xato: {e}")

    # ── Zafar tili metodlari ──────────────────────────────────────

    def _zafar_run(self, args):
        """zafar "kod" yoki zafar fayl.zf"""
        if not ZAFAR_BOR:
            print("  ❌ Zafar tili yuklanmagan (zafar/zafar.py kerak)")
            return
        if args.endswith('.zf') and not args.startswith('"'):
            try:
                kod = open(args, encoding='utf-8').read()
            except FileNotFoundError:
                print(f"  ❌ Fayl topilmadi: {args}"); return
        else:
            kod = args.strip('"\'').replace('\\n', '\n')
        if not kod.strip():
            print("  zafar \"kod\"  yoki  zafar fayl.zf"); return

        print("  ⟳ Zafar → xASM → xCPU-1...")
        t0 = time.time()
        natija = self._zafar.run(kod, machine=self.machine)
        elapsed = time.time() - t0

        if not natija.get('muvaffaqiyat'):
            print(f"  ❌ Xato [{natija.get('bosqich','?')}]: {natija.get('xato','?')}")
            return

        self.last_result = natija
        chiqish = natija.get('chiqish', '')
        print(f"\n  ▶ Zafar dasturi")
        print(f"  {'─'*48}")
        if chiqish:
            print(f"  Chiqish     : {chiqish}")
        regs = natija.get('registrlar', [0]*8)
        print(f"  Registrlar  : X0={regs[0]} X1={regs[1]} X2={regs[2]}")
        print(f"  Buyruqlar   : {natija.get('buyruqlar', 0)}")
        print(f"  Baytlar     : {natija.get('baytlar', 0)}")
        print(f"  Vaqt        : {elapsed:.4f}s")
        holat_423 = "✅ To'xtadi" if natija.get('to_xtatildi') else "⏸ Limit"
        print(f"  Holat       : {holat_423}")
        print()

    def _zafar_tahlil(self, args):
        """Zafar kodi tokenlar + xASM ko'rsatish"""
        if not ZAFAR_BOR:
            print("  ❌ Zafar tili yuklanmagan"); return
        kod = args.strip('"\'').replace('\\n', '\n')
        if not kod.strip():
            print("  zafar.tahlil \"kod\""); return
        print(self._zafar.tahlil(kod))

    def _zafar_demo(self):
        """Zafar namuna dasturlarini ko'rsatish"""
        if not ZAFAR_BOR:
            print("  ❌ Zafar tili yuklanmagan"); return
        demolar = [
            ("Fibonacci", "son a = 0\nson b = 1\ntakror i = 0, 10:\n    son c = a + b\n    son a = b\n    son b = c\nchiqar b"),
            ("Faktorial", "son n = 7\nson f = 1\ntakror i = 1, 8:\n    son f = f * i\nchiqar f"),
            ("Sonlar yig'indisi", "son s = 0\ntakror i = 1, 101:\n    son s = s + i\nchiqar s"),
        ]
        print("\n  ═══ Zafar Tili — Namuna Dasturlar ═══")
        for nom, kod in demolar:
            print(f"\n  ▸ {nom}:")
            for satr in kod.split('\n'):
                print(f"    {satr}")
            natija = self._zafar.run(kod, machine=self.machine)
            if natija.get('muvaffaqiyat'):
                chiqish = natija.get('chiqish', '')
                regs = natija.get('registrlar', [0]*8)
                val = chiqish if chiqish else str(regs[0])
                print(f"    → Natija: {val}")
            else:
                print(f"    → Xato: {natija.get('xato','?')}")
        print()
