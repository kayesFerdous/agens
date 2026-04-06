# Database Migrations

This project uses **Alembic** for database schema management.

## Quick Start

The app automatically runs migrations on startup. Just run:

```bash
python main.py
```

## Manual Migration Commands

### Apply migrations
```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one step
alembic upgrade +1

# Downgrade one step
alembic downgrade -1
```

### Create new migration

After modifying models in `db/models.py`:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new column to messages"

# Create empty migration (for data migrations)
alembic revision -m "Migrate old data format"
```

### View migration history

```bash
# Show current version
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic upgrade head --sql
```

## Migration Files

Location: `alembic/versions/`

- `001_initial_migration.py` - Creates sessions and messages tables

## Troubleshooting

**Problem:** "No such table" error  
**Solution:** Run `python main.py` (migrations run automatically)

**Problem:** Migration out of sync  
**Solution:** Check current version with `alembic current`, then upgrade/downgrade as needed

**Problem:** Want to reset database  
**Solution:** Delete `app.db` file, then run `python main.py`
