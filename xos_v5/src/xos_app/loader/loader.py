"""
xOS Loader — xELF Yuklovchi
==============================
xELF binaryni xotiraga yuklaydi.
Segmentlarni to'g'ri joylashtirib, CPU ni sozlaydi.
"""

import struct
import os

MAGIC      = b'xELF'
HEADER_SIZE= 0x20
SHDR_SIZE  = 32

SHT_NULL   = 0
SHT_TEXT   = 1
SHT_DATA   = 2
SHT_BSS    = 3
SHT_SYMTAB = 4
SHT_STRTAB = 5
SHT_RELOC  = 6
SHT_RODATA = 7

TEXT_ADDR  = 0x00020000


class LoaderError(Exception): pass


class LoadedProgram:
    """Yuklangan dastur ma'lumotlari."""

    def __init__(self):
        self.entry       = TEXT_ADDR
        self.sections    = []
        self.symbols     = {}
        self.text_start  = 0
        self.text_size   = 0
        self.data_start  = 0
        self.data_size   = 0
        self.bss_start   = 0
        self.bss_size    = 0
        self.total_size  = 0

    def __repr__(self):
        return (f"<LoadedProgram entry=0x{self.entry:08X} "
                f"text={self.text_size}B data={self.data_size}B "
                f"bss={self.bss_size}B>")


class Loader:
    """
    xELF yuklovchi.
    Xotiraga to'g'ri yuklaydi, BSS ni nol bilan to'ldiradi,
    CPU ni entry pointga sozlaydi.
    """

    def __init__(self, memory, cpu=None):
        self.mem = memory
        self.cpu = cpu
        self._loaded = []

    def load(self, source, base: int = TEXT_ADDR) -> LoadedProgram:
        """
        Manba: fayl yo'li, bytes, yoki xELF bytes.
        Qaytaradi: LoadedProgram.
        """
        # Fayl yo'li
        if isinstance(source, str):
            if not os.path.exists(source):
                raise LoaderError(f"Fayl topilmadi: {source}")
            with open(source, 'rb') as f:
                data = f.read()
        elif isinstance(source, (bytes, bytearray)):
            data = bytes(source)
        else:
            raise LoaderError(f"Noto'g'ri manba turi: {type(source)}")

        # xELF format tekshirish
        if data[:4] == MAGIC:
            return self._load_xelf(data)
        else:
            # Oddiy bytecode (xELF emas)
            return self._load_raw(data, base)

    def _load_raw(self, code: bytes, base: int = TEXT_ADDR) -> LoadedProgram:
        """Oddiy bytecode ni xotiraga yuklash."""
        prog = LoadedProgram()
        prog.entry      = base
        prog.text_start = base
        prog.text_size  = len(code)
        prog.total_size = len(code)

        self.mem.load_ram(code, base)

        if self.cpu:
            self.cpu.reset(base)

        self._loaded.append(prog)
        return prog

    def _load_xelf(self, data: bytes) -> LoadedProgram:
        """xELF faylni tahlil qilib xotiraga yuklash."""
        if len(data) < HEADER_SIZE:
            raise LoaderError("xELF fayl juda kichik")

        # Header tahlil
        magic, ver, arch, entry, flags, sec_cnt, sec_off, _ = \
            struct.unpack('<4sIIIIII4s', data[:HEADER_SIZE])

        if magic != MAGIC:
            raise LoaderError(f"Noto'g'ri magic: {magic!r}")

        prog = LoadedProgram()
        prog.entry = entry

        # Bo'limlarni yuklash
        for i in range(sec_cnt):
            off = sec_off + i * SHDR_SIZE
            if off + SHDR_SIZE > len(data):
                break

            name_off, stype, sflags, addr, foff, size, link, info = \
                struct.unpack('<IIIIIIII', data[off:off+SHDR_SIZE])

            prog.sections.append({
                'type': stype, 'addr': addr,
                'offset': foff, 'size': size,
                'flags': sflags,
            })

            if stype == SHT_TEXT and size > 0 and foff + size <= len(data):
                section_data = data[foff:foff+size]
                self.mem.load_ram(section_data, addr)
                prog.text_start = addr
                prog.text_size  = size
                prog.total_size += size

            elif stype == SHT_DATA and size > 0 and foff + size <= len(data):
                section_data = data[foff:foff+size]
                self.mem.load_ram(section_data, addr)
                prog.data_start = addr
                prog.data_size  = size
                prog.total_size += size

            elif stype == SHT_RODATA and size > 0 and foff + size <= len(data):
                section_data = data[foff:foff+size]
                self.mem.load_ram(section_data, addr)
                prog.total_size += size

            elif stype == SHT_BSS and size > 0:
                # BSS ni nol bilan to'ldirish
                zeros = bytes(size)
                self.mem.load_ram(zeros, addr)
                prog.bss_start = addr
                prog.bss_size  = size
                prog.total_size += size

            elif stype == SHT_SYMTAB and foff + size <= len(data):
                # Symbol tableni tahlil qilish
                sym_data = data[foff:foff+size]
                self._parse_symbols(sym_data, prog, data, prog.sections)

        # CPU ni sozlash
        if self.cpu:
            self.cpu.reset(prog.entry)

        self._loaded.append(prog)
        return prog

    def _parse_symbols(self, sym_data: bytes, prog: LoadedProgram,
                       elf_data: bytes, sections: list):
        """Symbol jadvalini tahlil qilish."""
        # Har symbol 16 byte
        for i in range(0, len(sym_data), 16):
            if i + 16 > len(sym_data):
                break
            name_off, value, size, type_bind, _ = \
                struct.unpack('<IIIHH', sym_data[i:i+16])
            sym_type = type_bind & 0xF
            binding  = (type_bind >> 4) & 0xF
            if value:
                prog.symbols[name_off] = {
                    'value': value, 'size': size,
                    'type': sym_type, 'binding': binding
                }

    def dump_loaded(self) -> str:
        """Yuklangan dasturlar ro'yxati."""
        if not self._loaded:
            return "  Hech narsa yuklanmagan."
        lines = ["  Yuklangan dasturlar:"]
        for i, prog in enumerate(self._loaded):
            lines.append(f"  [{i}] entry=0x{prog.entry:08X} "
                        f"text={prog.text_size}B "
                        f"data={prog.data_size}B "
                        f"bss={prog.bss_size}B")
        return "\n".join(lines)

    def stats(self) -> dict:
        return {
            'loaded_count': len(self._loaded),
            'total_bytes': sum(p.total_size for p in self._loaded),
        }
