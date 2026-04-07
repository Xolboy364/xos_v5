"""xOS Machine v3.2 — To'liq versiya"""
import os, sys, time
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from memory.memory import Memory
from cpu.cpu import CPU
from compiler.assembler import Assembler, AsmError
from brain.brain import Brain
from devices.devices import DeviceBus
from linker.linker import Linker, build_elf
from loader.loader import Loader
from core.isa import disassemble
RAM_START = 0x00020000


class _MachineShell:
    """Machine ichida shell buyruqlarini bajarish uchun minimal adapter."""
    def __init__(self, machine):
        self._m = machine

    def run(self, cmd):
        """Satrni buyruq sifatida bajaradi, natija satr qaytaradi."""
        parts = cmd.strip().split(None, 1)
        if not parts:
            return ''
        c   = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ''

        if c in ('quit', 'exit', 'q'):
            return 'Chiqish...'
        elif c == 'help':
            return ('Buyruqlar: exec, demo, demos, regs, mem, status, reset,\n'
                    'bstatus, rl, gen, hamza, zafar, devices, gpio, timer, chat')
        elif c == 'demos':
            return 'Demolar: ' + ', '.join(self._m.available_demos())
        elif c == 'demo':
            if not arg:
                return f"demo <nom>. Mavjud: {', '.join(self._m.available_demos())}"
            try:
                r = self._m.run_demo(arg)
                out = r.get('output', '')
                return (f"✅ demo '{arg}'\n"
                        f"Chiqish: {out}\n"
                        f"Instr: {r['instr']}  MIPS: {r['mips']}  "
                        f"{'Halted ✅' if r['halted'] else 'Limit ⏸'}")
            except ValueError as e:
                return f"❌ {e}"
        elif c == 'exec':
            if not arg:
                return 'exec "KOD"'
            try:
                r = self._m.run_source(arg.strip('"\'').replace('\\n', '\n'))
                out = r.get('output', '')
                return (f"✅ exec\nChiqish: {out}\n"
                        f"Instr: {r['instr']}  {'Halted ✅' if r['halted'] else 'Limit ⏸'}")
            except Exception as e:
                return f"❌ {e}"
        elif c == 'regs':
            return self._m.dump_regs()
        elif c == 'mem':
            try:
                addr = int(arg, 16) if arg else RAM_START
            except ValueError:
                addr = RAM_START
            return self._m.dump_mem(addr, 64)
        elif c == 'status':
            st  = self._m.status()
            cpu = st['cpu']; mem = st['memory']; brn = st['brain']
            return (f"CPU: {cpu['instr']} instr, {cpu['mips']} MIPS\n"
                    f"Xotira: {mem['total_mb']} MB\n"
                    f"Brain: {brn['patterns']} pattern, {brn['rules']} qoida")
        elif c == 'reset':
            self._m.reset()
            return '✅ Mashina qayta boshlandi.'
        elif c == 'bstatus':
            return self._m.brain_status()
        elif c == 'gen':
            return self._m.brain_generate(arg) if arg else 'gen <vazifa>'
        elif c == 'chat':
            return f"🧠 {self._m.brain_chat(arg)}" if arg else 'chat <xabar>'
        elif c == 'rl':
            if not self._m.brain.rl_available():
                return '❌ RL Engine yuklanmagan'
            if not arg or arg == 'status':
                return self._m.brain.rl_status()
            try:
                n = int(arg.split()[0])
            except ValueError:
                n = 5
            r = self._m.brain.rl_train(n)
            return (f"✅ RL {r['episodes']} ep | "
                    f"avg={r.get('avg_reward','?')} | "
                    f"success={r.get('success_rate','?')}%")
        elif c == 'devices':
            d = self._m.bus.summary()
            return (f"UART : tx={d['uart']['tx_len']} rx={d['uart']['rx_len']}\n"
                    f"Timer: val={d['timer0']['value']} fires={d['timer0']['fires']}\n"
                    f"GPIO : dir={d['gpio']['dir']} out={d['gpio']['out']}\n"
                    f"Display: {d['display']['size']} {d['display']['bpp']}bpp")
        elif c == 'gpio':
            p2 = arg.split()
            if len(p2) >= 2:
                self._m.gpio_set(int(p2[0]), bool(int(p2[1])))
                return f"GPIO pin {p2[0]} = {p2[1]}"
            return 'gpio <pin> <0|1>'
        elif c == 'timer':
            if arg:
                self._m.timer_start(int(arg))
                return f"Timer0 ishga tushdi: load={arg}"
            return 'timer <load_value>'
        else:
            # Brain suhbati
            return f"🧠 {self._m.brain_chat(cmd)}"


class Machine:
    def __init__(self, brain_file=None):
        self.mem = Memory(4*1024*1024)   # 4MB — Android optimized
        self.brain = Brain(machine=self)
        self.cpu = CPU(self.mem, brain=self.brain)
        self.bus = DeviceBus(self.mem)
        self.asm = Assembler()
        self.linker = Linker()
        self.loader = Loader(self.mem, self.cpu)
        self._output = []
        self._shell_obj = None
        def uart_out(ch): self._output.append(ch)
        self.cpu.set_output_callback(uart_out)
        self.bus.uart.set_output_callback(uart_out)
        self.bus.set_irq_callback(lambda irq: self.cpu.int_pending.append(irq))
        if brain_file: self.brain.load(brain_file)

    @property
    def memory(self):
        """mem uchun qo'shimcha nom (app.py compatibility)"""
        return self.mem

    @property
    def shell(self):
        """Shell adapter — app.py shell buyruqlarini qayta ishlatish uchun"""
        if self._shell_obj is None:
            self._shell_obj = _MachineShell(self)
        return self._shell_obj

    def compile(self, source): return self.asm.assemble(source, base=RAM_START)
    def compile_to_elf(self, source, output_path=None):
        code = self.compile(source); lnk = Linker(); lnk.add_code(code)
        for name, addr in self.asm.labels.items(): lnk.add_symbol(name.lower(), addr)
        elf = lnk.link()
        if output_path: lnk.save(output_path, elf)
        return elf
    def disassemble(self, data): return disassemble(data, RAM_START)
    def dump_elf(self, elf_data): return self.linker.dump(elf_data)
    def load_elf(self, elf_data): return self.loader.load(elf_data)
    def load_raw(self, code): return self.mem.load_ram(code, RAM_START)

    def run(self, max_cycles=10_000_000):
        self._output.clear(); start = time.time()
        for _ in range(max_cycles):
            self.bus.tick()
            if self.cpu.step(): break
        elapsed = time.time() - start
        stats = self.cpu.stats()
        stats.update({'halted': self.cpu.halted, 'time_sec': round(elapsed,4),
                      'output': "".join(self._output), 'devices': self.bus.summary()})
        self.brain.learn_from_run(stats)
        return stats

    def run_source(self, source, max_cycles=10_000_000):
        code = self.compile(source); self.reset(); self.load_raw(code)
        result = self.run(max_cycles); result['source'] = source; result['bytes'] = len(code)
        return result

    def run_elf(self, elf_data, max_cycles=10_000_000):
        self.load_elf(elf_data); self._output.clear(); return self.run(max_cycles)

    def reset(self, entry=RAM_START): self.cpu.reset(entry); self._output.clear()

    def brain_chat(self, msg): return self.brain.chat(msg)
    def brain_generate(self, task): return self.brain.generate(task)
    def brain_analyze(self, source): return self.brain.analyze(source)
    def brain_evaluate(self, stats): return self.brain.evaluate(stats)
    def brain_status(self): return self.brain.status_str()
    def brain_save(self, path): self.brain.save(path)
    def brain_load(self, path): self.brain.load(path)

    def run_demo(self, name):
        programs = self.brain.kb.programs
        if name not in programs:
            raise ValueError(f"Demo '{name}' topilmadi. Mavjud: {list(programs.keys())}")
        return self.run_source(programs[name])

    def available_demos(self): return list(self.brain.kb.programs.keys())

    def uart_send(self, text):
        for ch in text: self.bus.uart.feed_rx(ch)
    def gpio_set(self, pin, val): self.bus.gpio.set_pin(pin, val)
    def gpio_get(self, pin): return self.bus.gpio.get_pin(pin)
    def timer_start(self, load, periodic=True):
        self.bus.timer0.write_reg(0, load)
        self.bus.timer0.write_reg(8, 0x1 | 0x2 | (0x4 if periodic else 0))
    def display_set_pixel(self, x, y, color): self.bus.display.set_pixel(x, y, color)
    def display_clear(self, color=0): self.bus.display.clear(color)

    def dump_regs(self): return self.cpu.dump_regs()
    def dump_mem(self, addr=RAM_START, size=64): return self.mem.dump(addr, size)
    def status(self):
        return {'cpu': self.cpu.stats(), 'memory': self.mem.stats(),
                'brain': self.brain.kb.stats(), 'devices': self.bus.summary(),
                'output': "".join(self._output)}


# ══════════════════════════════════════════════════════════
# xOS v4.0 — Scheduler, xFS, MMU integratsiya
# ══════════════════════════════════════════════════════════

class MachineV4(Machine):
    """
    xOS v4.0 Machine — to'liq OS muhiti.
    Machine ustiga qo'shilgan:
      - Scheduler (multitasking)
      - xFS (fayl tizimi)
      - MMU (virtual memory)
      - To'liq syscall table
    """

    def __init__(self):
        super().__init__()
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        # v4.0 komponentlar
        from kernel.scheduler import Scheduler
        from fs.xfs import xFS
        from kernel.mmu import MMU

        self.scheduler = Scheduler(self)
        self.fs        = xFS(self.mem)
        self.mmu       = MMU(self.mem)

        # xFS formatla
        self.fs.format()

        # Syscall ni kengaytirish
        self._setup_v4_syscalls()

    def _setup_v4_syscalls(self):
        """v4.0 syscall handler o'rnatish."""
        original_syscall = self.cpu._syscall

        fs  = self.fs
        sch = self.scheduler
        cpu = self.cpu
        mem = self.mem

        def v4_syscall(num):
            # File syscalls
            if num in (3, 4, 5, 6, 7, 20, 21, 22):
                result = fs.handle_syscall(num, cpu, mem)
                cpu.regs[0] = result & 0xFFFFFFFF
                return

            # Process syscalls
            elif num == 9:   # fork
                child_pid = sch.syscall_fork()
                cpu.regs[0] = child_pid & 0xFFFFFFFF
                return

            elif num == 11:  # exit
                sch.syscall_exit(cpu.regs[1])
                return

            elif num == 12:  # wait
                result = sch.syscall_wait(cpu.regs[0])
                cpu.regs[0] = result & 0xFFFFFFFF
                return

            elif num == 13:  # getpid
                cpu.regs[0] = sch.syscall_getpid()
                return

            elif num == 14:  # sleep(ms)
                sch.syscall_sleep(cpu.regs[0])
                return

            elif num == 15:  # malloc
                addr = mem.alloc(cpu.regs[0])
                cpu.regs[0] = addr
                return

            elif num == 16:  # free
                mem.free(cpu.regs[0])
                cpu.regs[0] = 0
                return

            elif num == 17:  # time() → ms
                import time
                cpu.regs[0] = int(time.time() * 1000) & 0xFFFFFFFF
                return

            elif num == 18:  # yield
                sch.syscall_yield()
                return

            elif num == 19:  # kill(pid, signal)
                result = sch.syscall_kill(cpu.regs[0], cpu.regs[1])
                cpu.regs[0] = result & 0xFFFFFFFF
                return

            # Eski syscall lar
            else:
                original_syscall(num)

        self.cpu._syscall = v4_syscall

    # ── Scheduler API ─────────────────────────────────────

    def spawn(self, name: str, source: str, priority: int = 1):
        """xASM manbasidan yangi jarayon yaratish."""
        return self.scheduler.create_from_source(name, source, priority)

    def spawn_hamza(self, name: str, code: str, priority: int = 1):
        """Hamza tilidan yangi jarayon yaratish."""
        return self.scheduler.create_from_hamza(name, code, priority)

    def spawn_zafar(self, name: str, code: str, priority: int = 1):
        """Zafar tilidan yangi jarayon yaratish."""
        return self.scheduler.create_from_zafar(name, code, priority)

    def run_all(self, max_cycles: int = 2_000_000) -> dict:
        """Barcha jarayonlarni ishlatish."""
        return self.scheduler.run(max_cycles)

    def ps(self) -> str:
        """Jarayonlar ro'yxati."""
        return self.scheduler.ps()

    def kill(self, pid: int) -> int:
        """Jarayonni o'ldirish."""
        from kernel.scheduler import Signal
        return self.scheduler.syscall_kill(pid, Signal.SIGKILL)

    # ── xFS API ───────────────────────────────────────────

    def ls(self, path: str = '/') -> str:
        """Katalog ko'rsatish."""
        return self.fs.ls(path)

    def tree(self) -> str:
        """Fayl tizimi daraxti."""
        lines = ['📁 /']
        t = self.fs.tree('/')
        if t:
            lines.append(t)
        return '\n'.join(lines)

    def cat(self, path: str) -> str:
        """Fayl mazmunini ko'rsatish."""
        data = self.fs.read_file(path)
        if not data:
            return f"  '{path}' topilmadi yoki bo'sh"
        return data.decode('utf-8', errors='replace')

    def write_file(self, path: str, content: str) -> bool:
        """Faylga yozish."""
        n = self.fs.write_file(path, content.encode('utf-8'))
        return n >= 0

    def mkdir(self, path: str) -> bool:
        """Katalog yaratish."""
        return self.fs.mkdir(path) == 0

    def rm(self, path: str) -> bool:
        """Fayl o'chirish."""
        return self.fs.unlink(path) == 0

    def fs_status(self) -> str:
        """xFS holati."""
        return self.fs.status()

    # ── MMU API ───────────────────────────────────────────

    def mmu_status(self) -> str:
        """MMU holati."""
        s = self.mmu.stats()
        return (
            f"MMU: {'faol' if s['enabled'] else 'o\'chirilgan'}  |  "
            f"Jarayonlar: {s['processes']}  |  "
            f"Sahifalar: {s['total_pages']} "
            f"({s['total_mem_kb']} KB)  |  "
            f"Page faults: {s['total_faults']}"
        )

    # ── To'liq holat ──────────────────────────────────────

    def status_v4(self) -> str:
        """xOS v4.0 to'liq holat."""
        lines = [
            "╔══ xOS v4.0 Holat ═══════════════════════════╗",
            f"║  CPU  : {self.cpu.instr_count:,} buyruq, "
            f"{self.cpu.stats().get('mips',0)} MIPS",
            f"║  RAM  : {self.mem.stats()['total_mb']} MB",
            f"║  xFS  : {self.fs.status()}",
            f"║  Sched: {self.scheduler.stats()['active']} jarayon, "
            f"{self.scheduler.stats()['switches']} switch",
            f"║  MMU  : {self.mmu.stats()['total_pages']} sahifa",
            f"║  Brain: {self.brain.kb.stats()['patterns']} pattern",
            "╚═════════════════════════════════════════════╝",
        ]
        return '\n'.join(lines)
