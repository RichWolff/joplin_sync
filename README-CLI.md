# Joplin Note CLI (pull/edit/push/create)

This tool talks to your running Joplin Server API and lets you:
- pull a note by note ID to local markdown
- edit markdown locally and push it back
- create a new note in a notebook by notebook ID

## File
- `joplin_note_cli.py`

## Install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Auth
Set env vars or pass flags:
- `JOPLIN_BASE_URL` (default: `https://notes.home.arpa`)
- `JOPLIN_EMAIL`
- `JOPLIN_PASSWORD`
- `JOPLIN_CA_CERT` (path to your trusted root CA, e.g. `root_ca.crt`)

Example:
```bash
export JOPLIN_BASE_URL="https://notes.home.arpa"
export JOPLIN_EMAIL="your-user@example.com"
export JOPLIN_PASSWORD="your-password"
export JOPLIN_CA_CERT="$HOME/homelab-certs/root_ca.crt"
```

You can also put these in `.env` in this folder.
- `joplin_note_cli.py` auto-loads `.env` via `python-dotenv`.
- `make` also auto-loads `.env`.

## Pull a note
```bash
python3 joplin_note_cli.py pull --note-id <NOTE_ID_32HEX> --out ./notes/my-note.md
```

## Edit then push
1. Edit `./notes/my-note.md`
2. Push it back:
```bash
python3 joplin_note_cli.py push --file ./notes/my-note.md
```

Make shortcut (supports trailing note ID):
```bash
make push FILE=./notes/my-note.md ee39ed70ff624e2aade2142a2cf60d4e
```

The pulled markdown uses front matter:
```yaml
---
note_id: <NOTE_ID>
parent_id: <NOTEBOOK_ID>
title: <TITLE>
---
```

## Create new note in notebook
```bash
python3 joplin_note_cli.py create \
  --notebook-id <NOTEBOOK_ID_32HEX> \
  --title "New AI Note" \
  --body "Hello from automation" \
  --out ./notes/new-ai-note.md
```

Or body from file:
```bash
python3 joplin_note_cli.py create \
  --notebook-id <NOTEBOOK_ID_32HEX> \
  --title "New AI Note" \
  --body-file ./draft.md
```

## Docker usage (optional)
Run the script in a disposable Python container:
```bash
docker run --rm -it \
  -v "$PWD:/work" -w /work \
  -e JOPLIN_BASE_URL -e JOPLIN_EMAIL -e JOPLIN_PASSWORD \
  python:3.12-alpine \
  sh -lc "python3 joplin_note_cli.py --help"
```

Then replace `--help` with `pull`, `push`, or `create` commands.
