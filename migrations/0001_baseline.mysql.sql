-- PRI District Tracker - MySQL baseline: sql/schema.sql as written before the
-- PostgreSQL port, with one fix: `lead` is back-quoted, because LEAD became a
-- reserved word in MySQL 8.0.2 and the unquoted name fails to parse there.
-- Never edit this file once it has run anywhere; put a change in the next number.

SET NAMES utf8mb4;

-- ------------------------------------------------------------------ activities
-- The database of record. NOTHING is ever deleted here. A record is shown on the
-- public site only while show_until IS NULL (evergreen) or show_until >= CURDATE().
CREATE TABLE IF NOT EXISTS activities (
  id           VARCHAR(64)  NOT NULL PRIMARY KEY,   -- stable slug, matches the local JSON id
  survey       VARCHAR(8)   NOT NULL DEFAULT 'INHS', -- INHS/ISGS/ISWS/ISAS/ISTC
  title        VARCHAR(255) NOT NULL,
  type         VARCHAR(40)  NOT NULL DEFAULT 'Project',
  topic        VARCHAR(80)  DEFAULT '',
  `group`      VARCHAR(120) DEFAULT '',             -- "Program area" (reserved word -> backticked)
  summary      TEXT,
  description  TEXT,
  `lead`       VARCHAR(160) DEFAULT '',
  program      VARCHAR(160) DEFAULT '',
  funder       VARCHAR(255) DEFAULT '',
  partners     VARCHAR(255) DEFAULT '',
  status       VARCHAR(60)  DEFAULT '',
  start_year   VARCHAR(20)  DEFAULT '',
  end_year     VARCHAR(20)  DEFAULT '',
  url          VARCHAR(400) DEFAULT '',
  image        VARCHAR(400) DEFAULT '',             -- photo shown in the drill-in popup / handout feature
  scope        VARCHAR(20)  NOT NULL DEFAULT 'statewide', -- statewide/sited/regional/external
  latitude     DECIMAL(9,6) NULL,
  longitude    DECIMAL(9,6) NULL,
  county       VARCHAR(60)  DEFAULT '',
  location     VARCHAR(255) DEFAULT '',
  us_house     VARCHAR(160) DEFAULT '[]',           -- JSON int array, e.g. [13]
  il_senate    VARCHAR(160) DEFAULT '[]',
  il_house     VARCHAR(160) DEFAULT '[]',
  featured     TINYINT(1)   NOT NULL DEFAULT 0,
  confirm      TINYINT(1)   NOT NULL DEFAULT 0,
  keywords     VARCHAR(255) DEFAULT '',
  notes        TEXT,
  theme        VARCHAR(60)  DEFAULT '',
  ingested_at  DATETIME     NULL,                   -- first load (set once)
  updated_at   DATETIME     NULL,                   -- last edit / re-ingest (resets freshness)
  show_until   DATE         NULL,                   -- NULL = evergreen; else hides after this date
  KEY idx_show_until (show_until),
  KEY idx_survey (survey),
  KEY idx_scope (scope)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------ awards ($)
-- Drives the "10-yr funding" card. Same lifecycle stamps.
CREATE TABLE IF NOT EXISTS awards (
  award_id       VARCHAR(64)  NOT NULL PRIMARY KEY,
  survey         VARCHAR(8)   NOT NULL DEFAULT 'INHS',
  activity_id    VARCHAR(64)  DEFAULT '',           -- links the money to an activity (and its districts)
  activity_title VARCHAR(255) DEFAULT '',
  award_title    VARCHAR(255) NOT NULL,
  description    TEXT,
  sponsor        VARCHAR(160) DEFAULT '',
  amount         BIGINT       DEFAULT 0,            -- whole dollars
  start_year     VARCHAR(20)  DEFAULT '',
  end_year       VARCHAR(20)  DEFAULT '',
  pi             VARCHAR(160) DEFAULT '',
  status         VARCHAR(40)  DEFAULT '',
  url            VARCHAR(400) DEFAULT '',
  notes          TEXT,
  ingested_at    DATETIME     NULL,
  updated_at     DATETIME     NULL,
  show_until     DATE         NULL,
  KEY idx_awards_activity (activity_id),
  KEY idx_awards_show_until (show_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------ settings
-- Optional global knobs (e.g. a default display window used when the admin leaves
-- show_until blank on a dated item). Per-record show_until always wins.
CREATE TABLE IF NOT EXISTS settings (
  k VARCHAR(64) NOT NULL PRIMARY KEY,
  v VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO settings (k, v) VALUES ('default_window_days', '548')
  ON DUPLICATE KEY UPDATE v = v;
