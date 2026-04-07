"""
xOS Brain — Fon O'rganish Mexanizmi v1.0
==========================================
Brain ilova yopiq bo'lganda ham o'rganadi.
Threading orqali parallel ishlaydi.

Rejalar:
  1. Fon RL trening  — har N daqiqada epizodlar
  2. O'z-o'zini sinash — yozgan kodlarini sinaydi
  3. Bilim sintezi  — patternlardan yangi qoidalar
  4. Davriy saqlash — holat diskka saqlanadi

Android da:
  - Ilova fonda bo'lsa ham ishlaydi
  - Batareya tejash uchun interval uzayadi
  - Wakelock orqali uxlamaslik ta'minlanadi
"""

import threading
import time
import random
from collections import deque


# ═══════════════════════════════════════════════
# FON O'RGANISH REJASI
# ═══════════════════════════════════════════════

class LearningSchedule:
    """
    Brain fon o'rganish jadvalini boshqaradi.
    Telefon holati va vaqtga qarab moslashadi.
    """

    def __init__(self):
        # Daqiqada bir bajarish intervallari
        self.rl_interval      = 2.0    # RL epizod har 2 min
        self.synthesis_interval = 10.0  # Bilim sintezi har 10 min
        self.save_interval    = 5.0    # Saqlash har 5 min
        self.self_test_interval = 15.0  # O'z-o'zini sinash har 15 min

        self._last_rl       = 0.0
        self._last_synth    = 0.0
        self._last_save     = 0.0
        self._last_selftest = 0.0

    def should_rl(self) -> bool:
        now = time.time()
        if now - self._last_rl >= self.rl_interval * 60:
            self._last_rl = now
            return True
        return False

    def should_synthesize(self) -> bool:
        now = time.time()
        if now - self._last_synth >= self.synthesis_interval * 60:
            self._last_synth = now
            return True
        return False

    def should_save(self) -> bool:
        now = time.time()
        if now - self._last_save >= self.save_interval * 60:
            self._last_save = now
            return True
        return False

    def should_self_test(self) -> bool:
        now = time.time()
        if now - self._last_selftest >= self.self_test_interval * 60:
            self._last_selftest = now
            return True
        return False

    def set_power_save(self, on: bool):
        """Batareya tejash rejimi — intervallar uzayadi."""
        if on:
            self.rl_interval      = 10.0
            self.synthesis_interval = 30.0
            self.save_interval    = 15.0
        else:
            self.rl_interval      = 2.0
            self.synthesis_interval = 10.0
            self.save_interval    = 5.0


# ═══════════════════════════════════════════════
# BILIM SINTEZI
# ═══════════════════════════════════════════════

class KnowledgeSynthesizer:
    """
    Mavjud bilimlardan yangi bilimlar hosil qiladi.
    Bola maktabda o'qiganlarini uyda o'ylab ko'rib,
    yangi narsalarni o'zi kashf etgani kabi.
    """

    def __init__(self, kb, nn):
        self.kb = kb
        self.nn = nn
        self.synthesis_count = 0

    def synthesize(self) -> list:
        """Yangi bilimlar hosil qiladi, ro'yxat qaytaradi."""
        results = []
        self.synthesis_count += 1

        # 1. Patternlardan qoidalar chiqarish
        r1 = self._patterns_to_rules()
        if r1:
            results.append(r1)

        # 2. Dasturlarni tahlil qilib yangi bilim olish
        r2 = self._analyze_programs()
        if r2:
            results.append(r2)

        # 3. Qoidalarni birlashtirish (meta-qoida)
        r3 = self._combine_rules()
        if r3:
            results.append(r3)

        # 4. NN ni yangi ma'lumotlar bilan o'qitish
        r4 = self._retrain_nn()
        if r4:
            results.append(r4)

        return results

    def _patterns_to_rules(self) -> str:
        """Kuchli patternlardan qoidalar hosil qiladi."""
        strong = [p for p in self.kb.patterns.values() if p.hits >= 5]
        if not strong:
            return ''
        p = random.choice(strong)
        rule = self.kb.add_rule(
            f"Pattern '{p.id[:8]}' ko'p ishlatilgan ({p.hits}x)",
            f"Ketma-ketlik {str(p.sequence)[:40]} samarali",
            conf=min(0.9, 0.3 + p.hits * 0.05),
            priority=2
        )
        return f"Qoida: {rule.id[:8]} (pattern {p.id[:8]})"

    def _analyze_programs(self) -> str:
        """Dasturlarni tahlil qilib, xususiyatlar o'rganadi."""
        if not self.kb.programs:
            return ''
        name, code = random.choice(list(self.kb.programs.items()))
        lines = [l.strip() for l in code.splitlines()
                 if l.strip() and not l.strip().startswith(';')]
        has_loop = any(l.upper().startswith(('JEQ','JNE','JLT','JGT','JLE','JGE')) for l in lines)
        has_call = any(l.upper().startswith('CALL') for l in lines)
        instr_count = sum(1 for l in lines if not l.startswith('.') and not l.endswith(':'))

        if has_loop and has_call:
            self.kb.add_rule(
                f"'{name}' loop+call ishlatadi",
                "Rekursiv loop samarali",
                conf=0.75, priority=2
            )
            return f"Tahlil: '{name}' → rekursiv loop"
        elif has_loop:
            self.kb.add_rule(
                f"'{name}' {instr_count} instruksiya",
                "Loop dasturlari ixcham bo'ladi",
                conf=0.70, priority=1
            )
            return f"Tahlil: '{name}' → {instr_count} instr loop"
        return ''

    def _combine_rules(self) -> str:
        """Ikkita qoidani birlashtiradi."""
        top = self.kb.top_rules(6)
        if len(top) < 2:
            return ''
        r1, r2 = random.sample(top, 2)
        meta_rule = self.kb.add_rule(
            f"[SYN] {r1.condition[:30]} + {r2.condition[:30]}",
            f"[SYN] {r1.action[:30]} → {r2.action[:30]}",
            conf=min(0.85, (r1.confidence + r2.confidence) / 2),
            priority=max(r1.priority, r2.priority) + 1
        )
        return f"Meta-qoida: {meta_rule.id[:8]}"

    def _retrain_nn(self) -> str:
        """KB statistikasi bilan NNni qayta o'qitadi."""
        kb = self.kb.stats()
        patterns_n = min(1.0, kb['patterns'] / 200.0)
        rules_n    = min(1.0, kb['rules'] / 100.0)
        programs_n = min(1.0, kb['programs'] / 50.0)

        features = {
            'opcode': int(patterns_n * 64),
            'cycles': int(rules_n * 1_000_000),
            'mips':   programs_n * 10.0,
            'mem_ops': kb['history'],
            'regs': [int(patterns_n * 2**31), int(rules_n * 2**31),
                     int(programs_n * 2**31)] + [0] * 13,
            'flags': 'NZCV' if patterns_n > 0.5 else '----',
        }
        out_neurons = list(self.nn.output_layer.neurons.keys())
        target = {}
        for i, nid in enumerate(out_neurons):
            if i == 0:   target[nid] = patterns_n
            elif i == 1: target[nid] = rules_n
            elif i == 2: target[nid] = programs_n
            else:        target[nid] = (patterns_n + rules_n) / 2

        self.nn.train(features, target)
        return f"NN qayta o'qitildi: loss={self.nn.avg_loss():.6f}"


# ═══════════════════════════════════════════════
# O'Z-O'ZINI SINASH
# ═══════════════════════════════════════════════

class SelfTester:
    """
    Brain o'zi yozgan dasturlarni o'zi sinaydi.
    Xato topsa, o'zidan o'zi o'rganadi.
    """

    def __init__(self, brain):
        self.brain = brain
        self.test_count = 0
        self.pass_count = 0
        self.fail_count = 0
        self.log = deque(maxlen=200)

    def run_self_test(self) -> dict:
        """Tasodifiy bir dasturni sinaydi."""
        if not self.brain.kb.programs:
            return {'status': 'skip', 'reason': 'dastur yo\'q'}

        name, code = random.choice(list(self.brain.kb.programs.items()))
        self.test_count += 1

        try:
            # Machine orqali sinash
            machine = self.brain.machine
            if machine is None:
                return {'status': 'skip', 'reason': 'machine yo\'q'}

            result = machine.run_source(code, max_cycles=100_000)
            halted = result.get('halted', False)
            instr  = result.get('instr', 0)
            mips   = result.get('mips', 0)

            if halted and instr > 0:
                self.pass_count += 1
                # Yaxshi natija → o'rgan
                self.brain.learn_from_run(result, code)
                entry = {
                    'program': name, 'status': 'pass',
                    'instr': instr, 'mips': mips,
                    'ts': time.time()
                }
            else:
                self.fail_count += 1
                entry = {
                    'program': name, 'status': 'fail',
                    'halted': halted, 'instr': instr,
                    'ts': time.time()
                }

            self.log.append(entry)
            return entry

        except Exception as e:
            self.fail_count += 1
            entry = {'program': name, 'status': 'error', 'error': str(e)[:100]}
            self.log.append(entry)
            return entry

    def stats(self) -> dict:
        rate = self.pass_count / max(self.test_count, 1) * 100
        return {
            'tests': self.test_count,
            'pass':  self.pass_count,
            'fail':  self.fail_count,
            'rate':  round(rate, 1),
        }


# ═══════════════════════════════════════════════
# FON O'RGANISH MEXANIZMI — Asosiy sinf
# ═══════════════════════════════════════════════

class BackgroundLearner:
    """
    Brain fon rejimida o'rganishini boshqaradi.

    Ishga tushirish:
        learner = BackgroundLearner(brain, store)
        learner.start()

    To'xtatish:
        learner.stop()
    """

    def __init__(self, brain, store, check_interval: float = 30.0):
        """
        brain          — Brain obyekti
        store          — PersistentStore obyekti
        check_interval — Har necha sekundda tekshiradi (default: 30s)
        """
        self.brain          = brain
        self.store          = store
        self.check_interval = check_interval

        self.schedule    = LearningSchedule()
        self.synthesizer = KnowledgeSynthesizer(brain.kb, brain.nn)
        self.tester      = SelfTester(brain)

        self._thread  = None
        self._running = False
        self._paused  = False

        # Statistika
        self.total_rl_episodes  = 0
        self.total_syntheses    = 0
        self.total_self_tests   = 0
        self.total_saves        = 0
        self.start_time         = None
        self.activity_log       = deque(maxlen=500)

    def start(self) -> bool:
        """Fon o'rganishni boshlaydi."""
        if self._running:
            return False
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop,
            name='BrainBackgroundLearner',
            daemon=True          # Ilova yopilsa thread ham to'xtaydi
        )
        self._thread.start()
        self.start_time = time.time()
        self.store.diary.log('bg_start', {
            'check_interval': self.check_interval,
            'msg': 'Fon o\'rganish boshlandi'
        })
        return True

    def stop(self):
        """Fon o'rganishni to'xtatadi va saqlaydi."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        # Oxirgi saqlash
        self.store.save_brain(self.brain)
        self.store.diary.log('bg_stop', {
            'total_rl': self.total_rl_episodes,
            'total_synth': self.total_syntheses,
            'msg': 'Fon o\'rganish to\'xtatildi'
        })

    def pause(self):
        """To'xtatmasdan pauza qiladi."""
        self._paused = True

    def resume(self):
        """Pauzadan davom ettiradi."""
        self._paused = False

    def set_power_save(self, on: bool):
        """Batareya tejash rejimi."""
        self.schedule.set_power_save(on)

    def _loop(self):
        """Asosiy fon sikli."""
        while self._running:
            if not self._paused:
                self._tick()
            time.sleep(self.check_interval)

    def _tick(self):
        """Bir fon tsikli."""
        try:
            # 1. RL Trening
            if self.schedule.should_rl() and self.brain.rl_available():
                self._do_rl()

            # 2. Bilim sintezi
            if self.schedule.should_synthesize():
                self._do_synthesis()

            # 3. O'z-o'zini sinash
            if self.schedule.should_self_test():
                self._do_self_test()

            # 4. Saqlash
            if self.schedule.should_save():
                self._do_save()

        except Exception as e:
            self._log_activity('error', f"Fon xatosi: {str(e)[:100]}")

    def _do_rl(self):
        """Fon RL trening."""
        n = random.randint(3, 8)  # 3-8 epizod
        try:
            result = self.brain.rl_train(n)
            self.total_rl_episodes += n
            self._log_activity('rl', (
                f"RL {n} ep | "
                f"avg={result.get('avg_reward', '?')} | "
                f"success={result.get('success_rate', '?')}%"
            ))
        except Exception as e:
            self._log_activity('rl_error', str(e)[:80])

    def _do_synthesis(self):
        """Bilim sintezi."""
        results = self.synthesizer.synthesize()
        self.total_syntheses += 1
        if results:
            self._log_activity('synthesis', ' | '.join(results[:3]))
        else:
            self._log_activity('synthesis', 'Yangi bilim topilmadi')

    def _do_self_test(self):
        """O'z-o'zini sinash."""
        result = self.tester.run_self_test()
        self.total_self_tests += 1
        status = result.get('status', '?')
        prog   = result.get('program', '?')
        self._log_activity('self_test', f"'{prog}' → {status}")

    def _do_save(self):
        """Holat saqlash."""
        ok = self.store.save_brain(self.brain)
        self.total_saves += 1
        self._log_activity('save', '✅ saqlandi' if ok else '❌ saqlash xato')

    def _log_activity(self, activity_type: str, message: str):
        """Faollik logi."""
        entry = {
            'ts': time.time(),
            'time_str': time.strftime('%H:%M:%S'),
            'type': activity_type,
            'msg': message,
        }
        self.activity_log.append(entry)
        # Kundaliqa ham yozamiz
        self.store.diary.log(f'bg_{activity_type}', {'msg': message})

    def status(self) -> str:
        """Fon o'rganish holati."""
        if not self.start_time:
            return "⏸ Fon o'rganish ishga tushmagan"

        uptime = time.time() - self.start_time
        h = int(uptime // 3600)
        m = int((uptime % 3600) // 60)
        s = int(uptime % 60)

        state = '🟢 Faol' if (self._running and not self._paused) else ('⏸ Pauza' if self._paused else '🔴 To\'xtagan')
        tester = self.tester.stats()

        lines = [
            f"🤖 Fon O'rganish:",
            f"  Holat        : {state}",
            f"  Ishlash vaqti: {h:02d}:{m:02d}:{s:02d}",
            f"  RL epizodlar : {self.total_rl_episodes}",
            f"  Sintezlar    : {self.total_syntheses}",
            f"  O'z testlar  : {self.total_self_tests} ({tester['rate']}% pass)",
            f"  Saqlashlar   : {self.total_saves}",
        ]

        # Oxirgi 3 faollik
        recent = list(self.activity_log)[-3:]
        if recent:
            lines.append("  Oxirgi:")
            for a in recent:
                lines.append(f"    [{a['time_str']}] {a['type']}: {a['msg'][:50]}")

        return '\n'.join(lines)

    def recent_activity(self, n: int = 20) -> list:
        """Oxirgi N ta faollik."""
        return list(self.activity_log)[-n:]
