-- LarcRH — Table Kanban des tâches RH
-- Usage : psql -U postgres -d NewLarcDB -f migration_20260809_staff_todo.sql

BEGIN;

CREATE TABLE IF NOT EXISTS staff_todo (
    id          SERIAL PRIMARY KEY,
    staff_id    INT,
    task_type   VARCHAR(32) DEFAULT 'custom',
    description TEXT,
    status      VARCHAR(16) DEFAULT 'todo',
    assigned_to INT,
    created_by  INT,
    created_at  TIMESTAMP DEFAULT NOW(),
    due_date    DATE,
    resolved_at TIMESTAMP,
    resolved_by INT,
    log         JSONB
);

CREATE INDEX IF NOT EXISTS idx_staff_todo_status ON staff_todo(status);
CREATE INDEX IF NOT EXISTS idx_staff_todo_assigned ON staff_todo(assigned_to);

COMMIT;
