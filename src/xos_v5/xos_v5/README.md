# ⬡ xOS v5.0 — Shaxsiy Virtual Laboratoriya

> O'z virtual protsessori (xCPU-1), **Persistent Brain AI** (o'zi o'rganadi, eslab qoladi),
> Hamza va Zafar O'zbek dasturlash tillari bilan 100% offline Android ilovasi.

## 🆕 v5.0 Yangiliklar

| Yangilik | Tavsif |
|----------|--------|
| 💾 Persistent Xotira | O'rganganlar diskka saqlanadi, ilova yopilsa ham |
| 🤖 Fon O'rganish | Ilova fonda bo'lsa ham RL trening davom etadi |
| 🧠 Aqlli Chat | "xos nima?", "fibonacci kodi", "10+20" tushunadi |
| 📖 Suhbat Tarixi | Barcha suhbatlar saqlanadi, qidiriladi |
| ✍️ O'zi Yozgan Kod | Brain yaxshi dasturlarini o'zi saqlaydi |

## 📱 APK Olish — GitHub Actions

```bash
git init
git add .
git commit -m "xOS v5.0"
git remote add origin https://github.com/SIZNING_USERNAME/xos-android.git
git branch -M main
git push -u origin main
# GitHub → Actions → Build xOS APK → Run workflow → ~20 daqiqa → APK tayyor
```

## 📱 9 ta Tab

| Tab | Vazifa |
|-----|--------|
| 💻 Shell | xOS interaktiv buyruq qatori |
| 📝 xASM | Assembly editor + Run/Assemble/xELF |
| ⚡ Hamza | O'zbek dasturlash tili |
| 🌟 Zafar | O'zbek dasturlash tili |
| 🧠 Brain | AI suhbat + kod generatsiya |
| 🤖 RL | Reinforcement Learning trening |
| 🔌 Devices | Qurilmalar paneli |
| 📊 CPU | Registrlar + flaglar monitor |
| 📖 Qo'llanma | To'liq yo'riqnoma |

## 🧠 Brain AI — Aqlli Chat Misollari

```
👤 salom
🧠 Salom! xOS Brain v5.0 | Yosh: 2.3 soat | Suhbatlar: 15 ta

👤 fibonacci kodi
🧠 Fibonacci — Hamza tilida:
   ish fibonacci(n):
       agar n < 2:
           qayt n
       qayt fibonacci(n-1) + fibonacci(n-2)
   chiqar fibonacci(10)  → 55

👤 10 + 20
🧠 10 + 20 = 30

👤 xos nima
🧠 xOS — shaxsiy virtual laboratoriya...

👤 fon
🧠 🤖 Fon O'rganish: Faol | RL: 42 ep | Sintez: 8 ta
```

## 💾 Persistent Xotira

Brain o'rganganlarini `~/.xos_brain/` papkasiga saqlaydi:
- `brain_state.json` — asosiy holat (KB, NN, RL)
- `brain_diary.jsonl` — o'rganish kundaligi
- `brain_chat.jsonl` — suhbat tarixi
- `brain_self.py` — o'zi yozgan dasturlar

## ⚡ Hamza Misoli

```hamza
ish fibonacci(n):
    agar n < 2:
        qayt n
    qayt fibonacci(n - 1) + fibonacci(n - 2)

chiqar fibonacci(10)
```
→ Natija: 55

## 🧪 Test Natijalari

```
✅ PASS: 75/75 — 100%
```

---
*xOS Team — 2026 | v5.0.0 | MIT License*
