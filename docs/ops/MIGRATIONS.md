# Database Migrations

## Rules

1. **Every migration must implement `downgrade()`.** If a change is genuinely irreversible (dropping data, one-way schema transforms), `downgrade()` must `raise NotImplementedError("Irreversible: <reason>")` with justification — silence is not allowed.
2. **One logical change per migration.** Do not bundle unrelated schema changes.
3. **Never edit a merged migration.** Create a new one that patches forward.
4. **Destructive operations (DROP COLUMN / DROP TABLE / ALTER TYPE with data loss) require an explicit comment** naming the approver and the rollback plan.
5. **Test round-trip locally before committing:**
   ```bash
   alembic upgrade head && alembic downgrade -1 && alembic upgrade head
   ```

## Creating a new migration

```bash
cd backend
alembic revision --autogenerate -m "short_slug"
# Edit the generated file: verify upgrade() and write downgrade()
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

## Deploy order

1. Merge migration PR (migration runs on deploy; app code must tolerate both old and new schema).
2. Merge app-code PR that depends on the migration.

Never ship an app change and its migration in the same PR unless the code is backward-compatible with the old schema.

## CI

`.github/workflows/migrations.yml` runs `alembic upgrade head → downgrade base → upgrade head` on every PR that touches `backend/alembic/versions/**`. If the round-trip fails, the PR is blocked.
