# -*- coding: utf-8 -*-
"""EU4 陪玩面板后端。
- 监测存档文件夹，存档一变就解析 + 让 Claude 生成年度简报，推给前端
- WebSocket 收发聊天
启动:  python -m uvicorn server:app --port 8777
"""
import os, asyncio, json, time, argparse, traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import eu4_parser as P
import claude_bridge as CB

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.environ.get("EU4_SAVE_DIR") or P.find_dir()
POLL = float(os.environ.get("EU4_POLL", "4"))

app = FastAPI()

# 共享状态
STATE = {
    "save_path": None,
    "save_mtime": None,
    "state": None,       # 当前抽取的状态
    "prev_state": None,  # 上一年状态(复盘用)
    "briefing": None,    # 当前年度简报
    "history": [],       # 聊天记录 [{'role','text'}]
}
CLIENTS = set()
LOCK = asyncio.Lock()


async def broadcast(msg):
    dead = []
    for ws in CLIENTS:
        try:
            await ws.send_text(json.dumps(msg, ensure_ascii=False))
        except Exception:
            dead.append(ws)
    for ws in dead:
        CLIENTS.discard(ws)


def snapshot_msg():
    return {"kind": "snapshot", "state": STATE["state"], "briefing": STATE["briefing"],
            "history": STATE["history"], "save_dir": SAVE_DIR}


async def process_save(path):
    """解析存档 + 生成简报，更新共享状态并广播。"""
    try:
        top = await asyncio.to_thread(P.parse_save, path)
        new_state = P.extract_state(top)
    except Exception as e:
        await broadcast({"kind": "error", "text": f"解析失败: {e}"})
        return
    async with LOCK:
        STATE["prev_state"] = STATE["state"]
        STATE["state"] = new_state
        year = new_state.get("year")
        await broadcast({"kind": "state", "state": new_state})
        await broadcast({"kind": "toast", "text": f"📅 {year} 年存档已读取，正在生成战略简报…"})
    # 让 Claude 生成简报(慢, 放线程池)
    brief = await asyncio.to_thread(CB.briefing, new_state, STATE["prev_state"])
    async with LOCK:
        STATE["briefing"] = brief
    await broadcast({"kind": "briefing", "briefing": brief, "state": new_state})


async def watcher():
    if not SAVE_DIR:
        print("⚠️ 没找到存档文件夹，设环境变量 EU4_SAVE_DIR 指定。")
        return
    print(f"👀 监测存档: {SAVE_DIR}")
    # 启动时先读一次最新存档
    last = None
    first = True
    while True:
        try:
            cur = P.latest_save(SAVE_DIR)
            if cur:
                mt = os.path.getmtime(cur)
                if cur != STATE["save_path"] or mt != STATE["save_mtime"]:
                    if not first:
                        await asyncio.sleep(1.2)  # 等游戏写完
                    STATE["save_path"] = cur
                    STATE["save_mtime"] = os.path.getmtime(cur)
                    await process_save(cur)
            first = False
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(POLL)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(watcher())


@app.get("/")
async def index():
    return FileResponse(os.path.join(HERE, "web", "index.html"))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    CLIENTS.add(ws)
    try:
        await ws.send_text(json.dumps(snapshot_msg(), ensure_ascii=False))
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("action") == "chat":
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                async with LOCK:
                    STATE["history"].append({"role": "user", "text": text})
                await broadcast({"kind": "chat", "role": "user", "text": text})
                await broadcast({"kind": "thinking"})
                if not STATE["state"]:
                    reply = "还没读到存档。先在游戏里存一次档（普通局、非铁人），或确认存档文件夹路径。"
                else:
                    reply = await asyncio.to_thread(
                        CB.chat, STATE["history"], STATE["state"], STATE["briefing"])
                async with LOCK:
                    STATE["history"].append({"role": "assistant", "text": reply})
                await broadcast({"kind": "chat", "role": "assistant", "text": reply})
            elif msg.get("action") == "reanalyze":
                if STATE["save_path"]:
                    await process_save(STATE["save_path"])
    except WebSocketDisconnect:
        pass
    finally:
        CLIENTS.discard(ws)


app.mount("/web", StaticFiles(directory=os.path.join(HERE, "web")), name="web")


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--dir", help="存档文件夹")
    a = ap.parse_args()
    if a.dir:
        os.environ["EU4_SAVE_DIR"] = a.dir
        SAVE_DIR = a.dir
    uvicorn.run("server:app", host="127.0.0.1", port=a.port, reload=False)
