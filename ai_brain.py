# ai_brain.py
# التثبيت: pip install aiohttp requests
# التشغيل: python ai_brain.py
import json, time, requests, sys

RELAY   = "http://localhost:8080"          # <-- ضع رابط السيرفر إن كان مستضافاً
API_KEY = "ROBLOX_AI_KEY_2026"             # <-- نفس مفتاح السيرفر
SESSION = "map1"
H = {"X-Auth": API_KEY, "Content-Type": "application/json"}
result_cursor = 0

# ════════ الجزء 1: ذكاء مدمج (يعمل بدون أي API خارجي) ════════
# يحلل الجملة العربية/الإنجليزية ويحولها لأوامر Roblox

def parse_text(text: str):
    """المحلل المدمج — يفهم أوامر البناء الشائعة"""
    t = text.lower().strip()
    cmds = []

    if "ping" in t or "فحص" in t or "اتصال" in t:
        return [{"action": "ping", "args": {}}]

    if "امسح" in t or "احذف" in t or "delete" in t:
        words = text.replace("احذف", "").replace("امسح", "").replace("delete", "").strip()
        return [{"action": "delete", "args": {"name": words or "AIPart"}}]

    if "جزء" in t or "مكعب" in t or "جزء" in t or "part" in t or "cube" in t or "wall" in t or "جدار" in t:
        import re
        name = "AIPart"
        for m in re.findall(r'اسم[:\s]+(\S+)', text): name = m
        size  = [4, 1, 4]
        pos   = [0, 10, 0]
        color = [163, 162, 165]
        # استخراج الأبعاد: "بحجم 10 5 2" أو "size 10 5 2"
        m = re.search(r'(?:بحجم|size)\s+(\d+)[\s,xX]+(\d+)[\s,xX]+(\d+)', t)
        if m: size = [int(m.group(i)) for i in (1, 2, 3)]
        # الموقع: "في 0 20 0" أو "at ..."
        m = re.search(r'(?:في|at|position)\s+(-?\d+)[\s,]+(-?\d+)[\s,]+(-?\d+)', t)
        if m: pos = [int(m.group(i)) for i in (1, 2, 3)]
        # اللون
        colors = {"احمر": [196,40,28], "أحمر": [196,40,28], "red": [196,40,28],
                  "ازرق": [13,105,172], "أزرق": [13,105,172], "blue": [13,105,172],
                  "اخضر": [75,151,75], "أخضر": [75,151,75], "green": [75,151,75],
                  "اصفر": [245,205,48], "أصفر": [245,205,48], "yellow": [245,205,48],
                  "ابيض": [242,243,243], "أبيض": [242,243,243], "white": [242,243,243],
                  "اسود": [27,42,53], "أسود": [27,42,53], "black": [27,42,53]}
        for cname, rgb in colors.items():
            if cname in t: color = rgb; break
        m = re.search(r'(?:لون|color)\s+(?:rgb\s*)?(\d+)[\s,]+(\d+)[\s,]+(\d+)', t)
        if m: color = [int(m.group(i)) for i in (1, 2, 3)]
        cmds.append({"action": "createPart",
                     "args": {"name": name, "size": size, "position": pos, "color": color}})
        return cmds

    if "غيّر" in t or "غير" in t or "set" in t:
        import re
        name = "AIPart"
        for m2 in re.findall(r'اسم[:\s]+(\S+)', text): name = m2
        # شفافية
        m = re.search(r'شفافية\s+(\d+)', t)
        if m:
            cmds.append({"action": "setProperty",
                         "args": {"name": name, "property": "Transparency", "value": int(m.group(1)) / 10}})
        # تثبيت
        if "ثبّت" in t or "ثبت" in t or "anchor" in t:
            cmds.append({"action": "setProperty",
                         "args": {"name": name, "property": "Anchored", "value": True}})
        # لون
        m = re.search(r'(?:لون|color)\s+(?:rgb\s*)?(\d+)[\s,]+(\d+)[\s,]+(\d+)', t)
        if m:
            cmds.append({"action": "setProperty",
                         "args": {"name": name, "property": "Color",
                                  "value": [int(m.group(i)) for i in (1, 2, 3)]}})
        return cmds or [{"action": "ping", "args": {}}]

    return None  # لم يفهم → يمرر للـ LLM أو يرد بعدم الفهم

# ════════ الجزء 2: وضع LLM (اختياري) ════════
# ضع مفتاحك في المتغير وسيصبح الـ AI قادراً على فهم أي طلب معقد
OPENAI_KEY = ""   # مثال: sk-... (اختياري تماماً)

SYSTEM_PROMPT = """أنت مساعد بناء داخل Roblox. حوّل طلب المستخدم إلى JSON فقط، مصفوفة أوامر:
[{"action":"createPart","args":{"name":"...","size":[x,y,z],"position":[x,y,z],"color":[r,g,b]}},
 {"action":"delete","args":{"name":"..."}},
 {"action":"setProperty","args":{"name":"...","property":"Anchored|Transparency|Color|Position|Size","value":...}}]
أعطِ JSON فقط دون أي شرح."""

def llm_plan(text):
    r = requests.post("https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={"model": "gpt-4o-mini",
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": text}],
              "temperature": 0})
    return json.loads(r.json()["choices"][0]["message"]["content"])

# ════════ الجزء 3: إرسال + استقبال ════════
def send(cmds):
    ids = []
    for c in cmds:
        r = requests.post(f"{RELAY}/cmd", headers=H,
                          json={"session": SESSION, **c}, timeout=10)
        print(f"  ➤ أُرسل: {c['action']} -> {r.json().get('cmdId')}")
        ids.append(r.json().get("cmdId"))
    return ids

def wait_results(seconds=8):
    global result_cursor
    import requests as rq
    end = time.time() + seconds
    got = []
    while time.time() < end:
        r = rq.get(f"{RELAY}/results", headers=H,
                   params={"session": SESSION, "since": result_cursor}, timeout=10)
        for res in r.json()["results"]:
            result_cursor = r.json()["next"]
            status = "✔ نجح" if res.get("ok") else f"✘ فشل: {res.get('result', {}).get('error')}"
            print(f"  ✦ [{res.get('action')}] {status}")
            got.append(res)
            if res.get("action") == "ping":
                print(f"    ⏱ زمن الاستجابة الكلي: {round(time.time()*1000 - ping_start)}ms")
        time.sleep(1)
    return got

ping_start = 0

def main():
    global ping_start
    # فحص السيرفر
    try:
        h = requests.get(f"{RELAY}/health", headers=H, timeout=5).json()
        print(f"[AI] السيرفر حيّ ✔ | الجلسات: {h['sessions']}")
    except Exception as e:
        print(f"[AI] ✘ السيرفر غير متاح: {e}"); sys.exit(1)

    print("[AI] فحص الاتصال مع Roblox (ping)...")
    ping_start = time.time() * 1000
    send([{"action": "ping", "args": {}}])
    res = wait_results(10)
    if not any(r.get("action") == "ping" for r in res):
        print("[AI] ✘ لا يوجد رد من Roblox — تأكد أن السكربت يعمل داخل Studio Lite و HttpService مفعّل")
        return
    print("[AI] ✔ الاتصال مع Roblox مؤكد!\n")

    print("اكتب أوامرك للـ AI (اكتب 'خروج' للإنهاء):")
    while True:
        text = input("\n🧠 AI> ").strip()
        if text in ("خروج", "exit", "quit"): break
        cmds = parse_text(text)
        if cmds is None:
            if OPENAI_KEY:
                try: cmds = llm_plan(text)
                except Exception as e: print(f"  ✘ LLM خطأ: {e}"); continue
            else:
                print("  ؟ لم أفهم الطلب (وضع LLM غير مفعّل — ضع OPENAI_KEY لفهم أعمق)")
                continue
        print(f"  [AI] خطة التنفيذ: {len(cmds)} أمر")
        send(cmds)
        wait_results()

if __name__ == "__main__":
    main()
