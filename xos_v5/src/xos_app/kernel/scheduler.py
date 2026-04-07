"""
xOS v4.0 — Scheduler (Jarayonlar boshqaruvchisi)
==================================================
Round-robin multitasking scheduler.

Arxitektura:
  ┌─────────────────────────────────────────────┐
  │  Timer IRQ → Scheduler.tick()               │
  │  → Context switch (joriy PCB saqlash)        │
  │  → Keyingi READY jarayon tanlash            │
  │  → Context restore (yangi PCB yuklash)       │
  └─────────────────────────────────────────────┘

PCB (Process Control Block):
  - PID, holat, prioritet
  - Registrlar snapshot (16 ta)
  - Stack pointer, Program counter
  - Xotira chegaralari
  - Statistika (tsikllar, buyruqlar)

Jarayon holatlari:
  READY   → ishga tayyor, navbatda
  RUNNING → hozir ishlamoqda (faqat bitta)
  BLOCKED → kutmoqda (I/O, sleep, wait)
  ZOMBIE  → tugadi, parent kutmoqda
  DEAD    → o'chirildi

Syscall integratsiya:
  SYSCALL #9  → fork()
  SYSCALL #10 → exec()
  SYSCALL #11 → exit()
  SYSCALL #12 → wait()
  SYSCALL #13 → getpid()
  SYSCALL #14 → sleep()
  SYSCALL #18 → yield()
  SYSCALL #19 → kill()
"""

import time
from collections import deque

# ── Jarayon holatlari ──────────────────────────────────
class PState:
    READY   = 'READY'
    RUNNING = 'RUNNING'
    BLOCKED = 'BLOCKED'
    ZOMBIE  = 'ZOMBIE'
    DEAD    = 'DEAD'

# ── Signal raqamlari ───────────────────────────────────
class Signal:
    SIGKILL = 9
    SIGTERM = 15
    SIGSTOP = 19
    SIGCONT = 18

# Stack hajmi har jarayon uchun
PROCESS_STACK_SIZE = 32 * 1024   # 32 KB (Android optimized)
PROCESS_STACK_BASE = 0x00300000  # Stack zone (4MB ichida)
MAX_PROCESSES      = 16
TIME_SLICE         = 500          # Tsikl soni (context switch oralig'i)
MAX_FDS            = 16           # Har jarayon uchun max ochiq fayllar


class PCB:
    """
    Process Control Block — bitta jarayon ma'lumotlari.
    """

    _next_pid = 1

    def __init__(self, name: str, entry: int, parent_pid: int = 0,
                 priority: int = 1):
        self.pid        = PCB._next_pid
        PCB._next_pid  += 1

        self.name       = name
        self.state      = PState.READY
        self.priority   = priority       # 1 (past) – 5 (yuqori)
        self.parent_pid = parent_pid

        # CPU kontekst
        self.regs       = [0] * 16       # X0–X15 snapshot
        self.regs[15]   = entry          # PC = entry point
        self.flag_n     = False
        self.flag_z     = False
        self.flag_c     = False
        self.flag_v     = False
        self.halted     = False

        # Xotira
        self.stack_base = 0              # Scheduler tomonidan beriladi
        self.stack_size = PROCESS_STACK_SIZE
        self.heap_start = 0
        self.heap_end   = 0
        self.text_start = entry
        self.text_size  = 0

        # Fayl deskriptorlar (fd → xFS FileDescriptor)
        self.fds        = {}             # {fd: FileDescriptor}
        self.next_fd    = 3              # 0=stdin, 1=stdout, 2=stderr

        # Vaqt
        self.created_at = time.time()
        self.cpu_time   = 0.0
        self.cycles     = 0
        self.instr      = 0

        # Wait/sleep
        self.wait_pid   = None           # wait() uchun
        self.sleep_until= 0.0            # sleep() uchun
        self.exit_code  = 0

        # Chiqish bufer
        self.output     = []

    def save_context(self, cpu):
        """CPU holatini PCB ga saqlash (context switch)."""
        self.regs   = list(cpu.regs)
        self.flag_n = cpu.flag_n
        self.flag_z = cpu.flag_z
        self.flag_c = cpu.flag_c
        self.flag_v = cpu.flag_v
        self.halted = cpu.halted
        self.cycles += cpu.cycles
        self.instr  += cpu.instr_count

    def restore_context(self, cpu):
        """PCB dan CPU ga holatni tiklash (context switch)."""
        cpu.regs   = list(self.regs)
        cpu.flag_n = self.flag_n
        cpu.flag_z = self.flag_z
        cpu.flag_c = self.flag_c
        cpu.flag_v = self.flag_v
        cpu.halted = self.halted
        cpu.cycles = 0
        cpu.instr_count = 0
        cpu._uart_buf = []

    def open_fd(self, file_desc):
        """Yangi fayl deskriptor ochish."""
        fd = self.next_fd
        self.fds[fd] = file_desc
        self.next_fd += 1
        return fd

    def close_fd(self, fd):
        """Fayl deskriptor yopish."""
        return self.fds.pop(fd, None)

    def get_fd(self, fd):
        """Fayl deskriptor olish."""
        return self.fds.get(fd)

    def stats(self) -> dict:
        elapsed = time.time() - self.created_at
        return {
            'pid':      self.pid,
            'name':     self.name,
            'state':    self.state,
            'priority': self.priority,
            'cycles':   self.cycles,
            'instr':    self.instr,
            'cpu_sec':  round(elapsed, 3),
            'pc':       self.regs[15],
            'sp':       self.regs[13],
        }

    def __repr__(self):
        return f"<PCB pid={self.pid} '{self.name}' {self.state}>"


class Scheduler:
    """
    Round-robin scheduler.

    Ishlash tartibi:
      1. run_step() — joriy jarayonning bir tsiklini bajarish
      2. Har TIME_SLICE tsiklda → preempt() → context switch
      3. YIELD/INT/SYSCALL → ixtiyoriy context switch
      4. Timer IRQ → majburiy context switch
    """

    def __init__(self, machine):
        self.machine    = machine
        self.cpu        = machine.cpu
        self.mem        = machine.mem

        self.processes  = {}             # {pid: PCB}
        self.ready_q    = deque()        # READY jarayonlar navbati
        self.current    = None           # Joriy ishlaydigan PCB

        self._tick      = 0
        self._switches  = 0
        self._total_procs = 0

        # Idle jarayon (hech narsa bo'lmaganda)
        self._idle_cycles = 0

        # Xotira ajratish - instance variables
        self._stack_alloc = PROCESS_STACK_BASE
        self._text_alloc_ptr = 0x00020000   # RAM_START

    # ── Jarayon yaratish ──────────────────────────────────

    def create_process(self, name: str, code: bytes,
                       priority: int = 1,
                       parent_pid: int = 0) -> 'PCB':
        """
        Yangi jarayon yaratish:
          1. Kodni RAMga yuklash
          2. Stack ajratish
          3. PCB yaratish
          4. READY navbatiga qo'shish
        """
        if len(self.processes) >= MAX_PROCESSES:
            raise RuntimeError(f"Max jarayonlar soni {MAX_PROCESSES} ga yetdi")

        # Kodni RAMga yuklash (har jarayon uchun alohida joy)
        entry = self._alloc_text(len(code))
        self.mem.load_ram(code, entry)

        # Stack ajratish
        stack_top = self._alloc_stack()

        # PCB yaratish
        pcb = PCB(name, entry, parent_pid, priority)
        pcb.regs[13] = stack_top   # SP = stack top
        pcb.regs[15] = entry       # PC = entry
        pcb.stack_base = stack_top - PROCESS_STACK_SIZE
        pcb.text_start = entry
        pcb.text_size  = len(code)

        self.processes[pcb.pid] = pcb
        self.ready_q.append(pcb.pid)
        self._total_procs += 1

        return pcb

    def create_from_source(self, name: str, source: str,
                           priority: int = 1) -> 'PCB':
        """xASM manbasidan jarayon yaratish."""
        code = self.machine.compile(source)
        return self.create_process(name, code, priority)

    def create_from_hamza(self, name: str, hamza_code: str,
                          priority: int = 1) -> 'PCB':
        """Hamza tilidan jarayon yaratish."""
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from hamza.hamza import Hamza
        h = Hamza()
        xasm, err = h.compile(hamza_code)
        if err:
            raise ValueError(f"Hamza kompilatsiya xatosi: {err}")
        return self.create_from_source(name, xasm, priority)

    def create_from_zafar(self, name: str, zafar_code: str,
                          priority: int = 1) -> 'PCB':
        """Zafar tilidan jarayon yaratish."""
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from zafar.zafar import Zafar
        z = Zafar()
        xasm, err = z.compile(zafar_code)
        if err:
            raise ValueError(f"Zafar kompilatsiya xatosi: {err}")
        return self.create_from_source(name, xasm, priority)

    # ── Asosiy ishlatish ──────────────────────────────────

    def run(self, max_total_cycles: int = 5_000_000) -> dict:
        """
        Barcha jarayonlarni ishlatish.
        Har biri TIME_SLICE tsikl ishlaydi, keyin navbat.
        """
        total_cycles = 0
        start_time = time.time()
        self._final_outputs = {}   # Tugagan jarayonlar chiqishi

        # Birinchi jarayonni tanlash
        if not self._switch_next():
            return self._summary(0, time.time() - start_time)

        while total_cycles < max_total_cycles:
            if not self.current:
                if not self.ready_q:
                    break   # Hamma tugadi
                if not self._switch_next():
                    break

            pcb = self.current

            # TIME_SLICE tsikl ishlatish
            slice_cycles = 0
            output_buf = []

            # Jarayon chiqishini ushlash (closure bug fix: pcb=pcb)
            def _make_cb(current_pcb, buf):
                def capture_output(ch):
                    buf.append(ch)
                    current_pcb.output.append(ch)
                return capture_output

            self.cpu.set_output_callback(_make_cb(pcb, output_buf))
            self.cpu._uart_buf = []

            for _ in range(TIME_SLICE):
                if self.cpu.halted:
                    break
                try:
                    self.cpu.step()
                    slice_cycles += 1
                    total_cycles += 1

                    # SYSCALL tekshiruv
                    # (cpu.step() ichida syscall bajariladi)

                except Exception as e:
                    pcb.state = PState.DEAD
                    pcb.exit_code = -1
                    break

            self._tick += slice_cycles

            # HALT bo'ldimi?
            if self.cpu.halted:
                pcb.save_context(self.cpu)
                pcb.state = PState.ZOMBIE
                pcb.exit_code = 0
                # Chiqishni saqlash (remove_process dan oldin)
                self._final_outputs[pcb.pid] = {
                    'name':   pcb.name,
                    'output': ''.join(pcb.output),
                    'instr':  pcb.instr,
                }
                self.current = None
                self._cleanup_zombie(pcb)
            else:
                # Sleep tekshiruv
                if (pcb.state == PState.BLOCKED and
                        pcb.sleep_until > 0 and
                        time.time() >= pcb.sleep_until):
                    pcb.sleep_until = 0
                    pcb.state = PState.READY
                    self.ready_q.append(pcb.pid)

                # Context switch
                if pcb.state == PState.RUNNING:
                    pcb.save_context(self.cpu)
                    pcb.state = PState.READY
                    self.ready_q.append(pcb.pid)
                    self.current = None

                self._switch_next()

        elapsed = time.time() - start_time
        return self._summary(total_cycles, elapsed)

    def run_step(self) -> bool:
        """
        Bitta scheduler tsikli.
        True = hali jarayonlar bor.
        """
        if not self.current:
            if not self._switch_next():
                return False

        pcb = self.current

        # Bir instruksiya bajarish
        try:
            halted = self.cpu.step()
        except Exception:
            pcb.state = PState.DEAD
            self.current = None
            return bool(self.ready_q or self.processes)

        self._tick += 1

        # Preemption tekshiruv
        if self._tick % TIME_SLICE == 0:
            self._preempt()

        # HALT tekshiruv
        if halted:
            pcb.save_context(self.cpu)
            pcb.state = PState.ZOMBIE
            self.current = None
            self._cleanup_zombie(pcb)

        return bool(self.current or self.ready_q)

    # ── Syscall handlerlari ───────────────────────────────

    def syscall_fork(self) -> int:
        """
        fork() — joriy jarayonni nusxalash.
        Parent: child PID qaytaradi.
        Child:  0 qaytaradi.
        """
        parent = self.current
        if not parent:
            return -1

        # Yangi PCB yaratish
        child = PCB(f"{parent.name}_child",
                    parent.regs[15],
                    parent.pid)
        child.regs = list(parent.regs)
        child.flag_n = parent.flag_n
        child.flag_z = parent.flag_z
        child.regs[0] = 0   # Child: X0 = 0

        # Stack ajratish va nusxalash
        child_stack = self._alloc_stack()
        child.regs[13] = child_stack
        child.stack_base = child_stack - PROCESS_STACK_SIZE

        # Parent stack ni nusxalash
        try:
            stack_data = self.mem.read_bytes(
                parent.stack_base,
                PROCESS_STACK_SIZE
            )
            self.mem.write_bytes(child.stack_base, stack_data)
        except Exception:
            pass

        self.processes[child.pid] = child
        self.ready_q.append(child.pid)
        self._total_procs += 1

        return child.pid

    def syscall_exit(self, code: int):
        """exit(code) — joriy jarayonni tugatish."""
        pcb = self.current
        if not pcb:
            return
        pcb.exit_code = code
        pcb.state = PState.ZOMBIE
        self.cpu.halted = True
        self.current = None

        # Parent ni wake up qilish (agar wait() da bo'lsa)
        parent = self.processes.get(pcb.parent_pid)
        if parent and parent.state == PState.BLOCKED:
            if parent.wait_pid in (pcb.pid, -1):
                parent.regs[0] = pcb.pid
                parent.state = PState.READY
                self.ready_q.append(parent.pid)

        self._cleanup_zombie(pcb)

    def syscall_wait(self, target_pid: int) -> int:
        """
        wait(pid) — child jarayon tugashini kutish.
        pid=-1: istalgan child.
        """
        pcb = self.current
        if not pcb:
            return -1

        # Allaqachon zombie bo'lgan child bor?
        for pid, p in self.processes.items():
            if (p.state == PState.ZOMBIE and
                    p.parent_pid == pcb.pid and
                    (target_pid == -1 or pid == target_pid)):
                exit_code = p.exit_code
                self._remove_process(p)
                return pid

        # Kutish kerak
        pcb.state = PState.BLOCKED
        pcb.wait_pid = target_pid
        pcb.save_context(self.cpu)
        self.current = None
        self._switch_next()
        return 0

    def syscall_sleep(self, ms: int):
        """sleep(ms) — ms millisekund kutish."""
        pcb = self.current
        if not pcb:
            return
        pcb.sleep_until = time.time() + ms / 1000.0
        pcb.state = PState.BLOCKED
        pcb.save_context(self.cpu)
        self.current = None
        self._switch_next()

    def syscall_getpid(self) -> int:
        """getpid() — joriy jarayon PID."""
        return self.current.pid if self.current else 0

    def syscall_kill(self, pid: int, signal: int) -> int:
        """kill(pid, signal) — jarayonga signal yuborish."""
        target = self.processes.get(pid)
        if not target:
            return -1

        if signal == Signal.SIGKILL:
            target.state = PState.DEAD
            if self.current and self.current.pid == pid:
                self.cpu.halted = True
                self.current = None
                self._switch_next()
            else:
                self.ready_q = deque(
                    p for p in self.ready_q if p != pid
                )
            self._remove_process(target)

        elif signal == Signal.SIGSTOP:
            if target.state == PState.RUNNING:
                target.state = PState.BLOCKED
                if self.current and self.current.pid == pid:
                    target.save_context(self.cpu)
                    self.current = None
                    self._switch_next()

        elif signal == Signal.SIGCONT:
            if target.state == PState.BLOCKED:
                target.state = PState.READY
                self.ready_q.append(pid)

        return 0

    def syscall_yield(self):
        """yield() — ixtiyoriy ravishda CPU ni bo'shatish."""
        pcb = self.current
        if not pcb:
            return
        pcb.save_context(self.cpu)
        pcb.state = PState.READY
        self.ready_q.append(pcb.pid)
        self.current = None
        self._switch_next()

    # ── Context switch ────────────────────────────────────

    def _switch_next(self) -> bool:
        """
        Navbatdagi READY jarayonga o'tish.
        True = muvaffaqiyatli, False = hech narsa yo'q.
        """
        # Blocked jarayonlarni wake up qilish
        self._check_blocked()

        if not self.ready_q:
            return False

        # Prioritet asosida tanlash (oddiy: eng yuqori prioritet)
        # Hozircha FIFO (round-robin)
        next_pid = self.ready_q.popleft()
        next_pcb = self.processes.get(next_pid)

        if not next_pcb or next_pcb.state == PState.DEAD:
            return self._switch_next()

        next_pcb.state = PState.RUNNING
        next_pcb.restore_context(self.cpu)
        self.current = next_pcb
        self._switches += 1

        # Output callback (closure fix)
        def _make_out_cb(p):
            def out_cb(ch):
                p.output.append(ch)
            return out_cb
        self.cpu.set_output_callback(_make_out_cb(next_pcb))

        return True

    def _preempt(self):
        """TIME_SLICE tugadi — majburiy context switch."""
        if not self.current:
            return
        if not self.ready_q:
            return   # Faqat bitta jarayon — davom

        pcb = self.current
        pcb.save_context(self.cpu)
        pcb.state = PState.READY
        self.ready_q.append(pcb.pid)
        self.current = None
        self._switch_next()

    def _check_blocked(self):
        """Blocked jarayonlarni tekshirish (sleep timeout)."""
        now = time.time()
        for pid, pcb in self.processes.items():
            if (pcb.state == PState.BLOCKED and
                    pcb.sleep_until > 0 and
                    now >= pcb.sleep_until):
                pcb.sleep_until = 0
                pcb.state = PState.READY
                self.ready_q.append(pid)

    # ── Xotira ajratish ───────────────────────────────────

    # Text (kod) segmentlari uchun - instance da saqlanadi

    def _alloc_text(self, size: int) -> int:
        """Kod uchun RAM joy ajratish."""
        size  = (size + 63) & ~63   # 64-baytli hizalash
        addr  = self._text_alloc_ptr
        self._text_alloc_ptr += size + 256  # guard zone
        if self._text_alloc_ptr > 0x00280000:  # max 160KB
            raise MemoryError("Kod uchun RAM tugadi!")
        return addr

    def _alloc_stack(self) -> int:
        """Stack uchun joy ajratish (pastdan yuqoriga)."""
        # Har jarayon uchun alohida stack zone
        n = len(self.processes)
        base = PROCESS_STACK_BASE + n * PROCESS_STACK_SIZE
        top  = base + PROCESS_STACK_SIZE - 4
        if top > 0x003FFFFF:
            raise MemoryError("Stack uchun joy tugadi!")
        # Stack xotirani nol bilan to'ldirish
        try:
            self.mem.write_bytes(base, bytes(PROCESS_STACK_SIZE))
        except Exception:
            pass
        return top

    # ── Tozalash ──────────────────────────────────────────

    def _cleanup_zombie(self, pcb: 'PCB'):
        """Zombie jarayonni tekshirish — parent kutmasa, o'chirish."""
        parent = self.processes.get(pcb.parent_pid)
        if not parent:
            self._remove_process(pcb)

    def _remove_process(self, pcb: 'PCB'):
        """Jarayonni butunlay o'chirish."""
        self.processes.pop(pcb.pid, None)
        self.ready_q = deque(p for p in self.ready_q if p != pcb.pid)
        if self.current and self.current.pid == pcb.pid:
            self.current = None

    # ── Status ────────────────────────────────────────────

    def ps(self) -> str:
        """Process list — ps buyrug'i kabi."""
        if not self.processes:
            return "  Hech qanday jarayon yo'q."
        lines = [
            f"  {'PID':>4}  {'NOM':<16} {'HOLAT':<10} "
            f"{'PRIOR':>5}  {'TSIKL':>8}  {'PC':>10}",
            "  " + "─" * 62,
        ]
        cur_pid = self.current.pid if self.current else -1
        for pid, pcb in sorted(self.processes.items()):
            marker = "▶" if pid == cur_pid else " "
            lines.append(
                f"  {marker}{pid:>3}  {pcb.name:<16} {pcb.state:<10} "
                f"{pcb.priority:>5}  {pcb.cycles:>8,}  "
                f"0x{pcb.regs[15]:08X}"
            )
        lines.append(f"\n  Jami: {len(self.processes)} ta  |  "
                     f"Switch: {self._switches}  |  "
                     f"Tick: {self._tick:,}")
        return "\n".join(lines)

    def process_output(self, pid: int) -> str:
        """Jarayon chiqishini olish."""
        pcb = self.processes.get(pid)
        if not pcb:
            return ""
        return "".join(pcb.output)

    def all_outputs(self) -> dict:
        """Barcha jarayonlar chiqishi."""
        return {
            pid: "".join(pcb.output)
            for pid, pcb in self.processes.items()
        }

    def _summary(self, total_cycles: int, elapsed: float) -> dict:
        """Ishlatish xulosasi."""
        # Hali ishlayotgan jarayonlar chiqishi
        running_outputs = self.all_outputs()
        # Tugagan jarayonlar chiqishi
        final = getattr(self, '_final_outputs', {})
        # Barcha chiqishlarni birlashtirish
        all_out = {pid: info['output'] for pid, info in final.items()}
        all_out.update(running_outputs)
        all_procs = {pid: info for pid, info in final.items()}
        all_procs.update({pid: pcb.stats() for pid, pcb in self.processes.items()})
        return {
            'total_cycles':  total_cycles,
            'elapsed':       round(elapsed, 4),
            'mips':          round(total_cycles / max(elapsed, 1e-9) / 1e6, 4),
            'switches':      self._switches,
            'total_procs':   self._total_procs,
            'outputs':       all_out,
            'processes':     all_procs,
        }

    def stats(self) -> dict:
        return {
            'active':    len(self.processes),
            'ready':     len(self.ready_q),
            'switches':  self._switches,
            'tick':      self._tick,
            'current':   self.current.pid if self.current else None,
        }
