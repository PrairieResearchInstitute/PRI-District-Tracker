-- data/activities.json carries two fields the written schema had no column for:
-- region (6 records, e.g. "Chicago metro") and historic (3 records, true). Without
-- these columns a load silently drops them. Open question Q-05 asks the owner to
-- confirm keeping them; dropping them later is a new migration, never an edit here.
ALTER TABLE activities ADD COLUMN region VARCHAR(60) DEFAULT '';
ALTER TABLE activities ADD COLUMN historic BOOLEAN NOT NULL DEFAULT FALSE;
