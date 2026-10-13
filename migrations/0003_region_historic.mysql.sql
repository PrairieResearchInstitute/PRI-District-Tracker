-- region and historic from data/activities.json; see the pgsql twin and Q-05.
ALTER TABLE activities ADD COLUMN region VARCHAR(60) DEFAULT '';
ALTER TABLE activities ADD COLUMN historic TINYINT(1) NOT NULL DEFAULT 0;
