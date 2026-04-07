"""
xOS v4.2 — MMU (Memory Management Unit)
=========================================
Har jarayon uchun virtual xotira izolyatsiyasi.

Virtual xotira xaritasi (har jarayon uchun):
  0x00000000 – 0x0001FFFF  : Kod (text) — faqat o'qish/bajarish
  0x00020000 – 0x007FFFFF  : Heap — o'qish/yozish
  0x00800000 – 0x00EFFFFF  : xFS — kernel managed
  0x00F00000 – 0x00FFFFFF  : Stack — o'qish/yozish
  0xFF000000 – 0xFFFFFFFF  : I/O — kernel orqali

Sahifa jadvali (Page Table):
  Sahifa hajmi: 4096 byte (4 KB)
  Virtual → Physical tarjima
  Har sahifa uchun: R/W/X bitlar

Permission bitlar:
  bit 0 = READ   (o'qish)
  bit 1 = WRITE  (yozish)
  bit 2 = EXEC   (bajarish)
  bit 3 = USER   (user mode)
  bit 4 = KERNEL (kernel mode)

Page fault turlari:
  ACCESS_VIOLATION — ruxsat yo'q
  NOT_PRESENT      — sahifa yo'q (demand paging)
  STACK_OVERFLOW   — stack chegarasi oshdi
"""

import struct

PAGE_SIZE  = 4096
PAGE_MASK  = ~(PAGE_SIZE - 1)
PAGE_SHIFT = 12

# Permission bitlar
PERM_READ   = 0x01
PERM_WRITE  = 0x02
PERM_EXEC   = 0x04
PERM_USER   = 0x08
PERM_KERNEL = 0x10

# Standart kombinatsiyalar
PERM_RX  = PERM_READ | PERM_EXEC           # Kod
PERM_RW  = PERM_READ | PERM_WRITE          # Data/Stack
PERM_RWX = PERM_READ | PERM_WRITE | PERM_EXEC

# Page fault sabablari
class FaultReason:
    ACCESS_VIOLATION = 'ACCESS_VIOLATION'
    NOT_PRESENT      = 'NOT_PRESENT'
    STACK_OVERFLOW   = 'STACK_OVERFLOW'
    KERNEL_ACCESS    = 'KERNEL_ACCESS'


class PageFault(Exception):
    def __init__(self, vaddr: int, reason: str, pid: int = 0):
        self.vaddr  = vaddr
        self.reason = reason
        self.pid    = pid
        super().__init__(
            f"Page Fault PID={pid}: {reason} @ 0x{vaddr:08X}"
        )


class PageEntry:
    """Bitta sahifa jadvali yozuvi."""
    __slots__ = ('phys', 'perms', 'present', 'dirty', 'accessed')

    def __init__(self, phys: int, perms: int):
        self.phys     = phys      # Fizik manzil (page aligned)
        self.perms    = perms     # Permission bitlar
        self.present  = True
        self.dirty    = False
        self.accessed = False


class PageTable:
    """
    Bitta jarayon uchun sahifa jadvali.
    Virtual → Physical manzil tarjimasi.
    """

    def __init__(self, pid: int):
        self.pid     = pid
        self._pages  = {}   # {vpn: PageEntry}  vpn = virtual page number
        self._stats  = {'reads': 0, 'writes': 0, 'faults': 0}

    def map(self, vaddr: int, paddr: int, size: int, perms: int):
        """
        Virtual manzil oralig'ini fizik xotiraga ulash.
        vaddr, paddr — page-aligned bo'lishi kerak.
        """
        vaddr = vaddr & PAGE_MASK
        paddr = paddr & PAGE_MASK
        pages = (size + PAGE_SIZE - 1) // PAGE_SIZE

        for i in range(pages):
            vpn = (vaddr + i * PAGE_SIZE) >> PAGE_SHIFT
            ppn = paddr + i * PAGE_SIZE
            self._pages[vpn] = PageEntry(ppn, perms)

    def unmap(self, vaddr: int, size: int):
        """Virtual oraliqni xaritadan o'chirish."""
        pages = (size + PAGE_SIZE - 1) // PAGE_SIZE
        for i in range(pages):
            vpn = (vaddr >> PAGE_SHIFT) + i
            self._pages.pop(vpn, None)

    def translate(self, vaddr: int, write: bool = False,
                  exec_: bool = False) -> int:
        """
        Virtual → Fizik manzil tarjimasi.
        Xato bo'lsa PageFault ko'taradi.
        """
        vpn    = vaddr >> PAGE_SHIFT
        offset = vaddr & (PAGE_SIZE - 1)

        entry = self._pages.get(vpn)

        if entry is None:
            self._stats['faults'] += 1
            raise PageFault(vaddr, FaultReason.NOT_PRESENT, self.pid)

        # Ruxsat tekshiruv
        if write and not (entry.perms & PERM_WRITE):
            self._stats['faults'] += 1
            raise PageFault(vaddr, FaultReason.ACCESS_VIOLATION, self.pid)

        if exec_ and not (entry.perms & PERM_EXEC):
            self._stats['faults'] += 1
            raise PageFault(vaddr, FaultReason.ACCESS_VIOLATION, self.pid)

        # Statistika
        entry.accessed = True
        if write:
            entry.dirty = True
            self._stats['writes'] += 1
        else:
            self._stats['reads'] += 1

        return entry.phys + offset

    def is_mapped(self, vaddr: int) -> bool:
        """Manzil xaritadami?"""
        vpn = vaddr >> PAGE_SHIFT
        return vpn in self._pages

    def stats(self) -> dict:
        return {
            'pid':        self.pid,
            'pages':      len(self._pages),
            'mem_kb':     len(self._pages) * PAGE_SIZE // 1024,
            **self._stats
        }


class MMU:
    """
    Memory Management Unit — barcha jarayonlar uchun.
    Machine.mem bilan integratsiya:
      CPU → MMU.translate() → real Memory
    """

    def __init__(self, physical_memory):
        self.mem       = physical_memory
        self._tables   = {}    # {pid: PageTable}
        self._current  = None  # Joriy aktiv PageTable (PID)
        self._enabled  = False # MMU yoqilganmi?
        self._fault_handler = None

        # Kernel sahifalari (barcha jarayonlarga ko'rinadi)
        self._kernel_pages = {}

    def enable(self):
        """MMU ni yoqish."""
        self._enabled = True

    def disable(self):
        """MMU ni o'chirish (kernel mode)."""
        self._enabled = False

    def set_fault_handler(self, handler):
        """Page fault handler o'rnatish."""
        self._fault_handler = handler

    # ── Jarayon xotira maydonlari ─────────────────────────

    def create_table(self, pid: int) -> PageTable:
        """Yangi jarayon uchun sahifa jadvali yaratish."""
        table = PageTable(pid)
        self._tables[pid] = table

        # Kernel sahifalarini ulash (barcha jarayonlar uchun)
        for vpn, entry in self._kernel_pages.items():
            table._pages[vpn] = entry

        return table

    def remove_table(self, pid: int):
        """Jarayon tugagach sahifa jadvalini o'chirish."""
        self._tables.pop(pid, None)
        if self._current == pid:
            self._current = None

    def switch_to(self, pid: int):
        """Context switch: boshqa jarayon sahifa jadvaliga o'tish."""
        self._current = pid

    def setup_process_memory(self, pid: int, entry: int,
                              code_size: int, stack_top: int):
        """
        Jarayon uchun standart xotira xaritasi:
          Text  : entry → entry + code_size  (RX)
          Stack : stack_top - 64KB → stack_top  (RW)
          Heap  : entry + code_size + 4KB → ... (RW)
        """
        table = self._tables.get(pid)
        if not table:
            table = self.create_table(pid)

        # Text segment (kod)
        text_pages = (code_size + PAGE_SIZE - 1) // PAGE_SIZE
        for i in range(text_pages):
            vaddr = entry + i * PAGE_SIZE
            table.map(vaddr, vaddr, PAGE_SIZE, PERM_READ | PERM_EXEC)

        # Stack segment
        stack_size = 64 * 1024   # 64 KB
        stack_base = stack_top - stack_size
        table.map(stack_base, stack_base, stack_size,
                  PERM_READ | PERM_WRITE)

        # Heap (dastlab 64 KB)
        heap_start = entry + text_pages * PAGE_SIZE
        table.map(heap_start, heap_start, 64 * 1024,
                  PERM_READ | PERM_WRITE)

        return table

    def map_kernel(self, vaddr: int, size: int):
        """Kernel xotirasini barcha jarayonlarga ulash."""
        for i in range((size + PAGE_SIZE - 1) // PAGE_SIZE):
            vpn = (vaddr + i * PAGE_SIZE) >> PAGE_SHIFT
            entry = PageEntry(vaddr + i * PAGE_SIZE, PERM_READ | PERM_KERNEL)
            self._kernel_pages[vpn] = entry
            # Mavjud jadvallarga ham qo'shish
            for table in self._tables.values():
                table._pages[vpn] = entry

    # ── Xotira kirish ─────────────────────────────────────

    def read8(self, vaddr: int) -> int:
        """Virtual manzildan 1 byte o'qish."""
        if not self._enabled or not self._current:
            return self.mem.read8(vaddr)
        paddr = self._translate(vaddr, write=False)
        return self.mem.read8(paddr)

    def write8(self, vaddr: int, val: int):
        """Virtual manzilga 1 byte yozish."""
        if not self._enabled or not self._current:
            self.mem.write8(vaddr, val)
            return
        paddr = self._translate(vaddr, write=True)
        self.mem.write8(paddr, val)

    def read32(self, vaddr: int) -> int:
        """Virtual manzildan 4 byte o'qish."""
        if not self._enabled or not self._current:
            return self.mem.read32(vaddr)
        paddr = self._translate(vaddr, write=False)
        return self.mem.read32(paddr)

    def write32(self, vaddr: int, val: int):
        """Virtual manzilga 4 byte yozish."""
        if not self._enabled or not self._current:
            self.mem.write32(vaddr, val)
            return
        paddr = self._translate(vaddr, write=True)
        self.mem.write32(paddr, val)

    def _translate(self, vaddr: int, write: bool = False) -> int:
        """Joriy jarayon sahifa jadvali orqali tarjima."""
        table = self._tables.get(self._current)
        if not table:
            # Jadval yo'q — bevosita
            return vaddr

        try:
            return table.translate(vaddr, write=write)
        except PageFault as fault:
            if self._fault_handler:
                result = self._fault_handler(fault)
                if result is not None:
                    return result
            # Fault hal qilinmadi — jarayonni o'ldirish kerak
            raise

    # ── Holat ─────────────────────────────────────────────

    def ps_memory(self) -> str:
        """Barcha jarayonlar xotira sarfi."""
        if not self._tables:
            return "  MMU: hech qanday jarayon xotirasi yo'q"
        lines = [f"  {'PID':>4}  {'SAHIFALAR':>10}  {'XOTIRA':>10}  "
                 f"{'O\'QISH':>8}  {'YOZISH':>8}"]
        lines.append("  " + "─" * 50)
        for pid, table in sorted(self._tables.items()):
            s = table.stats()
            lines.append(
                f"  {pid:>4}  {s['pages']:>10}  {s['mem_kb']:>8} KB  "
                f"{s['reads']:>8}  {s['writes']:>8}"
            )
        return '\n'.join(lines)

    def stats(self) -> dict:
        total_pages = sum(len(t._pages) for t in self._tables.values())
        total_faults = sum(t._stats['faults'] for t in self._tables.values())
        return {
            'enabled':      self._enabled,
            'processes':    len(self._tables),
            'total_pages':  total_pages,
            'total_mem_kb': total_pages * PAGE_SIZE // 1024,
            'total_faults': total_faults,
            'current_pid':  self._current,
        }
