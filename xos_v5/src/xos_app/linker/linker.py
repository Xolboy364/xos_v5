"""
xOS Linker — xELF Binary Format
==================================
xCPU-1 uchun o'z ELF-ga o'xshash binary format.

xELF Format:
  [0x00] Magic:    "xELF" (4 bytes)
  [0x04] Version:  1 (4 bytes)
  [0x08] Arch:     1 = xCPU-1 (4 bytes)
  [0x0C] Entry:    kirish manzili (4 bytes)
  [0x10] Flags:    bayroqlar (4 bytes)
  [0x14] Sec_count:bo'limlar soni (4 bytes)
  [0x18] Sec_off:  bo'limlar jadvali ofset (4 bytes)
  [0x1C] Reserved: (4 bytes)
  [0x20] Section headers jadvali
  [?]    Section ma'lumotlari

Section header (32 bytes):
  [0]  name_off:  Nom ofset (string table da)
  [4]  type:      0=null, 1=text, 2=data, 3=bss, 4=symtab, 5=strtab, 6=reloc
  [8]  flags:     bit0=ALLOC, bit1=EXEC, bit2=WRITE
  [12] addr:      virtual manzil
  [16] offset:    fayldagi ofset
  [20] size:      hajm
  [24] link:      bog'langan bo'lim indeksi
  [28] info:      qo'shimcha info

Symbol table entry (16 bytes):
  [0]  name_off   (4)
  [4]  value      (4) — manzil
  [8]  size       (4)
  [12] type_bind  (1+1)
  [13] reserved   (2)
"""

import struct

MAGIC   = b'xELF'
VERSION = 1
ARCH    = 1   # xCPU-1

# Section turlari
SHT_NULL   = 0
SHT_TEXT   = 1
SHT_DATA   = 2
SHT_BSS    = 3
SHT_SYMTAB = 4
SHT_STRTAB = 5
SHT_RELOC  = 6
SHT_RODATA = 7

# Section bayroqlari
SHF_ALLOC  = 0x1
SHF_EXEC   = 0x2
SHF_WRITE  = 0x4

# Symbol turlari
STT_NOTYPE = 0
STT_FUNC   = 1
STT_OBJECT = 2
STT_SECTION= 3

# Symbol ko'rinishi
STB_LOCAL  = 0
STB_GLOBAL = 1

# Manzillar
TEXT_ADDR  = 0x00020000
DATA_ADDR  = 0x00080000
BSS_ADDR   = 0x000C0000

HEADER_SIZE = 0x20
SHDR_SIZE   = 32
SYM_SIZE    = 16


class LinkerError(Exception): pass


class Section:
    """ELF bo'limi."""

    def __init__(self, name: str, stype: int, flags: int, addr: int, data: bytes = b''):
        self.name  = name
        self.type  = stype
        self.flags = flags
        self.addr  = addr
        self.data  = data
        self.size  = len(data)
        self.link  = 0
        self.info  = 0

    def __repr__(self):
        return f"<Section '{self.name}' type={self.type} addr=0x{self.addr:08X} size={self.size}>"


class Symbol:
    """Symbol jadval yozuvi."""

    def __init__(self, name: str, value: int, size: int = 0,
                 sym_type: int = STT_NOTYPE, binding: int = STB_LOCAL):
        self.name    = name
        self.value   = value
        self.size    = size
        self.type    = sym_type
        self.binding = binding

    def __repr__(self):
        return f"<Symbol '{self.name}' @ 0x{self.value:08X}>"


class Linker:
    """
    xOS Linker — xASM bytecode → xELF binary.
    Ko'p bo'limli, symbol table, relocation.
    """

    def __init__(self):
        self.sections = []
        self.symbols  = {}   # nom → Symbol
        self._strtab  = bytearray(b'\x00')   # null string birinchi
        self._text    = b''
        self._data    = b''
        self._bss_size= 0
        self._entry   = TEXT_ADDR

    def add_code(self, code: bytes, name: str = '.text', addr: int = TEXT_ADDR):
        """Kod bo'limi qo'shish."""
        sec = Section(name, SHT_TEXT, SHF_ALLOC | SHF_EXEC, addr, code)
        self.sections.append(sec)
        self._text = code
        self._entry = addr
        # Global start symbol
        self.add_symbol('_start', addr, sym_type=STT_FUNC, binding=STB_GLOBAL)
        self.add_symbol('_end',   addr + len(code), binding=STB_GLOBAL)
        return sec

    def add_data(self, data: bytes, name: str = '.data', addr: int = DATA_ADDR):
        """Ma'lumot bo'limi qo'shish."""
        sec = Section(name, SHT_DATA, SHF_ALLOC | SHF_WRITE, addr, data)
        self.sections.append(sec)
        self._data = data
        self.add_symbol('_data_start', addr, binding=STB_GLOBAL)
        self.add_symbol('_data_end',   addr + len(data), binding=STB_GLOBAL)
        return sec

    def add_rodata(self, data: bytes, addr: int = None):
        """O'qiladigan ma'lumot bo'limi."""
        if addr is None:
            addr = DATA_ADDR + 0x10000
        sec = Section('.rodata', SHT_RODATA, SHF_ALLOC, addr, data)
        self.sections.append(sec)
        return sec

    def add_bss(self, size: int, addr: int = BSS_ADDR):
        """BSS bo'limi (nol bilan to'ldirilgan)."""
        sec = Section('.bss', SHT_BSS, SHF_ALLOC | SHF_WRITE, addr, b'')
        sec.size     = size
        self._bss_size = size
        self.sections.append(sec)
        self.add_symbol('_bss_start', addr, binding=STB_GLOBAL)
        self.add_symbol('_bss_end',   addr + size, binding=STB_GLOBAL)
        return sec

    def add_symbol(self, name: str, value: int, size: int = 0,
                   sym_type: int = STT_NOTYPE, binding: int = STB_LOCAL):
        """Symbol qo'shish."""
        sym = Symbol(name, value, size, sym_type, binding)
        self.symbols[name] = sym
        return sym

    # ── String table ─────────────────────────────────────

    def _add_string(self, s: str) -> int:
        """String table ga yozish, ofset qaytarish."""
        off = len(self._strtab)
        self._strtab += s.encode('utf-8') + b'\x00'
        return off

    # ── Symbol table binary ──────────────────────────────

    def _build_symtab(self) -> bytes:
        """Symbol table binary yaratish."""
        result = bytearray()
        # Null symbol birinchi
        result += struct.pack('<IIII', 0, 0, 0, 0)
        for sym in self.symbols.values():
            name_off = self._add_string(sym.name)
            type_bind = (sym.type & 0xF) | ((sym.binding & 0xF) << 4)
            result += struct.pack('<IIIHH',
                name_off, sym.value, sym.size,
                type_bind, 0)
        return bytes(result)

    # ── Header ───────────────────────────────────────────

    def _build_header(self, entry: int, sec_count: int, sec_off: int) -> bytes:
        return struct.pack('<4sIIIIII4s',
            MAGIC, VERSION, ARCH, entry,
            0,        # flags
            sec_count,
            sec_off,
            b'\x00'*4
        )

    # ── Section header ───────────────────────────────────

    def _build_shdr(self, name_off: int, sec: Section, file_off: int) -> bytes:
        return struct.pack('<IIIIIIII',
            name_off, sec.type, sec.flags,
            sec.addr, file_off, sec.size,
            sec.link, sec.info
        )

    # ── Link ─────────────────────────────────────────────

    def link(self) -> bytes:
        """Barcha bo'limlarni birlashtirib xELF yaratish."""
        if not self.sections:
            raise LinkerError("Hech qanday bo'lim yo'q!")

        # String table bo'limi
        sec_names = ['.shstrtab', '.symtab']
        for sec in self.sections:
            sec_names.append(sec.name)

        # Symbol table yaratish
        symtab_data = self._build_symtab()
        strtab_data = bytes(self._strtab)

        # Bo'limlar ro'yxati (meta bo'limlari bilan)
        all_sections = list(self.sections)

        # .symtab bo'limi
        symtab_sec = Section('.symtab', SHT_SYMTAB, 0, 0, symtab_data)
        symtab_sec.link = len(all_sections) + 1   # .strtab indeksi
        symtab_sec.info = len(self.symbols)
        all_sections.append(symtab_sec)

        # .strtab bo'limi
        strtab_sec = Section('.strtab', SHT_STRTAB, 0, 0, strtab_data)
        all_sections.append(strtab_sec)

        # .shstrtab bo'limi
        shstrtab = bytearray(b'\x00')
        name_offsets = []
        for sec in all_sections:
            off = len(shstrtab)
            name_offsets.append(off)
            shstrtab += sec.name.encode() + b'\x00'
        shstrtab_sec = Section('.shstrtab', SHT_STRTAB, 0, 0, bytes(shstrtab))
        all_sections.append(shstrtab_sec)
        name_offsets.append(len(shstrtab) - len(shstrtab_sec.data))

        # Joylashtirish
        header_sz = HEADER_SIZE
        shdr_table_sz = SHDR_SIZE * len(all_sections)

        # Ma'lumot offsetlari
        data_start = header_sz + shdr_table_sz
        offsets = []
        cur_off = data_start
        for sec in all_sections:
            offsets.append(cur_off if sec.data else 0)
            if sec.data:
                cur_off += len(sec.data)

        # Binary yig'ish
        shdr_off = header_sz
        header = self._build_header(self._entry, len(all_sections), shdr_off)

        shdrs = bytearray()
        for i, sec in enumerate(all_sections):
            noff = name_offsets[i] if i < len(name_offsets) else 0
            shdrs += self._build_shdr(noff, sec, offsets[i])

        data = bytearray()
        for sec in all_sections:
            if sec.data:
                data += sec.data

        return header + bytes(shdrs) + bytes(data)

    def save(self, path: str, binary: bytes = None):
        """xELF faylga saqlash."""
        if binary is None:
            binary = self.link()
        with open(path, 'wb') as f:
            f.write(binary)

    @staticmethod
    def load(path: str) -> bytes:
        """xELF faylni o'qish."""
        with open(path, 'rb') as f:
            return f.read()

    def dump(self, binary: bytes) -> str:
        """xELF ni matn ko'rinishida chiqarish."""
        if len(binary) < HEADER_SIZE:
            return "❌ Juda kichik fayl"

        magic, ver, arch, entry, flags, sec_cnt, sec_off, _ = \
            struct.unpack('<4sIIIIII4s', binary[:HEADER_SIZE])

        if magic != MAGIC:
            return f"❌ Noto'g'ri magic: {magic}"

        lines = [
            "╔══ xELF Header ═══════════════════════════════╗",
            f"║  Magic   : {magic.decode()}",
            f"║  Version : {ver}",
            f"║  Arch    : xCPU-{arch}",
            f"║  Entry   : 0x{entry:08X}",
            f"║  Sections: {sec_cnt}",
            f"║  Total   : {len(binary)} bytes",
            "╠══ Sections ══════════════════════════════════╣",
        ]

        for i in range(min(sec_cnt, 20)):
            off = sec_off + i * SHDR_SIZE
            if off + SHDR_SIZE > len(binary):
                break
            name_off, stype, sflags, addr, foff, size, link, info = \
                struct.unpack('<IIIIIIII', binary[off:off+SHDR_SIZE])

            type_names = {0:'NULL',1:'TEXT',2:'DATA',3:'BSS',
                         4:'SYMTAB',5:'STRTAB',6:'RELOC',7:'RODATA'}
            tname = type_names.get(stype, f'?{stype}')

            lines.append(f"║  [{i:2d}] {tname:8s}  addr=0x{addr:08X}  size={size:6d}  off={foff}")

        lines.append("╚══════════════════════════════════════════════╝")
        return "\n".join(lines)


def build_elf(code: bytes, data: bytes = b'', entry: int = TEXT_ADDR,
              symbols: dict = None) -> bytes:
    """Qulay funksiya: bytecode → xELF."""
    lnk = Linker()
    lnk.add_code(code, addr=entry)
    if data:
        lnk.add_data(data)
    if symbols:
        for name, addr in symbols.items():
            lnk.add_symbol(name, addr, binding=STB_GLOBAL)
    return lnk.link()
