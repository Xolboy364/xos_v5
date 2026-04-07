"""
xOS Brain — Reinforcement Learning Engine
==========================================
Haqiqiy RL: Brain o'zi kod yozadi, ishlatadi,
natijaga qarab o'zini mukofotlaydi/jazolaydi.

Arxitektura:
  ┌─────────────────────────────────────────────┐
  │           RL SIKLI                          │
  │  1. Agent   → Holat kuzatadi               │
  │  2. Policy  → Harakat tanlaydi (kod gen)   │
  │  3. Execute → Kodni ishlatadi               │
  │  4. Reward  → Natijani baholaydi            │
  │  5. Update  → Policy yangilanadi            │
  │  6. Expand  → Yaxshi natija → yangi shablon│
  └─────────────────────────────────────────────┘

Reward funksiyasi:
  +20  → Dastur to'g'ri to'xtadi (HALT)
  +15  → MIPS > 1.0
  +10  → Kod ixcham (instr < 50)
  +5   → Xotira muvozanatlangan
  -10  → Dastur to'xtamadi
  -15  → Kompilyatsiya xatosi
  -5   → MIPS < 0.1
"""

import math
import time
import random
import hashlib
from collections import deque


# ═══════════════════════════════════════════════
# EXPERIENCE — bir tajriba
# ═══════════════════════════════════════════════

class Experience:
    """Bitta RL tajribasi: holat → harakat → mukofot → yangi holat."""

    def __init__(self, state: dict, action: str, reward: float,
                 next_state: dict, done: bool = False):
        self.state      = state
        self.action     = action    # Generatsiya qilingan kod
        self.reward     = reward
        self.next_state = next_state
        self.done       = done
        self.ts         = time.time()

    def to_dict(self):
        return {
            'action_hash': hashlib.md5(self.action.encode()).hexdigest()[:8],
            'reward': round(self.reward, 3),
            'done': self.done,
            'ts': self.ts,
        }


# ═══════════════════════════════════════════════
# REPLAY BUFFER — tajribalar xotirasi
# ═══════════════════════════════════════════════

class ReplayBuffer:
    """
    Experience Replay — o'tgan tajribalardan o'rganish.
    Tasodifiy namuna olib, correlation ni kamaytiradi.
    """

    def __init__(self, capacity: int = 2000):
        self.buffer   = deque(maxlen=capacity)
        self.capacity = capacity

    def push(self, exp: Experience):
        self.buffer.append(exp)

    def sample(self, n: int) -> list:
        n = min(n, len(self.buffer))
        return random.sample(list(self.buffer), n)

    def best(self, n: int = 5) -> list:
        """Eng yaxshi mukofotli tajribalar."""
        sorted_buf = sorted(self.buffer, key=lambda e: -e.reward)
        return sorted_buf[:n]

    def avg_reward(self) -> float:
        if not self.buffer:
            return 0.0
        return sum(e.reward for e in self.buffer) / len(self.buffer)

    def __len__(self):
        return len(self.buffer)

    def stats(self) -> dict:
        if not self.buffer:
            return {'count': 0, 'avg_reward': 0, 'best_reward': 0, 'worst_reward': 0}
        rewards = [e.reward for e in self.buffer]
        return {
            'count':        len(self.buffer),
            'avg_reward':   round(sum(rewards) / len(rewards), 3),
            'best_reward':  round(max(rewards), 3),
            'worst_reward': round(min(rewards), 3),
        }


# ═══════════════════════════════════════════════
# REWARD FUNCTION
# ═══════════════════════════════════════════════

class RewardFunction:
    """
    Kod sifatini baholab mukofot hisoblaydi.
    Har qoida asosiy fizika kabi — o'zgarmaydigan.
    """

    def compute(self, run_result: dict, compile_error: bool = False) -> tuple:
        """
        Qaytaradi: (reward: float, breakdown: dict)
        """
        if compile_error:
            return -15.0, {'compile_error': -15.0}

        reward     = 0.0
        breakdown  = {}

        halted  = run_result.get('halted',   False)
        mips    = run_result.get('mips',     0.0)
        instr   = run_result.get('instr',    0)
        mem_r   = run_result.get('mem_reads', 0)
        mem_w   = run_result.get('mem_writes', 0)
        cycles  = run_result.get('cycles',   0)
        output  = run_result.get('output',   '')

        # To'xtadi?
        if halted:
            reward += 20.0
            breakdown['halted'] = +20.0
        else:
            reward -= 10.0
            breakdown['not_halted'] = -10.0

        # Tezlik
        if mips > 2.0:
            r = +15.0; breakdown['mips_great'] = r
        elif mips > 1.0:
            r = +10.0; breakdown['mips_good'] = r
        elif mips > 0.5:
            r = +5.0;  breakdown['mips_ok'] = r
        elif mips > 0.1:
            r = 0.0
        else:
            r = -5.0;  breakdown['mips_bad'] = r
        reward += r

        # Ixchamlik
        if 0 < instr <= 20:
            r = +10.0; breakdown['very_compact'] = r
        elif instr <= 50:
            r = +8.0;  breakdown['compact'] = r
        elif instr <= 200:
            r = +3.0;  breakdown['medium'] = r
        elif instr > 1000:
            r = -5.0;  breakdown['too_long'] = r
        else:
            r = 0.0
        reward += r

        # Chiqish bor?
        if output and len(output) > 0:
            reward += 5.0
            breakdown['has_output'] = +5.0

        # Xotira muvozanati
        if mem_r > 0 and mem_w > 0:
            ratio = mem_r / max(mem_w, 1)
            if 0.5 <= ratio <= 10:
                reward += 3.0
                breakdown['mem_balanced'] = +3.0

        # Nol instruksiya — hech narsa qilmadi
        if instr == 0:
            reward -= 20.0
            breakdown['no_instr'] = -20.0

        return round(reward, 2), breakdown


# ═══════════════════════════════════════════════
# POLICY — harakat tanlash strategiyasi
# ═══════════════════════════════════════════════

class Policy:
    """
    Epsilon-greedy policy:
    - epsilon ehtimollik bilan tasodifiy harakat
    - (1-epsilon) ehtimollik bilan eng yaxshi harakat
    Epsilon vaqt o'tishi bilan kamayadi (exploitation ↑).
    """

    def __init__(self, epsilon: float = 1.0, epsilon_min: float = 0.1,
                 epsilon_decay: float = 0.995):
        self.epsilon       = epsilon
        self.epsilon_min   = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.steps         = 0

        # Harakat turlari: qanday vazifalar generatsiya qilish
        self.action_space = [
            'fibonacci', 'factorial', 'count', 'sum',
            'gcd', 'power', 'primes', 'sort',
            'max', 'min', 'binary search', 'random walk',
            'multiply', 'hello',
        ]

        # Har harakat uchun Q-qiymat (o'rta mukofot)
        self.q_values  = {a: 0.0 for a in self.action_space}
        self.action_counts = {a: 0 for a in self.action_space}

    def select(self, state: dict = None) -> str:
        """Harakat tanlash (epsilon-greedy)."""
        self.steps += 1

        if random.random() < self.epsilon:
            # Exploration: tasodifiy
            return random.choice(self.action_space)
        else:
            # Exploitation: eng yaxshi Q-qiymatli
            return max(self.q_values, key=self.q_values.get)

    def update_q(self, action: str, reward: float, alpha: float = 0.1):
        """Q-qiymatni yangilash (incremental mean)."""
        if action not in self.q_values:
            self.q_values[action]      = 0.0
            self.action_counts[action] = 0

        self.action_counts[action] += 1
        n = self.action_counts[action]
        # Incremental mean: Q = Q + alpha * (reward - Q)
        self.q_values[action] += alpha * (reward - self.q_values[action])

    def decay_epsilon(self):
        """Epsilon ni kamaytirish."""
        self.epsilon = max(self.epsilon_min,
                          self.epsilon * self.epsilon_decay)

    def best_actions(self, n: int = 5) -> list:
        """Eng yaxshi harakatlar ro'yxati."""
        return sorted(self.q_values.items(), key=lambda x: -x[1])[:n]

    def stats(self) -> dict:
        return {
            'epsilon':    round(self.epsilon, 4),
            'steps':      self.steps,
            'best':       self.best_actions(3),
            'explored':   sum(1 for c in self.action_counts.values() if c > 0),
        }

    def save(self) -> dict:
        return {
            'epsilon':      self.epsilon,
            'steps':        self.steps,
            'q_values':     self.q_values,
            'action_counts':self.action_counts,
        }

    def load(self, d: dict):
        self.epsilon       = d.get('epsilon', self.epsilon)
        self.steps         = d.get('steps', 0)
        self.q_values      = d.get('q_values', self.q_values)
        self.action_counts = d.get('action_counts', self.action_counts)


# ═══════════════════════════════════════════════
# RL AGENT — asosiy RL agenti
# ═══════════════════════════════════════════════

class RLAgent:
    """
    Reinforcement Learning agenti.

    O'z-o'zini kengaytirish sikli:
      1. Holat → Policy → Harakat (vazifa tanlash)
      2. Generator → xASM kodi yaratish
      3. Machine → Kodni ishlatish
      4. Reward → Natijani baholash
      5. Q-update → Politikani yangilash
      6. Replay → O'tgan tajribalardan o'rganish
      7. Expand → Yaxshi kod → yangi shablon sifatida saqlash
    """

    def __init__(self, machine, generator, kb, nn):
        self.machine   = machine
        self.generator = generator
        self.kb        = kb
        self.nn        = nn

        self.policy    = Policy(epsilon=1.0, epsilon_min=0.15, epsilon_decay=0.993)
        self.reward_fn = RewardFunction()
        self.buffer    = ReplayBuffer(capacity=2000)

        self.episode         = 0
        self.total_reward    = 0.0
        self.best_reward     = -float('inf')
        self.best_action     = None
        self.best_code       = None
        self.success_count   = 0
        self.fail_count      = 0
        self.auto_expand_threshold = 30.0   # Bu mukofotdan yuqori → yangi shablon

        # Tarix
        self.reward_history = deque(maxlen=500)
        self.episode_log    = deque(maxlen=200)

    def _get_state(self) -> dict:
        """Joriy holat vektori."""
        kb    = self.kb.stats()
        buf   = self.buffer.stats()
        nn_st = self.nn.stats()
        return {
            'patterns':    kb['patterns'],
            'rules':       kb['rules'],
            'programs':    kb['programs'],
            'avg_reward':  buf.get('avg_reward', 0),
            'epsilon':     self.policy.epsilon,
            'nn_loss':     nn_st['avg_loss'],
            'episode':     self.episode,
        }

    def run_episode(self) -> dict:
        """
        Bitta RL epizodi:
        Harakat tanlash → Kod gen → Ishlatish → Mukofot → Yangilash
        """
        self.episode += 1

        # 1. Holat
        state = self._get_state()

        # 2. Harakat tanlash (qaysi vazifani generatsiya qilish)
        action = self.policy.select(state)

        # 3. Kod generatsiya
        try:
            code = self.generator.generate(action)
            compile_error = False
        except Exception as e:
            code = ""
            compile_error = True

        # 4. Kodni ishlatish
        run_result = {}
        if not compile_error and code.strip():
            try:
                run_result = self.machine.run_source(code, max_cycles=500_000)
            except Exception as e:
                compile_error = True
                run_result = {}

        # 5. Mukofot hisoblash
        reward, breakdown = self.reward_fn.compute(run_result, compile_error)
        self.total_reward += reward
        self.reward_history.append(reward)

        # 6. Yangi holat
        next_state = self._get_state()

        # 7. Tajriba saqlash
        exp = Experience(state, code, reward, next_state, done=True)
        self.buffer.push(exp)

        # 8. Q-qiymat yangilash
        self.policy.update_q(action, reward)
        self.policy.decay_epsilon()

        # 9. NN o'qitish (replay)
        if len(self.buffer) >= 8:
            self._replay_train(batch_size=8)

        # 10. Eng yaxshi natija?
        if reward > self.best_reward:
            self.best_reward = reward
            self.best_action = action
            self.best_code   = code

        # 11. Yaxshi kod → yangi shablon sifatida saqlash
        if reward >= self.auto_expand_threshold and not compile_error and code:
            self._auto_expand(action, code, reward)
            self.success_count += 1
        elif reward < 0:
            self.fail_count += 1

        # Log
        log_entry = {
            'episode':  self.episode,
            'action':   action,
            'reward':   reward,
            'epsilon':  round(self.policy.epsilon, 4),
            'halted':   run_result.get('halted', False),
            'instr':    run_result.get('instr', 0),
            'mips':     run_result.get('mips', 0),
            'breakdown': breakdown,
        }
        self.episode_log.append(log_entry)

        return log_entry

    def _replay_train(self, batch_size: int = 8):
        """Replay buffer dan o'qitish — to'g'ri normalizatsiya bilan."""
        batch = self.buffer.sample(batch_size)
        for exp in batch:
            s = exp.next_state
            avg_r = s.get('avg_reward', 0.0)

            # KB statistikalarini 0..1 ga to'g'ri normalize qilish
            # (CPU regs uchun 2^31 emas, KB uchun mos shkala)
            patterns_n  = min(1.0, s.get('patterns', 0)  / 1000.0)
            rules_n     = min(1.0, s.get('rules', 0)     / 500.0)
            programs_n  = min(1.0, s.get('programs', 0)  / 100.0)
            episode_n   = min(1.0, s.get('episode', 0)   / 2000.0)
            avg_r_n     = max(0.0, min(1.0, (avg_r + 20.0) / 70.0))  # -20..+50 → 0..1
            nn_loss_n   = max(0.0, min(1.0, 1.0 - s.get('nn_loss', 0.5) * 10))
            epsilon_n   = max(0.0, min(1.0, s.get('epsilon', 1.0)))

            features = {
                'opcode':  int(patterns_n * 64),      # 0..64 oraliq
                'cycles':  int(episode_n  * 1000000), # 0..1M oraliq
                'mips':    avg_r_n * 10.0,            # 0..10 oraliq
                'mem_ops': int(rules_n   * 1000),     # 0..1000 oraliq
                'regs': [
                    int(patterns_n  * 2**31),  # endi to'g'ri shkala
                    int(rules_n     * 2**31),
                    int(programs_n  * 2**31),
                    int(episode_n   * 2**31),
                    int(avg_r_n     * 2**31),
                    int(nn_loss_n   * 2**31),
                    int(epsilon_n   * 2**31),
                ],
                'flags': (
                    ('N' if avg_r < 0    else '-') +
                    ('Z' if avg_r == 0   else '-') +
                    ('C' if epsilon_n < 0.3 else '-') +  # exploitation fazasi
                    ('V' if programs_n > 0.5 else '-')   # dasturlar to'lib bormoqda
                ),
            }

            out_neurons = list(self.nn.output_layer.neurons.keys())
            # Reward -15..+53 → 0..1
            norm_reward = max(0.0, min(1.0, (exp.reward + 15) / 68.0))

            # Har neyron uchun semantik target
            target = {}
            for i, nid in enumerate(out_neurons):
                if i == 0:   target[nid] = norm_reward          # asosiy reward signal
                elif i == 1: target[nid] = avg_r_n              # o'rtacha mukofot
                elif i == 2: target[nid] = epsilon_n            # exploration darajasi
                elif i == 3: target[nid] = programs_n           # KB boyishi
                elif i == 4: target[nid] = patterns_n           # pattern o'sishi
                elif i == 5: target[nid] = rules_n              # qoidalar soni
                elif i == 6: target[nid] = nn_loss_n            # NN sifati
                else:
                    target[nid] = norm_reward  # qolganlar reward ni kuchaytiradi
            self.nn.train(features, target)

    def _auto_expand(self, action: str, code: str, reward: float):
        """
        Yaxshi kod → KB ga yangi shablon sifatida saqlash.
        Bir xil action uchun maksimal 3 ta shablon.
        To'lganda eng past reward li eskisini almashtiradi.
        Reward qiymati to'g'ridan dastur kommentiga yoziladi — indeks xatosi yo'q.
        """
        prefix = f"rl_{action.replace(' ', '_')}_"
        existing = {k: v for k, v in self.kb.programs.items() if k.startswith(prefix)}

        new_name = f"{prefix}{self.episode}"
        new_code = f"; 🤖 RL reward={reward:.1f} ep={self.episode}\n{code}"

        if len(existing) < 3:
            self.kb.programs[new_name] = new_code
        else:
            # Eng past reward li eskisini topish (kommentdan o'qish)
            worst_key = None
            worst_r = float('inf')
            for k, v in existing.items():
                # Birinchi qatordan reward ni o'qish: "; 🤖 RL reward=28.5 ep=7"
                first_line = v.split('\n')[0] if v else ''
                try:
                    r_str = first_line.split('reward=')[1].split(' ')[0]
                    r_val = float(r_str)
                except (IndexError, ValueError):
                    r_val = 0.0
                if r_val < worst_r:
                    worst_r = r_val
                    worst_key = k
            # Yangi reward eskidan yaxshiroq bo'lsagina almashtir
            if worst_key and reward > worst_r:
                del self.kb.programs[worst_key]
                self.kb.programs[new_name] = new_code

        # Qoida qo'shish yoki yangilash
        self.kb.add_rule(
            f"RL '{action}' yaxshi (ep={self.episode})",
            f"'{action}' ishonchli: reward={reward:.1f}",
            conf=min(0.95, 0.5 + reward / 100),
            priority=3
        )

    def run_n_episodes(self, n: int, verbose: bool = False) -> dict:
        """N ta epizod ishlatish."""
        results = []
        for i in range(n):
            r = self.run_episode()
            results.append(r)
            if verbose:
                print(f"  Ep {r['episode']:4d} | {r['action']:15s} | "
                      f"R={r['reward']:+6.1f} | ε={r['epsilon']:.3f} | "
                      f"instr={r['instr']:4d} | {'✅' if r['halted'] else '❌'}")

        rewards = [r['reward'] for r in results]
        return {
            'episodes':    n,
            'avg_reward':  round(sum(rewards)/max(len(rewards),1), 3),
            'max_reward':  round(max(rewards), 3),
            'min_reward':  round(min(rewards), 3),
            'success_rate':round(sum(1 for r in rewards if r > 0)/max(len(rewards),1)*100, 1),
            'best_action': self.best_action,
            'new_programs':self.success_count,
        }

    def avg_recent_reward(self, n: int = 20) -> float:
        if not self.reward_history:
            return 0.0
        recent = list(self.reward_history)[-n:]
        return round(sum(recent) / len(recent), 3)

    def status_str(self) -> str:
        buf  = self.buffer.stats()
        pol  = self.policy.stats()
        lines = [
            f"  RL Agent:",
            f"    Epizodlar    : {self.episode}",
            f"    Jami mukofot : {round(self.total_reward, 1)}",
            f"    O'rt mukofot : {self.avg_recent_reward(20)} (oxirgi 20)",
            f"    Eng yaxshi   : {round(self.best_reward, 1)} ({self.best_action})",
            f"    Epsilon (ε)  : {round(self.policy.epsilon, 4)}",
            f"    Muvaffaqiyat : {self.success_count} ta yangi shablon",
            f"    Xatolik      : {self.fail_count}",
            f"    Replay buffer: {buf['count']} tajriba",
            f"    Top harakatlar:",
        ]
        for action, q in pol['best']:
            lines.append(f"      {action:20s} Q={q:+.2f}")
        return "\n".join(lines)

    def save(self) -> dict:
        return {
            'episode':      self.episode,
            'total_reward': self.total_reward,
            'best_reward':  self.best_reward,
            'best_action':  self.best_action,
            'success_count':self.success_count,
            'fail_count':   self.fail_count,
            'policy':       self.policy.save(),
            'buffer_stats': self.buffer.stats(),
        }

    def load(self, d: dict):
        self.episode       = d.get('episode', 0)
        self.total_reward  = d.get('total_reward', 0.0)
        self.best_reward   = d.get('best_reward', -float('inf'))
        self.best_action   = d.get('best_action', None)
        self.success_count = d.get('success_count', 0)
        self.fail_count    = d.get('fail_count', 0)
        if 'policy' in d:
            self.policy.load(d['policy'])
