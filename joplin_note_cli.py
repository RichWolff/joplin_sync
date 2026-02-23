#!/usr/bin/env python3
import argparse
import json
import os
import re
import secrets
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple
from urllib import error, parse, request
import ssl


META_ORDER = [
    "id",
    "parent_id",
    "created_time",
    "updated_time",
    "is_conflict",
    "latitude",
    "longitude",
    "altitude",
    "author",
    "source_url",
    "is_todo",
    "todo_due",
    "todo_completed",
    "source",
    "source_application",
    "application_data",
    "order",
    "user_created_time",
    "user_updated_time",
    "encryption_cipher_text",
    "encryption_applied",
    "markup_language",
    "is_shared",
    "share_id",
    "conflict_original_id",
    "master_key_id",
    "user_data",
    "deleted_time",
    "type_",
]


class ApiError(RuntimeError):
    pass


SSL_CONTEXT = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def http_json(method: str, url: str, data=None, headers=None):
    payload = None
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = request.Request(url, data=payload, headers=req_headers, method=method)
    try:
        with request.urlopen(req, context=SSL_CONTEXT) as resp:
            body = resp.read()
            if not body:
                return None
            return json.loads(body.decode("utf-8"))
    except error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise ApiError(f"HTTP {e.code} {url}: {msg}") from e
    except error.URLError as e:
        raise ApiError(f"Request failed for {url}: {e}") from e


def http_text(method: str, url: str, headers=None) -> str:
    req = request.Request(url, headers=headers or {}, method=method)
    try:
        with request.urlopen(req, context=SSL_CONTEXT) as resp:
            return resp.read().decode("utf-8")
    except error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise ApiError(f"HTTP {e.code} {url}: {msg}") from e
    except error.URLError as e:
        raise ApiError(f"Request failed for {url}: {e}") from e


def http_put_multipart(url: str, api_auth: str, file_name: str, file_bytes: bytes):
    boundary = f"----joplincli{uuid.uuid4().hex}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{file_name}\"\r\n".encode("utf-8")
    )
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    headers = {
        "X-API-AUTH": api_auth,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }

    req = request.Request(url, data=bytes(body), headers=headers, method="PUT")
    try:
        with request.urlopen(req, context=SSL_CONTEXT) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise ApiError(f"HTTP {e.code} {url}: {msg}") from e
    except error.URLError as e:
        raise ApiError(f"Request failed for {url}: {e}") from e


def create_session(base_url: str, email: str, password: str) -> str:
    res = http_json("POST", f"{base_url}/api/sessions", {"email": email, "password": password})
    if not res or "id" not in res:
        raise ApiError("Missing session id from /api/sessions response")
    return res["id"]


def parse_serialized_note(serialized: str) -> Tuple[str, str, Dict[str, str]]:
    lines = serialized.splitlines()
    if not lines:
        raise ValueError("Empty note content")

    type_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("type_:"):
            type_idx = i
            break
    if type_idx < 0:
        raise ValueError("Cannot find metadata block (type_) in note content")

    kv_re = re.compile(r"^[a-z0-9_]+:\s?.*$")
    meta_start = type_idx
    while meta_start > 0 and kv_re.match(lines[meta_start - 1]):
        meta_start -= 1

    metadata = {}
    for line in lines[meta_start : type_idx + 1]:
        key, _, val = line.partition(":")
        metadata[key.strip()] = val.lstrip(" ")

    title = lines[0]

    # Expected note format: title, blank, body..., blank, metadata...
    body_start = 2 if len(lines) >= 2 and lines[1] == "" else 1
    body_end = meta_start
    if body_end > body_start and lines[body_end - 1] == "":
        body_end -= 1
    body = "\n".join(lines[body_start:body_end])

    return title, body, metadata


def serialize_note(title: str, body: str, metadata: Dict[str, str]) -> str:
    meta = metadata.copy()
    meta["type_"] = "1"

    lines = [title, "", body, ""]
    for key in META_ORDER:
        if key in meta:
            lines.append(f"{key}: {meta[key]}")

    # Keep any extra metadata keys too.
    extra = sorted(k for k in meta.keys() if k not in META_ORDER)
    for key in extra:
        lines.append(f"{key}: {meta[key]}")

    return "\n".join(lines)


def parse_markdown_file(path: Path) -> Tuple[Dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            front = text[4:end]
            body = text[end + 5 :]
            meta = {}
            for line in front.splitlines():
                if not line.strip() or line.strip().startswith("#"):
                    continue
                key, _, val = line.partition(":")
                if not _:
                    continue
                meta[key.strip()] = val.strip()
            return meta, body
    return {}, text


def write_markdown_file(path: Path, title: str, body: str, note_id: str, parent_id: str):
    front = [
        "---",
        f"note_id: {note_id}",
        f"parent_id: {parent_id}",
        f"title: {title}",
        "---",
        "",
    ]
    path.write_text("\n".join(front) + body + ("\n" if not body.endswith("\n") else ""), encoding="utf-8")


def item_path_for_note(note_id: str) -> str:
    return f"root:/{note_id}.md:"


def cmd_pull(args):
    session_id = create_session(args.base_url, args.email, args.password)
    item_path = item_path_for_note(args.note_id)
    url = f"{args.base_url}/api/items/{parse.quote(item_path, safe=':/')}/content"
    content = http_text("GET", url, headers={"X-API-AUTH": session_id})

    title, body, meta = parse_serialized_note(content)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_markdown_file(out, title, body, meta.get("id", args.note_id), meta.get("parent_id", ""))
    print(f"Pulled note {meta.get('id', args.note_id)} to {out}")


def cmd_push(args):
    session_id = create_session(args.base_url, args.email, args.password)
    src = Path(args.file)
    front, body = parse_markdown_file(src)

    note_id = front.get("note_id") or args.note_id
    if not note_id:
        raise SystemExit("Missing note id. Add 'note_id' in front matter or pass --note-id.")

    item_path = item_path_for_note(note_id)
    get_url = f"{args.base_url}/api/items/{parse.quote(item_path, safe=':/')}/content"
    remote = http_text("GET", get_url, headers={"X-API-AUTH": session_id})
    remote_title, _remote_body, remote_meta = parse_serialized_note(remote)

    new_title = front.get("title") or args.title or remote_title
    parent_id = front.get("parent_id") or remote_meta.get("parent_id", "")

    now = utc_now_iso()
    remote_meta["id"] = note_id
    remote_meta["parent_id"] = parent_id
    remote_meta["updated_time"] = now
    remote_meta["user_updated_time"] = now

    payload = serialize_note(new_title, body.rstrip("\n"), remote_meta)
    put_url = f"{args.base_url}/api/items/{parse.quote(item_path, safe=':/')}/content"
    http_put_multipart(put_url, session_id, f"{note_id}.md", payload.encode("utf-8"))
    print(f"Pushed note {note_id}")


def cmd_create(args):
    session_id = create_session(args.base_url, args.email, args.password)

    note_id = args.note_id or secrets.token_hex(16)
    title = args.title
    body = ""

    if args.body_file:
        _front, parsed_body = parse_markdown_file(Path(args.body_file))
        body = parsed_body.rstrip("\n")
    elif args.body:
        body = args.body

    now = utc_now_iso()
    meta = {
        "id": note_id,
        "parent_id": args.notebook_id,
        "created_time": now,
        "updated_time": now,
        "is_conflict": "0",
        "latitude": "0.00000000",
        "longitude": "0.00000000",
        "altitude": "0.0000",
        "author": "",
        "source_url": "",
        "is_todo": "0",
        "todo_due": "0",
        "todo_completed": "0",
        "source": "joplin-server-api",
        "source_application": "net.cozic.joplin-desktop",
        "application_data": "",
        "order": "0",
        "user_created_time": now,
        "user_updated_time": now,
        "encryption_cipher_text": "",
        "encryption_applied": "0",
        "markup_language": "1",
        "is_shared": "0",
        "share_id": "",
        "conflict_original_id": "",
        "master_key_id": "",
        "user_data": "",
        "deleted_time": "0",
        "type_": "1",
    }

    payload = serialize_note(title, body, meta)
    item_path = item_path_for_note(note_id)
    put_url = f"{args.base_url}/api/items/{parse.quote(item_path, safe=':/')}/content"
    http_put_multipart(put_url, session_id, f"{note_id}.md", payload.encode("utf-8"))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_markdown_file(out, title, body, note_id, args.notebook_id)
        print(f"Created note {note_id} and wrote {out}")
    else:
        print(f"Created note {note_id}")


def build_parser():
    p = argparse.ArgumentParser(description="Pull/push/create Joplin notes by note/notebook ID")
    p.add_argument("--base-url", default=os.getenv("JOPLIN_BASE_URL", "https://notes.home.arpa"))
    p.add_argument("--email", default=os.getenv("JOPLIN_EMAIL"))
    p.add_argument("--password", default=os.getenv("JOPLIN_PASSWORD"))
    p.add_argument("--ca-cert", default=os.getenv("JOPLIN_CA_CERT"), help="Path to root CA cert PEM/CRT")

    sub = p.add_subparsers(dest="cmd", required=True)

    pull = sub.add_parser("pull", help="Pull a note by note ID into a markdown file")
    pull.add_argument("--note-id", required=True)
    pull.add_argument("--out", required=True)
    pull.set_defaults(func=cmd_pull)

    push = sub.add_parser("push", help="Push edited markdown back to an existing note")
    push.add_argument("--file", required=True)
    push.add_argument("--note-id", help="Optional override if front matter has no note_id")
    push.add_argument("--title", help="Optional override for note title")
    push.set_defaults(func=cmd_push)

    create = sub.add_parser("create", help="Create a new note in a notebook ID")
    create.add_argument("--notebook-id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--body", default="")
    create.add_argument("--body-file", help="Read body from markdown file (front matter ignored)")
    create.add_argument("--note-id", help="Optional custom note ID (32 hex); default auto-generated")
    create.add_argument("--out", help="Optionally write created note to local markdown file")
    create.set_defaults(func=cmd_create)

    return p


def main():
    global SSL_CONTEXT
    parser = build_parser()
    args = parser.parse_args()

    if not args.email or not args.password:
        parser.error("Provide --email and --password or set JOPLIN_EMAIL/JOPLIN_PASSWORD")

    if args.ca_cert:
        SSL_CONTEXT = ssl.create_default_context(cafile=args.ca_cert)

    try:
        args.func(args)
    except ApiError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
