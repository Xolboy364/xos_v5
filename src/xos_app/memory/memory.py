"""
xOS Memory — Virtual xotira tizimi
=====================================
Segmentlangan xotira modeli:
  0x00000000 – 0x00000FFF  : NULL/kafolatlangan (ruxsat yo'q)
  0x00001000 – 0x0001FFFF  : ROM/Bootloader
  0x00020000 – 0x00EFFFFF  : RAM (dastur + heap)
  0x00F00000 – 0x00FFFFFF  : Stack
  0xFF000000 – 0xFFFFFFFF  : I/O mapped
"""

import struct

NULL_END   = 0x00000FFF
ROM_START  = 0x00001000
ROM_END    = 0x0001FFFF
RAM_START  = 0x00020000
RAM_END    = 0x00EFFFFF
STACK_START= 0x00F00000
STACK_END  = 0x00FFFFFF
IO_START   = 0xFF000000

DEFAULT_SIZE = 4 * 1024 * 1024    # 4 MB — Android uchun optimallashtirilgan


class MemoryError(Exception): pass


class Memory:
    """
    xOS Virtual Xotira.
    Bytearray asosida, segment himoyasi bilan.
    """

    def __init__(self, size: int = DEFAULT_SIZE):
        self.size = size
        self._mem = bytearray(size)
        self._write_protect = set()   # himoyalangan sahifalar
        self._access_log = []         # brain o'rganadi
        self._alloc_ptr = RAM_START   # heap pointer
        self._alloc_map = {}          # addr → size

    # ── Asosiy o'qish/yozish ─────────────────────────────

    def _check(self, addr: int, size: int, write: bool = False):
        if addr < 0 or addr + size > self.size:
            raise MemoryError(f"Manzil chegaradan tashqari: 0x{addr:08X}")
        if addr <= NULL_END:
            raise MemoryError(f"NULL pointer dereference: 0x{addr:08X}")
        page = addr >> 12
        if write and page in self._write_protect:
            raise MemoryError(f"Himoyalangan xotiraga yozish: 0x{addr:08X}")

    def read8(self, addr: int) -> int:
        self._check(addr, 1)
        return self._mem[addr]

    def write8(self, addr: int, val: int):
        self._check(addr, 1, write=True)
        self._mem[addr] = val & 0xFF

    def read16(self, addr: int) -> int:
        self._check(addr, 2)
        return struct.unpack_from('<H', self._mem, addr)[0]

    def write16(self, addr: int, val: int):
        self._check(addr, 2, write=True)
        struct.pack_into('<H', self._mem, addr, val & 0xFFFF)

    def read32(self, addr: int) -> int:
        self._check(addr, 4)
        return struct.unpack_from('<I', self._mem, addr)[0]

    def write32(self, addr: int, val: int):
        self._check(addr, 4, write=True)
        struct.pack_into('<I', self._mem, addr, val & 0xFFFF_FFFF)

    def read_bytes(self, addr: int, count: int) -> bytes:
        self._check(addr, count)
        return bytes(self._mem[addr:addr+count])

    def write_bytes(self, addr: int, data: bytes):
        self._check(addr, len(data), write=True)
        self._mem[addr:addr+len(data)] = data

    def read_str(self, addr: int, max_len: int = 256) -> str:
        """Null-terminated string o'qish."""
        result = []
        for i in range(max_len):
            b = self.read8(addr + i)
            if b == 0:
                break
            result.append(chr(b))
        return "".join(result)

    def write_str(self, addr: int, s: str):
        """Null-terminated string yozish."""
        for i, ch in enumerate(s):
            self.write8(addr + i, ord(ch))
        self.write8(addr + len(s), 0)

    # ── Heap allokator ───────────────────────────────────

    def alloc(self, size: int) -> int:
        """Oddiy bump allokator."""
        size = (size + 3) & ~3   # 4-baytli hizalash
        addr = self._alloc_ptr
        if addr + size > RAM_END:
            return 0   # Xotira tugadi
        self._alloc_ptr += size
        self._alloc_map[addr] = size
        return addr

    def free(self, addr: int):
        """Hozircha stub — to'liq GC keyingi versiyada."""
        self._alloc_map.pop(addr, None)

    # ── ROM yuklash ──────────────────────────────────────

    def load_rom(self, data: bytes, addr: int = ROM_START):
        """ROM ga kod yuklash va himoyalash."""
        if addr + len(data) > self.size:
            raise MemoryError("ROM hajmi katta!")
        self._mem[addr:addr+len(data)] = data
        # ROM sahifalarini himoyalash
        for page in range(addr >> 12, ((addr + len(data) - 1) >> 12) + 1):
            self._write_protect.add(page)
        return addr

    def load_ram(self, data: bytes, addr: int = RAM_START) -> int:
        """RAM ga kod/ma'lumot yuklash."""
        if addr + len(data) > self.size:
            raise MemoryError("Hajm katta!")
        self._mem[addr:addr+len(data)] = data
        return addr

    # ── Dump / debug ─────────────────────────────────────

    def dump(self, addr: int, size: int = 64) -> str:
        lines = [f"  Xotira dump: 0x{addr:08X} – 0x{addr+size:08X}"]
        for i in range(0, size, 16):
            if addr + i >= self.size:
                break
            row_addr = addr + i
            chunk = self._mem[row_addr:row_addr+16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            asc_part = "".join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
            lines.append(f"  0x{row_addr:08X}:  {hex_part:<47}  {asc_part}")
        return "\n".join(lines)

    def stats(self) -> dict:
        used = self._alloc_ptr - RAM_START
        total = RAM_END - RAM_START
        return {
            'total_mb': round(self.size / 1024 / 1024, 1),
            'heap_used': used,
            'heap_free': total - used,
            'alloc_count': len(self._alloc_map),
            'protected_pages': len(self._write_protect),
        }

    def clear(self):
        self._mem = bytearray(self.size)
        self._write_protect.clear()
        self._alloc_ptr = RAM_START
        self._alloc_map.clear()
