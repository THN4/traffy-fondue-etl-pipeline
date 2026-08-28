-- 1. Dimension: Problem Types
CREATE TABLE IF NOT EXISTS dim_problem_type (
    type_id SERIAL PRIMARY KEY,
    full_type VARCHAR(255) UNIQUE NOT NULL,
    main_category VARCHAR(100) NOT NULL,
    sub_category VARCHAR(150),
    detail_category TEXT
);

-- 2. Dimension: Locations
CREATE TABLE IF NOT EXISTS dim_location (
    location_id SERIAL PRIMARY KEY,
    subdistrict VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    province VARCHAR(100) NOT NULL,
    CONSTRAINT uq_location UNIQUE (subdistrict, district, province)
);

-- 3. Dimension: Organizations
CREATE TABLE IF NOT EXISTS dim_organizations (
    org_id SERIAL PRIMARY KEY,
    org_name VARCHAR(255) UNIQUE NOT NULL
);

-- 4. Fact: Tickets
CREATE TABLE IF NOT EXISTS fact_tickets (
    ticket_id VARCHAR(50) PRIMARY KEY,
    message_id BIGINT,
    type_id INTEGER REFERENCES dim_problem_type(type_id),
    location_id INTEGER REFERENCES dim_location(location_id),
    state VARCHAR(50) NOT NULL,
    tags TEXT,
    star DECIMAL(2,1),
    count_reopen INTEGER DEFAULT 0,
    is_internal_rework BOOLEAN DEFAULT FALSE,
    comment TEXT,
    address TEXT,
    longitude DECIMAL(9,6),
    latitude DECIMAL(8,6),
    photo_url TEXT,
    photo_after_url TEXT,
    timestamp TIMESTAMP NOT NULL,
    timestamp_inprogress TIMESTAMP,
    timestamp_finished TIMESTAMP,
    last_activity TIMESTAMP,
    duration_minutes_total DECIMAL(12,2),
    calculated_from_start DECIMAL(12,2),
    calculated_from_inprogress DECIMAL(12,2),
    primary_org_id INTEGER REFERENCES dim_organizations(org_id),
    latest_action_org_id INTEGER REFERENCES dim_organizations(org_id),
    org_count INTEGER DEFAULT 1
);

-- 5. Bridge Table: Ticket Organizations
CREATE TABLE IF NOT EXISTS ticket_organizations (
    ticket_id VARCHAR(50) REFERENCES fact_tickets(ticket_id) ON DELETE CASCADE,
    org_id INTEGER REFERENCES dim_organizations(org_id),
    sequence_order INTEGER NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,
    is_latest_actor BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (ticket_id, org_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_fact_tickets_timestamp ON fact_tickets(timestamp);
CREATE INDEX IF NOT EXISTS idx_fact_tickets_state ON fact_tickets(state);