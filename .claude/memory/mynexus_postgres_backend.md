---
name: mynexus-postgres-backend
description: How MyNexus's Postgres storage backend works alongside SQLite — shared SQL, placeholder-rewriting driver, config/docker-compose switches
metadata:
  type: project
---

Added a real Postgres backend (`core-api/internal/storage/postgres`) alongside the existing SQLite one, resolving the gap flagged in [[mynexus_known_gaps_and_conflicts]] (item was previously "postgres is a config placeholder, not implemented").

**Both backends implement `storage.Database`** (`DB() *sql.DB`, `Health()`, `Close()`) — `router.go` and `system_handler.go` now take `storage.Database` instead of the concrete `*sqlite.Store`, so the rest of Core API is backend-agnostic. `main.go`'s `openStore(cfg)` picks sqlite/postgres based on `storage.database` (env `MYNEXUS_STORAGE_DATABASE`).

**Service-layer SQL is NOT duplicated per backend.** All `internal/service/*.go` queries are written once, using SQLite-style `?` placeholders. Postgres wants `$1, $2, ...`, so `storage/postgres/qmark_driver.go` registers a custom `database/sql` driver (`postgres-qmark`) that wraps `github.com/jackc/pgx/v5/stdlib`'s connection: it implements `Prepare`/`PrepareContext`/`ExecContext`/`QueryContext`/`BeginTx`/`Ping`/`CheckNamedValue`, rewriting `?` → `$N` before delegating to the real pgx conn. This means adding Postgres support required zero changes to any service file.
Why this approach over forking every query: the alternative (parallel query sets, or a query builder/ORM) is much larger surface area for a single-developer project; a ~100-line driver shim is the smallest change that keeps "one save, `?` everywhere" from [[mynexus_m2_decisions]]/[[mynexus_m3_decisions]]'s style intact.

**Migrations are NOT shared verbatim between backends** — `storage/postgres/migrations/0001_init.sql` is a separate file from `storage/sqlite/migrations/0001_init.sql`, kept in lockstep by hand (same tables/columns, only `DATETIME` → `TIMESTAMP` differs, since Postgres has no `DATETIME` type). If a future schema change touches one, it must touch both.
Both now run through the same shared, version-tracked runner — see [[mynexus_migration_versioning]] — which splits every migration file into individual `;`-separated statements before executing (needed for Postgres's extended query protocol, harmless for SQLite).

**Dependency added:** `github.com/jackc/pgx/v5/stdlib` — pure Go, no CGO, so cross-compilation and the `CGO_ENABLED=0` Dockerfile build are unaffected (consistent with the reasoning for choosing `modernc.org/sqlite` originally).

**Switching backends:**
- `config/config.yaml`: `storage.database: sqlite|postgres`, `storage.postgres.dsn`.
- Env overrides: `MYNEXUS_STORAGE_DATABASE`, `MYNEXUS_STORAGE_POSTGRES_DSN`.
- `docker-compose.yml`: added an optional `postgres` service gated behind the `postgres` Compose profile (`docker compose --profile postgres up`) plus `STORAGE_DATABASE`/`STORAGE_POSTGRES_DSN`/`POSTGRES_*` env vars — default `docker compose up` still runs plain SQLite with no postgres container started. Note: `core-api` does NOT `depends_on: postgres` (would force the profile on for the default sqlite path), so on first boot with the profile enabled, core-api may fail-and-restart once or twice via its `restart: unless-stopped` policy until postgres is ready — expected, not a bug.

**Still open / not done:** no data migration/export tool between the two backends (switching an existing deployment from sqlite to postgres means starting with an empty postgres DB, not migrating existing books/chunks). No connection pooling tuning beyond `database/sql` defaults. No postgres-specific tests were added beyond a clean `go build`/`go vet`/`gofmt` pass — not verified against a live Postgres instance in this session.
