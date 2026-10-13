-- plan.md R8: several editors once hosted, so every write to an activity bumps a
-- version (includes/activities.php: the upsert and retire both add 1). A save that
-- carries the version it read can then refuse to overwrite a newer one.
ALTER TABLE activities ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
