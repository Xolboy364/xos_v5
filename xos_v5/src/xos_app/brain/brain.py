"""
xOS Brain v3.0 — Android Edition
====================================
100% offline. Hech qanday API kerak emas.
Haqiqiy neyron tarmoq (3 qatlam, backprop),
Pattern ML, Rule Engine, Episodik xotira,
Genetik kengaytirish, Critic tizimi,
+ To'liq Reinforcement Learning (v3 dan olingan).
"""

import json, math, time, random, hashlib, re
from collections import defaultdict, deque

# RL Engine — brain/ papkasida (to'g'ri yo'l)
try:
    from .rl_engine import RLAgent, ReplayBuffer, Policy, RewardFunction
    _RL_AVAILABLE = True
except ImportError:
    try:
        from rl_engine import RLAgent, ReplayBuffer, Policy, RewardFunction
        _RL_AVAILABLE = True
    except ImportError:
        _RL_AVAILABLE = False

# Persistent xotira va fon o'rganish
try:
    from .persistent import PersistentStore
    from .background import BackgroundLearner
    _PERSISTENT_AVAILABLE = True
except ImportError:
    try:
        from persistent import PersistentStore
        from background import BackgroundLearner
        _PERSISTENT_AVAILABLE = True
    except ImportError:
        _PERSISTENT_AVAILABLE = False


# ═══════════════════════════════════════════════
# NEURON
# ═══════════════════════════════════════════════

class Neuron:
    def __init__(self, nid, activation='relu'):
        self.id = nid
        self.activation = activation
        self.bias = random.gauss(0, 0.1)
        self.weights = {}
        self.value = 0.0
        self.fire_count = 0
        self.reward_sum = 0.0
        self.memory = deque(maxlen=500)

    def activate(self, x):
        self.fire_count += 1
        self.memory.append(x)
        if self.activation == 'relu':
            r = x if x > 0 else 0.01 * x
        elif self.activation == 'sigmoid':
            r = 1.0 / (1.0 + math.exp(-max(-500, min(500, x))))
        elif self.activation == 'tanh':
            r = math.tanh(x)
        else:
            r = x
        self.value = r
        return r

    def forward(self, inputs):
        total = self.bias
        for nid, w in self.weights.items():
            if nid in inputs:
                total += inputs[nid] * w
        return self.activate(total)

    def learn(self, signal, rate=0.01):
        self.bias += rate * signal
        self.bias = max(-3.0, min(3.0, self.bias))
        self.reward_sum += signal

    def update_weight(self, src_id, src_val, grad, rate=0.01):
        if src_id not in self.weights:
            self.weights[src_id] = random.gauss(0, 0.1)
        delta = rate * grad * src_val
        self.weights[src_id] += delta
        self.weights[src_id] = max(-2.0, min(2.0, self.weights[src_id]))

    def to_dict(self):
        return {'id': self.id, 'bias': round(self.bias, 6),
                'weights': {k: round(v, 6) for k, v in list(self.weights.items())[:20]},
                'fire_count': self.fire_count, 'reward': round(self.reward_sum, 4)}

    @classmethod
    def from_dict(cls, d):
        n = cls(d['id'])
        n.bias = d.get('bias', 0.0)
        n.weights = d.get('weights', {})
        n.fire_count = d.get('fire_count', 0)
        n.reward_sum = d.get('reward', 0.0)
        return n


class Layer:
    def __init__(self, name, size, activation='relu'):
        self.name = name
        self.activation = activation
        self.neurons = {f"{name}_{i}": Neuron(f"{name}_{i}", activation) for i in range(size)}
        self.output = {}
        self.input_ids = []

    def connect(self, prev, scale=0.1):
        self.input_ids = list(prev.neurons.keys())
        for n in self.neurons.values():
            for sid in self.input_ids:
                n.weights[sid] = random.gauss(0, scale)

    def forward(self, inputs):
        self.output = {nid: n.forward(inputs) for nid, n in self.neurons.items()}
        return self.output

    def backward(self, grads, prev_out, rate=0.01):
        for nid, n in self.neurons.items():
            g = grads.get(nid, 0.0)
            n.learn(g, rate)
            for sid, sv in prev_out.items():
                n.update_weight(sid, sv, g, rate)

    def add_neuron(self, activation='relu'):
        idx = len(self.neurons)
        nid = f"{self.name}_{idx}"
        n = Neuron(nid, activation)
        for sid in self.input_ids:
            n.weights[sid] = random.gauss(0, 0.1)
        self.neurons[nid] = n
        return n

    def stats(self):
        return {'count': len(self.neurons),
                'avg_bias': round(sum(n.bias for n in self.neurons.values()) / max(len(self.neurons), 1), 4),
                'total_fires': sum(n.fire_count for n in self.neurons.values())}


class NeuralNetwork:
    def __init__(self, inp=32, h1=64, h2=32, out=16):
        self.input_layer = Layer('inp', inp, 'linear')
        self.hidden1 = Layer('h1', h1, 'relu')
        self.hidden2 = Layer('h2', h2, 'relu')
        self.output_layer = Layer('out', out, 'sigmoid')
        self.hidden1.connect(self.input_layer)
        self.hidden2.connect(self.hidden1)
        self.output_layer.connect(self.hidden2)
        self.learn_rate = 0.001
        self.iterations = 0
        self.loss_history = deque(maxlen=1000)
        self._lr_decay = 0.9999
        self._min_lr = 0.0001

    def _encode(self, features):
        inp = {}
        neurons = list(self.input_layer.neurons.keys())
        vals = [
            features.get('opcode', 0) / 64.0,
            min(1.0, features.get('cycles', 0) / 1000000.0),
            min(1.0, features.get('mips', 0) / 10.0),
            min(1.0, features.get('mem_ops', 0) / 1000.0),
        ]
        regs = features.get('regs', [])
        for i, r in enumerate(regs[:16]):
            vals.append(min(1.0, abs(r) / (2**31)))
        flags = features.get('flags', '----')
        for c in flags[:4]:
            vals.append(1.0 if c != '-' else 0.0)
        for i, nid in enumerate(neurons):
            inp[nid] = vals[i] if i < len(vals) else 0.0
        return inp

    def forward(self, features):
        inp = self._encode(features)
        self.input_layer.output = inp
        h1 = self.hidden1.forward(inp)
        h2 = self.hidden2.forward(h1)
        out = self.output_layer.forward(h2)
        self.iterations += 1
        return out

    def backward(self, output, target):
        grad_out = {}
        loss = 0.0
        for nid in output:
            err = target.get(nid, 0.0) - output[nid]
            grad_out[nid] = err
            loss += err * err
        self.loss_history.append(loss / max(len(output), 1))
        self.learn_rate = max(self._min_lr, self.learn_rate * self._lr_decay)
        self.output_layer.backward(grad_out, self.hidden2.output, self.learn_rate)
        grad_h2 = {}
        for h2id in self.hidden2.neurons:
            grad_h2[h2id] = sum(
                self.output_layer.neurons[oid].weights.get(h2id, 0) * grad_out.get(oid, 0)
                for oid in self.output_layer.neurons)
        self.hidden2.backward(grad_h2, self.hidden1.output, self.learn_rate)
        grad_h1 = {}
        for h1id in self.hidden1.neurons:
            grad_h1[h1id] = sum(
                self.hidden2.neurons[h2id].weights.get(h1id, 0) * grad_h2.get(h2id, 0)
                for h2id in self.hidden2.neurons)
        self.hidden1.backward(grad_h1, self.input_layer.output, self.learn_rate)

    def train(self, features, target):
        out = self.forward(features)
        self.backward(out, target)
        return out

    def predict(self, features):
        return self.forward(features)

    def avg_loss(self):
        return sum(self.loss_history) / len(self.loss_history) if self.loss_history else 0.0

    def expand_hidden(self, n=8):
        for _ in range(n):
            self.hidden1.add_neuron('relu')
            self.hidden2.add_neuron('relu')

    def stats(self):
        return {'iterations': self.iterations, 'avg_loss': round(self.avg_loss(), 6),
                'learn_rate': round(self.learn_rate, 6),
                'layers': {'input': self.input_layer.stats(), 'hidden1': self.hidden1.stats(),
                           'hidden2': self.hidden2.stats(), 'output': self.output_layer.stats()}}

    def save(self):
        def ld(l): return {nid: n.to_dict() for nid, n in l.neurons.items()}
        return {'hidden1': ld(self.hidden1), 'hidden2': ld(self.hidden2),
                'output': ld(self.output_layer), 'lr': self.learn_rate, 'iter': self.iterations}

    def load(self, d):
        def rl(l, data):
            for nid, nd in data.items():
                if nid in l.neurons:
                    n = l.neurons[nid]; n.bias = nd.get('bias', 0); n.weights = nd.get('weights', {})
                else:
                    l.neurons[nid] = Neuron.from_dict(nd)
        rl(self.hidden1, d.get('hidden1', {}))
        rl(self.hidden2, d.get('hidden2', {}))
        rl(self.output_layer, d.get('output', {}))
        self.learn_rate = d.get('lr', self.learn_rate)
        self.iterations = d.get('iter', 0)


# ═══════════════════════════════════════════════
# PATTERN ENGINE
# ═══════════════════════════════════════════════

class Pattern:
    def __init__(self, pid, seq, tags=None):
        self.id = pid; self.sequence = seq; self.hits = 0; self.score = 0.0
        self.tags = set(tags or []); self.outcomes = []; self.born_at = time.time()
        self.last_seen = time.time()

    def update(self, outcome=None):
        self.hits += 1; self.last_seen = time.time()
        if outcome: self.outcomes.append(outcome)
        if len(self.outcomes) > 100: self.outcomes = self.outcomes[-100:]
        self.score = math.log1p(self.hits) * (1 + len(self.tags) * 0.2)

    def to_dict(self):
        return {'id': self.id, 'seq': self.sequence, 'hits': self.hits,
                'score': round(self.score, 3), 'tags': list(self.tags)}


class PatternEngine:
    def __init__(self, kb):
        self.kb = kb; self.window = deque(maxlen=16)
        self.bigrams = defaultdict(int); self.trigrams = defaultdict(int)
        self.fourgrams = defaultdict(int); self.total = 0; self.anomalies = []

    def observe(self, op, ctx=None):
        prev = list(self.window); self.window.append(op); self.total += 1
        if len(prev) >= 1:
            bg = (prev[-1], op); self.bigrams[bg] += 1
            if self.bigrams[bg] >= 3: self.kb.add_pattern(list(bg), tags={'bigram'})
        if len(prev) >= 2:
            tg = (prev[-2], prev[-1], op); self.trigrams[tg] += 1
            if self.trigrams[tg] >= 2: self.kb.add_pattern(list(tg), tags={'trigram'})

    def stats(self):
        return {'total': self.total, 'bigrams': len(self.bigrams),
                'trigrams': len(self.trigrams), 'anomalies': len(self.anomalies)}


# ═══════════════════════════════════════════════
# RULE
# ═══════════════════════════════════════════════

class Rule:
    def __init__(self, rid, cond, action, conf=0.5, priority=1):
        self.id = rid; self.condition = cond; self.action = action
        self.confidence = conf; self.priority = priority
        self.uses = 0; self.successes = 0; self.born_at = time.time()

    def apply(self, success=True):
        self.uses += 1
        if success: self.successes += 1; self.confidence = min(1.0, self.confidence + 0.03)
        else: self.confidence = max(0.0, self.confidence - 0.02)

    @property
    def accuracy(self): return self.successes / max(self.uses, 1)
    @property
    def fitness(self): return self.confidence * math.log1p(self.uses) * self.priority

    def to_dict(self):
        return {'id': self.id, 'if': self.condition, 'then': self.action,
                'conf': round(self.confidence, 3), 'uses': self.uses,
                'acc': round(self.accuracy, 3), 'priority': self.priority}

    @classmethod
    def from_dict(cls, d):
        r = cls(d['id'], d.get('if',''), d.get('then',''), d.get('conf', 0.5), d.get('priority', 1))
        r.uses = d.get('uses', 0); return r


# ═══════════════════════════════════════════════
# EPISODIC MEMORY
# ═══════════════════════════════════════════════

class EpisodicMemory:
    def __init__(self, capacity=5000):
        self.capacity = capacity; self.episodes = deque(maxlen=capacity); self.index = {}

    def store(self, ep):
        ep = {'ts': time.time(), 'id': hashlib.md5(str(ep).encode()).hexdigest()[:8], **ep}
        self.episodes.append(ep)
        for tag in ep.get('tags', []):
            self.index.setdefault(tag, []).append(ep['id'])

    def stats(self): return {'count': len(self.episodes), 'capacity': self.capacity, 'tags': len(self.index)}


# ═══════════════════════════════════════════════
# CRITIC
# ═══════════════════════════════════════════════

class Critic:
    GRADES = {(90,100):"A+ (Mukammal)",(80,90):"A  (A'lo)",(70,80):"B+ (Yaxshi)",
              (60,70):"B  (O'rtacha)",(50,60):"C  (Qonikarli)",(0,50):"D  (Yomon)"}

    def __init__(self, nn):
        self.nn = nn; self.evaluations = []

    def evaluate(self, stats):
        score = 50.0; comments = []
        instr=stats.get('instr',0); mips=stats.get('mips',0); halted=stats.get('halted',False)
        mem_r=stats.get('mem_reads',0); mem_w=stats.get('mem_writes',0); cycles=stats.get('cycles',0)
        if halted: score += 20; comments.append("✅ Dastur to'g'ri yakunlandi")
        else: score -= 20; comments.append("⚠️ Dastur to'xtamadi")
        if mips > 1.0: score += 15; comments.append(f"✅ Tezlik: {mips} MIPS")
        elif mips > 0.1: score += 5; comments.append(f"ℹ️ Tezlik: {mips} MIPS")
        else: score -= 10; comments.append(f"⚠️ Tezlik past: {mips} MIPS")
        if 1 <= instr <= 50: score += 10; comments.append(f"✅ Ixcham: {instr} instr")
        nn_out = self.nn.predict({'opcode':0,'cycles':cycles,'mips':mips,'mem_ops':mem_r+mem_w})
        nn_boost = sum(nn_out.values()) / max(len(nn_out), 1) * 10
        score += nn_boost; score = max(0, min(100, score))
        grade = "D  (Yomon)"
        for (lo,hi), g in self.GRADES.items():
            if lo <= score <= hi: grade = g; break
        r = {'score': round(score,1), 'grade': grade, 'comments': comments, 'nn_boost': round(nn_boost,2)}
        self.evaluations.append(r); return r


# ═══════════════════════════════════════════════
# KNOWLEDGE BASE
# ═══════════════════════════════════════════════

class KnowledgeBase:
    def __init__(self):
        self.facts = {}; self.patterns = {}; self.rules = {}
        self.programs = {}; self.history = deque(maxlen=20000)
        self._seed()

    def _seed(self):
        self.facts.update({'arch':'xCPU-1','word_size':32,'reg_count':16,
                           'sp':13,'lr':14,'pc':15,'ram_start':'0x00020000','endian':'little'})
        self.programs['hello'] = "; Salom dunyo\n.section text\n    LOAD X0, #83\n    PUTC X0\n    LOAD X0, #97\n    PUTC X0\n    LOAD X0, #108\n    PUTC X0\n    PUTC X0\n    LOAD X0, #111\n    PUTC X0\n    LOAD X0, #109\n    PUTC X0\n    LOAD X0, #33\n    PUTC X0\n    HALT\n"
        self.programs['fibonacci'] = "; Fibonacci 10\n.section text\n    LOAD X0, #0\n    LOAD X1, #1\n    LOAD X2, #10\n    PRINT X0\nfib_loop:\n    ADD  X3, X0, X1\n    MOV  X0, X1\n    MOV  X1, X3\n    PRINT X1\n    ADDI X2, X2, #-1\n    CMPI X2, #0\n    JGT  fib_loop\n    HALT\n"
        self.programs['factorial'] = "; 7! = 5040\n.section text\n    LOAD X0, #7\n    LOAD X1, #1\nfact_loop:\n    MUL  X1, X1, X0\n    ADDI X0, X0, #-1\n    CMPI X0, #1\n    JGE  fact_loop\n    PRINT X1\n    HALT\n"
        self.programs['gcd'] = "; GCD(48,18)=6\n.section text\n    LOAD X0, #48\n    LOAD X1, #18\ngcd_loop:\n    CMPI X1, #0\n    JEQ  done\n    MOD  X2, X0, X1\n    MOV  X0, X1\n    MOV  X1, X2\n    JMP  gcd_loop\ndone:\n    PRINT X0\n    HALT\n"
        self.programs['primes'] = "; Tub sonlar 2..30\n.section text\n    LOAD X5, #2\nouter:\n    CMPI X5, #30\n    JGT  done\n    LOAD X6, #2\n    LOAD X7, #1\ninner:\n    MUL  X8, X6, X6\n    CMP  X8, X5\n    JGT  check_prime\n    MOD  X9, X5, X6\n    CMPI X9, #0\n    JNE  next_d\n    LOAD X7, #0\n    JMP  check_prime\nnext_d:\n    ADDI X6, X6, #1\n    JMP  inner\ncheck_prime:\n    CMPI X7, #0\n    JEQ  next_n\n    PRINT X5\nnext_n:\n    ADDI X5, X5, #1\n    JMP  outer\ndone:\n    HALT\n"
        self.programs['sort'] = "; Bubble sort\n.section text\n    LOAD X0, #64\n    LOAD X1, #34\n    LOAD X2, #25\n    LOAD X3, #12\n    LOAD X4, #22\n    CMP  X0, X1\n    JLE  c01\n    MOV  X8, X0\n    MOV  X0, X1\n    MOV  X1, X8\nc01:\n    CMP  X1, X2\n    JLE  c12\n    MOV  X8, X1\n    MOV  X1, X2\n    MOV  X2, X8\nc12:\n    CMP  X2, X3\n    JLE  done\n    MOV  X8, X2\n    MOV  X2, X3\n    MOV  X3, X8\ndone:\n    PRINT X0\n    PRINT X1\n    PRINT X2\n    PRINT X3\n    PRINT X4\n    HALT\n"
        self.programs['power'] = "; 2^10=1024\n.section text\n    LOAD X0, #2\n    LOAD X1, #10\n    LOAD X2, #1\npow_loop:\n    CMPI X1, #0\n    JEQ  done\n    MUL  X2, X2, X0\n    ADDI X1, X1, #-1\n    JMP  pow_loop\ndone:\n    PRINT X2\n    HALT\n"
        self.programs['sum100'] = "; 1..100=5050\n.section text\n    LOAD X0, #0\n    LOAD X1, #1\n    LOAD X2, #100\nsum_loop:\n    ADD  X0, X0, X1\n    ADDI X1, X1, #1\n    CMP  X1, X2\n    JLE  sum_loop\n    ADD  X0, X0, X2\n    PRINT X0\n    HALT\n"
        self.programs['count10'] = "; 1..10\n.section text\n    LOAD X1, #1\n    LOAD X2, #10\nloop:\n    PRINT X1\n    ADDI X1, X1, #1\n    CMP  X1, X2\n    JLE  loop\n    PRINT X2\n    HALT\n"
        self.programs['random_walk'] = "; Random walk\n.section text\n    LOAD X0, #0\n    LOAD X1, #10\nstep_loop:\n    RAND X2\n    SHR  X2, X2, #31\n    CMPI X2, #0\n    JEQ  go_left\n    ADDI X0, X0, #1\n    JMP  next_step\ngo_left:\n    ADDI X0, X0, #-1\nnext_step:\n    PRINT X0\n    ADDI X1, X1, #-1\n    CMPI X1, #0\n    JGT  step_loop\n    HALT\n"

    def add_pattern(self, seq, tags=None):
        pid = hashlib.md5(str(seq).encode()).hexdigest()[:12]
        if pid not in self.patterns:
            self.patterns[pid] = Pattern(pid, seq, tags)
        p = self.patterns[pid]; p.update()
        if tags: p.tags.update(tags)
        return p

    def add_rule(self, cond, action, conf=0.5, priority=1):
        rid = hashlib.md5(f"{cond}>{action}".encode()).hexdigest()[:12]
        if rid not in self.rules:
            self.rules[rid] = Rule(rid, cond, action, conf, priority)
        return self.rules[rid]

    def log(self, ev): ev['ts'] = time.time(); self.history.append(ev)
    def top_patterns(self, n=5): return sorted(self.patterns.values(), key=lambda p: -p.score)[:n]
    def top_rules(self, n=5): return sorted(self.rules.values(), key=lambda r: -r.fitness)[:n]
    def stats(self): return {'facts': len(self.facts), 'patterns': len(self.patterns),
                              'rules': len(self.rules), 'programs': len(self.programs), 'history': len(self.history)}


# ═══════════════════════════════════════════════
# LEARNER
# ═══════════════════════════════════════════════

class Learner:
    def __init__(self, kb, nn):
        self.kb = kb; self.nn = nn; self.sessions = 0; self.rules_gen = 0

    def learn_from_execution(self, stats, source=''):
        self.sessions += 1
        instr=stats.get('instr',0); mips=stats.get('mips',0); halted=stats.get('halted',False)
        cycles=stats.get('cycles',0); mem_r=stats.get('mem_reads',0); mem_w=stats.get('mem_writes',0)
        self.kb.log({'type':'exec','instr':instr,'mips':mips,'halted':halted})
        features = {'opcode':0,'cycles':cycles,'mips':mips,'mem_ops':mem_r+mem_w,'regs':[0]*16,'flags':'----'}
        out_neurons = list(self.nn.output_layer.neurons.keys())
        target = {nid: ([1.0 if halted else 0.0, min(1.0,mips/10.0), 1.0 if instr>0 else 0.0]+[0.5]*20)[i]
                  for i, nid in enumerate(out_neurons)}
        self.nn.train(features, target)
        if not halted: self.kb.add_rule("Dastur to'xtamadi","HALT qo'shing",0.95,3).apply(True); self.rules_gen+=1
        if self.sessions % 5 == 0: self._derive_meta()

    def learn_from_code(self, source):
        lines = [l.strip() for l in source.splitlines() if l.strip() and not l.strip().startswith(';')]
        instr = sum(1 for l in lines if not l.startswith('.') and not l.endswith(':'))
        labels = sum(1 for l in lines if re.match(r'\w+:', l))
        has_loop = any(l.upper().startswith(('JEQ','JNE','JLT','JGT','JLE','JGE')) for l in lines)
        has_call = any(l.upper().startswith('CALL') for l in lines)
        has_mem  = any(l.upper().startswith(('LDW','STW','LDB','STB')) for l in lines)
        has_mul  = any('MUL' in l.upper() or 'DIV' in l.upper() for l in lines)
        if has_loop: self.kb.add_rule("Loop mavjud","Branch kerak",0.9,2)
        return {'instructions':instr,'labels':labels,'has_loop':has_loop,'has_call':has_call,
                'has_memory':has_mem,'has_multiply':has_mul,'complexity':instr+labels*2+has_loop*5+has_call*3}

    def _derive_meta(self):
        for p in self.kb.top_patterns(5):
            if p.hits > 5:
                self.kb.add_rule(f"Pattern {p.id[:8]} ({p.hits} hits)",
                                  f"Ketma-ketlik: {str(p.sequence)[:40]}",
                                  conf=min(0.95, 0.4+p.hits*0.04), priority=2)


# ═══════════════════════════════════════════════
# GENERATOR
# ═══════════════════════════════════════════════

class Generator:
    def __init__(self, kb, nn):
        self.kb = kb; self.nn = nn; self.gen_count = 0

    def generate(self, task):
        self.gen_count += 1
        tl = task.lower().strip()

        # 1. Aniq nom moslik (masalan 'fibonacci' → 'fibonacci', lekin 'count' → 'count10' EMS)
        for name, code in self.kb.programs.items():
            clean = name.replace('_', ' ')
            if clean == tl or name == tl:
                return f"; Brain Gen: '{task}'\n" + code

        # 2. Raqam
        n = self._num(task)

        # 3. Maxsus generatorlar — KB lookup DAN OLDIN (aniq moslik)
        if any(w in tl for w in ['fibonacci', 'fib']): return self._fib(n or 10)
        if any(w in tl for w in ['factorial', 'fact']): return self._factorial(n or 7)
        if any(w in tl for w in ['count', 'san']): return self._count(n or 10)
        if any(w in tl for w in ['sum', 'jamla']): return self._sum(n or 100)
        if any(w in tl for w in ['multiply', "ko'pay", 'times']): return self._multiply(n or 9)
        if any(w in tl for w in ['max', 'maksimal']): return self._max(n or 5)
        if any(w in tl for w in ['min', 'minimal']): return self._min(n or 5)
        if any(w in tl for w in ['binary', 'search']): return self._binary_search()
        if any(w in tl for w in ['sort', 'saral']):
            return self.kb.programs.get('sort') or self._sort_fallback()
        if any(w in tl for w in ['prime', 'tub']):
            return self.kb.programs.get('primes') or self._primes_fallback()
        if any(w in tl for w in ['gcd']):
            return self.kb.programs.get('gcd') or self._gcd_fallback()
        if any(w in tl for w in ['power', 'daraja']):
            return self.kb.programs.get('power') or self._power_fallback()
        if any(w in tl for w in ['rand', 'tasodif', 'random', 'walk']):
            return self.kb.programs.get('random_walk') or self._rand_walk_fallback()
        if any(w in tl for w in ['hello', 'salom']):
            return self.kb.programs.get('hello') or self._hello_fallback()

        # 4. Qisman KB qidirish (oxirgi chora)
        for name, code in self.kb.programs.items():
            clean = name.replace('_', ' ')
            if clean in tl or tl in clean:
                return f"; Brain Gen: '{task}'\n" + code

        return self._generic(task)

    def _num(self, t):
        nums = re.findall(r'\d+', t)
        return int(nums[-1]) if nums else None

    def _fib(self, n): return f"; Fibonacci n={n}\n.section text\n    LOAD X0, #0\n    LOAD X1, #1\n    LOAD X2, #{n}\n    PRINT X0\nfib_loop:\n    ADD  X3, X0, X1\n    MOV  X0, X1\n    MOV  X1, X3\n    PRINT X1\n    ADDI X2, X2, #-1\n    CMPI X2, #0\n    JGT  fib_loop\n    HALT\n"
    def _factorial(self, n): return f"; Factorial n={n}\n.section text\n    LOAD X0, #{n}\n    LOAD X1, #1\nfact_loop:\n    MUL  X1, X1, X0\n    ADDI X0, X0, #-1\n    CMPI X0, #1\n    JGE  fact_loop\n    PRINT X1\n    HALT\n"
    def _count(self, n): return f"; Count 1..{n}\n.section text\n    LOAD X1, #1\n    LOAD X2, #{n}\nloop:\n    PRINT X1\n    ADDI X1, X1, #1\n    CMP  X1, X2\n    JLE  loop\n    PRINT X2\n    HALT\n"
    def _sum(self, n): return f"; Sum 1..{n}\n.section text\n    LOAD X0, #0\n    LOAD X1, #1\n    LOAD X2, #{n}\nsum_loop:\n    ADD  X0, X0, X1\n    ADDI X1, X1, #1\n    CMP  X1, X2\n    JLE  sum_loop\n    ADD  X0, X0, X2\n    PRINT X0\n    HALT\n"

    def _max(self, n):
        """N ta tasodifiy sonning maksimalini topish."""
        return f"""; Max of {n} random numbers
.section text
    LOAD X0, #0        ; current max
    LOAD X1, #{n}      ; counter
max_loop:
    RAND X2
    SHR  X2, X2, #24   ; 0..255 oraliq
    CMP  X2, X0
    JLE  skip_max
    MOV  X0, X2
skip_max:
    ADDI X1, X1, #-1
    CMPI X1, #0
    JGT  max_loop
    PRINT X0
    HALT
"""

    def _min(self, n):
        """N ta tasodifiy sonning minimalini topish."""
        return f"""; Min of {n} random numbers
.section text
    LOAD X0, #255      ; current min (boshlanish qiymati)
    LOAD X1, #{n}      ; counter
min_loop:
    RAND X2
    SHR  X2, X2, #24   ; 0..255 oraliq
    CMP  X2, X0
    JGE  skip_min
    MOV  X0, X2
skip_min:
    ADDI X1, X1, #-1
    CMPI X1, #0
    JGT  min_loop
    PRINT X0
    HALT
"""

    def _multiply(self, n):
        """Ko'paytirish jadvali (1..N)."""
        return f"""; Ko'paytirish jadvali 1..{n}
.section text
    LOAD X1, #1
    LOAD X2, #{n}
    LOAD X3, #1
    LOAD X4, #{n}
mul_i:
    CMP  X1, X2
    JGT  done
    MOV  X3, X1
mul_j:
    CMP  X3, X4
    JGT  next_i
    MUL  X5, X1, X3
    PRINT X5
    ADDI X3, X3, #1
    JMP  mul_j
next_i:
    ADDI X1, X1, #1
    JMP  mul_i
done:
    HALT
"""

    def _sort_fallback(self):
        return self.kb.programs.get('sort', "; sort yo'q\nHALT\n")

    def _primes_fallback(self):
        return self.kb.programs.get('primes', "; primes yo'q\nHALT\n")

    def _gcd_fallback(self):
        return self.kb.programs.get('gcd', "; gcd yo'q\nHALT\n")

    def _power_fallback(self):
        return self.kb.programs.get('power', "; power yo'q\nHALT\n")

    def _rand_walk_fallback(self):
        return self.kb.programs.get('random_walk', "; random_walk yo'q\nHALT\n")

    def _hello_fallback(self):
        return self.kb.programs.get('hello', "; hello yo'q\nHALT\n")

    def _binary_search(self):
        return """; Binary search (target=5, array 0..9)
.section text
    LOAD X0, #0       ; low
    LOAD X1, #9       ; high
    LOAD X2, #5       ; target
    LOAD X9, #-1      ; result (topilmasa -1)
bs_loop:
    CMP  X0, X1
    JGT  bs_done
    ADD  X3, X0, X1
    SHR  X3, X3, #1   ; mid = (low+high)/2
    MOV  X4, X3       ; mid*2+1 — taxminiy qiymat
    ADDI X4, X4, #1
    CMP  X4, X2
    JEQ  bs_found
    JGT  bs_right
    ADDI X0, X3, #1
    JMP  bs_loop
bs_right:
    ADDI X1, X3, #-1
    JMP  bs_loop
bs_found:
    MOV  X9, X3
bs_done:
    PRINT X9
    HALT
"""

    def _generic(self, task): return f"; Generator: '{task}'\n.section text\n    LOAD X0, #0\n    LOAD X1, #10\nloop:\n    PRINT X0\n    ADDI X0, X0, #1\n    ADDI X1, X1, #-1\n    CMPI X1, #0\n    JGT  loop\n    HALT\n"


# ═══════════════════════════════════════════════
# EXPANDER
# ═══════════════════════════════════════════════

class Expander:
    def __init__(self, kb, nn):
        self.kb = kb; self.nn = nn; self.sessions = 0; self.expansions = []

    def maybe_expand(self, session_count):
        if session_count % 10 != 0: return None
        self.sessions += 1; action = self.sessions % 4
        if action == 1: return self._new_program()
        elif action == 2: return self._expand_nn()
        elif action == 3: return self._synth_rule()
        else: return self._combine()

    def _new_program(self):
        names = list(self.kb.programs.keys())
        if not names: return None
        base = random.choice(names); new_name = f"syn_{self.sessions}"
        self.kb.programs[new_name] = self.kb.programs[base]
        self.expansions.append(('new', new_name))
        return f"Yangi dastur: '{new_name}'"

    def _expand_nn(self):
        self.nn.expand_hidden(4)
        n1 = self.nn.hidden1.stats()['count']; n2 = self.nn.hidden2.stats()['count']
        self.expansions.append(('nn', n1+n2))
        return f"Neyronlar kengaydi: H1={n1}, H2={n2}"

    def _synth_rule(self):
        top = self.kb.top_rules(3)
        if not top: return None
        r1 = random.choice(top)
        nr = self.kb.add_rule(f"[META] {r1.condition}", f"[META] {r1.action}", r1.confidence*0.85, r1.priority+1)
        self.expansions.append(('meta', nr.id))
        return f"Meta-qoida: {nr.id[:8]}"

    def _combine(self):
        names = list(self.kb.programs.keys())
        if len(names) < 2: return None
        a, b = random.sample(names, 2); new_name = f"combo_{self.sessions}"
        self.kb.programs[new_name] = f"; {a}+{b}\n{self.kb.programs[a]}\n{self.kb.programs[b]}"
        self.expansions.append(('combo', new_name))
        return f"Combo: '{new_name}'"

    def stats(self): return {'expansions': len(self.expansions), 'sessions': self.sessions}


# ═══════════════════════════════════════════════
# BRAIN — Asosiy sinf (v3.0 Android)
# ═══════════════════════════════════════════════

class Brain:
    VERSION = "5.0.0-android"

    def __init__(self, machine=None, auto_load=True, auto_bg=True):
        self.machine = machine
        self.kb = KnowledgeBase()
        self.nn = NeuralNetwork(inp=32, h1=64, h2=32, out=16)
        self.pattern = PatternEngine(self.kb)
        self.memory = EpisodicMemory(5000)
        self.learner = Learner(self.kb, self.nn)
        self.generator = Generator(self.kb, self.nn)
        self.critic = Critic(self.nn)
        self.expander = Expander(self.kb, self.nn)
        self.sessions = 0; self.start_time = time.time()
        self.chat_history = deque(maxlen=200)

        # RL Agent
        if _RL_AVAILABLE:
            self.rl = RLAgent(machine=self, generator=self.generator, kb=self.kb, nn=self.nn)
        else:
            self.rl = None
        self._rl_log = deque(maxlen=200)

        # ─── Persistent xotira ───────────────────
        self.store = None
        self.bg_learner = None

        if _PERSISTENT_AVAILABLE:
            self.store = PersistentStore(auto_save_every=5)
            # Oldingi o'rganishlarni yukla
            if auto_load:
                self.store.load_brain(self)

            # Fon o'rganishni boshlash
            if auto_bg:
                self.bg_learner = BackgroundLearner(
                    brain=self,
                    store=self.store,
                    check_interval=30.0  # Har 30 sekundda tekshiradi
                )
                self.bg_learner.start()

    def shutdown(self):
        """Ilovani yopishda chaqiriladi — saqlaydi va fon threadni to'xtatadi."""
        if self.bg_learner:
            self.bg_learner.stop()
        elif self.store:
            self.store.save_brain(self)

    # ─── RL metodlari ──────────────────────────

    def rl_available(self) -> bool:
        return _RL_AVAILABLE and self.rl is not None

    def rl_train(self, n_episodes: int = 10, verbose: bool = False,
                 progress_cb=None) -> dict:
        """N ta RL epizodi. progress_cb(i, total, entry) UI progress uchun."""
        if not self.rl:
            return {'episodes': 0, 'error': 'RL Engine mavjud emas'}
        self.rl.machine = self.machine
        results = []
        for i in range(n_episodes):
            r = self.rl.run_episode()
            results.append(r)
            self._rl_log.append(r)
            if progress_cb:
                try: progress_cb(i + 1, n_episodes, r)
                except Exception: pass
        rewards = [r['reward'] for r in results]
        return {
            'episodes':    n_episodes,
            'avg_reward':  round(sum(rewards) / max(len(rewards), 1), 3),
            'max_reward':  round(max(rewards), 3),
            'min_reward':  round(min(rewards), 3),
            'success_rate':round(sum(1 for r in rewards if r > 0) / max(len(rewards), 1) * 100, 1),
            'best_action': self.rl.best_action,
            'new_programs':self.rl.success_count,
        }

    def rl_episode(self) -> dict:
        if not self.rl: return {}
        self.rl.machine = self.machine
        r = self.rl.run_episode()
        self._rl_log.append(r)
        return r

    def rl_status(self) -> str:
        if not self.rl:
            return "❌ RL Engine yuklanmagan (rl_engine.py topilmadi)"
        return self.rl.status_str()

    def rl_log(self) -> list:
        return list(self._rl_log)

    # ─── Signal / syscall ──────────────────────

    def signal(self, op, val): self.pattern.observe(op, {'val': val})
    def syscall(self, num, arg):
        if num == 0: return self.kb.stats()['patterns']
        if num == 1: return len(self.kb.rules)
        if num == 2: return self.nn.iterations
        return 0
    def force_learn(self): self.learner._derive_meta()

    def learn_from_run(self, stats, source=''):
        self.sessions += 1
        self.learner.learn_from_execution(stats, source)
        self.memory.store({'type':'execution','stats':stats,'tags':['run']})
        msg = self.expander.maybe_expand(self.sessions)
        if msg: self.kb.log({'type':'expansion','msg':msg})

    def analyze(self, source):
        a = self.learner.learn_from_code(source)
        lines = [
            "╔══ Brain v3.0 — Kod Tahlili ══════════",
            f"║  Instruksiya  : {a['instructions']}",
            f"║  Loop         : {'✅' if a['has_loop'] else '❌'}",
            f"║  Murakkablik  : {a['complexity']}",
            f"║  NN loss      : {self.nn.avg_loss():.6f}",
            "╚══════════════════════════════════════",
        ]
        return "\n".join(lines)

    def evaluate(self, stats):
        r = self.critic.evaluate(stats)
        lines = [f"  Baho: {r['grade']} ({r['score']}/100)"]
        for c in r['comments']: lines.append(f"  {c}")
        return "\n".join(lines)

    def generate(self, task): return self.generator.generate(task)

    def chat(self, message):
        self.chat_history.append({'role':'user','msg':message,'ts':time.time()})
        resp = self._process(message.lower().strip(), message)
        self.chat_history.append({'role':'brain','msg':resp,'ts':time.time()})

        # Suhbatni diskka saqlash
        if self.store:
            self.store.chat.add('user', message)
            self.store.chat.add('brain', resp, {
                'sessions': self.sessions,
                'kb_patterns': self.kb.stats()['patterns'],
            })
            self.store.maybe_auto_save(self)

        return resp

    def _process(self, ml, mo):
        # ─── Salom ───────────────────────────────
        if any(w in ml for w in ['salom','hello','hi','assalom','hay']):
            nn = self.nn.stats()
            age = self.store.brain_age() if self.store else 'yangi'
            chat_n = self.store.chat.total_count() if self.store else 0
            rl_info = f"  RL          : {'✅ Faol' if self.rl_available() else '❌'}\n"
            bg_info = f"  Fon o'rganish: {'✅' if (self.bg_learner and self.bg_learner._running) else '⏸'}\n"
            return (f"Salom! xOS Brain v{self.VERSION}\n"
                    f"  Yosh       : {age}\n"
                    f"  Suhbatlar  : {chat_n} ta\n"
                    f"  Neyronlar  : H1={nn['layers']['hidden1']['count']} H2={nn['layers']['hidden2']['count']}\n"
                    f"{rl_info}{bg_info}"
                    f"  'yordam' yozing yoki savol bering!")

        # ─── Yordam ──────────────────────────────
        if any(w in ml for w in ['help','yordam','nima qila']):
            return self._help()

        # ─── xOS nima ────────────────────────────
        if any(p in ml for p in ['xos nima', 'bu nima', 'tizim', 'ilova nima']):
            return ("xOS — shaxsiy virtual laboratoriya.\n"
                    "  • xCPU-1 virtual protsessor (50+ instruksiya)\n"
                    "  • Hamza va Zafar — O'zbek dasturlash tillari\n"
                    "  • xASM — assembly kompilyatori\n"
                    "  • Brain AI — o'zi o'rganuvchi neyron tarmoq\n"
                    "  • RL Engine — mustahkamlovchi o'rganish\n"
                    "Hammasi 100% offline Android da.")

        # ─── Kod so'rash ─────────────────────────
        if any(w in ml for w in ['fibonacci','fib']):
            code = ("ish fibonacci(n):\n"
                    "    agar n < 2:\n"
                    "        qayt n\n"
                    "    qayt fibonacci(n - 1) + fibonacci(n - 2)\n\n"
                    "chiqar fibonacci(10)")
            return f"Fibonacci — Hamza tilida:\n\n{code}\n\n→ Natija: 55"

        if any(w in ml for w in ['factorial','faktorial']):
            code = ("ish factorial(n):\n"
                    "    agar n <= 1:\n"
                    "        qayt 1\n"
                    "    qayt n * factorial(n - 1)\n\n"
                    "chiqar factorial(7)")
            return f"Factorial — Hamza tilida:\n\n{code}\n\n→ Natija: 5040"

        if any(w in ml for w in ['sort','saral']):
            xasm = self.kb.programs.get('sort', self.generator.generate('sort'))
            return f"Saralash — xASM:\n\n{xasm[:300]}"

        if any(w in ml for w in ['prime','tub son']):
            xasm = self.kb.programs.get('primes', self.generator.generate('primes'))
            return f"Tub sonlar — xASM:\n\n{xasm[:300]}"

        if 'hello' in ml or ('salom' in ml and 'dunyo' in ml):
            return "Salom Dunyo — Hamza tilida:\n\nchiqar \"Salom, Dunyo!\""

        # ─── Hisoblash ───────────────────────────
        try:
            parts = mo.strip().split()
            if len(parts) == 3 and parts[1] in ['+','-','*','/','%']:
                a, op, b = float(parts[0]), parts[1], float(parts[2])
                ops = {'+': a+b, '-': a-b, '*': a*b,
                       '/': (a/b if b != 0 else None), '%': (a%b if b != 0 else None)}
                r = ops.get(op)
                if r is not None:
                    return f"{a:g} {op} {b:g} = {r:g}"
        except Exception:
            pass

        # ─── Registrlar ──────────────────────────
        if any(w in ml for w in ['registr','register','xcpu']):
            return ("xCPU-1 registrlari:\n"
                    "  X0      — funksiya natijasi\n"
                    "  X1-X7   — umumiy maqsadli\n"
                    "  X8-X12  — vaqtinchalik\n"
                    "  X13 SP  — stack pointer\n"
                    "  X14 LR  — link register\n"
                    "  X15 PC  — dastur hisoblagichi")

        # ─── xASM ────────────────────────────────
        if any(w in ml for w in ['xasm','assembly','assembler']):
            return ("xASM misol — 10+20=30:\n\n"
                    "LOAD X0, #10\n"
                    "LOAD X1, #20\n"
                    "ADD  X2, X0, X1\n"
                    "PRINT X2\n"
                    "HALT\n\n→ Natija: 30")

        # ─── Hamza ───────────────────────────────
        if 'hamza' in ml:
            return ("Hamza — O'zbek dasturlash tili:\n\n"
                    "son x = 10\nson y = 20\nchiqar x + y\n\n"
                    "Kalit so'zlar: son, ish, qayt, agar, aks, takror, chiqar")

        # ─── Zafar ───────────────────────────────
        if 'zafar' in ml:
            return ("Zafar — O'zbek dasturlash tili №2:\n\n"
                    "son x = 42\nchiqar x\n\n"
                    "Kalit so'zlar: son, ish, qayt, agar, aks, takror, chiqar")

        # ─── Persistent xotira ───────────────────
        if any(w in ml for w in ['xotira','memory','persist','saqlash','esda']):
            if self.store:
                return self.store.summary()
            return "Persistent xotira yuklanmagan."

        # ─── Fon o'rganish ───────────────────────
        if any(w in ml for w in ['fon','background','tinmay']):
            if self.bg_learner:
                return self.bg_learner.status()
            return "Fon o'rganish yuklanmagan."

        # ─── Brain holati ────────────────────────
        if any(w in ml for w in ['status','holat','bstatus']):
            return self.status_str()

        # ─── RL ──────────────────────────────────
        if ml.startswith('rl') or 'reinforcement' in ml:
            return self._rl_chat(ml, mo)

        # ─── Kod generatsiya ─────────────────────
        if ml.startswith('gen ') or ml.startswith('yarat ') or 'kodi yoz' in ml or 'kod yoz' in ml:
            task = mo.split(None, 1)[1] if ' ' in mo else mo
            for kw in ['kodi yoz','kod yoz','kodi','yarat','gen']:
                task = task.replace(kw, '').strip()
            return self.generate(task)

        # ─── O'rganish ───────────────────────────
        if any(w in ml for w in ['learn',"o'rgan",'train']):
            self.force_learn()
            kb = self.kb.stats()
            return f"O'rganish: {kb['patterns']} pattern, {kb['rules']} qoida"

        # ─── Patternlar ──────────────────────────
        if any(w in ml for w in ['pattern','naqsh']):
            top = self.kb.top_patterns(5)
            if not top:
                return "Hali pattern yo'q."
            return "Patternlar:\n" + "\n".join(f"  • {p.id[:8]}: {p.hits} hits" for p in top)

        # ─── Qoidalar ────────────────────────────
        if any(w in ml for w in ['rule','qoida']):
            top = self.kb.top_rules(5)
            if not top:
                return "Hali qoida yo'q."
            return "Qoidalar:\n" + "\n".join(f"  • [{r.confidence:.0%}] {r.action[:50]}" for r in top)

        # ─── Dasturlar ───────────────────────────
        if any(w in ml for w in ['program','dastur','demo']):
            progs = list(self.kb.programs.keys())
            user_p = [p for p in progs if p.startswith(('rl_','syn_','combo_'))]
            base_p = [p for p in progs if p not in user_p]
            resp = f"Dasturlar ({len(progs)}):\nAsosiy: {chr(44)+chr(32).join(base_p)}"
            if user_p:
                resp += f"\nO'zi yozgan: {chr(44)+chr(32).join(user_p[:5])}"
            return resp

        # ─── Neyron tarmoq ───────────────────────
        if any(w in ml for w in ['neural','neyron','nn']):
            nn = self.nn.stats()
            return (f"Neyron Tarmoq:\n"
                    f"  Iter: {nn['iterations']}\n"
                    f"  Loss: {nn['avg_loss']:.6f}\n"
                    f"  H1  : {nn['layers']['hidden1']['count']} neyron\n"
                    f"  H2  : {nn['layers']['hidden2']['count']} neyron")

        # ─── Tarix ───────────────────────────────
        if any(w in ml for w in ['tarix','history']):
            if self.store:
                recent = self.store.chat.session_context(5)
                if recent:
                    lines = ["Oxirgi suhbat:"]
                    for e in recent:
                        role = "Siz" if e['role'] == 'user' else "Brain"
                        lines.append(f"  {role}: {e['msg'][:60]}")
                    return "\n".join(lines)
            return "Suhbat tarixi bo'sh."

        # ─── Umid beruvchi javob ─────────────────
        return (f"Tushunmadim: '{mo[:40]}'\n"
                f"Masalan: 'fibonacci kodi', 'xasm misol', '10 + 20', 'yordam'")

    def _help(self):
        rl_line = "  rl <N>       → N ta RL trening\n  rl status    → RL holati\n" if self.rl_available() else ""
        bg_line = "  fon          → Fon o'rganish holati\n" if self.bg_learner else ""
        mem_line = "  xotira       → Persistent xotira holati\n" if self.store else ""
        return (f"xOS Brain v{self.VERSION} — Barcha buyruqlar:\n\n"
                f"  SAVOL BERISH:\n"
                f"  fibonacci kodi → Hamza tilida fibonacci\n"
                f"  factorial kodi → Hamza tilida factorial\n"
                f"  xasm misol    → Assembly namuna\n"
                f"  10 + 20       → Hisoblash\n"
                f"  xos nima      → Tizim haqida\n\n"
                f"  BOSHQARUV:\n"
                f"  gen <vazifa>  → Kod generatsiya\n"
                f"  status        → Brain holati\n"
                f"  learn         → O'rganish\n"
                f"  patterns      → Patternlar\n"
                f"  programs      → Dasturlar\n"
                f"{rl_line}{bg_line}{mem_line}")

    def _rl_chat(self, ml: str, mo: str) -> str:
        if not self.rl_available():
            return "❌ RL Engine yuklanmagan.\nrl_engine.py faylini tekshiring."
        nums = re.findall(r'\d+', mo)
        n = int(nums[0]) if nums else 5
        if any(w in ml for w in ['start','boshlash','run','ishlatish']) or nums:
            results = self.rl_train(n, verbose=False)
            return (f"RL {results['episodes']} epizod bajarildi\n"
                    f"  O'rt mukofot : {results['avg_reward']}\n"
                    f"  Muvaffaqiyat : {results['success_rate']}%\n"
                    f"  Yangi shablon: {results['new_programs']}\n"
                    f"  Eng yaxshi   : {results['best_action']}")
        elif any(w in ml for w in ['status','holat']):
            return self.rl_status()
        elif any(w in ml for w in ['episode','bitta']):
            r = self.rl_episode()
            return (f"Epizod {r.get('episode','?')}:\n"
                    f"  Harakat : {r.get('action','?')}\n"
                    f"  Mukofot : {r.get('reward',0):+.1f}\n"
                    f"  Holat   : {'✅' if r.get('halted') else '❌'}")
        return f"RL buyruqlari:\n  rl 20      → 20 epizod\n  rl status  → holat\n\n{self.rl_status()}"

    def status_str(self):
        uptime = round(time.time()-self.start_time, 1)
        kb=self.kb.stats(); nn=self.nn.stats(); ps=self.pattern.stats()
        ms=self.memory.stats(); es=self.expander.stats()
        rl_info = ""
        if self.rl:
            rl_info = (f"\n  RL Epizodlar : {self.rl.episode}"
                       f"\n  RL Muvaffaqiyat: {self.rl.success_count} yangi shablon"
                       f"\n  RL Eng yaxshi: {round(self.rl.best_reward,1)} ({self.rl.best_action})")
        return "\n".join([
            f"Brain v{self.VERSION} | Uptime: {uptime}s",
            f"  Sessiyalar : {self.sessions}",
            f"  Faktlar    : {kb['facts']}",
            f"  Patternlar : {kb['patterns']} ({ps['bigrams']} bigram)",
            f"  Qoidalar   : {kb['rules']}",
            f"  Dasturlar  : {kb['programs']}",
            f"  NN H1={nn['layers']['hidden1']['count']} H2={nn['layers']['hidden2']['count']}",
            f"  NN Iter={nn['iterations']} Loss={nn['avg_loss']:.6f}",
            f"  Xotira: {ms['count']}/{ms['capacity']}",
            f"  Kengaytirish: {es['expansions']} ta",
            f"  RL: {'✅' if self.rl_available() else '❌'}" + rl_info,
        ])

    def save(self, path):
        data = {'version':self.VERSION,'facts':self.kb.facts,
                'patterns':{pid:p.to_dict() for pid,p in self.kb.patterns.items()},
                'rules':{rid:r.to_dict() for rid,r in self.kb.rules.items()},
                'programs':self.kb.programs,'sessions':self.sessions,'nn':self.nn.save()}
        if self.rl:
            data['rl'] = self.rl.save()
        with open(path,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)

    def load(self, path):
        try:
            with open(path,'r',encoding='utf-8') as f: data=json.load(f)
            self.kb.facts.update(data.get('facts',{}))
            self.kb.programs.update(data.get('programs',{}))
            self.sessions = data.get('sessions',0)
            for pid,pd in data.get('patterns',{}).items():
                p=Pattern(pid,pd.get('seq',[]),pd.get('tags',[])); p.hits=pd.get('hits',0); p.score=pd.get('score',0)
                self.kb.patterns[pid]=p
            for rid,rd in data.get('rules',{}).items(): self.kb.rules[rid]=Rule.from_dict(rd)
            if 'nn' in data: self.nn.load(data['nn'])
            if 'rl' in data and self.rl: self.rl.load(data['rl'])
        except FileNotFoundError: pass
        except Exception as e: print(f"Brain load xatosi: {e}")
