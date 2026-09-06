"""Loopback-only offline fixture. It does NOT generate 3D models or spend credits."""
from __future__ import annotations

import base64
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import struct
import threading
import time
import urllib.parse

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7WQAAAAASUVORK5CYII=")


def fixture_glb():
    vertices = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    document = {
        "asset": {"version": "2.0", "generator": "OFFLINE TEST FIXTURE - NOT MESHY GENERATED"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "buffers": [{"byteLength": len(vertices)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(vertices)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                       "min": [0, 0, 0], "max": [1, 1, 0]}],
    }
    encoded = json.dumps(document).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 28 + len(encoded) + len(vertices)) +
            struct.pack("<I4s", len(encoded), b"JSON") + encoded +
            struct.pack("<I4s", len(vertices), b"BIN\x00") + vertices)


class MockState:
    def __init__(self):
        self.balance = 3000
        self.tasks = {}
        self.requests = []
        self.post_status = None
        self.accept_then_fail = False
        self.malformed_post = False
        self.get_failures = []
        self.task_status = "SUCCEEDED"
        self.consumed = 30
        self.running_credits = None
        self.asset_status = 200
        self.model_data = fixture_glb()
        self.polls_until_done = 1
        self.bad_content_range = False

    @property
    def posts(self):
        return [request for request in self.requests if request["method"] == "POST"]


@contextlib.contextmanager
def mock_server(state=None):
    state = state or MockState()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, status, value, content_type="application/json"):
            data = json.dumps(value).encode("utf-8") if content_type == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            state.requests.append({"method": "POST", "path": self.path, "payload": payload,
                                   "authorization": self.headers.get("Authorization")})
            if self.path not in {"/openapi/v1/multi-image-to-3d", "/openapi/v1/image-to-3d", "/openapi/v1/retexture", "/openapi/v1/text-to-image", "/openapi/v1/image-to-image", "/openapi/v1/rigging", "/openapi/v1/animations", "/openapi/v1/text-to-motion"}:
                return self.respond(404, {})
            if state.post_status and not state.accept_then_fail:
                return self.respond(state.post_status, {"message": "injected rejection"})
            task_id = f"mock-{len(state.tasks) + 1:04d}"
            debit = (15 if payload.get("texture_resolution") == "8k" else 10) if self.path.endswith("/retexture") else 30
            image_task = self.path.endswith(("/text-to-image", "/image-to-image"))
            if image_task:
                debit = 9
            if self.path.endswith("/rigging"):
                debit = 5
            if self.path.endswith("/animations"):
                debit = 3
            if self.path.endswith('/text-to-motion'):
                debit = 3 if payload.get('mode') == 'swift' else 10
            state.balance -= debit
            state.tasks[task_id] = {"id": task_id, "name": payload.get("name"), "polls": 0,
                                    "image_task": image_task, "prompt": payload.get("prompt"),
                                    "ai_model": payload.get("ai_model"), "created_at": time.time() * 1000,
                                    "endpoint": self.path, "debit": debit,
                                    "mode": payload.get('mode', 'prime'),
                                    "textured": payload.get("should_texture", True),
                                    "save_source": payload.get("save_pre_remeshed_model", False)}
            if state.post_status:
                return self.respond(state.post_status, {"message": "accepted but response failed"})
            self.respond(202, {} if state.malformed_post else {"result": task_id})

        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            state.requests.append({"method": "GET", "path": self.path,
                                   "range": self.headers.get("Range"),
                                   "authorization": self.headers.get("Authorization")})
            if parsed.path.startswith("/assets/"):
                if state.asset_status != 200:
                    return self.respond(state.asset_status, {})
                data = state.model_data if parsed.path.endswith(".glb") else b"Kaydara FBX Binary  \x00\x1a\x00fixture" if parsed.path.endswith(".fbx") else PNG
                if parsed.path.endswith('.bvh'):
                    data = b'HIERARCHY\nROOT Hips { OFFSET 0 0 0 CHANNELS 0 }\nMOTION\nFrames: 1\nFrame Time: 0.033333\n'
                if self.headers.get("Range"):
                    start, end = (int(value) for value in self.headers["Range"].removeprefix("bytes=").split("-"))
                    chunk = data[start:end + 1]
                    self.send_response(206)
                    self.send_header("Content-Length", str(len(chunk)))
                    self.send_header("Content-Range", "invalid" if state.bad_content_range else f"bytes {start}-{end}/{len(data)}")
                    self.end_headers()
                    self.wfile.write(chunk)
                    return
                return self.respond(200, data, "model/gltf-binary" if parsed.path.endswith(".glb") else "image/png")
            if self.headers.get("Authorization") != "Bearer mock-key":
                return self.respond(401, {})
            if state.get_failures:
                return self.respond(state.get_failures.pop(0), {})
            if parsed.path == "/openapi/v1/balance":
                return self.respond(200, {"balance": state.balance})
            if parsed.path in {"/openapi/v1/multi-image-to-3d", "/openapi/v1/image-to-3d", "/openapi/v1/retexture", "/openapi/v1/text-to-image", "/openapi/v1/image-to-image"}:
                return self.respond(200, [{"id": task["id"], "name": task["name"]} for task in state.tasks.values()
                                         if task["endpoint"] == parsed.path])
            task_id = parsed.path.rsplit("/", 1)[-1]
            if task_id not in state.tasks:
                return self.respond(404, {})
            record = state.tasks[task_id]
            if parsed.path != record["endpoint"] + "/" + task_id:
                return self.respond(404, {})
            record["polls"] += 1
            terminal = record["polls"] > state.polls_until_done
            status = state.task_status if terminal else "IN_PROGRESS"
            observed = state.consumed if terminal else state.running_credits
            if terminal and "settled" not in record:
                state.balance += record["debit"] - (observed if observed is not None else record["debit"])
                record["settled"] = True
            asset = state.origin + "/assets/"
            task = {"id": task_id, "name": record["name"], "status": status, "progress": 100 if terminal else 35,
                    "consumed_credits": observed, "expires_at": 1800000000000,
                    "model_urls": {"glb": asset + "model.glb"},
                    "texture_urls": [{"base_color": asset + "base_color.png", "normal": asset + "normal.png"}],
                    "thumbnail_url": asset + "preview.png",
                    "thumbnail_urls": {side: asset + side + ".png" for side in ("front", "right", "back", "left")}}
            if record["save_source"]:
                task["model_urls"]["pre_remeshed_glb"] = asset + "pre_remeshed.glb"
            if not record["textured"]:
                task["texture_urls"] = []
            if record["image_task"]:
                task = {key: task[key] for key in ("id", "status", "progress", "consumed_credits", "expires_at")}
                task.update(image_urls=[asset + "generated.png"], prompt=record["prompt"],
                            ai_model=record["ai_model"], created_at=record["created_at"])
            if record["endpoint"].endswith(("/rigging", "/animations")):
                task = {key: task[key] for key in ("id", "status", "progress", "consumed_credits", "expires_at")}
                task["result"] = ({"rigged_character_glb_url": asset + "model.glb",
                    "rigged_character_fbx_url": asset + "rigged.fbx", "basic_animations": {
                    "walking_glb_url": asset + "walk.glb", "running_glb_url": asset + "run.glb"}}
                    if record["endpoint"].endswith("/rigging") else {
                    "animation_glb_url": asset + "model.glb", "animation_fbx_url": asset + "animation.fbx"})
            if record['endpoint'].endswith('/text-to-motion'):
                task = {key: task[key] for key in ('id', 'status', 'progress', 'consumed_credits', 'expires_at')}
                fmt = 'bvh' if record['mode'] == 'swift' else 'fbx'
                task['result'] = {'motion_url': asset + 'motion.' + fmt, 'motion_format': fmt}
            self.respond(200, task)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.origin = f"http://127.0.0.1:{server.server_port}"
    state.base = state.origin + "/openapi/v1"
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
