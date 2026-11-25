/* ============================================================================
   AMPLITUDE WEB ANALYTICS PIPELINE (SNOWFLAKE)
   Architecture: Bronze (raw) -> Base (amplitude_base) -> Silver (fact_events, dim_user) -> Gold (session_aggregations)
   Automation:   Snowpipe (09:15 daily) -> Streams & Chained Tasks (09:30 daily, Europe/London)
   ============================================================================ */

-- Set your Snowflake context before running:
-- USE ROLE <YOUR_ROLE>;
-- USE WAREHOUSE <YOUR_WAREHOUSE>;
-- USE DATABASE <YOUR_DATABASE>;
-- USE SCHEMA <YOUR_SCHEMA>;

/* ============================================================================
   SECTION 1: INITIAL TABLE BUILDS (BACKFILL FROM RAW)
   ============================================================================ */

-- 1.1 Base Layer: Unnest core JSON fields from raw
-- Kept intentionally lean (omitting ~30+ permanently NULL mobile-app fields);
-- Full JSON payload remains archived in the raw table.
CREATE OR REPLACE TABLE amplitude_base AS
SELECT 
    -- Identifiers (amplitude_id is used as the unified user key per Amplitude documentation)
    json_data:uuid::STRING AS uuid
    ,json_data:amplitude_id::NUMBER AS amplitude_id
    ,json_data:user_id::STRING AS user_id
    ,json_data:session_id::NUMBER AS session_id
    ,json_data:event_id::NUMBER AS event_id
    -- Event Details
    ,json_data:event_time::TIMESTAMP AS event_time
    ,json_data:event_type::STRING AS event_type
    -- Location & Device
    ,json_data:country::STRING AS country
    ,json_data:city::STRING AS city
    ,json_data:os_name::STRING AS os_name
    ,json_data:device_type::STRING AS device_type
    ,json_data:device_family::STRING AS device_family
    ,json_data:ip_address::STRING AS ip_address
    -- Second layer unnested Event & User Properties
    ,json_data:event_properties:"[Amplitude] Page URL"::STRING AS page_url
    ,json_data:event_properties:"[Amplitude] Page Title"::STRING AS page_title
    ,json_data:event_properties:"[Amplitude] Element Text"::STRING AS element_text
    ,json_data:user_properties:initial_referring_domain::STRING AS initial_referring_domain
FROM raw;

-- 1.2a Silver Layer (fact_events): One row per unique event (PK: uuid)
-- Stores device_type and os_name at the event level so multi-device users do not overwrite their historical device usage.
-- Converts literal 'EMPTY' strings to standard NULLs.
CREATE OR REPLACE TABLE fact_events AS
SELECT
    uuid
    ,amplitude_id
    ,session_id
    ,event_id
    ,event_time
    ,event_type
    ,device_type
    ,os_name
    ,page_url
    ,page_title
    ,element_text
    ,NULLIF(initial_referring_domain, 'EMPTY') AS initial_referring_domain
FROM amplitude_base
WHERE uuid IS NOT NULL;

-- 1.2b Silver Layer (dim_user): One row per unique user (PK: amplitude_id)
-- SCD Type 1: Keeps only the most recent location/IP details per user.
-- QUALIFY used to keep only each user's single most recent event in case user has multiple events in same batch
CREATE OR REPLACE TABLE dim_user AS
SELECT
    amplitude_id
    ,user_id
    ,country
    ,city
    ,ip_address
FROM amplitude_base
WHERE amplitude_id IS NOT NULL
QUALIFY ROW_NUMBER() OVER (PARTITION BY amplitude_id ORDER BY event_time DESC) = 1;


-- 1.3 Gold Layer (session_aggregations): Session-level summary metrics
-- Grain / Composite Key: (session_id, amplitude_id, device_type) to handle same-millisecond session_id collisions across different users
CREATE OR REPLACE TABLE session_aggregations AS
SELECT
    f.session_id
    ,f.amplitude_id
    ,u.country
    ,u.city
    ,f.device_type
    ,COUNT(*) AS event_count
    ,MIN(f.event_time) AS session_start_time
    ,MAX(f.event_time) AS session_end_time
    ,ROUND(DATEDIFF('second', MIN(f.event_time), MAX(f.event_time)) / 60, 2) AS session_duration_minutes
FROM fact_events f
LEFT JOIN dim_user u
    ON f.amplitude_id = u.amplitude_id
WHERE f.session_id IS NOT NULL
GROUP BY 
    f.session_id
    ,f.amplitude_id
    ,u.country
    ,u.city
    ,f.device_type;

/* ============================================================================
   SECTION 2: STREAMS
   Tracks newly inserted rows at each stage so transformations can run incrementally
   ============================================================================ */

CREATE OR REPLACE STREAM raw_stream ON TABLE raw;
CREATE OR REPLACE STREAM base_stream ON TABLE amplitude_base;
CREATE OR REPLACE STREAM fact_stream ON TABLE fact_events;

/* ============================================================================
   SECTION 3: STORED PROCEDURES
   Each procedure wraps its DML in a transaction with ROLLBACK on error
   ============================================================================ */

-- 3.1 Stage 1 Procedure: raw_stream -> amplitude_base
CREATE OR REPLACE PROCEDURE base_refresh()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    BEGIN TRANSACTION;

        INSERT INTO amplitude_base
        SELECT 
            json_data:uuid::STRING AS uuid
            ,json_data:amplitude_id::NUMBER AS amplitude_id
            ,json_data:user_id::STRING AS user_id
            ,json_data:session_id::NUMBER AS session_id
            ,json_data:event_id::NUMBER AS event_id
            ,json_data:event_time::TIMESTAMP AS event_time
            ,json_data:event_type::STRING AS event_type
            ,json_data:country::STRING AS country
            ,json_data:city::STRING AS city
            ,json_data:os_name::STRING AS os_name
            ,json_data:device_type::STRING AS device_type
            ,json_data:device_family::STRING AS device_family
            ,json_data:ip_address::STRING AS ip_address
            ,json_data:event_properties:"[Amplitude] Page URL"::STRING AS page_url
            ,json_data:event_properties:"[Amplitude] Page Title"::STRING AS page_title
            ,json_data:event_properties:"[Amplitude] Element Text"::STRING AS element_text
            ,json_data:user_properties:initial_referring_domain::STRING AS initial_referring_domain
        FROM raw_stream;

    COMMIT;
    RETURN 'Base table successfully refreshed';

EXCEPTION
    WHEN OTHER THEN
        ROLLBACK;
        RAISE;
END;
$$;

-- 3.2 Stage 2 Procedure: base_stream -> fact_events & dim_user
-- Copies stream into a temp table so the same batch can feed into both Silver tables
CREATE OR REPLACE PROCEDURE silver_refresh()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    BEGIN TRANSACTION;

        CREATE OR REPLACE TEMPORARY TABLE base_stream_temp AS
        SELECT * FROM base_stream;

        MERGE INTO fact_events AS target
        USING (
            SELECT
                uuid
                ,amplitude_id
                ,session_id
                ,event_id
                ,event_time
                ,event_type
                ,device_type
                ,os_name
                ,page_url
                ,page_title
                ,element_text
                ,NULLIF(initial_referring_domain, 'EMPTY') AS initial_referring_domain
            FROM base_stream_temp
            WHERE uuid IS NOT NULL
        ) AS source
        ON target.uuid = source.uuid
        WHEN NOT MATCHED THEN
            INSERT (
                uuid, amplitude_id, session_id, event_id, event_time, event_type,
                device_type, os_name, page_url, page_title, element_text, initial_referring_domain
            )
            VALUES (
                source.uuid, source.amplitude_id, source.session_id, source.event_id, source.event_time, source.event_type,
                source.device_type, source.os_name, source.page_url, source.page_title, source.element_text, source.initial_referring_domain
            );

        MERGE INTO dim_user AS target
        USING (
            SELECT
                amplitude_id
                ,user_id
                ,country
                ,city
                ,ip_address
            FROM base_stream_temp
            WHERE amplitude_id IS NOT NULL
            QUALIFY ROW_NUMBER() OVER (PARTITION BY amplitude_id ORDER BY event_time DESC) = 1
        ) AS source
        ON target.amplitude_id = source.amplitude_id
        WHEN MATCHED THEN
            UPDATE SET
                target.user_id = source.user_id
                ,target.country = source.country
                ,target.city = source.city
                ,target.ip_address = source.ip_address
        WHEN NOT MATCHED THEN
            INSERT (amplitude_id, user_id, country, city, ip_address)
            VALUES (source.amplitude_id, source.user_id, source.country, source.city, source.ip_address);

    COMMIT;
    RETURN 'Silver tables successfully refreshed';

EXCEPTION
    WHEN OTHER THEN
        ROLLBACK;
        RAISE;
END;
$$;

-- 3.3 Stage 3 Procedure: fact_stream -> session_aggregations
-- Uses fact_stream to identify affected sessions, then pulls full session history from fact_events so sessions crossing midnight calculate accurate totals.
CREATE OR REPLACE PROCEDURE gold_refresh()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    BEGIN TRANSACTION;

        MERGE INTO session_aggregations AS target
        USING (
            SELECT
                f.session_id
                ,f.amplitude_id
                ,u.country
                ,u.city
                ,f.device_type
                ,COUNT(*) AS event_count
                ,MIN(f.event_time) AS session_start_time
                ,MAX(f.event_time) AS session_end_time
                ,ROUND(DATEDIFF('second', MIN(f.event_time), MAX(f.event_time)) / 60, 2) AS session_duration_minutes
            FROM fact_events f
            LEFT JOIN dim_user u
                ON f.amplitude_id = u.amplitude_id
            WHERE f.session_id IN (
                SELECT DISTINCT session_id 
                FROM fact_stream 
                WHERE session_id IS NOT NULL
            )
            GROUP BY
                f.session_id
                ,f.amplitude_id
                ,u.country
                ,u.city
                ,f.device_type
        ) AS source
        ON target.session_id = source.session_id
        AND target.amplitude_id = source.amplitude_id
        AND target.device_type IS NOT DISTINCT FROM source.device_type
        WHEN MATCHED THEN
            UPDATE SET
                target.country = source.country
                ,target.city = source.city
                ,target.event_count = source.event_count
                ,target.session_start_time = source.session_start_time
                ,target.session_end_time = source.session_end_time
                ,target.session_duration_minutes = source.session_duration_minutes
        WHEN NOT MATCHED THEN
            INSERT (
                session_id, amplitude_id, country, city, device_type,
                event_count, session_start_time, session_end_time, session_duration_minutes
            )
            VALUES (
                source.session_id, source.amplitude_id, source.country, source.city, source.device_type,
                source.event_count, source.session_start_time, source.session_end_time, source.session_duration_minutes
            );

    COMMIT;
    RETURN 'Gold table successfully refreshed';

EXCEPTION
    WHEN OTHER THEN
        ROLLBACK;
        RAISE;
END;
$$;


/* ============================================================================
   SECTION 4: TASKS
   Scheduled for 09:30 UK time daily (15-min buffer after ~09:15 S3 upload)
   WHEN clauses prevent warehouse spin-up if no new data arrived
   ============================================================================ */

-- 4.1 Root Task (Stage 1)
CREATE OR REPLACE TASK run_base_refresh
    WAREHOUSE = <YOUR_WAREHOUSE>
    SCHEDULE = 'USING CRON 30 9 * * * Europe/London'
    WHEN system$stream_has_data('raw_stream')
AS
    CALL base_refresh();

-- 4.2 Child Task (Stage 2)
CREATE OR REPLACE TASK run_silver_refresh
    WAREHOUSE = <YOUR_WAREHOUSE>
    AFTER run_base_refresh
    WHEN system$stream_has_data('base_stream')
AS
    CALL silver_refresh();

-- 4.3 Child Task (Stage 3)
CREATE OR REPLACE TASK run_gold_refresh
    WAREHOUSE = <YOUR_WAREHOUSE>
    AFTER run_silver_refresh
    WHEN system$stream_has_data('fact_stream')
AS
    CALL gold_refresh();

-- 4.4 Enable Pipeline (Resume children first, root task last)
ALTER TASK run_gold_refresh RESUME;
ALTER TASK run_silver_refresh RESUME;
ALTER TASK run_base_refresh RESUME;

/* To pause the pipeline, suspend in order:
   ALTER TASK run_base_refresh SUSPEND;
   ALTER TASK run_silver_refresh SUSPEND;
   ALTER TASK run_gold_refresh SUSPEND;
*/

/* ============================================================================
   SECTION 5: CHECKS
   ============================================================================ */

-- Check 1: Testing procedures manually
CALL base_refresh();
CALL silver_refresh();
CALL gold_refresh();

-- Check 2: Confirm streams and tasks are active
SHOW STREAMS;
SHOW TASKS;

-- Check 3: Row count reconciliation across all layers
-- (raw, amplitude_base, and fact_events should match)
SELECT 'raw' AS table_name, COUNT(*) AS row_count FROM raw
UNION ALL
SELECT 'amplitude_base', COUNT(*) FROM amplitude_base
UNION ALL
SELECT 'fact_events', COUNT(*) FROM fact_events
UNION ALL
SELECT 'dim_user', COUNT(*) FROM dim_user
UNION ALL
SELECT 'session_aggregations', COUNT(*) FROM session_aggregations;

-- Check 4: Session grain check (small gap reflects same-millisecond collisions)
SELECT 
    COUNT(*) AS total_rows
    ,COUNT(DISTINCT session_id) AS unique_sessions
FROM session_aggregations;

-- Check 5: Verify recent automated task runs
SELECT 
    name
    ,state
    ,scheduled_time
    ,completed_time
    ,error_message
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY())
WHERE name IN ('RUN_BASE_REFRESH', 'RUN_SILVER_REFRESH', 'RUN_GOLD_REFRESH')
ORDER BY scheduled_time DESC
LIMIT 10;