"""xOS Lab AI Yordamchi — toga-siz ishlaydigan core"""
import time

HAMZA_MISOLLAR = {
    'fibonacci': 'ish fibonacci(n):\n    agar n < 2:\n        qayt n\n    qayt fibonacci(n - 1) + fibonacci(n - 2)\n\nchiqar fibonacci(10)',
    'factorial': 'ish factorial(n):\n    agar n <= 1:\n        qayt 1\n    qayt n * factorial(n - 1)\n\nchiqar factorial(7)',
    'hello':     'chiqar "Salom, Dunyo!"',
    'loop':      'son yig = 0\ntakror i = 1, 11:\n    yig = yig + i\nchiqar yig',
    'maksimal':  'son a = 15\nson b = 27\nagar a > b:\n    chiqar a\naks:\n    chiqar b',
}

class AIYordamchi:
    def __init__(self):
        self.tarix = []
        self.t0 = time.time()

    def javob(self, savol):
        k = savol.lower().strip()
        self.tarix.append(savol)
        return self._hisob(k, savol)

    def _hisob(self, k, asl):
        if any(s in k for s in ['salom','salm','hey','hi ']):
            return "Salom! Men xOS Lab AI yordamchisiman 🧠\nNima kerak?\n• 'hamza fibonacci' — kod\n• 'xasm misol' — assembly\n• 'xos nima' — tizim\n• 'yordam' — ro'yxat"
        if 'xos nima' in k or 'laboratoriya' in k:
            return "xOS — shaxsiy virtual laboratoriyangiz.\nTarkibi:\n• xCPU-1 virtual protsessori\n• Hamza/Zafar O'zbek tillari\n• xASM kompilyatori\n• Brain AI\nHammasi Android da ishlaydi!"
        if 'fibonacci' in k:
            return f"Fibonacci — Hamza tilida:\n\n{HAMZA_MISOLLAR['fibonacci']}\n\nNatija: 55"
        if 'factorial' in k:
            return f"Factorial — Hamza tilida:\n\n{HAMZA_MISOLLAR['factorial']}\n\nNatija: 5040"
        if any(s in k for s in ['loop','takror',"yig'indi",'sikl']):
            return f"Takrorlash (1-10 yig'indi):\n\n{HAMZA_MISOLLAR['loop']}\n\nNatija: 55"
        if 'hamza' in k and any(s in k for s in ['misol','kod','yoz',"ko'rsat"]):
            return "Hamza misollar:\n• fibonacci\n• factorial\n• hello\n• loop\n• maksimal"
        if 'xasm' in k or 'assembly' in k:
            return "xASM misol:\n\nLOAD X0, #25\nLOAD X1, #17\nADD X2, X0, X1\nPRINT X2\nHALT\n\nNatija: 42"
        if 'registr' in k:
            return "xCPU-1 registrlari:\nX0-X7: umumiy\nX8-X12: vaqtinchalik\nX13 (SP): stack\nX14 (LR): link\nX15 (PC): dastur hisoblagichi"
        if 'yordam' in k or 'help' in k:
            return "Men yordam bera olaman:\n1. Hamza/Zafar kodi\n2. xASM instruksiyalari\n3. xCPU-1 haqida\n4. Algoritmlar\n\nMisol: 'fibonacci kodi yoz'"
        if 'status' in k or 'holat' in k:
            uptime = int(time.time()-self.t0)
            return f"xOS Lab AI holati:\n• Sessiya: {uptime}s\n• Savollar: {len(self.tarix)}\n• xCPU-1: ✅"
        try:
            parts = asl.strip().split()
            if len(parts)==3 and parts[1] in ['+','-','*','/']:
                a,op,b = float(parts[0]),parts[1],float(parts[2])
                r = {'+':(a+b),'-':(a-b),'*':(a*b),'/':(a/b if b else None)}[op]
                if r is not None: return f"{a} {op} {b} = {r:g}"
        except: pass
        return f"Savolingiz: '{asl[:50]}'\n\n'yordam' yoki 'fibonacci kodi' deb yozing"
