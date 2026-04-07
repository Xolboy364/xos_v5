"""
xOS CPU — xCPU-1 Virtual Machine
===================================
O'z ISA si bilan ishlaydigan virtual protsessor.
100% offline. Hech qanday API kerak emas.
"""

import time
import random
from collections import deque
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.isa import OP, decode, REG_COUNT

SP = 13; LR = 14; PC = 15
UINT32_MAX = 0xFFFF_FFFF

def to_signed32(v):
    v &= UINT32_MAX
    return v - 0x1_0000_0000 if v & 0x8000_0000 else v

def to_unsigned32(v):
    return v & UINT32_MAX

class CPUError(Exception): pass

class CPU:
    def __init__(self, memory, brain=None):
        self.mem   = memory
        self.brain = brain
        self.regs  = [0] * REG_COUNT
        self.regs[SP] = memory.size - 4
        self.flag_n = self.flag_z = self.flag_c = self.flag_v = False
        self.halted = False
        self.cycles = self.instr_count = 0
        self.start_time = time.time()
        self.ports = {}
        self._uart_buf = []
        self._input_queue = deque()
        self._output_cb = None
        self.int_enabled = True
        self.int_pending = []
        self.int_handlers = {}
        self.exec_log = deque(maxlen=500)
        self.opcode_counts = {}
        self.branch_taken = self.branch_total = 0
        self.mem_reads = self.mem_writes = 0

    @property
    def pc(self): return self.regs[PC]
    @pc.setter
    def pc(self, v): self.regs[PC] = to_unsigned32(v)

    @property
    def sp(self): return self.regs[SP]
    @sp.setter
    def sp(self, v): self.regs[SP] = to_unsigned32(v)

    @property
    def lr(self): return self.regs[LR]
    @lr.setter
    def lr(self, v): self.regs[LR] = to_unsigned32(v)

    def _flags_str(self):
        return f"{'N' if self.flag_n else '-'}{'Z' if self.flag_z else '-'}{'C' if self.flag_c else '-'}{'V' if self.flag_v else '-'}"

    def _set_flags_sub(self, a, b, result):
        r = to_unsigned32(result)
        self.flag_z = (r == 0)
        self.flag_n = bool(r & 0x8000_0000)
        self.flag_c = (to_unsigned32(a) >= to_unsigned32(b))
        sa,sb,sr = to_signed32(a),to_signed32(b),to_signed32(r)
        self.flag_v = ((sa<0) != (sb<0)) and ((sr<0) != (sa<0))

    def _set_flags_add(self, a, b, result):
        r = to_unsigned32(result)
        self.flag_z = (r == 0)
        self.flag_n = bool(r & 0x8000_0000)
        self.flag_c = (result > UINT32_MAX)
        sa,sb,sr = to_signed32(a),to_signed32(b),to_signed32(r)
        self.flag_v = ((sa>0)==(sb>0)) and ((sr>0)!=(sa>0))

    def _set_flags_logic(self, result):
        r = to_unsigned32(result)
        self.flag_z = (r == 0)
        self.flag_n = bool(r & 0x8000_0000)
        self.flag_c = self.flag_v = False

    def _r(self, idx): return to_unsigned32(self.regs[idx & 0xF])
    def _w(self, idx, val):
        if (idx & 0xF) != PC:
            self.regs[idx & 0xF] = to_unsigned32(val)

    def _branch(self, taken, offset):
        self.branch_total += 1
        if taken:
            self.branch_taken += 1
            self.pc = to_unsigned32(self.pc + offset * 4)

    def _uart_out(self, s):
        if self._output_cb: self._output_cb(s)

    def set_output_callback(self, cb): self._output_cb = cb
    def feed_input(self, text):
        for ch in text: self._input_queue.append(ch)

    def step(self):
        if self.halted: return True
        addr = self.pc
        try: word = self.mem.read32(addr)
        except Exception as e: raise CPUError(f"Fetch xatosi 0x{addr:08X}: {e}")
        d = decode(word)
        op,ra,rb,rc,imm = d['opcode'],d['ra'],d['rb'],d['rc'],d['imm']
        self.opcode_counts[op] = self.opcode_counts.get(op, 0) + 1
        self.instr_count += 1; self.cycles += 1
        self.exec_log.append({'pc':addr,'op':op,'ra':ra,'rb':rb,'rc':rc,'imm':imm})
        if self.brain: self.brain.signal(op, 0)
        self.pc = to_unsigned32(addr + 4)
        try: self._execute(op, ra, rb, rc, imm, addr)
        except CPUError: raise
        except Exception as e: raise CPUError(f"0x{addr:08X} ({d['name']}): {e}")
        return self.halted

    def _execute(self, op, ra, rb, rc, imm, addr):
        if   op == OP.NOP:  pass
        elif op == OP.LOAD: self._w(ra, imm & UINT32_MAX)
        elif op == OP.MOVI: self._w(ra, to_unsigned32(imm))
        elif op == OP.LDHI:
            cur = self._r(ra)
            self._w(ra, (cur & 0x0000_FFFF) | ((imm & 0x3FFF) << 16))
        elif op == OP.MOV:  self._w(ra, self._r(rb))
        elif op == OP.ADD:
            a,b = self._r(rb),self._r(rc)
            r = a+b; self._set_flags_add(a,b,r); self._w(ra,r)
        elif op == OP.ADDI:
            a = self._r(rb); r = a+imm; self._set_flags_add(a,imm,r); self._w(ra,r)
        elif op == OP.SUB:
            a,b = self._r(rb),self._r(rc)
            r = a-b; self._set_flags_sub(a,b,r); self._w(ra,r)
        elif op == OP.MUL:
            self._w(ra, to_signed32(self._r(rb)) * to_signed32(self._r(rc)))
        elif op == OP.DIV:
            b = to_signed32(self._r(rc))
            if b == 0: raise CPUError("Nolga bo'linish!")
            # C-style truncation division (not Python floor division)
            a = to_signed32(self._r(rb))
            self._w(ra, int(a / b))
        elif op == OP.MOD:
            b = to_signed32(self._r(rc))
            if b == 0: raise CPUError("Nolga bo'linish!")
            self._w(ra, to_signed32(self._r(rb)) % b)
        elif op == OP.AND:
            r = self._r(rb) & self._r(rc); self._set_flags_logic(r); self._w(ra,r)
        elif op == OP.OR:
            r = self._r(rb) | self._r(rc); self._set_flags_logic(r); self._w(ra,r)
        elif op == OP.XOR:
            r = self._r(rb) ^ self._r(rc); self._set_flags_logic(r); self._w(ra,r)
        elif op == OP.NOT:
            r = (~self._r(rb)) & UINT32_MAX; self._set_flags_logic(r); self._w(ra,r)
        elif op == OP.SHL:
            s = imm & 31; a = self._r(rb)
            self.flag_c = bool((a >> (32-s)) & 1) if s else False
            r = (a << s) & UINT32_MAX; self._set_flags_logic(r); self._w(ra,r)
        elif op == OP.SHR:
            s = imm & 31; a = self._r(rb)
            self.flag_c = bool((a >> (s-1)) & 1) if s else False
            r = a >> s; self._set_flags_logic(r); self._w(ra,r)
        elif op == OP.CMP:
            a,b = self._r(ra),self._r(rb); self._set_flags_sub(a,b,a-b)
        elif op == OP.CMPI:
            a = self._r(ra); self._set_flags_sub(a, to_unsigned32(imm), a-imm)
        elif op == OP.LDW:
            ma = to_unsigned32(self._r(rb)+imm); self.mem_reads+=1; self._w(ra, self.mem.read32(ma))
        elif op == OP.STW:
            ma = to_unsigned32(self._r(rb)+imm); self.mem_writes+=1; self.mem.write32(ma, self._r(ra))
        elif op == OP.LDB:
            ma = to_unsigned32(self._r(rb)+imm); self.mem_reads+=1; self._w(ra, self.mem.read8(ma))
        elif op == OP.STB:
            ma = to_unsigned32(self._r(rb)+imm); self.mem_writes+=1; self.mem.write8(ma, self._r(ra)&0xFF)
        elif op == OP.PUSH:
            self.sp = to_unsigned32(self.sp-4); self.mem.write32(self.sp, self._r(ra))
        elif op == OP.POP:
            self._w(ra, self.mem.read32(self.sp)); self.sp = to_unsigned32(self.sp+4)
        elif op == OP.JMP:  self.pc = to_unsigned32(addr + 4 + imm * 4)
        elif op == OP.JMPR: self.pc = self._r(ra)
        elif op == OP.JEQ:  self._branch(self.flag_z, imm)
        elif op == OP.JNE:  self._branch(not self.flag_z, imm)
        elif op == OP.JLT:  self._branch(self.flag_n != self.flag_v, imm)
        elif op == OP.JGT:  self._branch(not self.flag_z and self.flag_n == self.flag_v, imm)
        elif op == OP.JLE:  self._branch(self.flag_z or self.flag_n != self.flag_v, imm)
        elif op == OP.JGE:  self._branch(self.flag_n == self.flag_v, imm)
        elif op == OP.CALL:
            self.lr = self.pc; self.pc = to_unsigned32(addr + 4 + imm * 4)
        elif op == OP.CALLR:
            self.lr = self.pc; self.pc = self._r(ra)
        elif op == OP.RET:  self.pc = self.lr
        elif op == OP.LOOP:
            v = to_unsigned32(self._r(ra)-1); self._w(ra,v); self._branch(v!=0, imm)
        elif op == OP.PRINT:
            s = str(to_signed32(self._r(ra))); self._uart_buf.append(s); self._uart_out(s)
        elif op == OP.PUTC:
            ch = chr(self._r(ra) & 0xFF); self._uart_buf.append(ch); self._uart_out(ch)
        elif op == OP.HALT: self.halted = True
        elif op == OP.SYSCALL: self._syscall(imm)
        elif op == OP.BRAIN:
            if self.brain: self.brain.signal(self._r(ra), self._r(rb))
        elif op == OP.TIME:
            self._w(ra, int((time.time()-self.start_time)*1000) & UINT32_MAX)
        elif op == OP.RAND: self._w(ra, random.randint(0, UINT32_MAX))
        elif op == OP.IN:   self._w(ra, self.ports.get(imm, 0))
        elif op == OP.OUT:  self.ports[imm] = self._r(ra)
        elif op == OP.DEBUG: print(self.dump_regs())
        elif op == OP.YIELD: pass
        else: raise CPUError(f"Noma'lum opcode: 0x{op:02X}")

    def _syscall(self, num):
        if   num == 0: self.halted = True
        elif num == 1: self._uart_out(str(to_signed32(self.regs[0])))
        elif num == 2:
            self.regs[0] = ord(self._input_queue.popleft()) if self._input_queue else 0
        elif num == 8:
            if self.brain:
                self.regs[0] = self.brain.syscall(self.regs[0], self.regs[1]) & UINT32_MAX

    def dump_regs(self):
        names = ['X0','X1','X2','X3','X4','X5','X6','X7',
                 'X8','X9','X10','X11','X12','SP','LR','PC']
        lines = ["═"*52, "  xCPU-1 Registrlar", "═"*52]
        for i in range(0, 16, 2):
            lines.append(f"  {names[i]:6}= 0x{self.regs[i]:08X}  ({to_signed32(self.regs[i]):11d})    "
                        f"{names[i+1]:6}= 0x{self.regs[i+1]:08X}  ({to_signed32(self.regs[i+1]):11d})")
        elapsed = time.time() - self.start_time
        mips = round(self.instr_count / max(elapsed, 1e-9) / 1e6, 4)
        lines.append(f"  Flaglar: {self._flags_str()}  |  Tsikl: {self.cycles}  |  {mips} MIPS")
        return "\n".join(lines)

    def stats(self):
        elapsed = time.time() - self.start_time
        return {
            'cycles': self.cycles, 'instr': self.instr_count,
            'mips': round(self.instr_count / max(elapsed,1e-9) / 1e6, 4),
            'mem_reads': self.mem_reads, 'mem_writes': self.mem_writes,
            'branch_acc': round(self.branch_taken/max(self.branch_total,1)*100, 1),
            'top_opcodes': sorted(self.opcode_counts.items(), key=lambda x:-x[1])[:5],
        }

    def reset(self, entry=0x00020000):  # RAM_START default
        self.regs = [0]*REG_COUNT; self.regs[SP] = self.mem.size-4
        self.pc = entry; self.halted = False
        self.flag_n=self.flag_z=self.flag_c=self.flag_v = False
        self.cycles = self.instr_count = 0
        self._uart_buf = []; self.start_time = time.time()

    def run(self, max_cycles=10_000_000):
        for _ in range(max_cycles):
            if self.step(): return True
        return False
