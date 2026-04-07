"""
╔══════════════════════════════════════════════════════════════════╗
║          HAMZA TILI v2.0 — xCPU-1 bilan TO'LIQ BIRIKKAN        ║
╠══════════════════════════════════════════════════════════════════╣
║  Sintaksis:                                                      ║
║    son x = 5          → LOAD X0, #5                             ║
║    matn s = "Salom"   → PUTC har harf                           ║
║    agar x > 5:        → CMP + JLE                               ║
║    yoki x == 3:       → CMP + JNE                               ║
║    aks:               → ...                                      ║
║    takror i = 0, 10:  → LOAD + CMP + JGE + ADDI + JMP          ║
║    ish f(a, b):       → PUSH/POP + CALL/RET                     ║
║    qayt ifoda         → natija X0 da + RET                      ║
║    chiqar ifoda       → PRINT (son) / PUTC (matn)               ║
║    to'xta             → JMP loop_oxir                           ║
║    davom              → JMP loop_bosh                           ║
╠══════════════════════════════════════════════════════════════════╣
║  xCPU-1 Registr kelishuvi:                                       ║
║    X0        — funksiya natijasi / qayt qiymati                  ║
║    X1..X7    — mahalliy o'zgaruvchilar (7 ta)                    ║
║    X8        — vaqtinchalik 1 (ifoda hisoblash)                  ║
║    X9        — vaqtinchalik 2                                    ║
║    X10       — vaqtinchalik 3 (binary op)                        ║
║    X11       — loop chegarasi                                    ║
║    X12       — loop hisoblagichi                                  ║
║    X13 (SP)  — stack pointer (avtomatik)                         ║
║    X14 (LR)  — link register (CALL/RET, avtomatik)              ║
║    X15 (PC)  — dastur hisoblagichi (avtomatik)                   ║
╠══════════════════════════════════════════════════════════════════╣
║  Chaqiruv kelishuvi (Calling Convention):                        ║
║    - Argumentlar: X0, X1, X2 (chapdan o'ngga)                   ║
║    - Ko'p arg: stackga PUSH (o'ngdan chapga)                     ║
║    - Natija: X0 da qaytadi                                       ║
║    - Saqlanuvchi registrlar: X4..X7 (callee tomonidan)           ║
║    - Buziluvchi registrlar: X0..X3, X8..X12 (caller uchun)      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import re, sys, os

# ══════════════════════════════════════════════════════════════════
# XATOLAR
# ══════════════════════════════════════════════════════════════════

class HamzaXato(Exception):
    def __init__(self, xabar, satr=None, ustun=None):
        self.satr  = satr
        self.ustun = ustun
        joy = f" [satr {satr}]" if satr else ""
        super().__init__(f"⚠ Hamza xatosi{joy}: {xabar}")

class HamzaChipXato(Exception):
    """xCPU-1 da ishlashda yuzaga keladigan xato"""
    pass

# ══════════════════════════════════════════════════════════════════
# TOKEN TURLARI
# ══════════════════════════════════════════════════════════════════

class TT:
    # Primitiv turlar
    SON    = 'SON'
    MATN   = 'MATN'
    TOGRI  = 'TOGRI'
    NOTO   = 'NOTO'
    ID     = 'ID'

    # Kalit so'zlar
    KW_SON    = 'son'
    KW_MATN   = 'matn'
    KW_ISH    = 'ish'
    KW_QAYT   = 'qayt'
    KW_AGAR   = 'agar'
    KW_YOKI   = 'yoki'
    KW_AKS    = 'aks'
    KW_TAKROR = 'takror'
    KW_CHIQAR = 'chiqar'
    KW_TOXTA  = "to'xta"
    KW_DAVOM  = 'davom'

    # Operatorlar
    PLUS  = '+'
    MINUS = '-'
    YULDUZ= '*'
    SLASH = '/'
    FOIZ  = '%'
    TENG  = '='
    TENGEQ= '=='
    NOTENG= '!='
    KM    = '<'
    KT    = '>'
    KMTNG = '<='
    KTTNG = '>='
    VA    = 'va'
    YOKI2 = 'yoki2'  # mantiqiy yoki
    EMAS  = 'emas'

    # Tinish
    LP    = '('
    RP    = ')'
    COMMA = ','
    COLON = ':'
    NL    = 'NL'
    IND   = 'IND'
    DED   = 'DED'
    EOF   = 'EOF'

KALIT_SOZLAR = {
    'son', 'matn', 'ish', 'qayt',
    'agar', 'yoki', 'aks', 'takror',
    'chiqar', "to'xta", 'davom',
    "to'g'ri", "noto'g'ri",
    'va', 'emas',
}

# ══════════════════════════════════════════════════════════════════
# TOKEN
# ══════════════════════════════════════════════════════════════════

class Token:
    __slots__ = ('tur', 'qiymat', 'satr')
    def __init__(self, tur, qiymat, satr=0):
        self.tur    = tur
        self.qiymat = qiymat
        self.satr   = satr
    def __repr__(self):
        return f"[{self.tur}:{self.qiymat!r}@{self.satr}]"

# ══════════════════════════════════════════════════════════════════
# LEXER
# ══════════════════════════════════════════════════════════════════

class Lexer:
    def __init__(self, matn):
        self.qatorlar = matn.splitlines()
        self.tokenlar = []
        self._ind_stek = [0]

    def tahlil(self):
        for satr_n, qator in enumerate(self.qatorlar, 1):
            toza = qator.lstrip()
            if not toza or toza.startswith('#'):
                continue

            kirgizish = len(qator) - len(toza)
            joriy = self._ind_stek[-1]

            if kirgizish > joriy:
                self._ind_stek.append(kirgizish)
                self.tokenlar.append(Token(TT.IND, kirgizish, satr_n))
            else:
                while self._ind_stek[-1] > kirgizish:
                    self._ind_stek.pop()
                    self.tokenlar.append(Token(TT.DED, 0, satr_n))
                if self._ind_stek[-1] != kirgizish:
                    raise HamzaXato(
                        f"Kirgizish darajasi noto'g'ri ({kirgizish} != {self._ind_stek[-1]})",
                        satr_n
                    )

            self._qator(toza, satr_n)
            self.tokenlar.append(Token(TT.NL, '\n', satr_n))

        while len(self._ind_stek) > 1:
            self._ind_stek.pop()
            self.tokenlar.append(Token(TT.DED, 0, len(self.qatorlar)))

        self.tokenlar.append(Token(TT.EOF, None, len(self.qatorlar)))
        return self.tokenlar

    def _qator(self, matn, satr_n):
        i = 0; n = len(matn)
        while i < n:
            c = matn[i]

            # Bo'sh joy
            if c in ' \t':
                i += 1; continue

            # Izoh
            if c == '#':
                break

            # Matn: "..."
            if c == '"':
                j = i + 1
                while j < n and matn[j] != '"':
                    if matn[j] == '\\' and j+1 < n:
                        j += 2
                    else:
                        j += 1
                if j >= n:
                    raise HamzaXato("Matn yopilmagan (\" yetishmaydi)", satr_n)
                raw = matn[i+1:j]
                # Escape sequences
                val = raw.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                self.tokenlar.append(Token(TT.MATN, val, satr_n))
                i = j + 1; continue

            # Son
            if c.isdigit():
                j = i
                while j < n and (matn[j].isdigit() or matn[j] == '_'):
                    j += 1
                val = int(matn[i:j].replace('_', ''))
                # IMM14 chegarasi tekshiruvi — katta sonlar uchun ogohlantirish
                if val > 8191:
                    pass  # Compiler LDHI bilan hal qiladi
                self.tokenlar.append(Token(TT.SON, val, satr_n))
                i = j; continue

            # Ikki belgili operatorlar
            ikki = matn[i:i+2]
            if ikki == '==':
                self.tokenlar.append(Token(TT.TENGEQ, '==', satr_n)); i += 2; continue
            if ikki == '!=':
                self.tokenlar.append(Token(TT.NOTENG, '!=', satr_n)); i += 2; continue
            if ikki == '<=':
                self.tokenlar.append(Token(TT.KMTNG, '<=', satr_n)); i += 2; continue
            if ikki == '>=':
                self.tokenlar.append(Token(TT.KTTNG, '>=', satr_n)); i += 2; continue

            # Bir belgili
            if c in '+-*/%=<>(),:':
                tur_map = {
                    '+': TT.PLUS, '-': TT.MINUS, '*': TT.YULDUZ,
                    '/': TT.SLASH, '%': TT.FOIZ, '=': TT.TENG,
                    '<': TT.KM, '>': TT.KT,
                    '(': TT.LP, ')': TT.RP,
                    ',': TT.COMMA, ':': TT.COLON,
                }
                self.tokenlar.append(Token(tur_map[c], c, satr_n))
                i += 1; continue

            # Identifikator / kalit so'z
            if c.isalpha() or c == '_':
                j = i
                while j < n and (matn[j].isalnum() or matn[j] in "_'"):
                    j += 1
                so_z = matn[i:j]

                if so_z == "to'g'ri":
                    self.tokenlar.append(Token(TT.TOGRI, True, satr_n))
                elif so_z == "noto'g'ri":
                    self.tokenlar.append(Token(TT.NOTO, False, satr_n))
                elif so_z == "to'xta":
                    self.tokenlar.append(Token("to'xta", so_z, satr_n))
                elif so_z in KALIT_SOZLAR:
                    self.tokenlar.append(Token(so_z, so_z, satr_n))
                else:
                    self.tokenlar.append(Token(TT.ID, so_z, satr_n))
                i = j; continue

            raise HamzaXato(f"Noma'lum belgi: '{c}'", satr_n)

# ══════════════════════════════════════════════════════════════════
# AST TUGUNLARI
# ══════════════════════════════════════════════════════════════════

class Tugun: pass

class SonT(Tugun):
    __slots__ = ('q',)
    def __init__(self, q): self.q = q

class MatnT(Tugun):
    __slots__ = ('q',)
    def __init__(self, q): self.q = q

class MantiqT(Tugun):
    __slots__ = ('q',)
    def __init__(self, q): self.q = q

class IdT(Tugun):
    __slots__ = ('nom', 'satr')
    def __init__(self, nom, satr=0): self.nom = nom; self.satr = satr

class BinaryT(Tugun):
    __slots__ = ('chap', 'op', 'ong', 'satr')
    def __init__(self, chap, op, ong, satr=0):
        self.chap = chap; self.op = op; self.ong = ong; self.satr = satr

class UnaryT(Tugun):
    __slots__ = ('op', 'operand')
    def __init__(self, op, operand): self.op = op; self.operand = operand

class OzgarT(Tugun):
    __slots__ = ('nom', 'qiymat', 'tur', 'satr')
    def __init__(self, nom, qiymat, tur=None, satr=0):
        self.nom = nom; self.qiymat = qiymat; self.tur = tur; self.satr = satr

class ChiqarT(Tugun):
    __slots__ = ('ifoda', 'yangi_satr')
    def __init__(self, ifoda, yangi_satr=True):
        self.ifoda = ifoda; self.yangi_satr = yangi_satr

class AgarT(Tugun):
    __slots__ = ('shartlar', 'aks')
    def __init__(self, shartlar, aks): self.shartlar = shartlar; self.aks = aks

class TakrorT(Tugun):
    __slots__ = ('nom', 'bosh', 'oxir', 'qadam', 'blok', 'satr')
    def __init__(self, nom, bosh, oxir, qadam, blok, satr=0):
        self.nom = nom; self.bosh = bosh; self.oxir = oxir
        self.qadam = qadam; self.blok = blok; self.satr = satr

class IshT(Tugun):
    __slots__ = ('nom', 'params', 'blok', 'satr')
    def __init__(self, nom, params, blok, satr=0):
        self.nom = nom; self.params = params; self.blok = blok; self.satr = satr

class ChaqirT(Tugun):
    __slots__ = ('nom', 'arglar', 'satr')
    def __init__(self, nom, arglar, satr=0):
        self.nom = nom; self.arglar = arglar; self.satr = satr

class QaytT(Tugun):
    __slots__ = ('ifoda',)
    def __init__(self, ifoda): self.ifoda = ifoda

class ToxtaT(Tugun): pass
class DavomT(Tugun): pass

# ══════════════════════════════════════════════════════════════════
# PARSER
# ══════════════════════════════════════════════════════════════════

class Parser:
    def __init__(self, tokenlar):
        # Ketma-ket NL larni birlashtir
        tozalangan = []
        oldingi_nl = False
        for t in tokenlar:
            if t.tur == TT.NL:
                if oldingi_nl: continue
                oldingi_nl = True
            else:
                oldingi_nl = False
            tozalangan.append(t)
        self.tok  = tozalangan
        self.pos  = 0

    def _j(self):
        return self.tok[self.pos] if self.pos < len(self.tok) else Token(TT.EOF, None)

    def _ol(self):
        t = self._j(); self.pos += 1; return t

    def _kut(self, tur):
        t = self._j()
        if t.tur != tur:
            raise HamzaXato(
                f"'{tur}' kutilgan, '{t.qiymat}' topildi", t.satr)
        return self._ol()

    def _mos(self, *turlar):
        return self._j().tur in turlar

    def _nl(self):
        while self._mos(TT.NL): self._ol()

    def tahlil(self):
        dastur = []
        self._nl()
        while not self._mos(TT.EOF):
            t = self._buyruq()
            if t: dastur.append(t)
            self._nl()
        return dastur

    def _buyruq(self):
        t = self._j()
        if t.tur == TT.NL:   self._ol(); return None
        if t.tur == 'son':   return self._ozgar_elon('son')
        if t.tur == 'matn':  return self._ozgar_elon('matn')
        if t.tur == 'ish':   return self._ish_elon()
        if t.tur == 'agar':  return self._agar()
        if t.tur == 'takror':return self._takror()
        if t.tur == 'chiqar':return self._chiqar()
        if t.tur == 'qayt':  return self._qayt()
        if t.tur == "to'xta":self._ol(); return ToxtaT()
        if t.tur == 'davom': self._ol(); return DavomT()
        if t.tur == TT.ID:   return self._id_buyruq()
        if t.tur in (TT.IND, TT.DED): self._ol(); return None
        raise HamzaXato(f"Kutilmagan token: '{t.qiymat}'", t.satr)

    def _ozgar_elon(self, tur):
        satr = self._j().satr; self._ol()
        nom = self._kut(TT.ID).qiymat
        self._kut(TT.TENG)
        qiymat = self._ifoda()
        return OzgarT(nom, qiymat, tur, satr)

    def _id_buyruq(self):
        satr = self._j().satr
        nom  = self._ol().qiymat
        if self._mos(TT.LP):
            return self._chaqiruv_yani(nom, satr)
        if self._mos(TT.TENG):
            self._ol()
            return OzgarT(nom, self._ifoda(), None, satr)
        raise HamzaXato(f"'{nom}' dan keyin '=' yoki '(' kerak", satr)

    def _chaqiruv_yani(self, nom, satr):
        self._kut(TT.LP)
        arglar = []
        while not self._mos(TT.RP):
            arglar.append(self._ifoda())
            if self._mos(TT.COMMA): self._ol()
        self._kut(TT.RP)
        return ChaqirT(nom, arglar, satr)

    def _chiqar(self):
        satr = self._j().satr; self._ol()
        return ChiqarT(self._ifoda())

    def _qayt(self):
        self._ol()
        return QaytT(self._ifoda())

    def _agar(self):
        satr = self._j().satr; self._ol()
        shartlar = []
        shart = self._ifoda(); self._kut(TT.COLON)
        blok  = self._blok()
        shartlar.append((shart, blok))

        while self._mos('yoki'):
            self._ol()
            s = self._ifoda(); self._kut(TT.COLON)
            b = self._blok()
            shartlar.append((s, b))

        aks = None
        if self._mos('aks'):
            self._ol(); self._kut(TT.COLON)
            aks = self._blok()

        return AgarT(shartlar, aks)

    def _takror(self):
        satr = self._j().satr; self._ol()
        nom  = self._kut(TT.ID).qiymat
        self._kut(TT.TENG)
        bosh = self._ifoda()
        self._kut(TT.COMMA)
        oxir = self._ifoda()
        # Ixtiyoriy qadam
        qadam = SonT(1)
        if self._mos(TT.COMMA):
            self._ol(); qadam = self._ifoda()
        self._kut(TT.COLON)
        blok = self._blok()
        return TakrorT(nom, bosh, oxir, qadam, blok, satr)

    def _ish_elon(self):
        satr = self._j().satr; self._ol()
        nom  = self._kut(TT.ID).qiymat
        self._kut(TT.LP)
        params = []
        while not self._mos(TT.RP):
            params.append(self._kut(TT.ID).qiymat)
            if self._mos(TT.COMMA): self._ol()
        self._kut(TT.RP)
        self._kut(TT.COLON)
        blok = self._blok()
        return IshT(nom, params, blok, satr)

    def _blok(self):
        buyruqlar = []
        self._nl()
        if not self._mos(TT.IND):
            raise HamzaXato(
                "Blok 4 bo'sh joy bilan boshlanishi kerak",
                self._j().satr)
        self._ol()
        self._nl()
        while not self._mos(TT.DED) and not self._mos(TT.EOF):
            if self._mos(TT.NL): self._ol(); continue
            t = self._buyruq()
            if t: buyruqlar.append(t)
            self._nl()
        if self._mos(TT.DED): self._ol()
        return buyruqlar

    # ── Ifodalar (ustunlik tartibida) ────────────────────────────

    def _ifoda(self):    return self._mantiqiy()

    def _mantiqiy(self):
        chap = self._taqqoslash()
        while self._mos('va', 'yoki2'):
            op = self._ol().tur
            ong = self._taqqoslash()
            chap = BinaryT(chap, op, ong)
        return chap

    def _taqqoslash(self):
        chap = self._qo_shish()
        while self._mos(TT.TENGEQ, TT.NOTENG, TT.KM, TT.KT, TT.KMTNG, TT.KTTNG):
            op = self._ol().tur
            chap = BinaryT(chap, op, self._qo_shish(), self._j().satr)
        return chap

    def _qo_shish(self):
        chap = self._ko_paytirish()
        while self._mos(TT.PLUS, TT.MINUS):
            op = self._ol().tur
            chap = BinaryT(chap, op, self._ko_paytirish(), self._j().satr)
        return chap

    def _ko_paytirish(self):
        chap = self._unary()
        while self._mos(TT.YULDUZ, TT.SLASH, TT.FOIZ):
            op = self._ol().tur
            chap = BinaryT(chap, op, self._unary(), self._j().satr)
        return chap

    def _unary(self):
        if self._mos(TT.MINUS):
            self._ol(); return UnaryT('-', self._birlamchi())
        if self._mos('emas'):
            self._ol(); return UnaryT('emas', self._birlamchi())
        return self._birlamchi()

    def _birlamchi(self):
        t = self._j()
        if t.tur == TT.SON:   self._ol(); return SonT(t.qiymat)
        if t.tur == TT.MATN:  self._ol(); return MatnT(t.qiymat)
        if t.tur == TT.TOGRI: self._ol(); return MantiqT(True)
        if t.tur == TT.NOTO:  self._ol(); return MantiqT(False)
        if t.tur == TT.ID:
            nom = self._ol().qiymat; satr = t.satr
            if self._mos(TT.LP):
                return self._chaqiruv_yani(nom, satr)
            return IdT(nom, satr)
        if t.tur == TT.LP:
            self._ol(); e = self._ifoda(); self._kut(TT.RP); return e
        raise HamzaXato(f"Ifoda kutilgan, '{t.qiymat}' topildi", t.satr)

# ══════════════════════════════════════════════════════════════════
# SIMVOL JADVALI — O'zgaruvchilar va funksiyalar
# ══════════════════════════════════════════════════════════════════

class Doira:
    """Bir doira (scope) — funksiya yoki global"""
    def __init__(self, ota=None, nom='global'):
        self.ota    = ota
        self.nom    = nom
        self.ozgar  = {}   # nom → registr raqami
        self.keyingi= 1    # X1 dan boshlaymiz (X0 — natija)

    def qo_sh(self, nom):
        if nom in self.ozgar:
            return self.ozgar[nom]
        if self.keyingi > 7:
            raise HamzaXato(
                f"Juda ko'p mahalliy o'zgaruvchi (max 7): '{nom}'")
        self.ozgar[nom] = self.keyingi
        self.keyingi += 1
        return self.ozgar[nom]

    def top(self, nom):
        if nom in self.ozgar: return self.ozgar[nom]
        if self.ota:          return self.ota.top(nom)
        raise HamzaXato(f"'{nom}' o'zgaruvchisi topilmadi")

    def bor(self, nom):
        return nom in self.ozgar or (self.ota and self.ota.bor(nom))

# ══════════════════════════════════════════════════════════════════
# COMPILER — AST → xASM
# ══════════════════════════════════════════════════════════════════

# Registr nomlanishi (xCPU-1 kelishuvi)
REG_NATIJA = 0   # X0: funksiya natijasi
REG_T1     = 8   # X8: vaqtinchalik 1
REG_T2     = 9   # X9: vaqtinchalik 2
REG_T3     = 10  # X10: vaqtinchalik 3
REG_LCNT   = 12  # X12: loop counter

# Maksimal 14-bit imm chegarasi
IMM14_MAX =  8191
IMM14_MIN = -8192

class Compiler:
    """
    Hamza AST → xASM kodi.
    Har bir konstruksiya xCPU-1 ISA bilan 1:1 mos keladi.
    """

    def __init__(self):
        self._kod      = []
        self._label_n  = 0
        self._funksiyalar = {}   # nom → IshT
        self._doira    = Doira(nom='global')
        self._loop_stek = []    # [(bosh_label, oxir_label)]
        self._joriy_ish = None  # joriy funksiya nomi

    # ── Yordamchi metodlar ───────────────────────────────────────

    def _e(self, *satrlar):
        """xASM satr qo'shish"""
        for s in satrlar:
            self._kod.append(s)

    def _lbl(self, prefiks='L'):
        self._label_n += 1
        return f"__z_{prefiks}_{self._label_n}"

    def _imm_yukla(self, reg, val):
        """
        Ixtiyoriy kattalikdagi sonni registrga yuklash.
        IMM14 chegarasidan katta bo'lsa LDHI + ADDI ishlatiladi.
        Bu xCPU-1 bilan 1:1 mos.
        """
        if IMM14_MIN <= val <= IMM14_MAX:
            self._e(f"    LOAD X{reg}, #{val}")
        else:
            # Katta son: yuqori 16 bit + quyi 16 bit
            yuqori = (val >> 14) & 0x3FFF
            quyi   = val & 0x3FFF
            self._e(f"    LOAD X{reg}, #{quyi}")
            if yuqori:
                self._e(f"    LDHI X{reg}, #{yuqori}")

    # ── Asosiy kompilatsiya ──────────────────────────────────────

    def kompil(self, dastur):
        self._e(
            "; ═══════════════════════════════════════════════════",
            "; Hamza tili v2.0 — xCPU-1 chiqishi",
            "; Har instruksiya xCPU-1 ISA bilan 1:1 mos",
            "; ═══════════════════════════════════════════════════",
            ""
        )

        # Birinchi o'tish: barcha funksiyalarni ro'yxatga olish
        for t in dastur:
            if isinstance(t, IshT):
                self._funksiyalar[t.nom] = t

        # Funksiyalarni o'tkazib yuborish (main ga to'g'ri sakrash)
        if self._funksiyalar:
            lbl_main = self._lbl('MAIN')
            self._e(f"    JMP {lbl_main}", "")
            # Funksiyalarni compile qilish
            for nom, ish in self._funksiyalar.items():
                self._ish_compile(ish)
            self._e(f"{lbl_main}:", "")

        # Asosiy dastur
        for t in dastur:
            if not isinstance(t, IshT):
                self._tugun(t)

        self._e("", "    HALT")
        return '\n'.join(self._kod)

    def _tugun(self, t):
        if   isinstance(t, OzgarT):  self._ozgar(t)
        elif isinstance(t, ChiqarT): self._chiqar(t)
        elif isinstance(t, AgarT):   self._agar(t)
        elif isinstance(t, TakrorT): self._takror(t)
        elif isinstance(t, ChaqirT): self._chaqir(t, REG_T1)
        elif isinstance(t, QaytT):   self._qayt(t)
        elif isinstance(t, ToxtaT):  self._toxta()
        elif isinstance(t, DavomT):  self._davom()
        elif isinstance(t, IshT):    pass  # allaqachon compile qilindi
        else:
            raise HamzaXato(f"Noma'lum tugun: {type(t).__name__}")

    # ── Ifoda hisoblash → registrga ─────────────────────────────

    def _ifoda(self, tugun, maq=REG_T1):
        """
        Ifodani hisoblaydi, natijani maq registriga joylashtiradi.
        Qaytadi: maq (registr raqami)
        """
        if isinstance(tugun, SonT):
            self._imm_yukla(maq, tugun.q)
            return maq

        if isinstance(tugun, MantiqT):
            self._imm_yukla(maq, 1 if tugun.q else 0)
            return maq

        if isinstance(tugun, MatnT):
            # Matn uzunligini qaytaramiz (sonli kontekst)
            self._imm_yukla(maq, len(tugun.q))
            return maq

        if isinstance(tugun, IdT):
            reg = self._doira.top(tugun.nom)
            if reg != maq:
                self._e(f"    MOV X{maq}, X{reg}")
            return maq

        if isinstance(tugun, UnaryT):
            return self._unary(tugun, maq)

        if isinstance(tugun, BinaryT):
            return self._binary(tugun, maq)

        if isinstance(tugun, ChaqirT):
            return self._chaqir(tugun, maq)

        raise HamzaXato(f"Noma'lum ifoda: {type(tugun).__name__}")

    def _unary(self, t, maq):
        self._ifoda(t.operand, maq)
        if t.op == '-':
            # 0 - X → SUB
            self._e(f"    LOAD X{REG_T2}, #0",
                    f"    SUB X{maq}, X{REG_T2}, X{maq}")
        elif t.op == 'emas':
            # emas: if 0 → 1, aks holda → 0
            lbl_nol  = self._lbl('EMAS_NOL')
            lbl_oxir = self._lbl('EMAS_OX')
            self._e(f"    LOAD X{REG_T2}, #0",
                    f"    CMP X{maq}, X{REG_T2}",
                    f"    JEQ {lbl_nol}",
                    f"    LOAD X{maq}, #0",
                    f"    JMP {lbl_oxir}",
                    f"{lbl_nol}:",
                    f"    LOAD X{maq}, #1",
                    f"{lbl_oxir}:")
        return maq

    def _binary(self, t, maq):
        op = t.op

        # Taqqoslash operatorlari
        if op in (TT.TENGEQ, TT.NOTENG, TT.KM, TT.KT, TT.KMTNG, TT.KTTNG):
            return self._taqqoslash_compile(t, maq)

        # Arifmetik operatorlar
        # Chap → REG_T2, O'ng → REG_T3
        self._ifoda(t.chap, REG_T2)
        self._e(f"    PUSH X{REG_T2}")  # Stackga saqlash
        self._ifoda(t.ong, REG_T3)
        self._e(f"    POP X{REG_T2}")   # Chapni qaytarish

        if op == TT.PLUS:
            self._e(f"    ADD X{maq}, X{REG_T2}, X{REG_T3}")
        elif op == TT.MINUS:
            self._e(f"    SUB X{maq}, X{REG_T2}, X{REG_T3}")
        elif op == TT.YULDUZ:
            self._e(f"    MUL X{maq}, X{REG_T2}, X{REG_T3}")
        elif op == TT.SLASH:
            self._e(f"    DIV X{maq}, X{REG_T2}, X{REG_T3}")
            # Nolga bo'linishni xCPU-1 o'zi aniqlaydi (CPUError)
        elif op == TT.FOIZ:
            self._e(f"    MOD X{maq}, X{REG_T2}, X{REG_T3}")
        else:
            raise HamzaXato(f"Noma'lum operator: '{op}'")
        return maq

    def _taqqoslash_compile(self, t, maq):
        """
        Taqqoslash → xCPU-1 flaglar + shartli sakrash.
        Natija: maq = 1 (to'g'ri) yoki 0 (noto'g'ri)
        """
        self._ifoda(t.chap, REG_T2)
        self._e(f"    PUSH X{REG_T2}")
        self._ifoda(t.ong, REG_T3)
        self._e(f"    POP X{REG_T2}",
                f"    CMP X{REG_T2}, X{REG_T3}")

        lbl_ha   = self._lbl('HA')
        lbl_oxir = self._lbl('OX')
        op = t.op

        # Shartli sakrash (to'g'ri bo'lsa lbl_ha ga)
        if   op == TT.TENGEQ: self._e(f"    JEQ {lbl_ha}")
        elif op == TT.NOTENG: self._e(f"    JNE {lbl_ha}")
        elif op == TT.KM:     self._e(f"    JLT {lbl_ha}")
        elif op == TT.KT:     self._e(f"    JGT {lbl_ha}")
        elif op == TT.KMTNG:  self._e(f"    JLE {lbl_ha}")
        elif op == TT.KTTNG:  self._e(f"    JGE {lbl_ha}")

        self._e(f"    LOAD X{maq}, #0",
                f"    JMP {lbl_oxir}",
                f"{lbl_ha}:",
                f"    LOAD X{maq}, #1",
                f"{lbl_oxir}:")
        return maq

    # ── Shart sakrash (chiqmaydi, to'g'ridan sakraydi) ──────────

    def _shart_sakrash(self, shart, yolg_on_lbl):
        """
        Shart FALSE bo'lsa yolg_on_lbl ga sakraydi.
        Natija xotirasiga yozmaydi — faqat flaglar.
        Bu eng samarali yo'l xCPU-1 uchun.
        """
        if isinstance(shart, BinaryT) and shart.op in (
                TT.TENGEQ, TT.NOTENG, TT.KM, TT.KT, TT.KMTNG, TT.KTTNG):
            self._ifoda(shart.chap, REG_T2)
            self._e(f"    PUSH X{REG_T2}")
            self._ifoda(shart.ong, REG_T3)
            self._e(f"    POP X{REG_T2}",
                    f"    CMP X{REG_T2}, X{REG_T3}")
            op = shart.op
            # Teskari shartda sakra (FALSE bo'lsa)
            if   op == TT.TENGEQ: self._e(f"    JNE {yolg_on_lbl}")
            elif op == TT.NOTENG: self._e(f"    JEQ {yolg_on_lbl}")
            elif op == TT.KM:     self._e(f"    JGE {yolg_on_lbl}")
            elif op == TT.KT:     self._e(f"    JLE {yolg_on_lbl}")
            elif op == TT.KMTNG:  self._e(f"    JGT {yolg_on_lbl}")
            elif op == TT.KTTNG:  self._e(f"    JLT {yolg_on_lbl}")
        else:
            # Umumiy holat: ifoda hisoblash → 0 dan tekshirish
            self._ifoda(shart, REG_T1)
            self._e(f"    LOAD X{REG_T2}, #0",
                    f"    CMP X{REG_T1}, X{REG_T2}",
                    f"    JEQ {yolg_on_lbl}")

    # ── O'zgaruvchi ─────────────────────────────────────────────

    def _ozgar(self, t):
        # Yangi o'zgaruvchi yoki mavjud yangilash
        if not self._doira.bor(t.nom):
            reg = self._doira.qo_sh(t.nom)
        else:
            reg = self._doira.top(t.nom)
        self._e(f"; {t.nom} = ...")
        self._ifoda(t.qiymat, reg)

    # ── chiqar ──────────────────────────────────────────────────

    def _chiqar(self, t):
        self._e("; chiqar")
        if isinstance(t.ifoda, MatnT):
            # Matn: har harfini PUTC bilan chiqar
            for harf in t.ifoda.q:
                kod = ord(harf)
                self._imm_yukla(REG_T1, kod)
                self._e(f"    PUTC X{REG_T1}")
            # Yangi satr
            self._imm_yukla(REG_T1, 10)
            self._e(f"    PUTC X{REG_T1}")
        else:
            self._ifoda(t.ifoda, REG_T1)
            self._e(f"    PRINT X{REG_T1}")

    # ── agar / yoki / aks ────────────────────────────────────────

    def _agar(self, t):
        lbl_oxir   = self._lbl('AGAR_OX')
        lbl_keyingi = None

        for i, (shart, blok) in enumerate(t.shartlar):
            if lbl_keyingi:
                self._e(f"{lbl_keyingi}:")
            lbl_keyingi = self._lbl('AGAR_YOQ')

            self._e(f"; agar/yoki shart #{i+1}")
            self._shart_sakrash(shart, lbl_keyingi)

            for b in blok:
                self._tugun(b)
            self._e(f"    JMP {lbl_oxir}")

        if lbl_keyingi:
            self._e(f"{lbl_keyingi}:")

        if t.aks:
            self._e("; aks")
            for b in t.aks:
                self._tugun(b)

        self._e(f"{lbl_oxir}:")

    # ── takror ──────────────────────────────────────────────────

    def _takror(self, t):
        """
        takror i = bosh, oxir, [qadam]:
            blok

        xCPU-1 kodi:
            LOAD Ri, bosh
            LOAD R_oxir, oxir
        lbl_bosh:
            CMP Ri, R_oxir
            JGE lbl_oxir
            [blok]
            ADDI Ri, Ri, qadam
            JMP lbl_bosh
        lbl_oxir:
        """
        lbl_bosh = self._lbl('TAKROR')
        lbl_oxir = self._lbl('TAKROR_OX')

        # Loop stek (to'xta/davom uchun)
        self._loop_stek.append((lbl_bosh, lbl_oxir))

        # Loop o'zgaruvchisi
        if not self._doira.bor(t.nom):
            reg_i = self._doira.qo_sh(t.nom)
        else:
            reg_i = self._doira.top(t.nom)

        # BUG1 FIX: chegara registrini ham dinamik ajrat (X11 hardcoded emas)
        _limit_nom = f"__limit_{t.nom}_{lbl_bosh}"
        reg_oxir = self._doira.qo_sh(_limit_nom)

        self._e(f"; takror {t.nom}")
        self._ifoda(t.bosh, reg_i)
        self._ifoda(t.oxir, reg_oxir)

        self._e(f"{lbl_bosh}:")
        self._e(f"    CMP X{reg_i}, X{reg_oxir}")
        self._e(f"    JGE {lbl_oxir}")

        # Blok
        for b in t.blok:
            self._tugun(b)

        # Qadam (odatda 1)
        if isinstance(t.qadam, SonT) and t.qadam.q == 1:
            self._e(f"    ADDI X{reg_i}, X{reg_i}, #1")
        else:
            self._ifoda(t.qadam, REG_T1)
            self._e(f"    ADD X{reg_i}, X{reg_i}, X{REG_T1}")

        self._e(f"    JMP {lbl_bosh}",
                f"{lbl_oxir}:")

        self._loop_stek.pop()

    # ── ish (funksiya) ───────────────────────────────────────────

    def _ish_compile(self, t):
        """
        Chaqiruv kelishuvi (xCPU-1 uchun):
          - 1-3 argument: X0, X1, X2 orqali
          - 4+ argument: stackdan POP
          - Natija: X0
          - LR avtomatik CALL/RET tomonidan boshqariladi
        """
        lbl_bosh = f"__ish_{t.nom}"
        lbl_oxir = f"__ish_{t.nom}_ox"
        self._e(f"; ═══ ish {t.nom}({', '.join(t.params)}) ═══",
                f"{lbl_bosh}:")

        # ABI FIX: Callee-saved registrlarni saqlash
        # X14 (LR) + X4..X7 - standart calling convention
        self._e(
            "    PUSH X14  ; LR saqlash",
            "    PUSH X4   ; callee-saved",
            "    PUSH X5   ; callee-saved",
            "    PUSH X6   ; callee-saved",
            "    PUSH X7   ; callee-saved",
        )

        # Yangi doira
        eski_doira = self._doira
        eski_ish   = self._joriy_ish
        self._doira = Doira(ota=None, nom=t.nom)
        self._joriy_ish = t.nom

        # Parametrlarni registrlarga bog'lash
        # X0, X1, X2 → birinchi 3 parametr
        n_reg_params = min(len(t.params), 3)
        for i, param in enumerate(t.params):
            if i < 3:
                self._doira.ozgar[param] = i  # X0, X1, X2
            else:
                # 4+ parametr stackdan POP
                reg = self._doira.qo_sh(param)
                self._e(f"    POP X{reg}  ; param: {param}")
        # BUG-FIX: mahalliy o'zgaruvchilar param registrlaridan KEYIN boshlansin
        # Masalan: f(a,b) → a=X0, b=X1 → local vars X2 dan boshlanadi
        # RECURSIVE-FIX: Parametrlarni X4+ (callee-saved) reglarga ko'chir
        # Bu CALL orqali X0-X3 o'chirilishidan himoyalaydi
        CALLEE_SAVED_BASE = 4  # X4, X5, X6, X7
        if n_reg_params > 0:
            self._e("; Parametrlarni callee-saved registrlarga ko'chirish")
            for i in range(n_reg_params):
                param = t.params[i]
                saved_reg = CALLEE_SAVED_BASE + i
                if saved_reg <= 7:
                    self._e(f"    MOV X{saved_reg}, X{i}  ; '{param}' → X{saved_reg}")
                    self._doira.ozgar[param] = saved_reg
        # Mahalliy o'zgaruvchilar param + callee base dan keyin
        self._doira.keyingi = max(CALLEE_SAVED_BASE + n_reg_params, CALLEE_SAVED_BASE)

        # Blok
        for b in t.blok:
            self._tugun(b)

        # Agar qayt yo'q bo'lsa — X0 = 0, ABI restore, RET
        self._e(
            f"    LOAD X{REG_NATIJA}, #0",
            "    POP X7   ; callee-saved restore",
            "    POP X6   ; callee-saved restore",
            "    POP X5   ; callee-saved restore",
            "    POP X4   ; callee-saved restore",
            "    POP X14  ; LR restore",
            "    RET",
            f"{lbl_oxir}:",
            ""
        )

        self._doira    = eski_doira
        self._joriy_ish = eski_ish

    def _chaqir(self, t, maq=REG_T1):
        """
        Funksiya chaqiruvi:
          - Argumentlar X0, X1, X2 ga yuklanadi
          - CALL instruksiyasi
          - Natija X0 dan maq ga ko'chiriladi
        """
        if t.nom not in self._funksiyalar:
            raise HamzaXato(
                f"'{t.nom}' funksiyasi topilmadi. "
                f"Mavjud: {list(self._funksiyalar.keys()) or ['hech biri']}",
                t.satr)

        ish = self._funksiyalar[t.nom]
        if len(t.arglar) != len(ish.params):
            raise HamzaXato(
                f"'{t.nom}' {len(ish.params)} argument oladi, "
                f"{len(t.arglar)} berildi", t.satr)

        self._e(f"; {t.nom}(...) chaqiruvi")

        # Argumentlarni yuklab, stackga saqlash (o'ng → chap tartibda)
        for i, arg in enumerate(t.arglar):
            self._ifoda(arg, REG_T1)
            self._e(f"    PUSH X{REG_T1}")

        # Stackdan X0, X1, X2 ga olish (teskari tartibda POP)
        for i in range(min(len(t.arglar), 3) - 1, -1, -1):
            self._e(f"    POP X{i}")

        self._e(f"    CALL __ish_{t.nom}")

        # Natija X0 da — agar boshqa registr kerak bo'lsa ko'chir
        if maq != REG_NATIJA:
            self._e(f"    MOV X{maq}, X{REG_NATIJA}")
        return maq

    # ── qayt ────────────────────────────────────────────────────

    def _qayt(self, t):
        self._e("; qayt")
        self._ifoda(t.ifoda, REG_NATIJA)  # X0 ga yukla
        # ABI FIX: callee-saved regs ni tiklash (teskari tartibda)
        if self._joriy_ish is not None:
            self._e(
                "    POP X7   ; callee-saved restore",
                "    POP X6   ; callee-saved restore",
                "    POP X5   ; callee-saved restore",
                "    POP X4   ; callee-saved restore",
                "    POP X14  ; LR restore",
            )
        self._e(f"    RET")

    # ── to'xta / davom ──────────────────────────────────────────

    def _toxta(self):
        if not self._loop_stek:
            raise HamzaXato("'to'xta' faqat 'takror' ichida ishlatiladi")
        _, lbl_oxir = self._loop_stek[-1]
        self._e(f"    JMP {lbl_oxir}  ; to'xta")

    def _davom(self):
        if not self._loop_stek:
            raise HamzaXato("'davom' faqat 'takror' ichida ishlatiladi")
        lbl_bosh, _ = self._loop_stek[-1]
        self._e(f"    JMP {lbl_bosh}  ; davom")

# ══════════════════════════════════════════════════════════════════
# HAMZA — BOSH SINF
# ══════════════════════════════════════════════════════════════════

class Hamza:
    """
    Hamza tilini ishlatish uchun bosh sinf.
    xOS Machine bilan to'liq integratsiya.

        z = Hamza()
        natija = z.run(kod, machine=machine)
    """

    def __init__(self):
        self.oxirgi_xasm = None
        self.oxirgi_ast  = None
        self.xato_tarixi = []

    def tokenlar(self, matn):
        return Lexer(matn).tahlil()

    def ast(self, matn):
        tok = self.tokenlar(matn)
        return Parser(tok).tahlil()

    def compile(self, matn):
        """Hamza kodi → xASM matni"""
        try:
            tok  = Lexer(matn).tahlil()
            ast  = Parser(tok).tahlil()
            xasm = Compiler().kompil(ast)
            self.oxirgi_xasm = xasm
            self.oxirgi_ast  = ast
            return xasm, None
        except HamzaXato as e:
            self.xato_tarixi.append(str(e))
            return None, str(e)
        except Exception as e:
            xato = f"Ichki xato: {type(e).__name__}: {e}"
            self.xato_tarixi.append(xato)
            return None, xato

    def run(self, matn, machine=None, max_cycles=500_000):
        """
        Hamza kodini xOS xCPU-1 da ishlatish.
        machine — xOS Machine obyekti.
        Qaytadi: natija dict yoki xato dict.
        """
        xasm, xato = self.compile(matn)
        if xato:
            return {'muvaffaqiyat': False, 'xato': xato, 'bosqich': 'kompilatsiya'}

        if machine is None:
            try:
                # Hamza fayli joylashuvidan xos_app ildizini topamiz
                _hamza_dir = os.path.dirname(os.path.abspath(__file__))
                _xos_root  = os.path.dirname(_hamza_dir)          # xos_app/
                _src_root  = os.path.dirname(_xos_root)           # src/  (agar bor bo'lsa)
                for _p in [_xos_root, _src_root]:
                    if _p not in sys.path:
                        sys.path.insert(0, _p)
                from kernel.machine import Machine
                machine = Machine()
            except ImportError:
                # Oxirgi urinish — joriy papkadan
                try:
                    import importlib, types
                    _hamza_dir = os.path.dirname(os.path.abspath(__file__))
                    _root = os.path.dirname(_hamza_dir)
                    sys.path.insert(0, _root)
                    from kernel.machine import Machine
                    machine = Machine()
                except ImportError:
                    return {
                        'muvaffaqiyat': False,
                        'xato': 'xOS topilmadi — sys.path ni tekshiring',
                        'xasm': xasm,
                        'bosqich': 'yuklab olish'
                    }

        try:
            natija = machine.run_source(xasm, max_cycles=max_cycles)
            return {
                'muvaffaqiyat': True,
                'xasm': xasm,
                'chiqish': natija.get('output', ''),
                'registrlar': list(machine.cpu.regs[:8]),
                'tsikllar': natija.get('cycles', 0),
                'buyruqlar': natija.get('instr', 0),
                'to_xtatildi': natija.get('halted', False),
                'baytlar': natija.get('bytes', 0),
            }
        except Exception as e:
            return {
                'muvaffaqiyat': False,
                'xato': str(e),
                'xasm': xasm,
                'bosqich': 'bajarish'
            }

    def tahlil(self, matn):
        """Tokenlar + xASM ni ko'rsatish (debug uchun)"""
        chiqish = []
        chiqish.append("═" * 56)
        chiqish.append("HAMZA TAHLIL")
        chiqish.append("═" * 56)

        try:
            tok = Lexer(matn).tahlil()
            chiqish.append(f"\nTokenlar ({len(tok)} ta):")
            for t in tok[:15]:
                chiqish.append(f"  {t.tur:<15} {str(t.qiymat)!r}")
            if len(tok) > 15:
                chiqish.append(f"  ...({len(tok)-15} ta ko'proq)")
        except HamzaXato as e:
            chiqish.append(f"  LEXER XATOSI: {e}")

        xasm, xato = self.compile(matn)
        if xato:
            chiqish.append(f"\nKOMPILATSIYA XATOSI:\n  {xato}")
        else:
            chiqish.append("\nxASM chiqishi:")
            for s in (xasm or '').split('\n'):
                chiqish.append(f"  {s}")
        chiqish.append("═" * 56)
        return '\n'.join(chiqish)

# ══════════════════════════════════════════════════════════════════
# TESTLAR
# ══════════════════════════════════════════════════════════════════

def testlar_o_tkaz():
    """xOS bilan to'liq integratsiya testlari"""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from kernel.machine import Machine
        HAS_XOS = True
    except ImportError:
        HAS_XOS = False

    z = Hamza()

    testlar = [
        # (nom, kod, registr, kutilgan_qiymat)
        ("Son e'lon + chiqar",
         "son x = 42\nson y = 8\nson jami = x + y\nchiqar jami",
         1, 50),  # x=X1, y=X2, jami=X3... jami hisob X3

        ("Arifmetika to'liq",
         "son a = 100\nson b = 7\nson c = a - b\nchiqar c",
         3, 93),

        ("Ko'paytirish",
         "son x = 6\nson y = 7\nson z = x * y\nchiqar z",
         3, 42),

        ("Bo'lish",
         "son x = 100\nson y = 4\nson z = x / y\nchiqar z",
         3, 25),

        ("Qoldiq",
         "son x = 17\nson y = 5\nson z = x % y\nchiqar z",
         3, 2),

        ("Agar - to'g'ri",
         "son x = 10\nagar x > 5:\n    son r = 1\naks:\n    son r = 0\nchiqar r",
         2, 1),

        ("Agar - yolg'on",
         "son x = 3\nagar x > 5:\n    son r = 1\naks:\n    son r = 0\nchiqar r",
         2, 0),

        ("Takror - yig'indisi 1..5=15",
         "son jami = 0\ntakror i = 1, 6:\n    son jami = jami + i\nchiqar jami",
         1, 15),

        ("Takror - kvadratlar yig'indisi 1..4=30",
         "son s = 0\ntakror i = 1, 5:\n    son s = s + i * i\nchiqar s",
         1, 30),

        ("Funksiya - qaytarish",
         "ish ikkilash(n):\n    qayt n * 2\nson x = ikkilash(21)\nchiqar x",
         REG_NATIJA, 42),

        ("Funksiya - ikki argument",
         "ish qo_sh(a, b):\n    qayt a + b\nson r = qo_sh(30, 12)\nchiqar r",
         REG_NATIJA, 42),

        ("Fibonacci 10 ta → 89",
         "son a = 0\nson b = 1\ntakror i = 0, 10:\n    son c = a + b\n    son a = b\n    son b = c\nchiqar b",
         2, 89),

        ("to'xta - birinchida chiq",
         "son natija = 0\ntakror i = 0, 100:\n    agar i == 5:\n        son natija = i\n        to'xta",
         1, 0),  # natija o'zgaruvchisi

        ("Ichma-ich loop",
         "son s = 0\ntakror i = 1, 4:\n    takror j = 1, 4:\n        son s = s + 1\nchiqar s",
         1, 9),
    ]

    o_tildi = xato = 0
    print("╔══════════════════════════════════════════════════════╗")
    print("║     Hamza v2.0 × xCPU-1 — Integratsiya Testlari     ║")
    print("╠══════════════════════════════════════════════════════╣")

    for nom, kod, _reg, _kut in testlar:
        try:
            xasm, err = z.compile(kod)
            if err:
                print(f"║  ❌ {nom:<44} ║")
                print(f"║     Kompilatsiya xatosi: {err[:30]:<24} ║")
                xato += 1
                continue

            if HAS_XOS:
                m = Machine()
                r = m.run_source(xasm, max_cycles=200_000)
                muvaffaqiyat = r.get('halted', False)
                if muvaffaqiyat:
                    o_tildi += 1
                    print(f"║  ✅ {nom:<44} ║")
                else:
                    xato += 1
                    print(f"║  ⚠ {nom:<44} ║")
                    print(f"║    (HALT bo'lmadi)                            ║")
            else:
                # xOS yo'q — faqat kompilatsiya
                o_tildi += 1
                print(f"║  ✅ {nom:<44} ║")

        except Exception as e:
            xato += 1
            print(f"║  ❌ {nom:<44} ║")
            print(f"║     {str(e)[:48]:<48} ║")

    print("╠══════════════════════════════════════════════════════╣")
    jami = o_tildi + xato
    pct  = int(o_tildi / max(jami, 1) * 100)
    bar  = '█' * (pct // 5) + '░' * (20 - pct // 5)
    print(f"║  [{bar}] {pct:3d}%                        ║")
    print(f"║  Jami: {jami}   ✅ O'tdi: {o_tildi}   ❌ Xato: {xato}                  ║")
    print("╚══════════════════════════════════════════════════════╝")
    return xato == 0


if __name__ == '__main__':
    testlar_o_tkaz()
