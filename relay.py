# relay.py — AI ↔ Roblox Relay (Render-Ready)
from aiohttp import web
import asyncio, time, os

API_KEY = os.environ.get("API_KEY", "ROBLOX_AI_KEY_2026")  # من متغيرات بيئة Render

queues: dict = {}
results: dict = {}

def auth(req):
    return req.headers.get("X-Auth") == API_KEY

async def ai_send(req):
    if not auth(req): return web.Response(status=401, text="bad key")
    d = await req.json()
    sid = d.get("session", "default")
    d["id"] = f"cmd_{time.time_ns()}"
    await queues.setdefault(sid, asyncio.Queue()).put(d)
    print(f"[RELAY] AI -> Roblox | {d['action']} ({d['id']})")
    return web.json_response({"ok": True, "cmdId": d["id"]})

async def rbx_poll(req):
    if not auth(req): return web.Response(status=401)
    q = queues.setdefault(req.query.get("session", "default"), asyncio.Queue())
    cmds = []
    try:
        while len(cmds) < 25:
            cmds.append(await asyncio.wait_for(q.get(), timeout=1.5))
    except asyncio.TimeoutError:
        pass
    return web.json_response({"commands": cmds})

async def rbx_result(req):
    if not auth(req): return web.Response(status=401)
    d = await req.json()
    results.setdefault(d.get("session", "default"), []).append(d)
    print(f"[RELAY] Roblox -> AI | {d.get('action')} | ok={d.get('ok')}")
    return web.json_response({"ok": True})

async def ai_results(req):
    if not auth(req): return web.Response(status=401)
    sid = req.query.get("session", "default")
    idx = int(req.query.get("since", "0"))
    lst = results.get(sid, [])
    return web.json_response({"results": lst[idx:], "next": len(lst)})

async def health(req):
    return web.json_response({"status": "alive", "sessions": list(queues.keys())})

app = web.Application()
app.router.add_post("/cmd", ai_send)
app.router.add_get("/poll", rbx_poll)
app.router.add_post("/result", rbx_result)
app.router.add_get("/results", ai_results)
app.router.add_get("/health", health)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Render يضبط PORT تلقائياً
    print(f"=== AI-Relay on port {port} ===")
    web.run_app(app, host="0.0.0.0", port=port)
