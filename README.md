# TUC — Telegram University Content Collector

TUC collects course files (PDF, images, Word, PowerPoint) from the Telegram channels you choose,
drops duplicates, extracts the text (with Arabic + English OCR), classifies each file by **subject**
and **content type**, files it into a tidy folder tree, and gives you a bilingual (Arabic/English)
dashboard to manage and watch all of it.

> Arabic documentation: [README_AR.md](README_AR.md) · [CONFIGURATION_AR.md](CONFIGURATION_AR.md) ·
> [TROUBLESHOOTING_AR.md](TROUBLESHOOTING_AR.md) · [DEPLOYMENT_AR.md](DEPLOYMENT_AR.md)

Runs natively on **macOS (Apple Silicon and Intel)**. No Docker, Redis, or Celery: it uses MySQL 8
and Tesseract from Homebrew, Python in a `uv` venv, and **launchd** for scheduling.

## What it does

```
Telegram channels ──► collect ──► storage/incoming ──► process ──► storage/processed/<SUBJECT>/<type>/
   (enabled in DB)     │  dedup by document.id          │  extract text (PDF text → OCR fallback)
                       │  then SHA-256                   │  rules classifier → OpenAI (optional)
                       └─ FloodWait + rate limit          └─ storage/unclassified/ when unsure
```

* **Collector** — reads only enabled channels, oldest → newest from each channel's `last_message_id`,
  and advances that cursor after every message it handles, so a crash never loses or repeats work.
  Duplicates are detected *before* downloading (Telegram `document.id`) and again after (SHA-256).
  Downloads are atomic (`.part` → rename) and confined to the storage root. Arabic file names are
  NFC-normalised (macOS stores NFD). `.doc`/`.ppt` are recorded as `unsupported` (convert them to
  `.docx`/`.pptx`/PDF).
* **Processing** — embedded PDF text first; OCR (`ara+eng`) when a PDF has fewer than
  `TUC_MIN_PDF_TEXT_CHARS` characters (max `TUC_OCR_MAX_PAGES` pages). Images → OCR.
  `.docx`/`.pptx` → python-docx / python-pptx. Text is cleaned and saved to
  `storage/texts/<id>.txt` (mode 600).
* **Classification (strict)**
  1. **Rules (`rules-v1`)**: subject code, names and keywords, plus content-type words
     (محاضرة/lecture, امتحان/exam/final/midterm, تكليف/assignment/sheet, نموذج إجابة/answer/solution,
     ملخص/summary) in the file name, caption, channel name and text.
  2. **OpenAI** (only if `TUC_AI_PROVIDER=openai`, and only for files the rules could not settle):
     Responses API with a strict JSON schema.
  3. **Validation**: the subject must exist, the type must be one of the five fixed types, and the
     confidence and evidence must clear the thresholds. Anything else ends up `unclassified` with a
     reason. Nothing is ever invented.
* **Locking** — one `fcntl.flock` lock (`storage/collector.lock`) shared by the CLI, the dashboard
  and launchd. A second job exits with code **75** and the dashboard shows who holds the lock.

**Classification needs subjects.** Define them in the dashboard (or import `config/subjects.yaml`).
The **rule classifier works without any API key**; the smart (AI) classifier needs an OpenAI key.

## Quick start (macOS)

```bash
./scripts/install_macos.sh                 # brew: mysql tesseract tesseract-lang node uv
mysql -u root < scripts/setup_mysql.sql    # databases tuc + tuc_test (utf8mb4) and user
uv sync
cp .env.example .env && chmod 600 .env     # then edit the values
uv run python -m app.cli health-check
uv run python -m app.cli init-db           # migrations + storage folders + YAML seed import
uv run python -m app.cli seed-demo         # optional: demo data to explore the dashboard
cd frontend && npm install && npm run build && cd ..
uv run python -m app.cli serve --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> and sign in with `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`.

Background operation (web + collect + process as LaunchAgents):

```bash
uv run python -m app.cli launchd install     # uninstall | status
```

### Before real use

1. Telegram API credentials from <https://my.telegram.org> → `TUC_TELEGRAM_API_ID`, `TUC_TELEGRAM_API_HASH`.
2. `uv run python -m app.cli telegram-login` (phone → code → optional 2FA). The session file is created with mode 600.
3. The Telegram account must be a **member** of every channel you add.
4. MySQL running (`brew services list`).
5. Tesseract with `ara` and `eng` (`tesseract --list-langs`).
6. Optional: `TUC_AI_PROVIDER=openai` + `TUC_OPENAI_API_KEY` for AI classification.

## CLI

| Command | Purpose |
|---|---|
| `health-check [--json]` | MySQL + utf8mb4, Tesseract + languages, Telegram session, OpenAI, storage, permissions, lock, launchd |
| `init-db` | Alembic migrations, storage folders, first YAML import |
| `telegram-login` | Interactive Telegram login |
| `collect [--channel X] [--limit N]` | Collect new files |
| `process [--limit N] [--file-id ID] [--retry-failed]` | Extract, classify, file away |
| `reclassify [--status unclassified]` | Re-run classification on stored text |
| `report [--json]` | Totals, by subject and type, subjects with no content |
| `import-config` / `export-config` | YAML ⇄ database |
| `serve --host 127.0.0.1 --port 8000` | Dashboard + API |
| `seed-demo [--reset]` | Demo data |
| `hash-password` | Prints an argon2 hash to use as `DASHBOARD_PASSWORD` |
| `launchd install / uninstall / status` | Background scheduling |

All commands run as `uv run python -m app.cli <command>`. `make help` lists shortcuts.

## Dashboard

React 18 + TypeScript + Vite, Tailwind + shadcn/ui, TanStack Query/Table, Recharts. Pages:
Overview (KPIs, 30-day chart, types, subjects, empty-subject alert, health), Live pull (SSE log
stream), Channels, Subjects, Files (server-side filters, detail drawer with text, evidence, timeline,
download, *Show in Finder*, reprocess, manual classification), Messages, Runs, Settings (read-only,
secrets masked). Arabic is the default language (full RTL), there's a light and dark theme, and
⌘K / Ctrl+K opens the command palette.

The production build (`frontend/dist`) is served by FastAPI, so you run a single server. For
development, run `make dev` (API with reload + Vite on :5173, proxying `/api`).

## Security

Session cookie (HttpOnly, SameSite=Strict, Secure in production), argon2 password check, CSRF token
on every mutating request, login rate limiting, and a server bound to `127.0.0.1` by default.
OpenAPI docs (`/api/docs`) are only visible after login. Secrets are never sent to the browser or
written to logs. `.env` and the Telegram session should be mode 600, and `health-check` warns
otherwise.

## Tests

```bash
uv run ruff check . && uv run mypy app tests && uv run pytest     # backend (MySQL tuc_test)
cd frontend && npm test -- --run && npm run typecheck             # Vitest
E2E_PASSWORD=... npm run e2e                                      # Playwright smoke (login → overview → files)
```

Backend tests use a real MySQL database from `TUC_TEST_DATABASE_URL` and **refuse to run unless its
name ends with `_test`**. OCR tests are skipped automatically, with a message, when Tesseract or its
`ara`/`eng` data is missing.

## Layout

```
app/            cli config database/{models,migrations,repositories} ingestion logging
                processing/{extractors,classifiers} reports runtime storage telegram web/{api,auth,jobs}
frontend/src/   components/ui components pages lib hooks i18n styles
config/         subjects.yaml channels.yaml (seed files)
deploy/         launchd/ (plist templates)  linux/ (optional systemd)  nginx/ (optional)
scripts/        install_macos.sh setup_mysql.sql
docs/           ARCHITECTURE.md
tests/
```
