# Database Migration

## Usage

### Export (Current Computer)

Double-click `export.bat`

SQL file will be saved to `backups/patient_agent.sql`

### Import (New Computer)

1. Install Docker Desktop
2. Copy the `migration` folder to new computer
3. Run `docker compose up -d` once to create containers
4. Double-click `import.bat`

---

## Files

| File | Purpose |
|------|---------|
| `export.bat` | Export database |
| `import.bat` | Import database |
| `backups/` | SQL backup files |

---

## Manual Commands

```bash
# Export
docker exec patient-agent-postgres pg_dump -U postgres patient_agent > backup.sql

# Import
docker exec -i patient-agent-postgres psql -U postgres patient_agent < backup.sql
```
