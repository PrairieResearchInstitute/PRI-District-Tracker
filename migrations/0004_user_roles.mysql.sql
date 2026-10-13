-- Authority by NetID or campus group (D-018); see the pgsql twin. CHECK constraints
-- are enforced from MySQL 8.0.16.
CREATE TABLE user_roles (
    principal_kind VARCHAR(10)  NOT NULL CHECK (principal_kind IN ('netid', 'group')),
    principal      VARCHAR(255) NOT NULL,
    role           VARCHAR(10)  NOT NULL CHECK (role IN ('admin', 'editor', 'viewer')),
    note           VARCHAR(255) NOT NULL DEFAULT '',
    granted_by     VARCHAR(255) NOT NULL DEFAULT '',
    granted_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at     DATETIME     NULL,
    PRIMARY KEY (principal_kind, principal)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
