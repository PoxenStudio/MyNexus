---
name: mynexus-migration-versioning
description: MyNexus schema migrations are now version-tracked (schema_migrations table) instead of re-running every file's full SQL on every startup
metadata:
  type: project
---

Replaced the original "re-run every migration file's full contents on every startup, no tracking" approach with a real version-tracked migration runner: `core-api/internal/storage/migrator.go`'s `RunMigrations(db, fsys, dir)`.

**How it works:** on connect, ensures a `schema_migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMP)` table exists, reads the embedded migration directory, and for each file not already recorded there, splits it into `;`-separated statements, runs them plus an `INSERT INTO schema_migrations` inside one transaction, and commits. Already-applied files are skipped entirely on subsequent boots. Shared by both `storage/sqlite` and `storage/postgres` (`Open()` in both just calls `storage.RunMigrations(db, migrationFiles, "migrations")`) — this is what the user asked for as "check the table structure on connect and auto create/upgrade."

**Why this replaces the earlier approach**: the old `migrate()` (documented in [[mynexus_m4_decisions]]'s token_suffix note) re-executed every `.sql` file's full text on every single startup with no record of what had run before. That only worked because every statement so far was `CREATE TABLE/INDEX IF NOT EXISTS` (idempotent). It could never have supported a real `ALTER TABLE ADD COLUMN` — a second run would error. That's why, at the time, a schema change (the `token_suffix` column) had to be hand-edited into the already-shipped `0001_init.sql` instead of added as a new file.

**New convention going forward: schema changes are new numbered migration files, not edits to shipped ones.** E.g. the next real schema change should be `0002_something.sql` in *both* `storage/sqlite/migrations/` and `storage/postgres/migrations/` (see [[mynexus_postgres_backend]] — the two backends keep separate migration files in lockstep, only `DATETIME`/`TIMESTAMP` differing). `0002_*.sql` can now safely contain non-idempotent statements like `ALTER TABLE ... ADD COLUMN ...` since it will only ever execute once per database, tracked by filename in `schema_migrations`.

**Backward compatible with the pre-existing `0001_init.sql` deployments**: since `0001_init.sql`'s statements are all `IF NOT EXISTS`-guarded, the first boot under the new runner re-runs them safely (no-op if tables already exist) and then records `0001_init.sql` as applied — no manual backfill step needed.

**Verified**: ran `core-api` locally against a fresh SQLite file — `schema_migrations` table created, `0001_init.sql` recorded with a timestamp; running it again left the row/timestamp untouched (confirmed skip-on-second-run via direct `sqlite3` inspection). Not yet verified against a live Postgres instance (no local Docker daemon running this session) — same code path, should behave identically since `storage.RunMigrations` only depends on `*sql.DB` behavior, not backend specifics beyond the already-handled statement-splitting.
