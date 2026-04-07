"""
xOS ISA — O'z Instruction Set Architecture
============================================
Bu ARM emas. Bu SIZning tilingiz.

Arxitektura: xCPU-1 (32-bit, RISC-style)
  - 16 ta registr: X0–X15
  - X13 = Stack Pointer (SP)
  - X14 = Link Register (LR)
  - X15 = Program Counter (PC)
  - XFLAGS: N, Z, C, V, H (Halt)

Bytecode formati (32-bit):
  [31:26] OPCODE  (6 bit  → 64 ta instruksiya)
  [25:22] REG_A   (4 bit  → 16 registr)
  [21:18] REG_B   (4 bit  → 16 registr)
  [17:14] REG_C   (4 bit  → 16 registr)
  [13:0]  IMM14   (14 bit → -8192..8191 imzolangan)

Instruksiya guruhlari:
  0x00–0x0F  : ALU (arifmetik/mantiq)
  0x10–0x1F  : Xotira (load/store)
  0x20–0x2F  : Boshqaruv oqimi (branch/jump/call)
  0x30–0x3F  : Maxsus (I/O, OS, AI)
"""

# ═══════════════════════════════════════════════════════
# OPCODE JADVALI
# ═══════════════════════════════════════════════════════

class OP:
    # ── ALU ─────────────────────────────────────────────
    NOP   = 0x00   # Hech narsa qilma
    LOAD  = 0x01   # Xd = imm14  (immediate load)
    MOV   = 0x02   # Xd = Xs
    ADD   = 0x03   # Xd = Xa + Xb
    SUB   = 0x04   # Xd = Xa - Xb
    MUL   = 0x05   # Xd = Xa * Xb
    DIV   = 0x06   # Xd = Xa / Xb
    MOD   = 0x07   # Xd = Xa % Xb
    AND   = 0x08   # Xd = Xa & Xb
    OR    = 0x09   # Xd = Xa | Xb
    XOR   = 0x0A   # Xd = Xa ^ Xb
    NOT   = 0x0B   # Xd = ~Xa
    SHL   = 0x0C   # Xd = Xa << imm
    SHR   = 0x0D   # Xd = Xa >> imm
    CMP   = 0x0E   # flaglar = Xa - Xb (natija saqlanmaydi)
    ADDI  = 0x0F   # Xd = Xa + imm14

    # ── Xotira ──────────────────────────────────────────
    LDW   = 0x10   # Xd = mem[Xa + imm]   (32-bit load)
    STW   = 0x11   # mem[Xa + imm] = Xd   (32-bit store)
    LDB   = 0x12   # Xd = mem[Xa + imm]   (8-bit load)
    STB   = 0x13   # mem[Xa + imm] = Xd   (8-bit store)
    PUSH  = 0x14   # SP -= 4; mem[SP] = Xd
    POP   = 0x15   # Xd = mem[SP]; SP += 4
    LDHI  = 0x16   # Xd[31:16] = imm14 << 2  (yuqori 16 bit)

    # ── Boshqaruv ────────────────────────────────────────
    JMP   = 0x20   # PC = imm (mutlaq)
    JEQ   = 0x21   # if Z: PC += imm
    JNE   = 0x22   # if !Z: PC += imm
    JLT   = 0x23   # if N: PC += imm
    JGT   = 0x24   # if !N && !Z: PC += imm
    JLE   = 0x25   # if N || Z: PC += imm
    JGE   = 0x26   # if !N: PC += imm
    CALL  = 0x27   # LR = PC+4; PC = imm
    RET   = 0x28   # PC = LR
    LOOP  = 0x29   # Xd--; if Xd != 0: PC += imm
    JMPR  = 0x2A   # PC = Xa (registr orqali jump)
    CALLR = 0x2B   # LR = PC+4; PC = Xa

    # ── Maxsus ───────────────────────────────────────────
    PRINT = 0x30   # UART ga Xa ni chiqar (raqam)
    PUTC  = 0x31   # UART ga Xa ni chiqar (belgi)
    HALT  = 0x32   # Mashinani to'xtat
    SYSCALL = 0x33 # OS syscall: X0=raqam, X1..=argumentlar
    BRAIN = 0x34   # AI brain ga signal yubor: X0=tur, X1=qiymat
    YIELD = 0x35   # Scheduler ga nazoratni ber
    INT   = 0x36   # Interrupt chiqar
    IRET  = 0x37   # Interrupt dan qayt
    IN    = 0x38   # Xd = port[imm] (I/O o'qish)
    OUT   = 0x39   # port[imm] = Xa (I/O yozish)
    TIME  = 0x3A   # Xd = vaqt tsikli
    RAND  = 0x3B   # Xd = tasodifiy son
    CMPI  = 0x3C   # flaglar = Xa - imm14
    MOVI  = 0x3D   # Xd = imm14 (signed)
    LOADS = 0x3E   # Xd = STRING[Xa]  (string load)
    DEBUG = 0x3F   # Debug info chiqar

    # Opcode → nom xaritasi
    NAMES = {}

# Nom xaritasini to'ldir
for _k, _v in list(vars(OP).items()):
    if isinstance(_v, int) and not _k.startswith('_') and _k != 'NAMES':
        OP.NAMES[_v] = _k


# ═══════════════════════════════════════════════════════
# INSTRUKSIYA KODLASH / DEKODLASH
# ═══════════════════════════════════════════════════════

UINT32_MAX = 0xFFFF_FFFF
REG_COUNT  = 16

def encode(opcode: int, ra: int = 0, rb: int = 0, rc: int = 0, imm: int = 0) -> int:
    """
    32-bit instruksiya kodlash:
      [31:26] opcode (6)
      [25:22] ra     (4)
      [21:18] rb     (4)
      [17:14] rc     (4)
      [13:0]  imm14  (14, signed)
    """
    imm14 = imm & 0x3FFF
    word  = ((opcode & 0x3F) << 26 |
             (ra     & 0x0F) << 22 |
             (rb     & 0x0F) << 18 |
             (rc     & 0x0F) << 14 |
             (imm14  & 0x3FFF))
    return word & UINT32_MAX


def decode(word: int) -> dict:
    """32-bit → instruksiya maydonlari."""
    opcode = (word >> 26) & 0x3F
    ra     = (word >> 22) & 0x0F
    rb     = (word >> 18) & 0x0F
    rc     = (word >> 14) & 0x0F
    imm14  = word & 0x3FFF
    # signed 14-bit
    if imm14 & 0x2000:
        imm14 -= 0x4000
    return {
        'opcode': opcode,
        'ra': ra,
        'rb': rb,
        'rc': rc,
        'imm': imm14,
        'name': OP.NAMES.get(opcode, f'OP_{opcode:02X}'),
        'raw': word,
    }


def to_bytes(word: int) -> bytes:
    """32-bit int → 4 byte (little-endian)."""
    return word.to_bytes(4, 'little')


def from_bytes(data: bytes, offset: int = 0) -> int:
    """4 byte (little-endian) → 32-bit int."""
    return int.from_bytes(data[offset:offset+4], 'little')


def disassemble_one(word: int, addr: int = 0) -> str:
    """Bitta instruksiyani matn ko'rinishida chiqar."""
    d = decode(word)
    op   = d['name']
    ra   = f"X{d['ra']}"
    rb   = f"X{d['rb']}"
    rc   = f"X{d['rc']}"
    imm  = d['imm']

    # Formatlash
    opcode = d['opcode']
    if opcode == OP.NOP:
        return f"  {addr:08X}:  NOP"
    elif opcode == OP.LOAD:
        return f"  {addr:08X}:  LOAD  {ra}, #{imm}"
    elif opcode == OP.MOV:
        return f"  {addr:08X}:  MOV   {ra}, {rb}"
    elif opcode in (OP.ADD, OP.SUB, OP.MUL, OP.DIV, OP.MOD,
                    OP.AND, OP.OR,  OP.XOR):
        return f"  {addr:08X}:  {op:<5} {ra}, {rb}, {rc}"
    elif opcode == OP.NOT:
        return f"  {addr:08X}:  NOT   {ra}, {rb}"
    elif opcode in (OP.SHL, OP.SHR):
        return f"  {addr:08X}:  {op:<5} {ra}, {rb}, #{imm}"
    elif opcode == OP.CMP:
        return f"  {addr:08X}:  CMP   {ra}, {rb}"
    elif opcode == OP.CMPI:
        return f"  {addr:08X}:  CMPI  {ra}, #{imm}"
    elif opcode == OP.ADDI:
        return f"  {addr:08X}:  ADDI  {ra}, {rb}, #{imm}"
    elif opcode == OP.MOVI:
        return f"  {addr:08X}:  MOVI  {ra}, #{imm}"
    elif opcode == OP.LDHI:
        return f"  {addr:08X}:  LDHI  {ra}, #{imm}"
    elif opcode in (OP.LDW, OP.LDB):
        return f"  {addr:08X}:  {op:<5} {ra}, [{rb}, #{imm}]"
    elif opcode in (OP.STW, OP.STB):
        return f"  {addr:08X}:  {op:<5} {ra}, [{rb}, #{imm}]"
    elif opcode == OP.PUSH:
        return f"  {addr:08X}:  PUSH  {ra}"
    elif opcode == OP.POP:
        return f"  {addr:08X}:  POP   {ra}"
    elif opcode in (OP.JMP, OP.CALL):
        target = addr + 4 + imm * 4
        return f"  {addr:08X}:  {op:<5} 0x{target:08X}"
    elif opcode in (OP.JEQ, OP.JNE, OP.JLT, OP.JGT, OP.JLE, OP.JGE):
        target = addr + 4 + imm * 4
        return f"  {addr:08X}:  {op:<5} 0x{target:08X}"
    elif opcode == OP.LOOP:
        target = addr + 4 + imm * 4
        return f"  {addr:08X}:  LOOP  {ra}, 0x{target:08X}"
    elif opcode == OP.RET:
        return f"  {addr:08X}:  RET"
    elif opcode == OP.JMPR:
        return f"  {addr:08X}:  JMPR  {ra}"
    elif opcode == OP.CALLR:
        return f"  {addr:08X}:  CALLR {ra}"
    elif opcode == OP.PRINT:
        return f"  {addr:08X}:  PRINT {ra}"
    elif opcode == OP.PUTC:
        return f"  {addr:08X}:  PUTC  {ra}"
    elif opcode == OP.HALT:
        return f"  {addr:08X}:  HALT"
    elif opcode == OP.SYSCALL:
        return f"  {addr:08X}:  SYSCALL #{imm}"
    elif opcode == OP.BRAIN:
        return f"  {addr:08X}:  BRAIN {ra}, {rb}"
    elif opcode == OP.IN:
        return f"  {addr:08X}:  IN    {ra}, #{imm}"
    elif opcode == OP.OUT:
        return f"  {addr:08X}:  OUT   #{imm}, {ra}"
    elif opcode == OP.TIME:
        return f"  {addr:08X}:  TIME  {ra}"
    elif opcode == OP.RAND:
        return f"  {addr:08X}:  RAND  {ra}"
    elif opcode == OP.DEBUG:
        return f"  {addr:08X}:  DEBUG"
    elif opcode == OP.HALT:
        return f"  {addr:08X}:  HALT"
    else:
        return f"  {addr:08X}:  {op:<5} X{d['ra']}, X{d['rb']}, #{imm}"


def disassemble(data: bytes, base: int = 0x1000) -> str:
    """Butun binary ni disassemble qilish."""
    lines = ["xOS Disassembler — xCPU-1 ISA", "=" * 40]
    for i in range(0, len(data) - 3, 4):
        word = from_bytes(data, i)
        addr = base + i
        lines.append(disassemble_one(word, addr))
    return "\n".join(lines)
