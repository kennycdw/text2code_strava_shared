CREATE TABLE IF NOT EXISTS main.botdata_v2 (
    -- Primary identifiers
    telestrava_id SERIAL UNIQUE,
    telegram_id TEXT PRIMARY KEY,
    strava_id TEXT UNIQUE,
    -- User information
    telegram_name TEXT,
    strava_firstname TEXT,
    strava_lastname TEXT,
    refresh_token VARCHAR(255),
    -- Approval flags (using boolean instead of SMALLINT for clarity)
    strava_approval BOOLEAN DEFAULT FALSE,
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_strava_id ON main.botdata_v2(strava_id);
CREATE INDEX IF NOT EXISTS idx_created_at ON main.botdata_v2(created_at);

-- Trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_botdata_timestamp
    BEFORE UPDATE ON main.botdata_v2
    FOR EACH ROW
    EXECUTE PROCEDURE update_updated_at_column();

-- DROP TRIGGER IF EXISTS update_botdata_timestamp ON main.botdata_v2;
-- DROP FUNCTION IF EXISTS update_updated_at_column();
-- DROP TABLE IF EXISTS main.botdata_v2 CASCADE;
-- DROP INDEX IF EXISTS idx_strava_id;
-- DROP INDEX IF EXISTS idx_created_at;


CREATE TABLE IF NOT EXISTS main.strava_activities (
    id SERIAL PRIMARY KEY,
    strava_id VARCHAR(255) NOT NULL,
    hashed_strava_id VARCHAR(255) NOT NULL,
    activity_id VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    distance FLOAT,
    moving_time INTEGER,
    elapsed_time INTEGER,
    total_elevation_gain FLOAT,
    type VARCHAR(50),
    sport_type VARCHAR(50),
    workout_type INTEGER,
    start_date TIMESTAMP,
    start_date_local TIMESTAMP,
    timezone VARCHAR(100),
    utc_offset INTEGER,
    start_latlng JSONB,
    end_latlng JSONB,
    location_country VARCHAR(100),
    achievement_count INTEGER,
    kudos_count INTEGER,
    comment_count INTEGER,
    athlete_count INTEGER,
    photo_count INTEGER,
    trainer BOOLEAN,
    commute BOOLEAN,
    manual BOOLEAN,
    private BOOLEAN,
    flagged BOOLEAN,
    gear_id VARCHAR(255),
    average_speed FLOAT,
    max_speed FLOAT,
    average_cadence FLOAT,
    average_watts FLOAT,
    weighted_average_watts FLOAT,
    kilojoules FLOAT,
    device_watts BOOLEAN,
    has_heartrate BOOLEAN,
    average_heartrate FLOAT,
    max_heartrate FLOAT,
    max_watts FLOAT,
    pr_count INTEGER,
    total_photo_count INTEGER,
    has_kudoed BOOLEAN,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    UNIQUE(strava_id, activity_id)
);

CREATE INDEX idx_strava_activities_strava_id ON main.strava_activities(strava_id);

-- Create a partial index for non-deleted records
-- This is more efficient than a regular index when querying for is_deleted = false
CREATE INDEX idx_strava_activities_not_deleted 
ON main.strava_activities (strava_id) 
WHERE is_deleted = FALSE;

-- DROP TABLE IF EXISTS main.strava_activities CASCADE;
-- DROP INDEX IF EXISTS idx_strava_activities_strava_id;
-- DROP INDEX IF EXISTS idx_strava_activities_not_deleted;

CREATE TABLE main.strava_charts (
    strava_id VARCHAR(50) NOT NULL,
    strava_hashed_id VARCHAR(50) NOT NULL,
    chart_identifier_id VARCHAR(50) NOT NULL,
    chart_id VARCHAR(50) NOT NULL,
    chart_title VARCHAR(100) NOT NULL,
    web_link TEXT NOT NULL,
    embed_code_responsive TEXT NOT NULL,
    embed_code_web_component TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT strava_charts_pkey PRIMARY KEY (strava_id, chart_identifier_id)
);

-- Index for faster lookups
CREATE INDEX idx_strava_charts_hashed_id ON main.strava_charts(strava_hashed_id);
-- DROP TABLE IF EXISTS main.strava_charts CASCADE;
-- DROP INDEX IF EXISTS idx_strava_charts_hashed_id;

CREATE TABLE main.known_good_queries (
    id SERIAL PRIMARY KEY,
    user_question TEXT NOT NULL UNIQUE,
    query TEXT,
    user_question_embedding VECTOR(768) NOT NULL,
    query_type TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE
);

-- DROP TABLE IF EXISTS main.known_good_queries CASCADE;
-- DROP INDEX IF EXISTS idx_query_embedding;
