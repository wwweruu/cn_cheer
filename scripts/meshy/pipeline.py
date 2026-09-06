"""Meshy multi-image candidate pipeline. Python 3.10+, standard library only.

Live requests use a fixed official origin. A durable reservation precedes each
paid POST; an uncertain response is never automatically submitted again.
"""
from __future__ import annotations

import base64
import contextlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
API = "https://api.meshy.ai/openapi/v1"
ENDPOINT = "/multi-image-to-3d"
SINGLE_IMAGE = "/image-to-3d"
RETEXTURE = "/retexture"
TEXT_IMAGE = "/text-to-image"
EDIT_IMAGE = "/image-to-image"
RIGGING = "/rigging"
ANIMATION = "/animations"
TEXT_MOTION = "/text-to-motion"
IMAGE_ENDPOINTS = {TEXT_IMAGE, EDIT_IMAGE}
PRICE_DATE = "2026-09-05"
BUDGET = 1800
BALANCE_FLOOR = 1200
RANGE_THRESHOLD = 32 * 1024 * 1024
RANGE_BYTES = 8 * 1024 * 1024
MAX_VARIANTS = 3
UNCERTAIN = {"RESERVED", "UNKNOWN"}
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELED"}


class PipelineError(Exception):
    pass


class ApiError(PipelineError):
    def __init__(self, status=None, detail=None):
        self.status = status
        self.detail = detail
        message = f"Meshy HTTP {status}" if status else "Network/invalid JSON response"
        super().__init__(message + (f": {detail}" if detail else ""))


def checked_endpoint(endpoint):
    if endpoint not in {ENDPOINT, SINGLE_IMAGE, RETEXTURE, TEXT_IMAGE, EDIT_IMAGE, RIGGING, ANIMATION, TEXT_MOTION}:
        raise PipelineError("Unsupported paid endpoint")
    return endpoint


def credit(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise PipelineError("Credit value must be a finite non-negative number")
    if not math.isfinite(value) or value < 0:
        raise PipelineError("Invalid credit value")
    return value


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def workspace_lock(directory):
    """OS lock, automatically released if the process exits or crashes."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "pipeline.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise PipelineError("Another Meshy process holds this project's lock") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_key(root=ROOT):
    key = os.environ.get("MESHY_API_KEY", "").strip()
    env = root / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.strip().removeprefix("export ").partition("=")
            if separator and name.strip() == "MESHY_API_KEY":
                key = value.strip().strip("\"'")
    if not re.fullmatch(r"msy_[A-Za-z0-9_-]+", key):
        raise PipelineError("Set MESHY_API_KEY in the project .env; do not use VITE_MESHY_API_KEY")
    return key


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, key, *, test_base=None, sleep=time.sleep, timeout=60):
        self.base = API
        self.test_origin = None
        if test_base:
            parsed = urllib.parse.urlsplit(test_base)
            if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or key != "mock-key":
                raise PipelineError("Test transport only accepts loopback and the dummy key")
            self.base = test_base.rstrip("/")
            self.test_origin = f"{parsed.scheme}://{parsed.netloc}"
        self.key = key
        self.sleep = sleep
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, body=None):
        if not path.startswith("/") or path.startswith("//"):
            raise PipelineError("Invalid API path")
        data = None if body is None else json.dumps(body).encode("utf-8")
        # Never retry a paid POST: even a timeout can mean it was accepted.
        attempts = 4 if method == "GET" else 1
        for attempt in range(attempts):
            request = urllib.request.Request(self.base + path, data=data, method=method,
                headers={"Authorization": "Bearer " + self.key,
                         "Content-Type": "application/json", "User-Agent": "cn-cheer-meshy-demo/1"})
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    raw = response.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024:
                    raise ApiError()
                return json.loads(raw)
            except urllib.error.HTTPError as error:
                status = error.code
                detail = None
                try:
                    failure = json.loads(error.read(8192))
                    candidate = failure.get('message') or failure.get('detail')
                    if isinstance(candidate, list):
                        candidate = '; '.join(str(item.get('msg', '')) for item in candidate if isinstance(item, dict))
                    if isinstance(candidate, str):
                        candidate = candidate.replace(self.key, '[redacted]')
                        candidate = re.sub(r'data:[^\s\"]+|msy_[A-Za-z0-9_-]+', '[redacted]', candidate)
                        detail = candidate[:500]
                except (ValueError, AttributeError):
                    pass
                error.close()
                if method != "GET" or status not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                    raise ApiError(status, detail) from None
            except (OSError, ValueError):
                if method != "GET" or attempt == attempts - 1:
                    raise ApiError() from None
            self.sleep(min(2 ** attempt, 8))
        raise ApiError()

    def balance(self):
        result = self.request("GET", "/balance")
        if not isinstance(result, dict) or "balance" not in result:
            raise PipelineError("Balance response is missing balance")
        return credit(result["balance"])

    def task(self, task_id, endpoint=ENDPOINT):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", task_id):
            raise PipelineError("Invalid task ID")
        return self.request("GET", checked_endpoint(endpoint) + "/" + task_id)

    def tasks(self, page=1, endpoint=ENDPOINT):
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise PipelineError("page must be at least 1")
        # OpenAPI's shared task-list PageSize has maximum 10; Usage has a separate 100 limit.
        result = self.request("GET", checked_endpoint(endpoint) + f"?page_num={page}&page_size=10&sort_by=-created_at")
        if not isinstance(result, list):
            raise PipelineError("Unexpected task list response")
        return result

    def download(self, url, destination):
        parsed = urllib.parse.urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        official = parsed.scheme == "https" and (
            parsed.hostname == "meshy.ai" or (parsed.hostname or "").endswith(".meshy.ai"))
        if parsed.username or parsed.password or not (official or (self.test_origin and origin == self.test_origin)):
            raise PipelineError("Unexpected asset host; review the saved task response before downloading")
        temporary = destination.with_suffix(destination.suffix + ".part")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Asset requests deliberately have no Authorization header; redirects disabled.
            head = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "cn-cheer-meshy-demo/1"})
            length = 0
            try:
                with self.opener.open(head, timeout=min(self.timeout, 20)) as response:
                    length = int(response.headers.get("Content-Length", 0))
            except (OSError, urllib.error.URLError):
                pass  # Some asset hosts omit HEAD; the streaming GET path still validates size.
            if length > 256 * 1024 * 1024:
                raise PipelineError("Asset exceeds the 256 MiB local download limit")
            if length > RANGE_THRESHOLD:
                with temporary.open("wb") as output:
                    self.download_ranges(url, output, length)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, destination)
                return
            request = urllib.request.Request(url, headers={"User-Agent": "cn-cheer-meshy-demo/1"})
            with self.opener.open(request, timeout=self.timeout) as response, temporary.open("wb") as output:
                size = 0
                length = int(response.headers.get("Content-Length", 0))
                if length > 256 * 1024 * 1024:
                    raise PipelineError("Asset exceeds the 256 MiB local download limit")
                if length > RANGE_THRESHOLD:
                    response.close()
                    self.download_ranges(url, output, length)
                    size = length
                else:
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > 256 * 1024 * 1024:
                            raise PipelineError("Asset exceeds the 256 MiB local download limit")
                        output.write(chunk)
                if not size:
                    raise PipelineError("Downloaded asset is empty")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
        except (OSError, urllib.error.URLError):
            raise PipelineError("Asset download failed; resume fetches fresh URLs without a paid POST") from None
        finally:
            temporary.unlink(missing_ok=True)

    def download_ranges(self, url, output, length):
        """Bounded, verified range GETs avoid stalls on large source GLBs; no API auth."""
        def fetch(start):
            end = min(length, start + RANGE_BYTES) - 1
            expected = end - start + 1
            for attempt in range(3):
                request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}",
                    "User-Agent": "cn-cheer-meshy-demo/1"})
                try:
                    with urllib.request.build_opener(NoRedirect()).open(request, timeout=min(self.timeout, 30)) as response:
                        if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{length}":
                            raise PipelineError("Asset server did not return the requested byte range")
                        data = response.read(expected + 1)
                    if len(data) != expected:
                        raise PipelineError("Incomplete asset byte range")
                    return start, data
                except (OSError, urllib.error.URLError):
                    if attempt == 2:
                        raise
                    self.sleep(2 ** attempt)
        with ThreadPoolExecutor(max_workers=4) as workers:
            futures = [workers.submit(fetch, start) for start in range(0, length, RANGE_BYTES)]
            for future in as_completed(futures):
                start, data = future.result()
                output.seek(start)
                output.write(data)


def estimate(params):
    """Fail closed for configurations outside this reviewed pricing snapshot."""
    if params.get("ai_model") not in {"meshy-6", "meshy-7"}:
        raise PipelineError("Only pinned meshy-6/meshy-7 are priced; do not use latest")
    if params.get("target_formats") != ["glb"] or params.get("auto_size") is not False:
        raise PipelineError("This profile exports GLB without automatic sizing")
    if params.get("should_texture") is False:
        if (params.get("ai_model") != "meshy-7" or params.get("ultra_mode") is not True
                or params.get("should_remesh") is not False or params.get("pose_mode") != ""
                or any(key in params for key in ("target_polycount", "decimation_mode", "texture_resolution", "topology"))):
            raise PipelineError("Geometry master requires Meshy 7 Ultra, no remesh or forced pose")
        return 25
    if params.get("ultra_mode") is not False or params.get("texture_resolution") not in {"2k", "4k", "8k"}:
        raise PipelineError("This budget profile requires Ultra off and an explicit 2k/4k/8k texture tier")
    if params.get("should_texture") is not True or params.get("enable_pbr") is not True:
        raise PipelineError("This project profile requires textured PBR candidates")
    return 35 if params["texture_resolution"] == "8k" else 30


def load_jobs(selection="pilot", variant=1, root=ROOT, *, texture_resolution=None,
              save_source=False, target_polycount=None, geometry_master=False, image_enhancement=None,
              reference_views=None, single_image=False):
    if variant not in range(1, MAX_VARIANTS + 1):
        raise PipelineError(f"variant must be 1..{MAX_VARIANTS}")
    if geometry_master and (texture_resolution is not None or target_polycount is not None):
        raise PipelineError("Geometry master is untextured and must not specify a target polycount")
    config = json.loads((root / "scripts/meshy/pieces.json").read_text(encoding="utf-8"))
    view_names = {"front": "正面.jpg", "side": "侧面.jpg", "back": "背面.jpg"}
    views = [view_names["front"]] if single_image else config["views"]
    if reference_views is not None:
        selected_views = reference_views.split(",")
        if not selected_views or len(set(selected_views)) != len(selected_views) or set(selected_views) - view_names.keys():
            raise PipelineError("reference_views must be unique front,side,back names")
        views = [view_names[name] for name in selected_views]
    if single_image and len(views) != 1:
        raise PipelineError("Image-to-3D requires exactly one reference view")
    known = {piece["id"] for piece in config["pieces"]}
    selected = known if selection == "all" else (
        {piece["id"] for piece in config["pieces"] if piece.get("pilot")} if selection == "pilot"
        else set(selection.split(",")))
    if not selected or selected - known:
        raise PipelineError("Unknown piece selection: " + ", ".join(sorted(selected - known)))
    jobs = []
    for piece in config["pieces"]:
        if piece["id"] not in selected:
            continue
        if not re.fullmatch(r"[a-z]+_(red|black)", piece["id"]):
            raise PipelineError("Invalid piece ID")
        params = {**config["request"], "target_polycount": piece["target_polycount"]}
        if image_enhancement is not None:
            if not isinstance(image_enhancement, bool):
                raise PipelineError("image_enhancement must be boolean")
            params["image_enhancement"] = image_enhancement
        if texture_resolution is not None:
            params["texture_resolution"] = texture_resolution
        if target_polycount is not None:
            params["target_polycount"] = target_polycount
        if save_source:
            params["save_pre_remeshed_model"] = True
        if not 100 <= params["target_polycount"] <= 300000:
            raise PipelineError("target_polycount is outside the documented range")
        if geometry_master:
            for field in ("texture_resolution", "enable_pbr", "remove_lighting", "target_polycount",
                          "topology", "decimation_mode", "save_pre_remeshed_model"):
                params.pop(field, None)
            params.update(ai_model="meshy-7", ultra_mode=True, should_remesh=False,
                          should_texture=False, pose_mode="")
        cost = estimate(params)
        images = []
        for view in views:
            path = (root / config["reference_root"] / piece["reference"] / view).resolve()
            if not path.is_relative_to(root.resolve()):
                raise PipelineError("Reference must be inside this project")
            if not path.is_file():
                raise PipelineError(f"Missing reference: {path}; extract the project's JPG backup first")
            data = path.read_bytes()
            if len(data) > 20 * 1024 * 1024:
                raise PipelineError("Reference exceeds the demo's 20 MiB per-image limit")
            mime = "image/jpeg" if data.startswith(b"\xff\xd8\xff") else (
                "image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else None)
            if not mime:
                raise PipelineError(f"Reference is not a JPEG/PNG: {path}")
            images.append({"path": str(path.relative_to(root.resolve())), "mime": mime,
                           "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        if not 1 <= len(images) <= 4:
            raise PipelineError("Meshy accepts 1..4 separate views")
        fingerprint_inputs = {"params": params, "images": images}
        if single_image:
            fingerprint_inputs["endpoint"] = SINGLE_IMAGE
        digest = hashlib.sha256(json.dumps(fingerprint_inputs, sort_keys=True,
            ensure_ascii=False).encode("utf-8")).hexdigest()
        jobs.append({"key": f"{piece['id']}/v{variant}", "piece": piece["id"], "variant": variant,
                     "fingerprint": digest, "params": params, "images": images, "estimate": cost})
        if single_image:
            jobs[-1]["endpoint"] = SINGLE_IMAGE
    return jobs


def make_payload(job, name, root=ROOT):
    images = []
    for item in job["images"]:
        data = (root / item["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise PipelineError("Reference changed since preflight; run plan again")
        images.append(f"data:{item['mime']};base64," + base64.b64encode(data).decode("ascii"))
    if job.get("endpoint") in IMAGE_ENDPOINTS:
        # Image APIs document prompt/model but no name field. The durable local
        # record keeps our name; uncertain recovery verifies the original prompt.
        return {**job["params"], **({"reference_image_urls": images} if images else {})}
    if job.get("endpoint") in {ANIMATION, TEXT_MOTION}:
        return dict(job["params"])
    if job.get("endpoint") in {RETEXTURE, RIGGING}:
        model = job["model"]
        data = (root / model["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != model["sha256"]:
            raise PipelineError("Source geometry changed since preflight; no texture POST sent")
        return {**job["params"], **({"multiview_image_urls": images} if images else {}),
                **({"name": name} if job.get("endpoint") == RETEXTURE else {}),
                "model_url": "data:application/octet-stream;base64," + base64.b64encode(data).decode("ascii")}
    if job.get("endpoint") == SINGLE_IMAGE:
        if len(images) != 1:
            raise PipelineError("Image-to-3D requires exactly one reference")
        return {**job["params"], "image_url": images[0], "name": name}
    return {**job["params"], "image_urls": images, "name": name}


def load_retexture_job(model_path, piece="general_red", variant=1, root=ROOT, texture_resolution="8k"):
    """Texture an explicit local source; preserve generation variants and one shared ledger."""
    if texture_resolution not in {"2k", "4k", "8k"}:
        raise PipelineError("Only 2k/4k/8k retexture is priced")
    path = Path(model_path)
    path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix.lower() != ".glb":
        raise PipelineError("Texture source must be a GLB inside this project")
    if path.stat().st_size > 256 * 1024 * 1024:
        raise PipelineError("Source GLB exceeds the 256 MiB local input limit")
    inspected = inspect_glb(path)
    inputs = load_jobs(piece, variant, root, geometry_master=True)
    if len(inputs) != 1:
        raise PipelineError("Retexture requires exactly one piece's reference views")
    params = {"ai_model": "meshy-7", "enable_original_uv": False, "enable_pbr": True,
              "texture_resolution": texture_resolution, "target_formats": ["glb"]}
    model = {"path": str(path.relative_to(root.resolve())), "sha256": inspected["sha256"], "bytes": inspected["bytes"]}
    images = inputs[0]["images"]
    digest = hashlib.sha256(json.dumps({"endpoint": RETEXTURE, "params": params, "images": images,
                                       "model": model}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"key": f"{piece}/texture/v{variant}", "piece": piece, "variant": variant,
            "endpoint": RETEXTURE, "fingerprint": digest, "params": params, "model": model,
            "images": images, "estimate": 15 if texture_resolution == "8k" else 10,
            "requires_geometry_preservation_check": True}


def inspect_glb(path):
    """Basic container/mesh checks, not an artistic, rigging or glTF conformance approval."""
    data = path.read_bytes()
    if len(data) < 20 or struct.unpack_from("<4sII", data) != (b"glTF", 2, len(data)):
        raise PipelineError("Downloaded model is not a complete GLB 2.0 file")
    offset, document = 12, None
    while offset < len(data):
        if offset + 8 > len(data):
            raise PipelineError("Truncated GLB chunk header")
        length, kind = struct.unpack_from("<I4s", data, offset)
        offset += 8
        if length % 4 or offset + length > len(data):
            raise PipelineError("Invalid GLB chunk length")
        if document is None:
            if kind != b"JSON":
                raise PipelineError("GLB must start with a JSON chunk")
            try:
                document = json.loads(data[offset:offset + length])
            except (ValueError, UnicodeDecodeError):
                raise PipelineError("Invalid GLB JSON") from None
        offset += length
    if not isinstance(document, dict) or document.get("asset", {}).get("version") != "2.0":
        raise PipelineError("Invalid glTF document")
    meshes = document.get("meshes", [])
    if not meshes or not any(mesh.get("primitives") for mesh in meshes):
        raise PipelineError("GLB has no mesh primitives")
    for item in document.get("images", []) + document.get("buffers", []):
        if item.get("uri") and not item["uri"].startswith("data:"):
            raise PipelineError("GLB depends on an external file; manual packaging required")
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "meshes": len(meshes), "primitives": sum(len(m.get("primitives", [])) for m in meshes),
            "materials": len(document.get("materials", [])), "textures": len(document.get("textures", [])),
            "skins": len(document.get("skins", [])), "animations": len(document.get("animations", [])),
            "production_accepted": False}


class Pipeline:
    def __init__(self, client, state_dir, output_dir, *, root=ROOT, sleep=time.sleep,
                 poll_seconds=10, wait_seconds=1800, emit=print):
        self.client, self.state_dir, self.output_dir = client, state_dir, output_dir
        self.root, self.sleep, self.emit = root, sleep, emit
        self.poll_seconds, self.wait_seconds = poll_seconds, wait_seconds
        self.path = state_dir / "ledger.json"
        self.ledger = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {
            "version": 1, "price_date": PRICE_DATE, "budget": BUDGET, "balance_floor": BALANCE_FLOOR,
            "environment": "mock" if client.test_origin else "live", "jobs": {}}
        if self.ledger.get("version") != 1 or self.ledger.get("environment") != ("mock" if client.test_origin else "live"):
            raise PipelineError("Ledger version/environment mismatch")

    def save(self):
        atomic_json(self.path, self.ledger)

    def committed(self):
        return sum(credit(job["held_credits"]) for job in self.ledger["jobs"].values())

    def unresolved(self):
        return [key for key, job in self.ledger["jobs"].items() if job["state"] in UNCERTAIN]

    def preflight(self, jobs):
        unresolved = self.unresolved()
        if unresolved:
            raise PipelineError("Uncertain paid submission; reconcile before any new POST: " + ", ".join(unresolved))
        for job in jobs:
            previous = self.ledger["jobs"].get(job["key"])
            if previous and previous["fingerprint"] != job["fingerprint"]:
                raise PipelineError(f"{job['key']}: references/settings changed; choose a new variant")
        # Refresh existing tasks first with resume if a failure refund is still pending.
        cost = sum(job["estimate"] for job in jobs if job["key"] not in self.ledger["jobs"])
        if self.committed() + cost > BUDGET:
            raise PipelineError(f"Batch exceeds {BUDGET} credit project cap")
        if cost and self.client.balance() - cost < BALANCE_FLOOR:
            raise PipelineError(f"Batch would leave less than {BALANCE_FLOOR} account credits")

    def submit(self, job):
        if self.unresolved():
            raise PipelineError("Resolve uncertain submissions before continuing")
        amount = credit(job["estimate"])
        if self.committed() + amount > BUDGET or self.client.balance() - amount < BALANCE_FLOOR:
            raise PipelineError("Credit cap/balance reserve reached; no POST sent")
        endpoint = checked_endpoint(job.get("endpoint", ENDPOINT))
        operation = "texture-" if endpoint == RETEXTURE else ""
        name = f"cn-cheer-{job['piece']}-{operation}v{job['variant']}-{uuid.uuid4().hex[:12]}"
        payload = make_payload(job, name, self.root)
        record = {**job, "name": name, "state": "RESERVED", "held_credits": amount,
                  "created_at": time.time(), "files": {}}
        self.ledger["jobs"][job["key"]] = record
        self.save()  # Must succeed BEFORE sending any paid request.
        try:
            result = self.client.request("POST", endpoint, payload)
            task_id = result.get("result") if isinstance(result, dict) else None
            if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", task_id):
                raise ApiError()
            record.update(task_id=task_id, state="SUBMITTED")
            self.save()
        except ApiError as error:
            # Only explicit request rejection is considered unbilled. 408/5xx/network
            # and malformed successful responses keep the reservation indefinitely.
            rejected = error.status in {400, 401, 402, 403, 404, 405, 413, 415, 422, 429}
            record.update(state="REJECTED" if rejected else "UNKNOWN",
                          held_credits=0 if rejected else amount, http_status=error.status,
                          error_detail=error.detail)
            self.save()
            raise PipelineError(f"{job['key']}: {error}; state={record['state']}; POST not retried") from None
        return record

    def refresh(self, record):
        task = self.client.task(record["task_id"], record.get("endpoint", ENDPOINT))
        if not isinstance(task, dict) or task.get("id") != record["task_id"]:
            raise PipelineError("Task response ID mismatch")
        status = task.get("status")
        if status not in TERMINAL | {"PENDING", "IN_PROGRESS"}:
            raise PipelineError("Unrecognized task status; keeping the credit reservation")
        observed = task.get("consumed_credits")
        if observed is not None:
            observed = credit(observed)
        record.update(state=status, progress=task.get("progress"), expires_at=task.get("expires_at"))
        # A zero on a running task does not prove a refund. A canceled task is also
        # charged conservatively unless the server explicitly returns consumed_credits=0.
        if observed is not None:
            record["reported_credits"] = observed
            record["held_credits"] = observed if status in {"FAILED", "CANCELED"} else max(record["estimate"], observed)
        record["price_mismatch"] = observed is not None and status == "SUCCEEDED" and observed != record["estimate"]
        if observed is not None and observed > record["estimate"]:
            record["price_mismatch"] = True
        self.save()
        atomic_json(self.output_dir / record["key"] / "task.json", task)
        return task

    def archive(self, record, task):
        directory = self.output_dir / record["key"]
        urls = {}
        image_task = record.get("endpoint") in IMAGE_ENDPOINTS
        motion_task = record.get("endpoint") == TEXT_MOTION
        if image_task:
            image_urls = task.get("image_urls")
            if not isinstance(image_urls, list) or len(image_urls) != 1 or not isinstance(image_urls[0], str):
                raise PipelineError("Expected exactly one generated image; no replacement task created")
            urls["image" + self.image_extension(image_urls[0])] = image_urls[0]
        glb = (task.get("model_urls") or {}).get("glb")
        result = task.get("result") or {}
        if motion_task:
            extension = result.get("motion_format")
            if extension not in {"fbx", "bvh"} or not result.get("motion_url"):
                raise PipelineError("Successful motion task has no supported motion output")
            urls["motion." + extension] = result["motion_url"]
        if record.get("endpoint") == RIGGING:
            glb = result.get("rigged_character_glb_url")
            if result.get("rigged_character_fbx_url"):
                urls["rigged.fbx"] = result["rigged_character_fbx_url"]
            basic = result.get("basic_animations") or {}
            for action in ("walking", "running"):
                for extension in ("glb", "fbx"):
                    if basic.get(f"{action}_{extension}_url"):
                        urls[f"{action}.{extension}"] = basic[f"{action}_{extension}_url"]
        if record.get("endpoint") == ANIMATION:
            glb = result.get("animation_glb_url")
            if result.get("animation_fbx_url"):
                urls["animation.fbx"] = result["animation_fbx_url"]
        if not glb and not image_task and not motion_task:
            raise PipelineError("Successful task has no GLB URL; no replacement task will be created")
        if glb and not image_task:
            urls["model.glb"] = glb
        source_glb = (task.get("model_urls") or {}).get("pre_remeshed_glb")
        if source_glb:
            urls["source_pre_remeshed.glb"] = source_glb
        for index, textures in enumerate(task.get("texture_urls") or []):
            for kind in ("base_color", "metallic", "roughness", "normal", "emission", "metallic_roughness"):
                if textures.get(kind):
                    urls[f"texture_{index}_{kind}" + self.image_extension(textures[kind])] = textures[kind]
        if task.get("thumbnail_url"):
            urls["preview" + self.image_extension(task["thumbnail_url"])] = task["thumbnail_url"]
        for side in ("front", "right", "back", "left"):
            url = (task.get("thumbnail_urls") or {}).get(side)
            if url:
                urls[f"preview_{side}" + self.image_extension(url)] = url
        for name, url in urls.items():
            destination = directory / name
            previous = record["files"].get(name)
            if previous and destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == previous["sha256"]:
                continue
            self.client.download(url, destination)
            data = destination.read_bytes()
            if name.endswith(".glb"):
                inspect_glb(destination)
            elif name.endswith(".fbx"):
                if not (data.startswith(b"Kaydara FBX Binary") or b"FBXHeaderExtension" in data[:1024]):
                    raise PipelineError("Downloaded FBX has an invalid header")
            elif name.endswith(".bvh"):
                if not data.lstrip().startswith(b"HIERARCHY") or b"MOTION" not in data:
                    raise PipelineError("Downloaded BVH has an invalid motion header")
            elif not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff") or
                      (data.startswith(b"RIFF") and data[8:12] == b"WEBP")):
                raise PipelineError("Downloaded texture/preview is not a supported image")
            record["files"][name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            self.save()
        report = ({"kind": "motion" if motion_task else "image", "files": record["files"], "production_accepted": False}
                  if image_task or motion_task else inspect_glb(directory / "model.glb"))
        report.update(piece=record["piece"], task_id=record["task_id"], environment=self.ledger["environment"],
                      requires_visual_review=True, source_fingerprint=record["fingerprint"])
        atomic_json(directory / "inspection.json", report)
        record["archived"] = True
        self.save()

    @staticmethod
    def image_extension(url):
        suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
        return suffix if suffix in {".png", ".jpg", ".jpeg", ".webp"} else ".bin"

    def wait_and_archive(self, record):
        deadline = time.monotonic() + self.wait_seconds
        previous_status = None
        while True:
            task = self.refresh(record)
            current = (record["state"], record["progress"])
            if current != previous_status:
                self.emit(f"{record['key']}: {current[0]} {current[1]}%")
                previous_status = current
            if record["state"] == "SUCCEEDED":
                self.archive(record, task)
                if record["price_mismatch"] or self.committed() > BUDGET:
                    raise PipelineError("Actual credits differ from the reviewed estimate; archived model, stopped new spending")
                return
            if record["price_mismatch"]:
                raise PipelineError("Unexpected reported credits; stopped, use resume to save the existing task")
            if record["state"] in {"FAILED", "CANCELED"}:
                raise PipelineError(f"Task {record['state']}; reserved {record['held_credits']} credits; no automatic regeneration")
            if time.monotonic() >= deadline:
                raise PipelineError("Polling deadline reached; run resume (no new paid request)")
            self.sleep(min(self.poll_seconds, max(0, deadline - time.monotonic())))

    def run(self, jobs):
        self.preflight(jobs)
        # Preserve serial processing across separate CLI invocations too.
        selected = {job["key"] for job in jobs}
        for key, record in self.ledger["jobs"].items():
            if key not in selected and record["state"] in {"SUBMITTED", "PENDING", "IN_PROGRESS"}:
                raise PipelineError("An earlier task is active; run resume before starting a different batch")
        if any(record.get("price_mismatch") for record in self.ledger["jobs"].values()):
            raise PipelineError("Price mismatch in ledger; review the price profile before new spending")
        for job in jobs:
            record = self.ledger["jobs"].get(job["key"])
            if record and record["state"] in {"FAILED", "CANCELED", "REJECTED"}:
                raise PipelineError(f"{job['key']} previously {record['state']}; inspect it, then select an unused variant")
            if record and self.locally_complete(record):
                self.emit(f"{job['key']}: already archived (no POST)")
                continue
            self.wait_and_archive(record or self.submit(job))
        self.emit(f"Account balance: {self.client.balance()}; project spent/reserved: {self.committed()}/{BUDGET}")

    def locally_complete(self, record):
        # Verify hashes without API calls, including after the retention window expires.
        files = record.get("files", {})
        has_output = any(name.startswith("image.") for name in files) if record.get("endpoint") in IMAGE_ENDPOINTS else files.get("model.glb")
        if record.get("endpoint") == TEXT_MOTION:
            has_output = files.get("motion.fbx") or files.get("motion.bvh")
        return bool(record.get("archived") and has_output) and all(
            (self.output_dir / record["key"] / name).is_file() and
            hashlib.sha256((self.output_dir / record["key"] / name).read_bytes()).hexdigest() == metadata["sha256"]
            for name, metadata in record["files"].items())

    def run_batch(self, jobs, max_active=3):
        """Bound remote work; one process owns reservations, POSTs and ledger writes.

        Restart with the same batch to resume known IDs. An uncertain POST or
        unexpected charge immediately stops new spending, as in serial mode.
        """
        if isinstance(max_active, bool) or max_active not in (1, 2, 3):
            raise PipelineError("Batch concurrency must be 1..3")
        self.preflight(jobs)
        selected = {job["key"] for job in jobs}
        if len(selected) != len(jobs):
            raise PipelineError("Duplicate job key in batch")
        for key, record in self.ledger["jobs"].items():
            if record.get("price_mismatch"):
                raise PipelineError("Price mismatch in ledger; stopped new spending")
            if key not in selected and record["state"] in {"SUBMITTED", "PENDING", "IN_PROGRESS"}:
                raise PipelineError("An earlier task is active; resume its batch first")
            if key in selected and record["state"] in {"FAILED", "CANCELED", "REJECTED"}:
                raise PipelineError(f"{key} previously {record['state']}; inspect before a new variant")
        waiting, active, previous = [], [], {}
        for job in jobs:
            record = self.ledger["jobs"].get(job["key"])
            if record and self.locally_complete(record):
                self.emit(f"{job['key']}: already archived (no POST)")
            elif record:
                active.append(record)
            else:
                waiting.append(job)
        deadlines = {record["key"]: time.monotonic() + self.wait_seconds for record in active}
        atomic_json(self.state_dir / "batch.json", {"keys": [job["key"] for job in jobs],
            "max_active": max_active, "estimated_if_new": sum(job["estimate"] for job in waiting)})
        while waiting or active:
            while waiting and len(active) < max_active:
                record = self.submit(waiting.pop(0))
                active.append(record)
                deadlines[record["key"]] = time.monotonic() + self.wait_seconds
                self.emit(f"{record['key']}: submitted {record['task_id']}")
            for record in active[:]:
                task = self.refresh(record)
                current = (record["state"], record["progress"])
                if previous.get(record["key"]) != current:
                    self.emit(f"{record['key']}: {current[0]} {current[1]}%")
                    previous[record["key"]] = current
                if record["state"] == "SUCCEEDED":
                    self.archive(record, task)
                    active.remove(record)
                if record.get("price_mismatch") or self.committed() > BUDGET:
                    raise PipelineError("Unexpected reported credits; stopped new spending")
                if record["state"] in {"FAILED", "CANCELED"}:
                    raise PipelineError(f"{record['key']}: {record['state']}; no automatic regeneration")
                if record in active and time.monotonic() >= deadlines[record["key"]]:
                    raise PipelineError("Batch polling deadline reached; resume existing IDs")
            if active:
                self.sleep(self.poll_seconds)
        self.emit(f"Account balance: {self.client.balance()}; project spent/reserved: {self.committed()}/{BUDGET}")

    def resume(self):
        problems = []
        for key, record in self.ledger["jobs"].items():
            if self.locally_complete(record):
                continue
            if not record.get("task_id"):
                if record["state"] in UNCERTAIN:
                    problems.append(key + ": reconcile required")
                continue
            try:
                self.wait_and_archive(record)
            except PipelineError as error:
                problems.append(f"{key}: {error}")
        if problems:
            raise PipelineError("; ".join(problems))

    def reconcile(self, key, task_id):
        record = self.ledger["jobs"].get(key)
        if not record or record["state"] not in UNCERTAIN:
            raise PipelineError("Only an uncertain ledger entry can be reconciled")
        task = self.client.task(task_id, record.get("endpoint", ENDPOINT))
        matches_input = task.get("name") == record["name"]
        if record.get("endpoint") in IMAGE_ENDPOINTS:
            matches_input = (task.get("prompt") == record["params"]["prompt"] and
                             task.get("ai_model") == record["params"]["ai_model"] and
                             0 <= task.get("created_at", 0) / 1000 - record["created_at"] <= 600)
        if task.get("id") != task_id or not matches_input:
            raise PipelineError("Remote task ID/name must match the reserved name exactly")
        if any(other.get("task_id") == task_id for other in self.ledger["jobs"].values()):
            raise PipelineError("Task ID already belongs to a ledger entry")
        record.update(task_id=task_id, state="SUBMITTED")
        self.save()
