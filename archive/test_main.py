import os
import sys
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

#importing your my functions
from modules.setup_logging import setup_logging
from modules.s3_check import s3_check
from modules.extract_function import extract_function
from modules.load_function import load_to_s3

#load env
load_dotenv()

#amplitude credentials
AMP_API_KEY = os.getenv('AMP_API_KEY')
AMP_SECRET_KEY = os.getenv('AMP_SECRET_KEY')
AMP_DATA_REGION = os.getenv('AMP_DATA_REGION')

#AWS credentials
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')

# --- HARDCODED TEST PARAMETERS ---
# Pulls exactly 1 hour of data (12:00 PM to 12:59 PM)
start_param = '20261117T12'
end_param = '20261117T12'
data_date = 'test_2026-11-17_H12'

extraction_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
file_label = f"data_{data_date}_extracted_{extraction_time}"

#setup log using function
log_filename = f"{file_label}.log"
logger = setup_logging(log_filename)

logger.info("Starting Amplitude ETL Pipeline (TEST MODE)...")

#where jsons are saved locally
json_dir = 'raw_json'

# --- BYPASSING S3 CHECK FOR TESTING ---
logger.info("Test mode: Skipping S3 check to force extraction.")
# data_exists = s3_check(...)
# if data_exists:
#     sys.exit(0)

#extract data from amplitude if it doesn't already exist using extract function
logger.info("Starting data extraction...")
extract_result = extract_function(
    AMP_API_KEY=AMP_API_KEY,
    AMP_SECRET_KEY=AMP_SECRET_KEY,
    AMP_DATA_REGION=AMP_DATA_REGION,
    start_param=start_param,
    end_param=end_param,
    json_dir=json_dir,
    file_label=file_label
)

#load function to load extracted data into s3
if extract_result:
    logger.info("Extraction successful, proceeding to load...")
    
    load_result = load_to_s3(
        AWS_ACCESS_KEY=AWS_ACCESS_KEY,
        AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY,
        AWS_BUCKET_NAME=AWS_BUCKET_NAME,
        data_dir=json_dir
    )
    
    if load_result:
        logger.info("Test pipeline completed successfully!")
    else:
        logger.error("Test pipeline failed during the Load stage.")
        
else:
    logger.error("Test pipeline failed during the Extract stage. Load aborted.")