-- ExamGuard Server — schema 0006 (Phase 3a fix): immediate disconnect detection.
-- Placeholder __APP_ROLE__ is replaced by the migration with the runtime role name.

-- When the client's WebSocket closes (crash, Ctrl+C, app closed, machine off) the server records it and
-- the attempt becomes INTERRUPTED at once, instead of waiting for missed heartbeats.
ALTER TABLE device_sessions ADD COLUMN connection_closed_at timestamptz;

-- OFFLINE and INTERRUPTED now share one threshold (PRD v0.3.5 Q25): default 30 s = three missed
-- 10-second heartbeats. Only installations still on the old default of 60 s are changed.
UPDATE platform_settings
   SET settings = jsonb_set(settings, '{defaults,interruption_threshold_seconds}', '30'::jsonb),
       updated_at = now()
 WHERE id = 1 AND (settings -> 'defaults' ->> 'interruption_threshold_seconds')::int = 60;
