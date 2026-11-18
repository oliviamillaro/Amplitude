# Amplitude ELT Project

## Project Overview

Amplitude is a product analytics platform that tracks user interactions and behavior across digital products. The aim of this project is to capture usage data from the company’s Data School website.

This pipeline extracts daily event data from Amplitude via its Export API, uploads it to an AWS S3 bucket, and automatically ingests it into Snowflake via a Snowpipe. The workflow is modularised in Python and orchestrated daily using Kestra.

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

- **Kestra Workflow (`amplitude_ingestion_des9`):**
  - **Schedule & Namespace:** Configured in the `amplitude` namespace to run automatically every day at `06:00 UTC` (`cron: "0 6 * * *"`).
  - **Containerised Execution:** Clones the `main` branch from GitHub into a clean working directory, spins up an isolated `python:slim` Docker container, installs dependencies from `requirements.txt`, and executes `python main.py`.
  - **Secrets Management:** All Amplitude and AWS credentials are stored encrypted in Kestra's namespace KV Store and injected as environment variables at runtime.

- **Snowflake Snowpipe (`om_des9_amplitude_snowpipe`):**
  - **Auto-Ingest Pipe:** Created with `auto_ingest = true` to continuously load new JSON files from the external stage into the `raw` table.
  - **AWS S3 Event Notifications:** Configured S3 bucket notifications (`s3:ObjectCreated:*` filtered to `.json` files) to publish directly to Snowflake's SQS notification channel, triggering ingestion within seconds while deduplicating previously loaded filenames.
