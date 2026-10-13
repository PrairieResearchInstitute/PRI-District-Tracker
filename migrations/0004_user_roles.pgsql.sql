-- Authority by NetID or campus group (owner, 2026-10-12, decision D-018): a user's
-- role is the highest role granted to the user's NetID or to any campus group the
-- user belongs to. The running app only reads this table; tools/roles.php, run as
-- the owner role, grants and revokes. A revoke stamps revoked_at and keeps the row,
-- so the history of who held which role stays in the table.
-- principal holds a lowercase NetID or a lowercase campus group name.
CREATE TABLE user_roles (
    principal_kind VARCHAR(10)  NOT NULL CHECK (principal_kind IN ('netid', 'group')),
    principal      VARCHAR(255) NOT NULL,
    role           VARCHAR(10)  NOT NULL CHECK (role IN ('admin', 'editor', 'viewer')),
    note           VARCHAR(255) NOT NULL DEFAULT '',
    granted_by     VARCHAR(255) NOT NULL DEFAULT '',
    granted_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at     TIMESTAMP    NULL,
    PRIMARY KEY (principal_kind, principal)
);
