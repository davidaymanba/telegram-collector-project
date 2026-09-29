# Architecture

## Processes

| Process | Started by | Holds the job lock |
|---|---|---|
| `serve` (FastAPI + built SPA) | you / `com.tuc.web` | no; web jobs run as CLI subprocesses |
| `collect` | CLI / dashboard / `com.tuc.collector` | yes |
| `process`, `reclassify` | CLI / dashboard / `com.tuc.process` | yes |
| file reprocess / manual classify | dashboard (in-request) | yes (423 if busy) |

The dashboard never runs collection in its own process. `JobManager` spawns
`python -m app.cli <kind> --trigger web` with `TUC_LOG_FORMAT=json`, parses the JSON log lines
(`run_started`, `progress`, `run_finished`) for live counters, and relays every line to the
browser over SSE (`/api/v1/jobs/{id}/stream`). launchd and the dashboard therefore run the exact
same code path, lock and run records.

## Data flow

1. `telegram/collector.py` talks to Telegram only through the `TelegramGateway` protocol
   (`telethon_gateway.py` in production, a fake in tests). Per message: store `Message` →
   unsupported? → duplicate by `document.id`? → download to `.part` → SHA-256 duplicate? →
   rename into `storage/incoming` → advance `channels.last_message_id` → commit.
2. `processing/pipeline.py`: extract (`extractors/`), `clean_text`, write `storage/texts/<id>.txt`,
   classify (`classifiers/service.py`: rules → OpenAI → validation), move to
   `processed/<SUBJECT>/<type>/` or `unclassified/`, one `ProcessingLog` per stage.
3. `reports/reporter.py` builds the same report for the CLI and `/api/v1/report`.

## Database

MySQL 8, utf8mb4_unicode_ci everywhere, SQLAlchemy 2 typed models, repositories in
`app/database/repositories/`, Alembic migrations in `app/database/migrations/`. Datetimes are
stored as UTC `DATETIME(6)` and returned timezone-aware.

## Frontend

`frontend/src`: `pages/` (one per route, lazy-loaded), `components/ui/` (shadcn/Radix primitives
written with logical properties for RTL), `hooks/queries.ts` (every API call via TanStack Query),
`i18n/` (`ar.ts` and `en.ts` with identical keys, enforced by a test), and `styles/globals.css`
(all design tokens: neutral zinc base, one teal accent, semantic file-state colours, and a
validated categorical palette used only for the content-type chart).
