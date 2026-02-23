PYTHON ?= python3
CLI := ./joplin_note_cli.py

JOPLIN_BASE_URL ?= https://notes.home.arpa

ifneq (,$(wildcard .env))
include .env
export
endif

# Allow: make push FILE=... <NOTE_ID>
ifneq (,$(filter push,$(MAKECMDGOALS)))
PUSH_EXTRA_GOALS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
ifneq ($(strip $(PUSH_EXTRA_GOALS)),)
NOTE_ID ?= $(firstword $(PUSH_EXTRA_GOALS))
$(eval $(PUSH_EXTRA_GOALS):;@:)
endif
endif

.PHONY: help check-env pull push create create-from-file

help:
	@echo "Targets:"
	@echo "  make pull NOTE_ID=<32hex> OUT=./notes/note.md"
	@echo "  make push FILE=./notes/note.md [NOTE_ID=<32hex>] [TITLE='New Title']"
	@echo "  make create NOTEBOOK_ID=<32hex> TITLE='New Note' [BODY='Text'] [OUT=./notes/new.md]"
	@echo "  make create-from-file NOTEBOOK_ID=<32hex> TITLE='New Note' BODY_FILE=./draft.md [OUT=./notes/new.md]"
	@echo ""
	@echo "Required env vars:"
	@echo "  JOPLIN_EMAIL, JOPLIN_PASSWORD"
	@echo "Optional env vars:"
	@echo "  JOPLIN_BASE_URL (default: $(JOPLIN_BASE_URL))"
	@echo "  JOPLIN_CA_CERT (path to root_ca.crt)"

check-env:
	@test -n "$$JOPLIN_EMAIL" || (echo "ERROR: JOPLIN_EMAIL is required" && exit 1)
	@test -n "$$JOPLIN_PASSWORD" || (echo "ERROR: JOPLIN_PASSWORD is required" && exit 1)

pull: check-env
	@test -n "$(NOTE_ID)" || (echo "ERROR: NOTE_ID is required" && exit 1)
	@test -n "$(OUT)" || (echo "ERROR: OUT is required" && exit 1)
	$(PYTHON) $(CLI) --base-url "$(JOPLIN_BASE_URL)" --email "$$JOPLIN_EMAIL" --password "$$JOPLIN_PASSWORD" \
		pull --note-id "$(NOTE_ID)" --out "$(OUT)"

push: check-env
	@test -n "$(FILE)" || (echo "ERROR: FILE is required" && exit 1)
	$(PYTHON) $(CLI) --base-url "$(JOPLIN_BASE_URL)" --email "$$JOPLIN_EMAIL" --password "$$JOPLIN_PASSWORD" \
		push --file "$(FILE)" $(if $(NOTE_ID),--note-id "$(NOTE_ID)",) $(if $(TITLE),--title "$(TITLE)",)

create: check-env
	@test -n "$(NOTEBOOK_ID)" || (echo "ERROR: NOTEBOOK_ID is required" && exit 1)
	@test -n "$(TITLE)" || (echo "ERROR: TITLE is required" && exit 1)
	$(PYTHON) $(CLI) --base-url "$(JOPLIN_BASE_URL)" --email "$$JOPLIN_EMAIL" --password "$$JOPLIN_PASSWORD" \
		create --notebook-id "$(NOTEBOOK_ID)" --title "$(TITLE)" $(if $(BODY),--body "$(BODY)",) $(if $(OUT),--out "$(OUT)",)

create-from-file: check-env
	@test -n "$(NOTEBOOK_ID)" || (echo "ERROR: NOTEBOOK_ID is required" && exit 1)
	@test -n "$(TITLE)" || (echo "ERROR: TITLE is required" && exit 1)
	@test -n "$(BODY_FILE)" || (echo "ERROR: BODY_FILE is required" && exit 1)
	$(PYTHON) $(CLI) --base-url "$(JOPLIN_BASE_URL)" --email "$$JOPLIN_EMAIL" --password "$$JOPLIN_PASSWORD" \
		create --notebook-id "$(NOTEBOOK_ID)" --title "$(TITLE)" --body-file "$(BODY_FILE)" $(if $(OUT),--out "$(OUT)",)
