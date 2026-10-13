-- plan.md R8: every write to an activity bumps a version; see the pgsql twin.
ALTER TABLE activities ADD COLUMN version INT NOT NULL DEFAULT 1;
