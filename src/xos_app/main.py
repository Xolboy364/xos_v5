#!/usr/bin/env python3
"""
xOS v5 — O'z Operatsion Tizimi
================================
xCPU-1 ISA + Brain AI (Neyron Tarmoq) + xASM + Devices + xELF + Shell

Foydalanish:
  python main.py                   → interaktiv shell
  python main.py --test            → 81 ta test
  python main.py --demo fibonacci  → demo
  python main.py --demos           → barcha demolar
  python main.py --run <fayl>      → fayl ishlatish
  python main.py --exec "KOD"      → kod ishlatish
  python main.py --gen <vazifa>    → kod generatsiya
  python main.py --asm "KOD"       → assembly → bytecode
  python main.py --elf "KOD"       → assembly → xELF
  python main.py --dis <fayl>      → disassemble
  python main.py --bstatus         → brain holati
  python main.py --bgen <vazifa>   → brain generatsiya
  python main.py --chat "xabar"    → brain suhbat
  python main.py --blearn          → o'rganish tsikli
"""
import sys, os, argparse
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

def main():
    p = argparse.ArgumentParser(description='xOS v5')
    p.add_argument('--test',    action='store_true')
    p.add_argument('--run',     metavar='FAYL')
    p.add_argument('--exec',    metavar='KOD')
    p.add_argument('--gen',     metavar='VAZIFA')
    p.add_argument('--demo',    metavar='NOM')
    p.add_argument('--demos',   action='store_true')
    p.add_argument('--asm',     metavar='KOD')
    p.add_argument('--elf',     metavar='KOD')
    p.add_argument('--dis',     metavar='FAYL')
    p.add_argument('--bstatus', action='store_true')
    p.add_argument('--bgen',    metavar='VAZIFA')
    p.add_argument('--chat',    metavar='XABAR')
    p.add_argument('--blearn',  action='store_true')
    p.add_argument('--analyze', metavar='FAYL')
    p.add_argument('--web',    action='store_true', help='Web IDE ishga tushirish')
    p.add_argument('--port',   type=int, default=8080, help='Web server porti')
    args = p.parse_args()

    if args.web if hasattr(args,'web') else False:
        from web.server import run
        run(args.port if hasattr(args,'port') else 8080)
        return
    if len(sys.argv) == 1:
        from shell.shell import Shell
        Shell().run()
        return

    from kernel.machine import Machine
    m = Machine()

    if args.test:
        from tests.test_all import run_tests
        sys.exit(0 if run_tests() else 1)

    elif args.demos:
        print("Mavjud demolar:")
        for d in m.available_demos(): print(f"  • {d}")

    elif args.demo:
        try:
            r = m.run_demo(args.demo)
            out = r.get('output','')
            print(f"▶ '{args.demo}':")
            if out: print(f"  Chiqish : {out}")
            print(f"  Instr   : {r['instr']}  |  {r['mips']} MIPS  |  {'✅' if r['halted'] else '⏸'}")
        except ValueError as e: print(f"❌ {e}")

    elif args.run:
        try:
            src = open(args.run, encoding='utf-8').read()
            r = m.run_source(src)
            out = r.get('output','')
            if out: print(f"Chiqish: {out}")
            print(f"Instr: {r['instr']}  |  {r['mips']} MIPS  |  {'✅' if r['halted'] else '⏸'}")
        except FileNotFoundError: print(f"❌ Fayl topilmadi: {args.run}")

    elif args.exec:
        r = m.run_source(args.exec.replace('\\n','\n'))
        out = r.get('output','')
        if out: print(f"Chiqish: {out}")
        print(f"Instr: {r['instr']}  |  {r['mips']} MIPS  |  {'✅' if r['halted'] else '⏸'}")

    elif args.gen or args.bgen:
        task = args.gen or args.bgen
        print(m.brain_generate(task))

    elif args.asm:
        src = args.asm.replace('\\n','\n')
        try:
            code = m.compile(src)
            print(f"Binary ({len(code)} byte):")
            for i in range(0, len(code), 4):
                w = int.from_bytes(code[i:i+4],'little')
                print(f"  0x{0x20000+i:08X}:  {w:08X}")
        except Exception as e: print(f"❌ {e}")

    elif args.elf:
        src = args.elf.replace('\\n','\n')
        try:
            elf = m.compile_to_elf(src)
            print(f"xELF ({len(elf)} byte):")
            print(m.dump_elf(elf))
        except Exception as e: print(f"❌ {e}")

    elif args.dis:
        try:
            data = open(args.dis,'rb').read()
            print(m.disassemble(data))
        except FileNotFoundError: print(f"❌ Fayl topilmadi: {args.dis}")

    elif args.bstatus: print(m.brain_status())

    elif args.blearn:
        m.brain.force_learn()
        kb = m.brain.kb.stats()
        print(f"✅ O'rganish bajarildi: {kb['patterns']} pattern, {kb['rules']} qoida")

    elif args.chat:
        print(f"🧠 {m.brain_chat(args.chat)}")

    elif args.analyze:
        try:
            src = open(args.analyze, encoding='utf-8').read()
            print(m.brain_analyze(src))
        except FileNotFoundError: print(f"❌ Fayl topilmadi: {args.analyze}")

if __name__ == '__main__':
    main()

# Web server sozlamalari main() ichiga qo'shimcha
def web_main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8080)
    args = p.parse_args()
    sys.path.insert(0, ROOT)
    from web.server import run
    run(args.port)
