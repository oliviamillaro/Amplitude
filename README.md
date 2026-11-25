# Amplitude ELT Project

## Project Overview

Amplitude is a product analytics platform that tracks user interactions and behavior across digital products. The aim of this project is to capture and model usage data from the company’s Data School website.

This end-to-end ELT pipeline extracts daily event data from Amplitude via its Export API, uploads it to an AWS S3 bucket, and automatically ingests it into Snowflake via Snowpipe. The ingestion workflow is modularised in Python and orchestrated daily using Kestra. Once raw JSON files land in Snowflake, an automated medallion-style transformation pipeline uses Streams, Stored Procedures, and Tasks to incrementally build analytics-ready fact, dimension, and session aggregation tables.

---

## Local Setup

**1. Clone the Repository**
I created the repository on GitHub, cloned it locally using **GitHub Desktop**, and opened the project directly into VS Code from the GitHub Desktop interface.

**2. Environment Setup (PowerShell)**
I opened a PowerShell terminal in VS Code to create a virtual environment and installed the required dependencies.

**3. Configuration & Security**
I then created a .env file in the root folder and added the necessary credentials (AMP and AWS credentials).

I ensured the .gitignore file included the raw_json, logs/ and .env files.

---

## Extract Stage

The extraction script (`modules/extract_function.py`) is responsible for retrieving daily event data from the Amplitude Export API and preparing it for loading.

Instead of hardcoded values, the script is designed for automated daily runs and features error handling. The extraction process is broken down into the following sections:

* **Dynamic Date Configuration:** The script calculates a midnight-to-midnight time range for the previous day, generating file labels that combine the data's date and the extraction timestamp.
* **API Request & Retry Logic:** Connects to the Export API using HTTP Basic Authentication. It features a `while` loop with doubling backoff to handle rate limits (429) and server errors (500+), and exiting if no data exists for the selected time range (404).
* **Data Unpacking & Decompression:** Amplitude returns a compressed ZIP containing nested, dynamically named folders with `.gz` files. The script downloads the ZIP, saved and unpacks it into a temporary directory, loops through the nested folders, and decompresses the binary `.gz` files into `.json` formats. The temporary directory is cleaned up after the JSONs have been extracted safely.
* **Logging & Cleanup:** Every API attempt, status code, and file extraction is recorded with a timestamp in a local `logs/` directory for full auditability. Upon successful extraction, the script automatically deletes the temporary directories and leftover compressed files.

*(Note: The `modules/extract_function.py` file contains line-by-line comments to help understand exactly how the code works.)*

---

## Load Stage

The loading phase transfers the extracted local JSON files into a secure AWS S3 bucket, and loads them into Snowflake, ready for the transformation stage. The process consists of three main stages:

- **AWS Bucket Setup:** 
  - **Storage & Security:** Created an AWS S3 bucket to store the raw Amplitude data, secured with Server-Side Encryption using an AWS Key Management Service (SSE-KMS) key.
  - **Access Management:** Configured IAM Policies to grant specific Read/Write/List permissions. Created an IAM User with access keys (stored securely in the `.env` file and Kestra's KV Store) for the Python script, and an IAM Role to establish a trust relationship with Snowflake.

- **Python Loading Script (`modules/load_function.py`):** 
  - **Automated Uploads:** Uses the `boto3` library to securely connect to AWS. The script iterates through the local `raw_json` directory and pushes each file to the S3 bucket.
  - **Safe Cleanup & Logging:** Wrapped in `try/except` blocks, the script only deletes the local JSON files if the S3 upload is successful. Every step is tracked via the `logging` module in case debugging is required.
  - *(Note: The `modules/load_function.py` file contains line-by-line comments to help understand exactly how the code works.)*

- **Snowflake Integration:**
  - **Storage Integration:** Created a `STORAGE INTEGRATION` to link Snowflake to S3. To secure the connection, the generated Snowflake External ID was passed back into the AWS IAM Role's Trust Policy.
  - **External Stage:** Set up an external `STAGE` acting as a secure portal to the S3 bucket. A custom `FILE_FORMAT` was applied to properly parse the JSON data (e.g., stripping outer arrays).
  - **Raw Table & Snowpipe Setup:** Created a raw landing table utilising Snowflake's VARIANT data type to hold the raw JSON payload alongside metadata columns (file_name, file_row_number, and file_last_modified). After validating the load with an initial COPY INTO test, automated ingestion was configured via a Snowpipe.
 
---

## Code Modularisation

Once the standalone extract and load scripts were tested, the code was split into reusable modules inside the modules/ folder and managed by a central controller (main.py). At runtime, main.py loads the required credentials, sets the previous day's midnight-to-midnight timestamps, initialises logging, and routes each step of the pipeline using True/False checks. The reusable modules are:

- **`modules/setup_logging.py`:** Configures a shared root logger that outputs timestamped logs to both the terminal and a local `logs/` directory.
- **`modules/s3_check.py`:** Checks the S3 bucket before extraction begins. If files for the target date already exist, the script logs the finding and exits early (`sys.exit(0)`) to prevent redundant API calls and duplicate uploads.
- **`modules/extract_function.py`:** Handles extracting and unpacking daily event data from the Amplitude Export API.
- **`modules/load_function.py`:** Handles uploading the extracted JSON files to AWS S3 and cleaning up local files.

---

## Orchestration & Automation

To orchestrate the pipeline, daily scheduling and event-driven ingestion were configured across Kestra and Snowflake:

- **Kestra Workflow:**
  - **Schedule & Namespace:** Configured in the `amplitude` namespace to run automatically every day at `09:15` UK time (`cron: "15 9 * * *"`, `Europe/London`), landing fresh files in S3 and Snowpipe ahead of the `09:30` Snowflake transformation tasks.
  - **Containerised Execution:** Clones the `main` branch from GitHub into a clean working directory, spins up an isolated `python:slim` Docker container, installs dependencies from `requirements.txt`, and executes `python main.py`.
  - **Secrets Management:** All Amplitude and AWS credentials are stored encrypted in Kestra's namespace KV Store and injected as environment variables at runtime.

- **Snowflake Snowpipe:**
  - **Auto-Ingest Pipe:** Created with `auto_ingest = true` to continuously load new JSON files from the external stage into the `raw` table.
  - **AWS S3 Event Notifications:** Configured S3 bucket notifications (`s3:ObjectCreated:*` filtered to `.json` files) to publish directly to Snowflake's SQS notification channel, triggering ingestion within seconds while deduplicating previously loaded filenames.
 
---

## Transform Stage

Once the raw JSON payloads lands in Snowflake via Snowpipe, an automated medallion-style pipeline (`amplitude_transformation.sql`) incrementally transforms the data from raw events into analytics-ready session metrics. All layers are materialised as physical tables rather than views so that Snowflake Streams can be used to track row-level changes and downstream queries never re-parse raw JSON.

- **Base Layer (`raw` → `amplitude_base`):**
  - **Incremental Ingestion:** Tracked by `raw_stream` and processed via the `base_refresh()` stored procedure, ensuring late-arriving records are captured and processed once without relying on brittle timestamp filters.
  - **Direct JSON Parsing:** Extracts fields using Snowflake's direct key referencing (`:`), as Amplitude event payloads are structured as JSON objects (`{}`).
  - **Lean Base Table:** Retains ~17 core web analytics columns and intentionally omits 30+ permanently `NULL` mobile-app fields (e.g., `idfa`, `adid`), keeping the base layer lightweight while the `raw` table preserves the full JSON payload for any future schema evolution.

- **Silver Layer (`amplitude_base` → `fact_events` & `dim_user`):**
  - **Multi-Table Stream Consumption:** Driven by `base_stream` and `silver_refresh()`. Incoming records are first staged in a temporary table (`base_stream_temp`) so a single stream batch can populate both Silver tables.
  - **Event Fact Table (`fact_events`):** Loaded via an `MERGE` (`WHEN NOT MATCHED THEN INSERT`) keyed on `uuid` to avoid duplicate file uploads. Stores `device_type` and `os_name` at the event grain so multi-device users do not overwrite historical device context, and standardises literal `'EMPTY'` strings in `initial_referring_domain` into true `NULL`s using `NULLIF`.
  - **User Dimension Table (`dim_user`):** Keyed on `amplitude_id` and maintained via a **SCD Type 1** `MERGE`, overwriting attributes (`user_id`, `country`, `city`, `ip_address`) with each user's latest details. Uses `QUALIFY ROW_NUMBER()` to deduplicate multiple events per user within the same batch, just retaining the latest information.
  - **Identity Resolution Choice:** Uses `amplitude_id` instead of a custom `COALESCE(user_id, amplitude_id)` key. Amplitude natively stitches pre-login anonymous activity to a logged-in `user_id` under one `amplitude_id` on the same device, preventing mid-session logins from splitting a user's journey.

- **Gold Layer (`fact_events` + `dim_user` → `session_aggregations`):**
  - **Midnight-Crossing Session Handling:** Driven by `fact_stream` and `gold_refresh()`. Rather than aggregating only newly arrived rows, the procedure treats `fact_stream` as a list of affected `session_id`s, pulls the complete event history for those sessions from `fact_events`, and `LEFT JOIN`s `dim_user` on `amplitude_id` so sessions spanning midnight are always recalculated accurately.
  - **Composite Key:** Merges on `(session_id, amplitude_id, device_type)` using `IS NOT DISTINCT FROM` to safely match `NULL` device types. As Amplitude generates `session_id` from millisecond timestamps, this composite grain prevents collisions when simultaneous visitors or bots start sessions in the exact same millisecond.

- **Snowflake Task Orchestration:**
  - **Chained Execution:** Automated via three dependent Snowflake Tasks: `run_base_refresh` runs daily at `09:30` UK time (`USING CRON 30 9 * * * Europe/London`), followed sequentially by `run_silver_refresh` and `run_gold_refresh` via `AFTER` dependencies.
  - **Zero-Waste Compute:** Every task is guarded by `WHEN system$stream_has_data(...)`, skipping execution without spinning up the warehouse whenever a stream is empty. Verified via `TASK_HISTORY()`, full end-to-end daily runs complete in ~17 seconds, while empty runs register as `SKIPPED` at zero compute cost.

*(Note: The `amplitude_transformation.sql` script contains the full SQL for more detail.)*
