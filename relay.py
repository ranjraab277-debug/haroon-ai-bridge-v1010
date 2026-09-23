# relay.py — AI + Relay + واجهة محادثة للهاتف (النسخة النهائية v2)
from aiohttp import web
import asyncio, time, os, re

API_KEY = os.environ.get("API_KEY", "ROBLOX_AI_KEY_2026")  # مفتاح سكربت Roblox
AI_KEY  = os.environ.get("AI_KEY",  "MY_AI_PASS_123")      # كلمة مرور واجهة المحادثة

queues:  dict = {}
results: dict = {}

def auth(req):
    return req.headers.get("X-Auth") == API_KEY

# ── المحلل الذكي المدمج (عربي/إنجليزي) ──────────────
COLORS = {"احمر":[196,40,28],"أحمر":[196,40,28],"red":[196,40,28],
          "ازرق":[13,105,172],"أزرق":[13,105,172],"blue":[13,105,172],
          "اخضر":[75,151,75],"أخضر":[75,151,75],"green":[75,151,75],
          "اصفر":[245,205,48],"أصفر":[245,205,48],"yellow":[245,205,48],
          "ابيض":[242,243,243],"أبيض":[242,243,243],"white":[242,243,243],
          "اسود":[27,42,53],"أسود":[27,42,53],"black":[27,42,53]}

def parse_text(text):
    t = text.lower().strip()
    if t in ("ping","فحص","اتصال"):
        return [{"action":"ping","args":{}}]
    if any(w in t for w in ("احذف","امسح","delete")):
        name = re.sub(r'(احذف|امسح|delete)', '', text).strip() or "AIPart"
        return [{"action":"delete","args":{"name":name}}]
    if any(w in t for w in ("انشئ","أنشئ","اصنع","جدار","مكعب","part","wall","cube","create")):
        name, size, pos, color = "AIPart", [4,1,4], [0,10,0], [163,162,165]
        m = re.search(r'اسم[:\s]+(\S+)', text)
        if m: name = m.group(1)
        if "جدار" in t or "wall" in t: size = [40,10,4]
        m = re.search(r'(?:بحجم|size)\s+(-?\d+)[\s,xX]+(-?\d+)[\s,xX]+(-?\d+)', t)
        if m: size = [int(m.group(i)) for i in (1,2,3)]
        m = re.search(r'(?:في|at|position)\s+(-?\d+)[\s,]+(-?\d+)[\s,]+(-?\d+)', t)
        if m: pos = [int(m.group(i)) for i in (1,2,3)]
        for cn, rgb in COLORS.items():
            if cn in t: color = rgb; break
        m = re.search(r'(?:لون|color)\s+rgb\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)', t)
        if m: color = [int(m.group(i)) for i in (1,2,3)]
        return [{"action":"createPart","args":{"name":name,"size":size,"position":pos,"color":color}}]
    if any(w in t for w in ("غيّر","غير","set","شفافية","ثبت","ثبّت")):
        name = "AIPart"
        m = re.search(r'اسم[:\s]+(\S+)', text)
        if m: name = m.group(1)
        cmds = []
        m = re.search(r'شفافية\s+(\d+)', t)
        if m: cmds.append({"action":"setProperty","args":{"name":name,"property":"Transparency","value":int(m.group(1))/10}})
        if any(w in t for w in ("ثبت","ثبّت","anchor")):
            cmds.append({"action":"setProperty","args":{"name":name,"property":"Anchored","value":True}})
        m = re.search(r'(?:لون|color)\s+rgb\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)', t)
        if m: cmds.append({"action":"setProperty","args":{"name":name,"property":"Color","value":[int(m.group(i)) for i in (1,2,3)]}})
        return cmds or [{"action":"ping","args":{}}]
    return None

# ── إدراج الأوامر في الطابور (داخلي) ──────────────
async def enqueue(cmds, session="map1"):
    ids = []
    for c in cmds:
        c["id"] = f"cmd_{time.time_ns()}"
        await queues.setdefault(session, asyncio.Queue()).put(c)
        ids.append(c["id"])
    return ids

# ── مسارات Roblox ──────────────
async def ai_send(req):
    if not auth(req): return web.Response(status=401, text="bad key")
    d = await req.json()
    d["id"] = f"cmd_{time.time_ns()}"
    await queues.setdefault(d.get("session","default"), asyncio.Queue()).put(d)
    print(f"[RELAY] AI -> Roblox | {d['action']} ({d['id']})")
    return web.json_response({"ok":True,"cmdId":d["id"]})

async def rbx_poll(req):
    if not auth(req): return web.Response(status=401)
    q = queues.setdefault(req.query.get("session","default"), asyncio.Queue())
    cmds = []
    try:
        while len(cmds) < 25:
            cmds.append(await asyncio.wait_for(q.get(), timeout=1.5))
    except asyncio.TimeoutError:
        pass
    return web.json_response({"commands":cmds})

async def rbx_result(req):
    if not auth(req): return web.Response(status=401)
    d = await req.json()
    results.setdefault(d.get("session","default"), []).append(d)
    print(f"[RELAY] Roblox -> AI | {d.get('action')} | ok={d.get('ok')}")
    return web.json_response({"ok":True})

async def ai_results(req):
    if not auth(req): return web.Response(status=401)
    sid = req.query.get("session","default")
    idx = int(req.query.get("since","0"))
    lst = results.get(sid,[])
    return web.json_response({"results":lst[idx:],"next":len(lst)})

# ── واجهة المحادثة للهاتف ──────────────
PAGE = """<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🤖 AI Bridge</title><style>
body{font-family:sans-serif;background:#111;color:#eee;max-width:600px;margin:auto;padding:10px}
#log{height:60vh;overflow-y:auto;border:1px solid #333;border-radius:10px;padding:10px;margin-bottom:10px}
.me{background:#1c4;color:#000;border-radius:10px;padding:6px 10px;margin:5px 0;display:table;margin-left:auto}
.ai{background:#333;border-radius:10px;padding:6px 10px;margin:5px 0;display:table}
input,button{width:100%;padding:12px;margin:3px 0;border-radius:8px;border:none;box-sizing:border-box}
button{background:#0a7;font-weight:bold}
.k{background:#222;padding:8px;border-radius:8px;margin-bottom:10px}
</style></head><body>
<h3>🤖 AI ↔ Roblox Bridge</h3>
<div class="k">🔑 <input id="pass" placeholder="كلمة مرور AI"></div>
<div id="log"></div>
<input id="msg" placeholder="مثال: أنشئ جدار لون أزرق في 0 5 -20 اسم Wall1">
<button onclick="send()">إرسال ➤</button>
<script>
function log(t,c){const d=document.createElement('div');d.className=c;d.textContent=t;
document.getElementById('log').appendChild(d);document.getElementById('log').scrollTop=1e9}
async function send(){const m=document.getElementById('msg').value.trim();if(!m)return;
document.getElementById('msg').value='';log('👤 '+m,'me');
const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({pass:document.getElementById('pass').value,text:m})});
const j=await r.json();
if(j.error){log('⚠ '+j.error,'ai');return}
for(const c of j.commands)log('🤖 أمر: '+c.action+' → '+JSON.stringify(c.args),'ai');
if(j.exec&&j.exec.length){for(const e of j.exec)
log(e.ok?'✅ نجح: '+e.action:'❌ فشل: '+e.action+' — '+(e.result&&e.result.error||''),'ai')}
else log('⏳ لا رد من Roblox بعد — تأكد أن التجربة تعمل في Studio Lite','ai')}
document.getElementById('msg').addEventListener('keydown',e=>{if(e.key=='Enter')send()});
</script></body></html>"""

async def index(req):
    return web.Response(text=PAGE, content_type="text/html")

async def chat(req):
    d = await req.json()
    if d.get("pass") != AI_KEY:
        return web.json_response({"error":"كلمة المرور خاطئة"}, status=401)
    cmds = parse_text(d.get("text",""))
    if not cmds:
        return web.json_response({"commands":[],
            "note":"لم أفهم الطلب — جرّب: أنشئ جدار لون أحمر بحجم 40 10 4 في 0 5 0 اسم Wall1"})
    cursor = len(results.get("map1",[]))
    await enqueue(cmds, "map1")
    # انتظار النتائج حتى 8 ثوانٍ
    exec_results = []
    end = time.time() + 8
    while time.time() < end and len(exec_results) < len(cmds):
        exec_results = results.get("map1",[])[cursor:]
        await asyncio.sleep(0.5)
    return web.json_response({"commands":cmds, "exec":exec_results})

async def health(req):
    return web.json_response({"status":"alive","sessions":list(queues.keys())})

app = web.Application()
app.router.add_get("/", index)
app.router.add_post("/chat", chat)
app.router.add_post("/cmd", ai_send)
app.router.add_get("/poll", rbx_poll)
app.router.add_post("/result", rbx_result)
app.router.add_get("/results", ai_results)
app.router.add_get("/health", health)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"=== AI-Relay v2 (Chat UI) on port {port} ===")
    web.run_app(app, host="0.0.0.0", port=port)
