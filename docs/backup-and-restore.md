# Backup & restore

Capital's PostgreSQL database holds the trade history, accounting, strategy
allocations and configuration. It must survive a disk failure.

## What to back up

| Item | How | Why |
|------|-----|-----|
| **Database** | `make backup` → `data/backups/*.sql.gz` | Trades, positions, equity history, settings |
| **`.env`** | Copy somewhere secure, separately | Holds `CAPITAL_SECRET_KEY` |

> ⚠ **The database dump does not contain `.env`.** The Binance/LLM API keys in
> the database are encrypted with `CAPITAL_SECRET_KEY`. A database restored
> without the **exact** secret key cannot decrypt them. Back up `.env`
> separately and securely.

## Taking a backup

```bash
make backup        # or: scripts/backup.sh
```

This runs `pg_dump --clean` inside the `postgres` container and writes a
timestamped, gzipped SQL file to `data/backups/` — which lives off the
database's data volume. The newest 14 dumps are kept (`CAPITAL_BACKUP_RETAIN`
overrides the count).

### Scheduling

Run it from cron on the host — e.g. a daily 03:00 backup:

```cron
0 3 * * *  cd /opt/capital && /usr/bin/make backup >> data/backups/backup.log 2>&1
```

## Restoring

```bash
make restore                       # restores the most recent dump
scripts/restore.sh data/backups/capital-20260521T030000Z.sql.gz
```

The restore is **destructive** — it overwrites the current database — and asks
for a typed confirmation first. Because dumps are taken with `--clean`, a
restore drops and recreates objects in place.

## Tested restore procedure

Verify backups are usable — do not assume:

1. Take a backup: `make backup`.
2. Bring up a throwaway database and restore into it:
   ```bash
   docker compose down -v          # wipes the data volume
   docker compose up -d postgres
   scripts/restore.sh              # restores the latest dump
   ```
3. Start the stack and confirm the dashboard shows the expected trade
   history, positions and equity curve.
4. Confirm stored API keys still work — this proves the `.env` /
   `CAPITAL_SECRET_KEY` you restored alongside the database matches.
