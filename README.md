# Amplitude ELT Project

## Project Overview

Amplitude is a product analytics platform that tracks user interactions and behavior across digital products. The aim of this project is to capture usage data from the company’s Data School website.

The complete pipeline achieves this by extracting event data from Amplitude via its Extract API, storing it locally for backup, uploading it to an AWS S3 bucket.

---

## Local Setup

**1. Clone the Repository**
I created the repository on GitHub, cloned it locally using **GitHub Desktop**, and opened the project directly into VS Code from the GitHub Desktop interface.

**2. Environment Setup (PowerShell)**
I opened a PowerShell terminal in VS Code to create a virtual environment and installed the required dependencies.

**3. Configuration & Security**
I then created a .env file in the root folder and added the necessary credentials (AMP_API_KEY and AMP_SECRET_KEY).

I ensured the .gitignore file included the raw_json and raw_zips files, as well as .env.

---

## Extract Stage

The extraction script (`amplitude_extract.py`) is responsible for retrieving daily event data from the Amplitude Export API and preparing it for loading.

Instead of hardcoded values, the script is designed for automated daily runs and features error handling. The extraction process is broken down into the following sections:

* **Dynamic Date Configuration:** The script calculates a midnight-to-midnight time range for the previous day, generating file labels that combine the data's date and the extraction timestamp.
* **API Request & Retry Logic:** Connects to the Export API using HTTP Basic Authentication. It features a `while` loop with doubling backoff to handle rate limits (429) and server errors (500+), and exiting if no data exists for the selected time range (404).
* **Data Unpacking & Decompression:** Amplitude returns a compressed ZIP containing nested, dynamically named folders with `.gz` files. The script downloads the ZIP, unpacks it into a temporary directory, loops through the nested folders, and decompresses the binary `.gz` files into `.json` formats.
* **Logging & Cleanup:** Every API attempt, status code, and file extraction is recorded with a timestamp in a local `logs/` directory for full auditability. Upon successful extraction, the script automatically deletes the temporary directories and leftover compressed files.

*(Note: The `amplitude_extract.py` file contains line-by-line comments to help understand exactly how the code works.)*

## Load Stage

The loading phase transfers the extracted local JSON files into a secure AWS S3 bucket, and loads them into Snowflake, ready for the transformation stage. The process consists of three main stages:

- **AWS Infrastructure Setup:** 
  - **Storage & Security:** Created an AWS S3 bucket to store the raw Amplitude data, secured with Server-Side Encryption using an AWS Key Management Service (SSE-KMS) key.
  - **Access Management:** Configured IAM Policies to grant specific Read/Write/List permissions. Created an IAM User with access keys (stored securely in the `.env` file) for the Python script, and an IAM Role to establish a trust relationship with Snowflake.

- **Python S3 Uploader (`amplitude_load.py`):** 
  - **Automated Uploads:** Uses the `boto3` library to securely connect to AWS. The script iterates through the local `raw_json` directory and pushes each file to the S3 bucket.
  - **Safe Cleanup & Logging:** Wrapped in `try/except` blocks, the script only deletes the local JSON files if the S3 upload is successful. Every step is tracked via the `logging` module in case debugging is required.
  - *(Note: The `amplitude_load.py` file contains line-by-line comments to help understand exactly how the code works.)*

- **Snowflake Data Warehouse Integration:**
  - **Storage Integration:** Created a `STORAGE INTEGRATION` to link Snowflake to S3. To secure the connection, the generated Snowflake External ID was passed back into the AWS IAM Role's Trust Policy.
  - **External Stage:** Set up an external `STAGE` acting as a secure portal to the S3 bucket. A custom `FILE_FORMAT` was applied to properly parse the JSON data (e.g., stripping outer arrays).
  - **Data Loading (`COPY INTO`):** Created a `raw` landing table utilising Snowflake's `VARIANT` data type to hold the raw JSON payload. The table also captures metadata, including original file name, file row number, and the S3 last-modified timestamp. The data is then migrated from the stage into the table using the `COPY INTO` command.