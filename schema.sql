-- OPTIONAL: drop tables if they already exist (wipe data!)
-- Uncomment these if you are re-running the script on an existing DB.
-- DROP TABLE IF EXISTS credit_history CASCADE;
-- DROP TABLE IF EXISTS notification_preferences CASCADE;
-- DROP TABLE IF EXISTS rma_owners CASCADE;
-- DROP TABLE IF EXISTS dispositions CASCADE;
-- DROP TABLE IF EXISTS attachments CASCADE;
-- DROP TABLE IF EXISTS notes_history CASCADE;
-- DROP TABLE IF EXISTS status_history CASCADE;
-- DROP TABLE IF EXISTS rma_lines CASCADE;
-- DROP TABLE IF EXISTS rmas CASCADE;
-- DROP TABLE IF EXISTS customers CASCADE;
-- DROP TABLE IF EXISTS users CASCADE;

-- Users (for authentication and ownership)
CREATE TABLE IF NOT EXISTS users (
    user_id          SERIAL PRIMARY KEY,
    username         TEXT NOT NULL UNIQUE,
    password_hash    TEXT NOT NULL,
    full_name        TEXT NOT NULL,
    email            TEXT NOT NULL UNIQUE,
    role             TEXT DEFAULT 'user',
    is_owner         INTEGER DEFAULT 0,
    is_admin         INTEGER DEFAULT 0,
    created_on       TIMESTAMP NOT NULL,
    last_login       TIMESTAMP
);

-- Customers
CREATE TABLE IF NOT EXISTS customers (
    customer_id      SERIAL PRIMARY KEY,
    customer_name    TEXT NOT NULL,
    contact_name     TEXT,
    contact_email    TEXT,
    contact_address  TEXT
);

-- RMAs (header)
CREATE TABLE IF NOT EXISTS rmas (
    rma_id                 SERIAL PRIMARY KEY,
    customer_id            INTEGER NOT NULL,
    created_by_user_id     INTEGER,
    date_opened            TIMESTAMP NOT NULL,
    customer_date_opened   DATE,
    date_closed            TIMESTAMP,
    closed_by              INTEGER,
    status                 TEXT NOT NULL DEFAULT 'Draft',
    return_type            TEXT,
    assigned_to_user_id    INTEGER,
    acknowledged           INTEGER DEFAULT 0,
    acknowledged_on        TIMESTAMP,
    acknowledged_by        INTEGER,
    customer_complaint_desc TEXT,
    internal_notes         TEXT,
    notes_last_modified    TIMESTAMP,
    notes_modified_by      TEXT,
    -- Credit fields
    credit_memo_number     TEXT,
    credit_amount          NUMERIC(12,2),
    credit_approved        INTEGER DEFAULT 0,
    credit_approved_on     TIMESTAMP,
    credit_approved_by     INTEGER,
    credit_rejected        INTEGER DEFAULT 0,
    credit_rejected_on     TIMESTAMP,
    credit_rejected_by     INTEGER,
    credit_rejection_reason TEXT,
    credit_issued_on       TIMESTAMP,
    CONSTRAINT fk_rmas_customer
      FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    CONSTRAINT fk_rmas_assigned_to
      FOREIGN KEY (assigned_to_user_id) REFERENCES users(user_id),
    CONSTRAINT fk_rmas_created_by
      FOREIGN KEY (created_by_user_id) REFERENCES users(user_id),
    CONSTRAINT fk_rmas_closed_by
      FOREIGN KEY (closed_by) REFERENCES users(user_id),
    CONSTRAINT fk_rmas_ack_by
      FOREIGN KEY (acknowledged_by) REFERENCES users(user_id),
    CONSTRAINT fk_rmas_credit_approved_by
      FOREIGN KEY (credit_approved_by) REFERENCES users(user_id),
    CONSTRAINT fk_rmas_credit_rejected_by
      FOREIGN KEY (credit_rejected_by) REFERENCES users(user_id)
);

-- RMA lines
CREATE TABLE IF NOT EXISTS rma_lines (
    rma_line_id     SERIAL PRIMARY KEY,
    rma_id          INTEGER NOT NULL,
    part_number     TEXT,
    tool_number     TEXT,
    item_description TEXT,
    qty_affected    INTEGER,
    po_lot_number   TEXT,
    total_cost      NUMERIC(12,2),
    CONSTRAINT fk_rma_lines_rma
      FOREIGN KEY (rma_id) REFERENCES rmas(rma_id) ON DELETE CASCADE
);

-- Status history
CREATE TABLE IF NOT EXISTS status_history (
    status_hist_id  SERIAL PRIMARY KEY,
    rma_id          INTEGER NOT NULL,
    status          TEXT NOT NULL,
    changed_by      INTEGER,
    changed_on      TIMESTAMP NOT NULL,
    comment         TEXT,
    CONSTRAINT fk_status_hist_rma
      FOREIGN KEY (rma_id) REFERENCES rmas(rma_id) ON DELETE CASCADE,
    CONSTRAINT fk_status_hist_changed_by
      FOREIGN KEY (changed_by) REFERENCES users(user_id)
);

-- Notes history
CREATE TABLE IF NOT EXISTS notes_history (
    note_hist_id    SERIAL PRIMARY KEY,
    rma_id          INTEGER NOT NULL,
    notes_content   TEXT,
    modified_by     TEXT,
    modified_on     TIMESTAMP NOT NULL,
    CONSTRAINT fk_notes_hist_rma
      FOREIGN KEY (rma_id) REFERENCES rmas(rma_id) ON DELETE CASCADE
);

-- Attachments
CREATE TABLE IF NOT EXISTS attachments (
    attachment_id   SERIAL PRIMARY KEY,
    rma_id          INTEGER NOT NULL,
    rma_line_id     INTEGER,
    file_path       TEXT NOT NULL,
    filename        TEXT,
    attachment_type TEXT,
    added_by        TEXT,
    uploaded_by     INTEGER,
    date_added      TIMESTAMP NOT NULL,
    uploaded_on     TIMESTAMP,
    CONSTRAINT fk_attachments_rma
      FOREIGN KEY (rma_id) REFERENCES rmas(rma_id) ON DELETE CASCADE,
    CONSTRAINT fk_attachments_line
      FOREIGN KEY (rma_line_id) REFERENCES rma_lines(rma_line_id) ON DELETE CASCADE,
    CONSTRAINT fk_attachments_uploaded_by
      FOREIGN KEY (uploaded_by) REFERENCES users(user_id)
);

-- Dispositions
CREATE TABLE IF NOT EXISTS dispositions (
    disposition_id      SERIAL PRIMARY KEY,
    rma_line_id         INTEGER NOT NULL,
    disposition         TEXT,
    failure_code        TEXT,
    failure_description TEXT,
    root_cause          TEXT,
    corrective_action   TEXT,
    qty_scrap           INTEGER,
    qty_rework          INTEGER,
    qty_replace         INTEGER,
    date_dispositioned  TIMESTAMP,
    disposition_by      INTEGER,
    CONSTRAINT fk_dispositions_line
      FOREIGN KEY (rma_line_id) REFERENCES rma_lines(rma_line_id) ON DELETE CASCADE,
    CONSTRAINT fk_dispositions_by
      FOREIGN KEY (disposition_by) REFERENCES users(user_id)
);

-- RMA Owners (for multiple owner assignments)
CREATE TABLE IF NOT EXISTS rma_owners (
    assignment_id   SERIAL PRIMARY KEY,
    rma_id          INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    is_primary      INTEGER DEFAULT 0,
    assigned_on     TIMESTAMP,
    assigned_by     INTEGER,
    CONSTRAINT fk_rma_owners_rma
      FOREIGN KEY (rma_id) REFERENCES rmas(rma_id) ON DELETE CASCADE,
    CONSTRAINT fk_rma_owners_user
      FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT fk_rma_owners_assigned_by
      FOREIGN KEY (assigned_by) REFERENCES users(user_id)
);

-- Notification Preferences
CREATE TABLE IF NOT EXISTS notification_preferences (
    preference_id        SERIAL PRIMARY KEY,
    user_id              INTEGER NOT NULL,
    days_threshold       INTEGER DEFAULT 3,
    notification_frequency TEXT DEFAULT 'weekly',
    -- Weekly schedule
    notify_sunday        BOOLEAN DEFAULT FALSE,
    notify_monday        BOOLEAN DEFAULT TRUE,
    notify_tuesday       BOOLEAN DEFAULT FALSE,
    notify_wednesday     BOOLEAN DEFAULT FALSE,
    notify_thursday      BOOLEAN DEFAULT FALSE,
    notify_friday        BOOLEAN DEFAULT FALSE,
    notify_saturday      BOOLEAN DEFAULT FALSE,
    notification_time    TIME DEFAULT '09:00:00',
    CONSTRAINT fk_notif_prefs_user
      FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Credit History (track all credit-related changes)
CREATE TABLE IF NOT EXISTS credit_history (
    credit_hist_id   SERIAL PRIMARY KEY,
    rma_id           INTEGER NOT NULL,
    action           TEXT NOT NULL,
    amount           NUMERIC(12,2),
    memo_number      TEXT,
    action_by        INTEGER,
    action_on        TIMESTAMP NOT NULL,
    comment          TEXT,
    CONSTRAINT fk_credit_hist_rma
      FOREIGN KEY (rma_id) REFERENCES rmas(rma_id) ON DELETE CASCADE,
    CONSTRAINT fk_credit_hist_action_by
      FOREIGN KEY (action_by) REFERENCES users(user_id)
);
