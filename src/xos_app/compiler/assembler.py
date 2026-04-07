"""
xOS Assembler — xASM Tili
===========================
xCPU-1 uchun Assembly kompilyatori.

xASM sintaksisi:
  ; bu izoh
  .section text          ; kod bo'limi
  .section data          ; ma'lumot bo'limi
  .string "salom"        ; string konstantasi
  .word 42               ; 32-bit qiymat
  label:                 ; sarlavha
  LOAD X0, #100          ; instruksiya
  ADD  X1, X0, X2        ; registrlar
  JEQ  loop              ; sarlavhaga sakrash

O'zgaruvchilar:
  .equ BUFER_HAJMI, 256  ; doimiy

Makrolar:
  .macro push_all        ; barcha registrlarni saqlash
  .macro pop_all
"""

import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.isa import OP, encode, to_bytes, UINT32_MAX

RAM_START = 0x00020000


class AsmError(Exception):
    def __init__(self, msg, line=None):
        self.line = line
        super().__init__(f"Satr {line}: {msg}" if line else msg)


class Assembler:
    """
    xASM → xCPU-1 bytecode.
    Ikki o'tish:
      1. Label manzillarini yig'ish
      2. Instruksiyalarni kodlash
    """

    REG_MAP = {
        'X0':0,'X1':1,'X2':2,'X3':3,'X4':4,'X5':5,'X6':6,'X7':7,
        'X8':8,'X9':9,'X10':10,'X11':11,'X12':12,
        'SP':13,'X13':13,'LR':14,'X14':14,'PC':15,'X15':15,
    }

    def __init__(self):
        self.labels   = {}    # nom → adres
        self.equates  = {}    # nom → qiymat
        self.code     = []    # (adres, word) ro'yxati
        self.data_seg = []    # (adres, bytes) ro'yxati
        self.errors   = []
        self.base     = RAM_START

    # ── Asosiy kirish nuqtasi ─────────────────────────────

    def assemble(self, source: str, base: int = RAM_START) -> bytes:
        """xASM manba → bytes."""
        self.base = base
        self.labels.clear()
        self.equates.clear()
        self.code.clear()
        self.data_seg.clear()
        self.errors.clear()

        lines = self._preprocess(source)
        self._pass1(lines, base)    # labellarni yig'
        binary = self._pass2(lines, base)   # kodlash
        return binary

    # ── Oldindan tayyorlash ───────────────────────────────

    def _preprocess(self, source: str):
        """Izohlarni olib tashlash, bo'sh satrlarni tozalash."""
        result = []
        for i, raw in enumerate(source.splitlines(), 1):
            line = raw.split(';')[0].strip()
            if line:
                result.append((i, line))
        return result

    # ── 1-o'tish: labellar ───────────────────────────────

    def _pass1(self, lines, base):
        addr = base
        for lineno, line in lines:
            # Equ direktiva
            m = re.match(r'\.equ\s+(\w+)\s*,\s*(.+)', line, re.I)
            if m:
                self.equates[m.group(1).upper()] = self._eval_imm(m.group(2), lineno)
                continue
            # Label
            if line.endswith(':'):
                name = line[:-1].strip()
                self.labels[name.upper()] = addr
                continue
            # Label + instruksiya bitta satrda: "loop: ADD X0, X1, X2"
            m = re.match(r'(\w+):\s+(.+)', line)
            if m:
                self.labels[m.group(1).upper()] = addr
                line = m.group(2)
            # Direktiva — kod chiqarmaydi (faqat .word, .byte chiqaradi)
            if line.startswith('.'):
                parts = line.split(None, 1)
                d = parts[0].lower()
                if d == '.word':
                    addr += 4
                elif d == '.string':
                    s = self._parse_string(parts[1] if len(parts)>1 else '')
                    addr += len(s) + 1   # null terminator
                elif d == '.byte':
                    addr += 1
                elif d in ('.section', '.equ', '.macro', '.endmacro'):
                    pass
                continue
            # Instruksiya
            addr += 4

    # ── 2-o'tish: kodlash ────────────────────────────────

    def _pass2(self, lines, base) -> bytes:
        result = bytearray()
        addr   = base
        in_data_section = False

        for lineno, raw_line in lines:
            # Label + instruksiya
            m = re.match(r'(\w+):\s+(.+)', raw_line)
            if m:
                line = m.group(2).strip()
            else:
                line = raw_line

            # Label-only satr
            if line.endswith(':'):
                continue

            # Direktiva
            if line.startswith('.'):
                parts = line.split(None, 1)
                d = parts[0].lower()
                if d == '.section':
                    in_data_section = (parts[1].strip().lower() == 'data' if len(parts)>1 else False)
                elif d == '.word':
                    val = self._eval_imm(parts[1].strip(), lineno) if len(parts)>1 else 0
                    result += (val & UINT32_MAX).to_bytes(4, 'little')
                    addr += 4
                elif d == '.string':
                    s = self._parse_string(parts[1] if len(parts)>1 else '')
                    result += s.encode('utf-8') + b'\x00'
                    addr += len(s) + 1
                elif d == '.byte':
                    val = self._eval_imm(parts[1].strip(), lineno) if len(parts)>1 else 0
                    result += bytes([val & 0xFF])
                    addr += 1
                elif d == '.equ':
                    pass   # 1-o'tishda bajarilib bo'lgan
                continue

            # Instruksiya kodlash
            try:
                word = self._encode_instr(line, addr, lineno)
                result += to_bytes(word)
                addr += 4
            except AsmError:
                raise
            except Exception as e:
                raise AsmError(str(e), lineno)

        return bytes(result)

    # ── Instruksiya kodlash ───────────────────────────────

    def _encode_instr(self, line: str, addr: int, lineno: int) -> int:
        """Bitta instruksiya satrini 32-bit word ga aylantirish."""
        # Tokenizatsiya
        tokens = re.split(r'[\s,\[\]]+', line.strip())
        tokens = [t for t in tokens if t]
        if not tokens:
            return encode(OP.NOP)

        mnemonic = tokens[0].upper()
        args = tokens[1:]

        # ── ALU ──────────────────────────────────────────
        if mnemonic == 'NOP':
            return encode(OP.NOP)

        elif mnemonic == 'HALT':
            return encode(OP.HALT)

        elif mnemonic == 'RET':
            return encode(OP.RET)

        elif mnemonic == 'DEBUG':
            return encode(OP.DEBUG)

        elif mnemonic == 'YIELD':
            return encode(OP.YIELD)

        elif mnemonic in ('LOAD', 'MOVI'):
            # LOAD X0, #imm  yoki  LOAD X0, label
            ra = self._reg(args[0], lineno)
            imm = self._resolve_imm(args[1], addr, lineno)
            op = OP.LOAD if mnemonic == 'LOAD' else OP.MOVI
            return encode(op, ra=ra, imm=imm)

        elif mnemonic == 'LDHI':
            ra = self._reg(args[0], lineno)
            imm = self._resolve_imm(args[1], addr, lineno)
            return encode(OP.LDHI, ra=ra, imm=imm)

        elif mnemonic == 'MOV':
            ra = self._reg(args[0], lineno)
            rb = self._reg(args[1], lineno)
            return encode(OP.MOV, ra=ra, rb=rb)

        elif mnemonic == 'ADD':
            ra = self._reg(args[0], lineno)
            rb = self._reg(args[1], lineno)
            if args[2].startswith('#'):
                imm = self._resolve_imm(args[2], addr, lineno)
                return encode(OP.ADDI, ra=ra, rb=rb, imm=imm)
            rc = self._reg(args[2], lineno)
            return encode(OP.ADD, ra=ra, rb=rb, rc=rc)

        elif mnemonic == 'ADDI':
            ra = self._reg(args[0], lineno)
            rb = self._reg(args[1], lineno)
            imm = self._resolve_imm(args[2], addr, lineno)
            return encode(OP.ADDI, ra=ra, rb=rb, imm=imm)

        elif mnemonic == 'SUB':
            ra = self._reg(args[0], lineno)
            rb = self._reg(args[1], lineno)
            rc = self._reg(args[2], lineno)
            return encode(OP.SUB, ra=ra, rb=rb, rc=rc)

        elif mnemonic == 'MUL':
            ra,rb,rc = self._reg(args[0],lineno),self._reg(args[1],lineno),self._reg(args[2],lineno)
            return encode(OP.MUL, ra=ra, rb=rb, rc=rc)

        elif mnemonic == 'DIV':
            ra,rb,rc = self._reg(args[0],lineno),self._reg(args[1],lineno),self._reg(args[2],lineno)
            return encode(OP.DIV, ra=ra, rb=rb, rc=rc)

        elif mnemonic == 'MOD':
            ra,rb,rc = self._reg(args[0],lineno),self._reg(args[1],lineno),self._reg(args[2],lineno)
            return encode(OP.MOD, ra=ra, rb=rb, rc=rc)

        elif mnemonic == 'AND':
            ra,rb,rc = self._reg(args[0],lineno),self._reg(args[1],lineno),self._reg(args[2],lineno)
            return encode(OP.AND, ra=ra, rb=rb, rc=rc)

        elif mnemonic == 'OR':
            ra,rb,rc = self._reg(args[0],lineno),self._reg(args[1],lineno),self._reg(args[2],lineno)
            return encode(OP.OR, ra=ra, rb=rb, rc=rc)

        elif mnemonic == 'XOR':
            ra,rb,rc = self._reg(args[0],lineno),self._reg(args[1],lineno),self._reg(args[2],lineno)
            return encode(OP.XOR, ra=ra, rb=rb, rc=rc)

        elif mnemonic == 'NOT':
            ra,rb = self._reg(args[0],lineno),self._reg(args[1],lineno)
            return encode(OP.NOT, ra=ra, rb=rb)

        elif mnemonic == 'SHL':
            ra,rb = self._reg(args[0],lineno),self._reg(args[1],lineno)
            imm = self._resolve_imm(args[2], addr, lineno)
            return encode(OP.SHL, ra=ra, rb=rb, imm=imm)

        elif mnemonic == 'SHR':
            ra,rb = self._reg(args[0],lineno),self._reg(args[1],lineno)
            imm = self._resolve_imm(args[2], addr, lineno)
            return encode(OP.SHR, ra=ra, rb=rb, imm=imm)

        elif mnemonic == 'CMP':
            ra,rb = self._reg(args[0],lineno),self._reg(args[1],lineno)
            return encode(OP.CMP, ra=ra, rb=rb)

        elif mnemonic == 'CMPI':
            ra = self._reg(args[0],lineno)
            imm = self._resolve_imm(args[1], addr, lineno)
            return encode(OP.CMPI, ra=ra, imm=imm)

        # ── Xotira ───────────────────────────────────────
        elif mnemonic == 'LDW':
            ra = self._reg(args[0], lineno)
            rb = self._reg(args[1], lineno)
            imm = self._resolve_imm(args[2], addr, lineno) if len(args) > 2 else 0
            return encode(OP.LDW, ra=ra, rb=rb, imm=imm)

        elif mnemonic == 'STW':
            ra = self._reg(args[0], lineno)
            rb = self._reg(args[1], lineno)
            imm = self._resolve_imm(args[2], addr, lineno) if len(args) > 2 else 0
            return encode(OP.STW, ra=ra, rb=rb, imm=imm)

        elif mnemonic == 'LDB':
            ra = self._reg(args[0], lineno)
            rb = self._reg(args[1], lineno)
            imm = self._resolve_imm(args[2], addr, lineno) if len(args) > 2 else 0
            return encode(OP.LDB, ra=ra, rb=rb, imm=imm)

        elif mnemonic == 'STB':
            ra = self._reg(args[0], lineno)
            rb = self._reg(args[1], lineno)
            imm = self._resolve_imm(args[2], addr, lineno) if len(args) > 2 else 0
            return encode(OP.STB, ra=ra, rb=rb, imm=imm)

        elif mnemonic == 'PUSH':
            ra = self._reg(args[0], lineno)
            return encode(OP.PUSH, ra=ra)

        elif mnemonic == 'POP':
            ra = self._reg(args[0], lineno)
            return encode(OP.POP, ra=ra)

        # ── Boshqaruv ────────────────────────────────────
        elif mnemonic == 'JMP':
            target = self._resolve_label(args[0], addr, lineno)
            offset_jmp = (target - addr - 4) // 4; return encode(OP.JMP, imm=offset_jmp)

        elif mnemonic == 'JMPR':
            ra = self._reg(args[0], lineno)
            return encode(OP.JMPR, ra=ra)

        elif mnemonic in ('JEQ','JNE','JLT','JGT','JLE','JGE'):
            op_map = {'JEQ':OP.JEQ,'JNE':OP.JNE,'JLT':OP.JLT,
                      'JGT':OP.JGT,'JLE':OP.JLE,'JGE':OP.JGE}
            target = self._resolve_label(args[0], addr, lineno)
            offset = (target - addr - 4) // 4
            return encode(op_map[mnemonic], imm=offset)

        elif mnemonic == 'CALL':
            target = self._resolve_label(args[0], addr, lineno)
            offset_call = (target - addr - 4) // 4; return encode(OP.CALL, imm=offset_call)

        elif mnemonic == 'CALLR':
            ra = self._reg(args[0], lineno)
            return encode(OP.CALLR, ra=ra)

        elif mnemonic == 'LOOP':
            ra = self._reg(args[0], lineno)
            target = self._resolve_label(args[1], addr, lineno)
            offset = (target - addr - 4) // 4
            return encode(OP.LOOP, ra=ra, imm=offset)

        # ── I/O ──────────────────────────────────────────
        elif mnemonic == 'PRINT':
            ra = self._reg(args[0], lineno)
            return encode(OP.PRINT, ra=ra)

        elif mnemonic == 'PUTC':
            ra = self._reg(args[0], lineno)
            return encode(OP.PUTC, ra=ra)

        elif mnemonic == 'SYSCALL':
            imm = self._resolve_imm(args[0], addr, lineno) if args else 0
            return encode(OP.SYSCALL, imm=imm)

        elif mnemonic == 'BRAIN':
            ra = self._reg(args[0], lineno)
            rb = self._reg(args[1], lineno) if len(args)>1 else 0
            return encode(OP.BRAIN, ra=ra, rb=rb)

        elif mnemonic == 'TIME':
            ra = self._reg(args[0], lineno)
            return encode(OP.TIME, ra=ra)

        elif mnemonic == 'RAND':
            ra = self._reg(args[0], lineno)
            return encode(OP.RAND, ra=ra)

        elif mnemonic == 'IN':
            ra = self._reg(args[0], lineno)
            imm = self._resolve_imm(args[1], addr, lineno)
            return encode(OP.IN, ra=ra, imm=imm)

        elif mnemonic == 'OUT':
            imm = self._resolve_imm(args[0], addr, lineno)
            ra = self._reg(args[1], lineno)
            return encode(OP.OUT, ra=ra, imm=imm)

        elif mnemonic == 'INT':
            imm = self._resolve_imm(args[0], addr, lineno)
            return encode(OP.INT, imm=imm)

        elif mnemonic == 'IRET':
            return encode(OP.IRET)

        else:
            raise AsmError(f"Noma'lum mnemonik: '{mnemonic}'", lineno)

    # ── Yordamchi ─────────────────────────────────────────

    def _reg(self, s: str, lineno=None) -> int:
        s = s.upper().strip()
        if s in self.REG_MAP:
            return self.REG_MAP[s]
        raise AsmError(f"Noma'lum registr: '{s}'", lineno)

    def _resolve_imm(self, s: str, addr: int, lineno=None) -> int:
        s = s.strip()
        if s.startswith('#'):
            s = s[1:]
        return self._eval_imm(s, lineno)

    def _resolve_label(self, s: str, addr: int, lineno=None) -> int:
        """Label yoki immediate manzil."""
        s = s.strip()
        key = s.upper()
        if key in self.labels:
            return self.labels[key]
        if key in self.equates:
            return self.equates[key]
        if s.startswith('#'):
            return self._eval_imm(s[1:], lineno)
        try:
            return self._eval_imm(s, lineno)
        except:
            raise AsmError(f"Noma'lum label: '{s}'", lineno)

    def _eval_imm(self, s: str, lineno=None) -> int:
        s = s.strip()
        key = s.upper()
        if key in self.equates:
            return self.equates[key]
        if key in self.labels:
            return self.labels[key]
        try:
            if s.startswith('0x') or s.startswith('0X'):
                return int(s, 16)
            elif s.startswith('0b') or s.startswith('0B'):
                return int(s, 2)
            elif s.startswith("'") and s.endswith("'") and len(s) == 3:
                return ord(s[1])
            else:
                return int(s)
        except:
            raise AsmError(f"Imm qiymat xatosi: '{s}'", lineno)

    def _parse_string(self, s: str) -> str:
        s = s.strip()
        if (s.startswith('"') and s.endswith('"')) or \
           (s.startswith("'") and s.endswith("'")):
            s = s[1:-1]
        return s.replace('\\n', '\n').replace('\\t', '\t').replace('\\0', '\x00')
