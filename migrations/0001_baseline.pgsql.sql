-- PRI District Tracker - PostgreSQL baseline.
-- A faithful translation of sql/schema.sql (the MySQL schema as written before the
-- port): the same tables, columns, sizes, defaults and indexes. Changes are dialect
-- only (plan.md R6): no ENGINE or CHARSET (the database is UTF8), TINYINT(1) becomes
-- BOOLEAN, DATETIME becomes TIMESTAMP, DECIMAL becomes NUMERIC, the reserved word
-- "group" is double-quoted, indexes are separate statements, and the settings seed
-- uses ON CONFLICT DO NOTHING.
-- Never edit this file once it has run anywhere; put a change in the next number.

-- ------------------------------------------------------------------ activities
-- The database of record once hosted. NOTHING is ever deleted here. A record is shown
-- on the public site only while show_until IS NULL (evergreen) or show_until >= CURRENT_DATE.
CREATE TABLE activities (
  id           VARCHAR(64)  NOT NULL PRIMARY KEY,
  survey       VARCHAR(8)   NOT NULL DEFAULT 'INHS',
  title        VARCHAR(255) NOT NULL,
  type         VARCHAR(40)  NOT NULL DEFAULT 'Project',
  topic        VARCHAR(80)  DEFAULT '',
  "group"      VARCHAR(120) DEFAULT '',
  summary      TEXT,
  description  TEXT,
  lead         VARCHAR(160) DEFAULT '',
  program      VARCHAR(160) DEFAULT '',
  funder       VARCHAR(255) DEFAULT '',
  partners     VARCHAR(255) DEFAULT '',
  status       VARCHAR(60)  DEFAULT '',
  start_year   VARCHAR(20)  DEFAULT '',
  end_year     VARCHAR(20)  DEFAULT '',
  url          VARCHAR(400) DEFAULT '',
  image        VARCHAR(400) DEFAULT '',
  scope        VARCHAR(20)  NOT NULL DEFAULT 'statewide',
  latitude     NUMERIC(9,6) NULL,
  longitude    NUMERIC(9,6) NULL,
  county       VARCHAR(60)  DEFAULT '',
  location     VARCHAR(255) DEFAULT '',
  us_house     VARCHAR(160) DEFAULT '[]',
  il_senate    VARCHAR(160) DEFAULT '[]',
  il_house     VARCHAR(160) DEFAULT '[]',
  featured     BOOLEAN      NOT NULL DEFAULT FALSE,
  confirm      BOOLEAN      NOT NULL DEFAULT FALSE,
  keywords     VARCHAR(255) DEFAULT '',
  notes        TEXT,
  theme        VARCHAR(60)  DEFAULT '',
  ingested_at  TIMESTAMP    NULL,
  updated_at   TIMESTAMP    NULL,
  show_until   DATE         NULL
);
CREATE INDEX idx_show_until ON activities (show_until);
CREATE INDEX idx_survey ON activities (survey);
CREATE INDEX idx_scope ON activities (scope);

-- ------------------------------------------------------------------ awards ($)
CREATE TABLE awards (
  award_id       VARCHAR(64)  NOT NULL PRIMARY KEY,
  survey         VARCHAR(8)   NOT NULL DEFAULT 'INHS',
  activity_id    VARCHAR(64)  DEFAULT '',
  activity_title VARCHAR(255) DEFAULT '',
  award_title    VARCHAR(255) NOT NULL,
  description    TEXT,
  sponsor        VARCHAR(160) DEFAULT '',
  amount         BIGINT       DEFAULT 0,
  start_year     VARCHAR(20)  DEFAULT '',
  end_year       VARCHAR(20)  DEFAULT '',
  pi             VARCHAR(160) DEFAULT '',
  status         VARCHAR(40)  DEFAULT '',
  url            VARCHAR(400) DEFAULT '',
  notes          TEXT,
  ingested_at    TIMESTAMP    NULL,
  updated_at     TIMESTAMP    NULL,
  show_until     DATE         NULL
);
CREATE INDEX idx_awards_activity ON awards (activity_id);
CREATE INDEX idx_awards_show_until ON awards (show_until);

-- ------------------------------------------------------------------ settings
CREATE TABLE settings (
  k VARCHAR(64)  NOT NULL PRIMARY KEY,
  v VARCHAR(255) NOT NULL
);

INSERT INTO settings (k, v) VALUES ('default_window_days', '548')
  ON CONFLICT (k) DO NOTHING;
