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
	. .venv/bin/activate && pip install -q ruff vulture pycln deptry
	. .venv/bin/activate && python scripts/audit_unused_modules.py
	. .venv/bin/activate && ruff . --select F401,F841,ERA || true
	. .venv/bin/activate && vulture . --min-confidence 80 || true
	. .venv/bin/activate && deptry . || true
