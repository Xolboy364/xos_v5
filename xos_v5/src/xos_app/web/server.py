"""
xOS v2 Web Server
==================
xOS v2 mashina uchun to'liq REST API backend.
Standart Python kutubxonasi — pip install kerak emas.

Ishlatish:
    python web/server.py
    python web/server.py --port 9000
    http://localhost:8080
"""

import os, sys, json, threading, traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from kernel.machine import Machine

_machine = Machine()
_lock    = threading.Lock()
PORT     = 8080

# Brain faylini avtomatik yuklash
_brain_file = os.path.join(ROOT, '.xos_web_brain.json')
_machine.brain_load(_brain_file)


def handle_api(path: str, body: dict) -> dict:
    global _machine
    with _lock:
        try:
            # ── Assemble ──────────────────────────────────
            if path == '/api/assemble':
                src  = body.get('source', '')
                code = _machine.compile(src)
                # Listing yaratish
                listing = []
                asm = _machine.asm
                addr = 0x20000
                lines = [l.strip() for l in src.splitlines()
                         if l.strip() and not l.strip().startswith(';')]
                for line in lines:
                    if line.endswith(':') or line.startswith('.'):
                        listing.append({'addr': f'0x{addr:08X}', 'hex': '        ', 'src': line})
                    else:
                        if addr - 0x20000 < len(code):
                            w = int.from_bytes(code[addr-0x20000:addr-0x20000+4], 'little')
                            listing.append({
                                'addr': f'0x{addr:08X}',
                                'hex':  f'{w:08X}',
                                'src':  line,
                            })
                            addr += 4
                return {
                    'ok':      True,
                    'size':    len(code),
                    'hex':     code.hex().upper(),
                    'listing': listing,
                    'labels':  {k: f'0x{v:08X}' for k, v in asm.labels.items()},
                }

            # ── Run ───────────────────────────────────────
            elif path == '/api/run':
                src        = body.get('source', '')
                max_cycles = body.get('max_cycles', 1_000_000)
                result     = _machine.run_source(src, max_cycles)
                cpu        = _machine.cpu
                return {
                    'ok':       True,
                    'halted':   result['halted'],
                    'cycles':   result['cycles'],
                    'instr':    result['instr'],
                    'mips':     result['mips'],
                    'time_sec': result['time_sec'],
                    'output':   result.get('output', ''),
                    'regs':     list(cpu.regs),
                    'flags': {
                        'N': int(cpu.flag_n), 'Z': int(cpu.flag_z),
                        'C': int(cpu.flag_c), 'V': int(cpu.flag_v),
                    },
                    'brain_eval': _machine.brain_evaluate(result),
                }

            # ── ELF kompilyatsiya ──────────────────────────
            elif path == '/api/compile_elf':
                src = body.get('source', '')
                elf = _machine.compile_to_elf(src)
                dump = _machine.dump_elf(elf)
                return {
                    'ok':   True,
                    'size': len(elf),
                    'hex':  elf.hex().upper(),
                    'dump': dump,
                }

            # ── Disassemble ───────────────────────────────
            elif path == '/api/disassemble':
                hex_str = body.get('hex', '')
                data    = bytes.fromhex(hex_str.replace(' ', ''))
                result  = _machine.disassemble(data)
                return {'ok': True, 'disasm': result}

            # ── Reset ─────────────────────────────────────
            elif path == '/api/reset':
                _machine.reset()
                return {'ok': True, 'msg': 'Mashina qayta ishga tushirildi'}

            # ── Status ────────────────────────────────────
            elif path == '/api/status':
                st  = _machine.status()
                cpu = _machine.cpu
                return {
                    'ok': True,
                    'cpu': st['cpu'],
                    'memory': st['memory'],
                    'brain': st['brain'],
                    'devices': st['devices'],
                    'regs': list(cpu.regs),
                    'flags': {
                        'N': int(cpu.flag_n), 'Z': int(cpu.flag_z),
                        'C': int(cpu.flag_c), 'V': int(cpu.flag_v),
                    },
                }

            # ── Registrlar ────────────────────────────────
            elif path == '/api/regs':
                cpu = _machine.cpu
                return {
                    'ok':     True,
                    'regs':   list(cpu.regs),
                    'halted': cpu.halted,
                    'flags': {
                        'N': int(cpu.flag_n), 'Z': int(cpu.flag_z),
                        'C': int(cpu.flag_c), 'V': int(cpu.flag_v),
                    },
                }

            # ── Xotira ────────────────────────────────────
            elif path == '/api/memory':
                addr = body.get('addr', 0x20000)
                size = body.get('size', 128)
                size = min(size, 512)
                dump = _machine.dump_mem(addr, size)
                raw  = []
                for i in range(size):
                    try:
                        raw.append(_machine.mem.read8(addr + i))
                    except:
                        raw.append(0)
                return {'ok': True, 'dump': dump, 'bytes': raw, 'addr': addr}

            # ── UART ──────────────────────────────────────
            elif path == '/api/uart':
                out = _machine.bus.uart.get_output()
                return {'ok': True, 'output': out}

            # ── UART ga yozish ────────────────────────────
            elif path == '/api/uart/send':
                text = body.get('text', '')
                _machine.uart_send(text)
                return {'ok': True}

            # ── GPIO ──────────────────────────────────────
            elif path == '/api/gpio':
                g = _machine.bus.gpio
                return {
                    'ok':   True,
                    'dir':  g.direction,
                    'out':  g.output_val,
                    'inp':  g.input_val,
                    'pins': [bool(g.output_val & (1 << i)) for i in range(32)],
                }

            elif path == '/api/gpio/set':
                pin = body.get('pin', 0)
                val = body.get('val', False)
                _machine.gpio_set(pin, val)
                return {'ok': True, 'pin': pin, 'val': val}

            # ── Display ───────────────────────────────────
            elif path == '/api/display':
                d = _machine.bus.display
                # Framebuffer ni base64 emas, oddiy list
                pixels = []
                for y in range(0, d.height, 4):   # Har 4 qatordan 1
                    row = []
                    for x in range(0, d.width, 4):
                        p = d.get_pixel(x, y)
                        row.append(p)
                    pixels.append(row)
                return {
                    'ok': True,
                    'width': d.width, 'height': d.height,
                    'enabled': d.enabled,
                    'frames': d._frame_count,
                    'pixels': pixels,
                }

            elif path == '/api/display/clear':
                color = body.get('color', 0)
                _machine.display_clear(color)
                return {'ok': True}

            elif path == '/api/display/pixel':
                x = body.get('x', 0); y = body.get('y', 0)
                color = body.get('color', 0xFFFF)
                _machine.display_set_pixel(x, y, color)
                return {'ok': True}

            # ── Timer ─────────────────────────────────────
            elif path == '/api/timer':
                t0 = _machine.bus.timer0
                t1 = _machine.bus.timer1
                return {
                    'ok': True,
                    'timer0': {'value': t0.value, 'load': t0.load_val,
                               'enabled': t0.enabled, 'fires': t0._fire_count},
                    'timer1': {'value': t1.value, 'load': t1.load_val,
                               'enabled': t1.enabled, 'fires': t1._fire_count},
                }

            elif path == '/api/timer/start':
                load     = body.get('load', 1000)
                periodic = body.get('periodic', True)
                _machine.timer_start(load, periodic)
                return {'ok': True, 'load': load, 'periodic': periodic}

            # ── Brain API ─────────────────────────────────
            elif path == '/api/brain/status':
                return {'ok': True, 'status': _machine.brain_status()}

            elif path == '/api/brain/generate':
                task = body.get('task', '')
                code = _machine.brain_generate(task)
                return {'ok': True, 'code': code}

            elif path == '/api/brain/analyze':
                src    = body.get('source', '')
                result = _machine.brain_analyze(src)
                return {'ok': True, 'result': result}

            elif path == '/api/brain/chat':
                msg  = body.get('message', '')
                resp = _machine.brain_chat(msg)
                return {'ok': True, 'response': resp}

            elif path == '/api/brain/learn':
                _machine.brain.force_learn()
                kb = _machine.brain.kb.stats()
                return {'ok': True, 'patterns': kb['patterns'], 'rules': kb['rules']}

            elif path == '/api/brain/save':
                _machine.brain_save(_brain_file)
                return {'ok': True, 'path': _brain_file}

            elif path == '/api/brain/programs':
                progs = list(_machine.brain.kb.programs.keys())
                return {'ok': True, 'programs': progs}

            elif path == '/api/brain/program':
                name = body.get('name', '')
                code = _machine.brain.kb.programs.get(name, '')
                return {'ok': True, 'name': name, 'code': code}

            # ── Demo ──────────────────────────────────────
            elif path == '/api/demo':
                name = body.get('name', '')
                try:
                    result = _machine.run_demo(name)
                    cpu    = _machine.cpu
                    return {
                        'ok':     True,
                        'halted': result['halted'],
                        'instr':  result['instr'],
                        'mips':   result['mips'],
                        'output': result.get('output', ''),
                        'regs':   list(cpu.regs),
                        'brain_eval': _machine.brain_evaluate(result),
                    }
                except ValueError as e:
                    return {'ok': False, 'error': str(e)}

            # ── Demos ro'yxati ────────────────────────────
            elif path == '/api/demos':
                return {'ok': True, 'demos': _machine.available_demos()}

            else:
                return {'ok': False, 'error': f"Noma'lum endpoint: {path}"}

        except Exception as e:
            return {
                'ok':    False,
                'error': str(e),
                'trace': traceback.format_exc(),
            }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Jimgina ishlash

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html'):
            self._file('web/index.html', 'text/html; charset=utf-8')
        elif path == '/api/status':
            self._json(handle_api('/api/status', {}))
        elif path == '/api/regs':
            self._json(handle_api('/api/regs', {}))
        elif path == '/api/uart':
            self._json(handle_api('/api/uart', {}))
        elif path == '/api/gpio':
            self._json(handle_api('/api/gpio', {}))
        elif path == '/api/timer':
            self._json(handle_api('/api/timer', {}))
        elif path == '/api/display':
            self._json(handle_api('/api/display', {}))
        elif path == '/api/demos':
            self._json(handle_api('/api/demos', {}))
        elif path == '/api/brain/status':
            self._json(handle_api('/api/brain/status', {}))
        elif path == '/api/brain/programs':
            self._json(handle_api('/api/brain/programs', {}))
        elif path == '/api/brain/save':
            self._json(handle_api('/api/brain/save', {}))
        elif path == '/api/brain/learn':
            self._json(handle_api('/api/brain/learn', {}))
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        raw    = self.rfile.read(length)
        try:    body = json.loads(raw) if raw else {}
        except: body = {}
        self._json(handle_api(self.path, body))

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(payload))
        self._cors()
        self.end_headers()
        self.wfile.write(payload)

    def _file(self, relpath, ctype):
        full = os.path.join(ROOT, relpath)
        if not os.path.exists(full):
            self.send_response(404); self.end_headers(); return
        data = open(full, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', len(data))
        self._cors()
        self.end_headers()
        self.wfile.write(data)


def run(port=PORT):
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f"\n{'═'*60}")
    print(f"  🚀 xOS v2 Web IDE")
    print(f"  URL    : http://localhost:{port}")
    print(f"  Brain  : {_machine.brain.kb.stats()['programs']} dastur, neyron tarmoq")
    print(f"  Ctrl+C : to'xtatish")
    print(f"{'═'*60}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Server to\'xtatildi')
        _machine.brain_save(_brain_file)
        print(f'  Brain saqlandi: {_brain_file}')
        server.shutdown()


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='xOS v2 Web Server')
    p.add_argument('--port', type=int, default=PORT)
    args = p.parse_args()
    run(args.port)
