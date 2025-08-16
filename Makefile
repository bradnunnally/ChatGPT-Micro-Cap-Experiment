coverage:
	. .venv/bin/activate && pytest --cov=services --cov=data --cov=core --cov-report=term-missing --cov-fail-under=80
.PHONY: install lint test run audit

install:
	python3 -m venv .venv || true
	. .venv/bin/activate && python -m pip install -U pip
	. .venv/bin/activate && pip install -r requirements.txt
	. .venv/bin/activate && pip install black ruff mypy pre-commit pydantic pydantic-settings
	@echo "Dev environment ready. Activate with: source .venv/bin/activate"

lint:
	. .venv/bin/activate && ruff check .
	. .venv/bin/activate && black --check .
	. .venv/bin/activate && mypy . || true

test:
	. .venv/bin/activate && pytest -q

run:
	. .venv/bin/activate && python -m streamlit run app.py

# Development run on alternate port to avoid snapshot (8501) conflict
run-dev:
	. .venv/bin/activate && STREAMLIT_SERVER_PORT=8601 python -m streamlit run app.py

migrate:
	. .venv/bin/activate && python apply_migrations.py

csv-migrate:
	. .venv/bin/activate && python scripts/migrate_csv_to_sqlite.py

backup:
	. .venv/bin/activate && python scripts/backup_db.py

restore:
	. .venv/bin/activate && python scripts/restore_db.py $(BACKUP)

audit:
	python3 -m venv .venv || true
	. .venv/bin/activate && python -m pip install -U pip
	. .venv/bin/activate && pip install -q ruff vulture pycln deptry detect-secrets
	. .venv/bin/activate && python scripts/audit_unused_modules.py
	. .venv/bin/activate && ruff . --select F401,F841,ERA || true
	. .venv/bin/activate && vulture . --min-confidence 80 || true
	. .venv/bin/activate && deptry . || true
	@echo "Run 'make secrets-scan' for dedicated secret leakage scan"

secrets-scan:
	@echo "Scanning for secrets..."
	. .venv/bin/activate && detect-secrets scan --baseline .secrets.baseline . || true
	@echo "If new findings appear, update baseline after review: detect-secrets scan > .secrets.baseline"

lock:
	@echo "Generating requirements.lock (deterministic hashes)"
	python3 -m venv .venv || true
	. .venv/bin/activate && python -m pip install -U pip pip-tools
	. .venv/bin/activate && pip-compile --quiet --generate-hashes --output-file requirements.lock requirements.txt
	@echo "Lock file written to requirements.lock"

.PHONY: cli cli-snapshot cli-export cli-import cli-rebalance freeze
cli:
	. .venv/bin/activate && python -m cli.main --help

cli-snapshot:
	. .venv/bin/activate && python -m cli.main snapshot $(ARGS)

cli-export:
	. .venv/bin/activate && python -m cli.main export --out $(OUT)

cli-import:
	. .venv/bin/activate && python -m cli.main import- --csv $(CSV)

cli-rebalance:
	. .venv/bin/activate && python -m cli.main rebalance $(ARGS)

cli-benchmark:
	. .venv/bin/activate && python -m cli.main benchmark-refresh $(ARGS)

cli-risk-free:
	. .venv/bin/activate && python -m cli.main risk-free $(ARGS)

# Create a self-contained frozen snapshot under dist/release-<VERSION>
freeze:
	@if [ -z "$(VERSION)" ]; then echo "Set VERSION, e.g.: make freeze VERSION=1.0.0"; exit 1; fi
	@echo "Creating frozen release $(VERSION)"
	rm -rf dist/release-$(VERSION)
	mkdir -p dist/release-$(VERSION)
	# Copy source (exclude dev/ephemeral directories)
	rsync -a \
		--exclude '.git' \
		--exclude '.venv' \
		--exclude 'dist' \
		--exclude '__pycache__' \
		--exclude '*.pyc' \
		--exclude 'tests' \
		./ dist/release-$(VERSION)/
	# Create virtual environment inside the snapshot
	cd dist/release-$(VERSION) && python3 -m venv .venv
	cd dist/release-$(VERSION) && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt
	# Record version metadata
	echo $(VERSION) > dist/release-$(VERSION)/VERSION
	# Create launch script
	printf '%s\n' '#!/bin/bash' \
	'DIR="$(cd "$(dirname "$0")" && pwd)"' \
	'if [ ! -f "$DIR/.venv/bin/activate" ]; then echo "Virtual env missing"; exit 1; fi' \
	'. "$DIR/.venv/bin/activate"' \
	'export APP_ENV="${APP_ENV:-production}"' \
	'echo "Starting Portfolio App (version $(cat "$DIR/VERSION" 2>/dev/null || echo unknown))"' \
	'exec streamlit run "$DIR/app.py"' > dist/release-$(VERSION)/launch.sh
	chmod +x dist/release-$(VERSION)/launch.sh
	@echo "Frozen release ready: dist/release-$(VERSION)"
	@echo "Run: ./dist/release-$(VERSION)/launch.sh"

release-smoke: migrate
	@echo "Running release smoke (tests + audit chain verify stub)"
	. .venv/bin/activate && pytest -q
	python - <<'PY'
from services.governance import verify_audit_chain
ok = verify_audit_chain()
print("Audit chain integrity:", "OK" if ok else "BROKEN")
PY
	@echo "Smoke complete."
