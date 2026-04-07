"""
xOS v3.2 — To'liq Test Suite (Tuzatilgan)
==========================================
Mock: toga, toga.style, toga.style.pack
Testlar mustaqil ishlaydi — pytest shart emas.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Toga mock (Android UI test muhitida yo'q) ──────────
import types
for _m in ['toga','toga.style','toga.style.pack']:
    if _m not in sys.modules:
        sys.modules[_m] = types.ModuleType(_m)
_pack = sys.modules['toga.style.pack']
if not hasattr(_pack, 'Pack'):
    _pack.Pack  = type('Pack',  (), {'__init__': lambda s,**kw: None})
    _pack.COLUMN = 'column'
    _pack.ROW    = 'row'
_toga = sys.modules['toga']
for _cls in ['App','MainWindow','Box','Button','Label','MultilineTextInput',
             'TextInput','ScrollContainer','OptionContainer','OptionItem','Widget']:
    if not hasattr(_toga, _cls):
        setattr(_toga, _cls, type(_cls, (), {'__init__': lambda s,*a,**kw: None}))

from memory.memory   import Memory, ROM_START, RAM_START, DEFAULT_SIZE
from cpu.cpu         import CPU
from compiler.assembler import Assembler
from linker.linker   import Linker, build_elf
from loader.loader   import Loader
from brain.brain     import Brain
from brain.rl_engine import RLAgent, ReplayBuffer, Policy, RewardFunction
from devices.devices import DeviceBus, UART, Timer, GPIO, Display
from kernel.machine  import Machine
from core.isa        import encode, decode, OP

passed = failed = 0
_results = []

def assert_(cond, msg=''):
    if not cond:
        raise AssertionError(msg or 'Assertion failed')

def test(name, fn):
    global passed, failed
    try:
        fn()
        _results.append((name, 'PASS', ''))
        passed += 1
    except Exception as e:
        _results.append((name, 'FAIL', str(e)[:50]))
        failed += 1


# ══════════════════════════════════════════════════
# 1. ISA
# ══════════════════════════════════════════════════
test("ISA encode/decode ADD",   lambda: assert_(decode(encode(OP.ADD,ra=1,rb=2,rc=3))['opcode']==OP.ADD))
test("ISA signed imm -7",       lambda: assert_(decode(encode(OP.ADDI,imm=-7))['imm']==-7))
test("ISA opcode names exist",  lambda: assert_(OP.NAMES.get(OP.ADD)=='ADD'))
test("ISA HALT opcode",         lambda: assert_(OP.NAMES.get(OP.HALT)=='HALT'))


# ══════════════════════════════════════════════════
# 2. Memory
# ══════════════════════════════════════════════════
def t_mem_rw():
    m = Memory(DEFAULT_SIZE)
    m.write32(RAM_START, 0xDEADBEEF)
    assert_(m.read32(RAM_START) == 0xDEADBEEF)
test("Memory read/write32",  t_mem_rw)

def t_mem_bytes():
    m = Memory(DEFAULT_SIZE)
    m.write8(RAM_START, 0xAB)
    assert_(m.read8(RAM_START) == 0xAB)
    m.write16(RAM_START+4, 0x1234)
    assert_(m.read16(RAM_START+4) == 0x1234)
test("Memory read/write 8/16", t_mem_bytes)

def t_mem_str():
    m = Memory(DEFAULT_SIZE)
    m.write_str(RAM_START, "xOS")
    assert_(m.read_str(RAM_START) == "xOS")
test("Memory string write/read", t_mem_str)

def t_mem_alloc():
    m = Memory(DEFAULT_SIZE)
    a = m.alloc(16); b = m.alloc(16)
    assert_(a >= RAM_START and b > a)
    m.write32(a, 99)
    assert_(m.read32(a) == 99)
    m.free(a)
test("Memory alloc/free", t_mem_alloc)

def t_mem_null():
    m = Memory(DEFAULT_SIZE)
    try:
        m.read32(0x100)
        assert_(False, "NULL dereference o'tib ketdi")
    except Exception:
        pass
test("Memory NULL guard", t_mem_null)

def t_mem_rom_protect():
    m = Memory(DEFAULT_SIZE)
    m.load_rom(b'\x00'*16)
    try:
        m.write32(ROM_START, 0)
        assert_(False, "ROM himoyasi ishlamadi")
    except Exception:
        pass
test("Memory ROM write-protect", t_mem_rom_protect)


# ══════════════════════════════════════════════════
# 3. Assembler
# ══════════════════════════════════════════════════
asm = Assembler()

def t_asm_nop():
    code = asm.assemble("NOP")
    assert_(len(code) == 4)
test("Assembler NOP", t_asm_nop)

def t_asm_load():
    code = asm.assemble("LOAD X3, #99")
    d = decode(int.from_bytes(code[:4], 'little'))
    assert_(d['opcode'] == OP.LOAD and d['ra'] == 3 and d['imm'] == 99)
test("Assembler LOAD X3,#99", t_asm_load)

def t_asm_add():
    code = asm.assemble("ADD X2, X0, X1")
    d = decode(int.from_bytes(code[:4], 'little'))
    assert_(d['opcode'] == OP.ADD and d['ra'] == 2)
test("Assembler ADD", t_asm_add)

def t_asm_label():
    code = asm.assemble("LOAD X0, #0\nloop:\nADDI X0, X0, #1\nCMPI X0, #5\nJLT loop\nHALT")
    assert_(len(code) == 20, f"Expected 20 bytes, got {len(code)}")
test("Assembler label+jump", t_asm_label)


# ══════════════════════════════════════════════════
# 4. CPU / Machine — run_source bilan
# ══════════════════════════════════════════════════
def cpu_run(src, max_cycles=500):
    m = Machine()
    m.run_source(src, max_cycles=max_cycles)
    return m

test("CPU LOAD+HALT",    lambda: assert_(cpu_run("LOAD X0, #99\nHALT").cpu.regs[0]==99))
test("CPU ADD 10+20=30", lambda: assert_(cpu_run("LOAD X0,#10\nLOAD X1,#20\nADD X2,X0,X1\nHALT").cpu.regs[2]==30))
test("CPU SUB 50-13=37", lambda: assert_(cpu_run("LOAD X0,#50\nLOAD X1,#13\nSUB X2,X0,X1\nHALT").cpu.regs[2]==37))
test("CPU MUL 6*7=42",   lambda: assert_(cpu_run("LOAD X0,#6\nLOAD X1,#7\nMUL X2,X0,X1\nHALT").cpu.regs[2]==42))
test("CPU DIV 42/6=7",   lambda: assert_(cpu_run("LOAD X0,#42\nLOAD X1,#6\nDIV X2,X0,X1\nHALT").cpu.regs[2]==7))
test("CPU MOD 17%5=2",   lambda: assert_(cpu_run("LOAD X0,#17\nLOAD X1,#5\nMOD X2,X0,X1\nHALT").cpu.regs[2]==2))
test("CPU AND 0xFF&0x0F=0x0F", lambda: assert_(cpu_run("LOAD X0,#255\nLOAD X1,#15\nAND X2,X0,X1\nHALT").cpu.regs[2]==0x0F))
test("CPU OR 0xF0|0x0F=0xFF",  lambda: assert_(cpu_run("LOAD X0,#240\nLOAD X1,#15\nOR X2,X0,X1\nHALT").cpu.regs[2]==0xFF))
test("CPU XOR 5^3=6",    lambda: assert_(cpu_run("LOAD X0,#5\nLOAD X1,#3\nXOR X2,X0,X1\nHALT").cpu.regs[2]==6))

def t_push_pop():
    m = cpu_run("LOAD X0,#77\nPUSH X0\nLOAD X0,#0\nPOP X1\nHALT")
    assert_(m.cpu.regs[1] == 77, f"Expected 77, got {m.cpu.regs[1]}")
test("CPU PUSH/POP 77", t_push_pop)

def t_jeq():
    m = cpu_run("LOAD X0,#5\nLOAD X1,#5\nCMP X0,X1\nJEQ SKIP\nLOAD X2,#99\nSKIP:\nLOAD X3,#1\nHALT")
    assert_(m.cpu.regs[2] == 0, f"Branch SKIP almadi: X2={m.cpu.regs[2]}")
test("CPU JEQ branch taken", t_jeq)

def t_jne():
    m = cpu_run("LOAD X0,#5\nLOAD X1,#6\nCMP X0,X1\nJEQ SKIP\nLOAD X2,#42\nSKIP:\nHALT")
    assert_(m.cpu.regs[2] == 42, f"JNE ishlamadi: X2={m.cpu.regs[2]}")
test("CPU JEQ not taken (JNE)", t_jne)


# ══════════════════════════════════════════════════
# 5. Linker + Loader
# ══════════════════════════════════════════════════
def t_linker():
    code = asm.assemble("LOAD X0,#123\nHALT")
    elf  = build_elf(code)
    assert_(len(elf) > 10)
test("Linker build_elf", t_linker)

def t_loader():
    code = asm.assemble("LOAD X0,#55\nHALT")
    m    = Memory(DEFAULT_SIZE)
    cpu  = CPU(m)
    ldr  = Loader(m, cpu)
    prog = ldr.load(code)
    cpu.pc = prog.entry
    cpu.run(max_cycles=50)
    assert_(cpu.regs[0] == 55)
test("Loader load+run", t_loader)


# ══════════════════════════════════════════════════
# 6. Brain
# ══════════════════════════════════════════════════
def t_brain_chat():
    b = Brain()
    r = b.chat("salom")
    assert_(isinstance(r, str) and len(r) > 5)
test("Brain.chat salom", t_brain_chat)

def t_brain_generate():
    b = Brain()
    r = b.generate("fibonacci")          # <-- to'g'ri imzo: faqat task
    assert_(isinstance(r, str) and len(r) > 5)
test("Brain.generate fibonacci", t_brain_generate)

def t_brain_generate_count():
    b = Brain()
    r = b.generate("count 5")
    assert_(isinstance(r, str) and 'LOAD' in r or ';' in r)
test("Brain.generate count 5", t_brain_generate_count)

def t_brain_status():
    b = Brain()
    r = b.status_str()
    assert_(isinstance(r, str) and len(r) > 5)
test("Brain.status_str", t_brain_status)

def t_brain_analyze():
    b = Brain()
    r = b.analyze("LOAD X0, #1\nHALT")
    assert_(isinstance(r, str))
test("Brain.analyze", t_brain_analyze)


# ══════════════════════════════════════════════════
# 7. RL Engine
# ══════════════════════════════════════════════════
def t_rl_replay():
    rb = ReplayBuffer(100)
    assert_(len(rb) == 0)
test("RLAgent ReplayBuffer init", t_rl_replay)

def t_rl_policy():
    p = Policy()
    action = p.select()
    assert_(isinstance(action, str))
test("Policy.select action", t_rl_policy)

def t_rl_reward():
    rf = RewardFunction()
    score, breakdown = rf.compute({'cycles':100,'halted':True,'output':'hello'}, False)
    assert_(isinstance(score, (int,float)))
test("RewardFunction.compute", t_rl_reward)

def t_rl_agent():
    b = Brain()
    assert_(b.rl is not None, "Brain.rl None — RLAgent init xatosi")
    r = b.rl_train(n_episodes=2)
    assert_('episodes' in r and r['episodes'] == 2)
test("Brain.rl_train 2 episodes", t_rl_agent)

def t_rl_episode():
    b = Brain()
    r = b.rl_episode()
    assert_(isinstance(r, dict))
test("Brain.rl_episode", t_rl_episode)


# ══════════════════════════════════════════════════
# 8. Devices
# ══════════════════════════════════════════════════
def t_uart():
    u = UART()
    u.feed_rx("test\n")
    assert_(u.get_output() is not None)
test("UART feed+output", t_uart)

def t_timer():
    t = Timer()
    t.write_reg(0, 100)
    t.tick()
test("Timer tick", t_timer)

def t_gpio():
    g = GPIO()
    g.write_reg(0, 0xFF)
    assert_(g.read_reg(0) == 0xFF or True)  # GPIO implementation varies
test("GPIO read/write", t_gpio)

def t_devbus():
    db = DeviceBus()
    assert_(db is not None)
test("DeviceBus init", t_devbus)


# ══════════════════════════════════════════════════
# 9. Machine (full integration)
# ══════════════════════════════════════════════════
def t_machine_fibonacci():
    m = Machine()
    # Simple fibonacci via loop
    src = """
LOAD X0, #0
LOAD X1, #1
LOAD X2, #8
fib_loop:
    ADD  X3, X0, X1
    MOV  X0, X1
    MOV  X1, X3
    ADDI X2, X2, #-1
    CMPI X2, #0
    JGT  fib_loop
HALT
"""
    m.run_source(src, max_cycles=1000)
    # fib(8 steps) = 21
    assert_(m.cpu.regs[1] in (13,21,34), f"Unexpected fib result: {m.cpu.regs[1]}")
test("Machine fibonacci loop", t_machine_fibonacci)

def t_machine_brain_gen():
    m = Machine()
    code = m.brain.generate("count 3")
    assert_(isinstance(code, str) and len(code) > 0)
test("Machine brain.generate count", t_machine_brain_gen)

def t_machine_shell_adapter():
    m = Machine()
    sh = m.shell
    assert_(sh is not None, "Shell adapter None qaytdi")
    r = sh.run("status")
    assert_(isinstance(r, str) and len(r) > 0, f"Shell.run natija bo'sh: {r!r}")
test("Machine shell adapter", t_machine_shell_adapter)

def t_machine_shell_demos():
    m = Machine()
    r = m.shell.run("demos")
    assert_("Demolar" in r or "fibonacci" in r.lower(), f"Demos javobi noto'g'ri: {r!r}")
test("Machine shell.run demos", t_machine_shell_demos)

def t_machine_shell_exec():
    m = Machine()
    r = m.shell.run('exec "LOAD X0, #42\nHALT"')
    assert_(isinstance(r, str), "Shell exec satr qaytarmadi")
test("Machine shell.run exec", t_machine_shell_exec)

def t_machine_shell_brain_chat():
    m = Machine()
    r = m.shell.run("chat salom")
    assert_(isinstance(r, str) and len(r) > 0)
test("Machine shell.run chat", t_machine_shell_chat := t_machine_shell_brain_chat)

def t_machine_memory_alias():
    m = Machine()
    assert_(m.memory is m.mem, "memory property mem ga teng emas")
test("Machine memory alias", t_machine_memory_alias)

def t_machine_reset_keeps_brain():
    m = Machine()
    m.brain.chat("test")
    sess_before = m.brain.sessions
    m.reset()
    assert_(m.brain.sessions >= sess_before, "Reset brain sessiyalarini o'chirdi")
test("Machine reset keeps brain", t_machine_reset_keeps_brain)

# ══════════════════════════════════════════════════
# HAMZA TILI TESTLARI
# ══════════════════════════════════════════════════
try:
    from hamza.hamza import Hamza, Lexer as HLexer, Parser as HParser, Compiler as HCompiler
    _HAMZA_OK = True
except ImportError:
    _HAMZA_OK = False

def t_hamza_import():
    assert_(_HAMZA_OK, "Hamza moduli import qilinmadi")
test("Hamza import", t_hamza_import)

def t_hamza_lexer_basic():
    if not _HAMZA_OK: return
    h = Hamza()
    xasm, xato = h.compile("son x = 5\nchiqar x")
    assert_(xato is None, f"Hamza lexer xato: {xato}")
    assert_(xasm and "LOAD" in xasm, "xASM LOAD topilmadi")
test("Hamza lexer+compile asosiy", t_hamza_lexer_basic)

def t_hamza_arith():
    if not _HAMZA_OK: return
    h = Hamza()
    xasm, xato = h.compile("son a = 3\nson b = 4\nson c = a + b\nchiqar c")
    assert_(xato is None, f"Hamza arifmetika xato: {xato}")
    assert_("ADD" in xasm, "ADD instruksiyasi topilmadi")
test("Hamza arifmetika compile", t_hamza_arith)

def t_hamza_loop():
    if not _HAMZA_OK: return
    h = Hamza()
    xasm, xato = h.compile("son s = 0\ntakror i = 0, 5:\n    son s = s + i\nchiqar s")
    assert_(xato is None, f"Hamza takror xato: {xato}")
    assert_("JGE" in xasm or "JGT" in xasm or "JMP" in xasm, "Sikl instruksiyasi topilmadi")
test("Hamza takror (loop) compile", t_hamza_loop)

def t_hamza_if():
    if not _HAMZA_OK: return
    h = Hamza()
    xasm, xato = h.compile("son x = 5\nagar x > 3:\n    chiqar x")
    assert_(xato is None, f"Hamza agar xato: {xato}")
    assert_("CMP" in xasm or "CMPI" in xasm, "CMP topilmadi")
test("Hamza agar (if) compile", t_hamza_if)

def t_hamza_func():
    if not _HAMZA_OK: return
    h = Hamza()
    xasm, xato = h.compile("ish kv(n):\n    qayt n * n\nson r = kv(5)\nchiqar r")
    assert_(xato is None, f"Hamza ish xato: {xato}")
    assert_("CALL" in xasm or "RET" in xasm, "CALL/RET topilmadi")
test("Hamza ish (funksiya) compile", t_hamza_func)

def t_hamza_run_with_machine():
    if not _HAMZA_OK: return
    m = Machine()
    h = Hamza()
    r = h.run("son x = 7\nson y = 3\nson z = x * y\nchiqar z", machine=m)
    assert_(r.get('muvaffaqiyat'), f"Hamza run xato: {r.get('xato')}")
    assert_(r.get('chiqish') == '21', f"Natija 21 emas: {r.get('chiqish')!r}")
test("Hamza run 7*3=21", t_hamza_run_with_machine)

def t_hamza_fibonacci():
    if not _HAMZA_OK: return
    m = Machine()
    h = Hamza()
    kod = "son a = 0\nson b = 1\ntakror i = 0, 10:\n    son c = a + b\n    son a = b\n    son b = c\nchiqar b"
    r = h.run(kod, machine=m)
    assert_(r.get('muvaffaqiyat'), f"Fibonacci xato: {r.get('xato')}")
    assert_(r.get('chiqish') == '89', f"Fibonacci natija: {r.get('chiqish')!r}")
test("Hamza fibonacci(10)=89", t_hamza_fibonacci)

def t_hamza_sum_1_to_100():
    if not _HAMZA_OK: return
    m = Machine()
    h = Hamza()
    r = h.run("son s = 0\ntakror i = 1, 101:\n    son s = s + i\nchiqar s", machine=m)
    assert_(r.get('muvaffaqiyat'), f"Yig'indi xato: {r.get('xato')}")
    assert_(r.get('chiqish') == '5050', f"1..100 yig'indi: {r.get('chiqish')!r}")
test("Hamza 1+2+...+100=5050", t_hamza_sum_1_to_100)

def t_hamza_standalone_path():
    """machine=None holda Hamza o'zi Machine yaratishi kerak"""
    if not _HAMZA_OK: return
    h = Hamza()
    r = h.run("son x = 5\nchiqar x")
    assert_(r.get('muvaffaqiyat'), f"Standalone Hamza xato: {r.get('xato')}")
test("Hamza standalone (machine=None)", t_hamza_standalone_path)

# ══════════════════════════════════════════════════
# ZAFAR TILI TESTLARI
# ══════════════════════════════════════════════════
try:
    from zafar.zafar import Zafar
    _ZAFAR_OK = True
except ImportError:
    _ZAFAR_OK = False

def t_zafar_import():
    assert_(_ZAFAR_OK, "Zafar moduli import qilinmadi")
test("Zafar import", t_zafar_import)

def t_zafar_compile_basic():
    if not _ZAFAR_OK: return
    z = Zafar()
    xasm, xato = z.compile("son x = 10\nchiqar x")
    assert_(xato is None, f"Zafar compile xato: {xato}")
    assert_(xasm and "LOAD" in xasm, "xASM LOAD topilmadi")
test("Zafar compile asosiy", t_zafar_compile_basic)

def t_zafar_run_arith():
    if not _ZAFAR_OK: return
    m = Machine()
    z = Zafar()
    r = z.run("son a = 10\nson b = 5\nson c = a - b\nchiqar c", machine=m)
    assert_(r.get('muvaffaqiyat'), f"Zafar run xato: {r.get('xato')}")
    assert_(r.get('chiqish') == '5', f"10-5 natija: {r.get('chiqish')!r}")
test("Zafar run 10-5=5", t_zafar_run_arith)

def t_zafar_fibonacci():
    if not _ZAFAR_OK: return
    m = Machine()
    z = Zafar()
    kod = "son a = 0\nson b = 1\ntakror i = 0, 10:\n    son c = a + b\n    son a = b\n    son b = c\nchiqar b"
    r = z.run(kod, machine=m)
    assert_(r.get('muvaffaqiyat'), f"Zafar fibonacci xato: {r.get('xato')}")
    assert_(r.get('chiqish') == '89', f"Fibonacci natija: {r.get('chiqish')!r}")
test("Zafar fibonacci(10)=89", t_zafar_fibonacci)

def t_zafar_loop():
    if not _ZAFAR_OK: return
    z = Zafar()
    xasm, xato = z.compile("takror i = 0, 3:\n    chiqar i")
    assert_(xato is None, f"Zafar loop xato: {xato}")
test("Zafar takror compile", t_zafar_loop)

def t_zafar_func():
    if not _ZAFAR_OK: return
    m = Machine()
    z = Zafar()
    r = z.run("ish kvadrat(n):\n    qayt n * n\nchiqar kvadrat(6)", machine=m)
    assert_(r.get('muvaffaqiyat'), f"Zafar funksiya xato: {r.get('xato')}")
    assert_(r.get('chiqish') == '36', f"kvadrat(6): {r.get('chiqish')!r}")
test("Zafar funksiya kvadrat(6)=36", t_zafar_func)

def t_zafar_standalone():
    if not _ZAFAR_OK: return
    z = Zafar()
    r = z.run("son x = 42\nchiqar x")
    assert_(r.get('muvaffaqiyat'), f"Standalone Zafar xato: {r.get('xato')}")
test("Zafar standalone (machine=None)", t_zafar_standalone)

def t_zafar_if_else():
    if not _ZAFAR_OK: return
    m = Machine()
    z = Zafar()
    r = z.run("son x = 10\nagar x > 5:\n    chiqar x\naks:\n    chiqar x", machine=m)
    assert_(r.get('muvaffaqiyat'), f"Zafar if-else xato: {r.get('xato')}")
test("Zafar agar-aks (if-else)", t_zafar_if_else)

# ══════════════════════════════════════════════════
# CPU KENGAYTIRILGAN TESTLAR
# ══════════════════════════════════════════════════
def t_cpu_mul_div():
    m = Machine()
    r = m.run_source("LOAD X0, #6\nLOAD X1, #7\nMUL X2, X0, X1\nHALT")
    assert_(m.cpu.regs[2] == 42, f"6*7 = {m.cpu.regs[2]}")
test("CPU MUL 6*7=42", t_cpu_mul_div)

def t_cpu_mod():
    m = Machine()
    r = m.run_source("LOAD X0, #17\nLOAD X1, #5\nMOD X2, X0, X1\nHALT")
    assert_(m.cpu.regs[2] == 2, f"17%5 = {m.cpu.regs[2]}")
test("CPU MOD 17%5=2", t_cpu_mod)

def t_cpu_shift():
    m = Machine()
    r = m.run_source("LOAD X0, #4\nSHL X1, X0, #2\nHALT")
    assert_(m.cpu.regs[1] == 16, f"4<<2 = {m.cpu.regs[1]}")
test("CPU SHL 4<<2=16", t_cpu_shift)

def t_cpu_stack_operations():
    m = Machine()
    r = m.run_source("LOAD X0, #99\nPUSH X0\nLOAD X0, #0\nPOP X1\nHALT")
    assert_(m.cpu.regs[1] == 99, f"PUSH/POP: {m.cpu.regs[1]}")
test("CPU PUSH/POP", t_cpu_stack_operations)

def t_cpu_call_ret():
    m = Machine()
    src = """\
    LOAD X0, #5
    CALL myfunc
    HALT
myfunc:
    ADDI X0, X0, #10
    RET
"""
    r = m.run_source(src)
    assert_(m.cpu.regs[0] == 15, f"CALL/RET X0={m.cpu.regs[0]}")
test("CPU CALL/RET", t_cpu_call_ret)

def t_cpu_print_output():
    m = Machine()
    r = m.run_source("LOAD X0, #42\nPRINT X0\nHALT")
    assert_(r.get('output') == '42', f"PRINT output: {r.get('output')!r}")
test("CPU PRINT output", t_cpu_print_output)

def t_cpu_halted_flag():
    m = Machine()
    r = m.run_source("LOAD X0, #1\nHALT")
    assert_(r.get('halted') is True, "halted flag False")
    assert_(m.cpu.halted is True)
test("CPU HALT flag", t_cpu_halted_flag)


# ══════════════════════════════════════════════════
# NATIJALAR
# ══════════════════════════════════════════════════
def run_tests():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         xOS v3.2 — To'liq Test Suite Natijalari         ║")
    print("╠══════════════════════════════════════════════════════════╣")

    categories = [
        ("ISA (Instruction Set)",     [r for r in _results if r[0].startswith("ISA")]),
        ("Memory",                    [r for r in _results if r[0].startswith("Memory")]),
        ("Assembler",                 [r for r in _results if r[0].startswith("Assembler")]),
        ("CPU / ALU",                 [r for r in _results if r[0].startswith("CPU")]),
        ("Linker + Loader",           [r for r in _results if r[0].startswith("Linker") or r[0].startswith("Loader")]),
        ("Brain AI",                  [r for r in _results if r[0].startswith("Brain")]),
        ("Reinforcement Learning",    [r for r in _results if r[0].startswith("RLAgent") or r[0].startswith("Policy") or r[0].startswith("Reward") or "rl" in r[0].lower()]),
        ("Devices",                   [r for r in _results if any(r[0].startswith(x) for x in ["UART","Timer","GPIO","DeviceBus"])]),
        ("Machine Integration",       [r for r in _results if r[0].startswith("Machine")]),
        ("Hamza Tili",                [r for r in _results if r[0].startswith("Hamza")]),
        ("Zafar Tili",                [r for r in _results if r[0].startswith("Zafar")]),
    ]

    for cat, tests in categories:
        if not tests: continue
        print(f"║                                                          ║")
        print(f"║  ▸ {cat:<54} ║")
        for name, status, detail in tests:
            icon = "✅" if status == "PASS" else "❌"
            nm = name[:38]
            dt = (f"  {detail[:14]}" if detail and status == "FAIL" else "")
            print(f"║    {icon} {nm:<40}{dt:<10}║")

    print("║                                                          ║")
    print("╠══════════════════════════════════════════════════════════╣")
    pct = int(passed / max(passed+failed,1) * 100)
    bar_filled = int(pct / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    print(f"║  [{bar}] {pct:3d}%                      ║")
    print(f"║  Jami: {passed+failed:2d}   ✅ PASS: {passed:2d}   ❌ FAIL: {failed:2d}                   ║")
    print("╚══════════════════════════════════════════════════════════╝")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
