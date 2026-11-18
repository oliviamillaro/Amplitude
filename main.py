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

#dates for API params and naming
yesterday = datetime.now() - timedelta(days=1)
start_param = yesterday.strftime('%Y%m%dT00')
end_param = yesterday.strftime('%Y%m%dT23')
data_date = yesterday.strftime('%Y-%m-%d')

extraction_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
file_label = f"data_{data_date}_extracted_{extraction_time}"

#setup log using function
log_filename = f"main_{file_label}.log"
logger = setup_logging(log_filename)

logger.info("Starting Amplitude ETL Pipeline...")

#where jsons are saved locally
json_dir = 'raw_json'

#check_s3 function to check for existing data
data_exists = s3_check(
    AWS_ACCESS_KEY=AWS_ACCESS_KEY, 
    AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY, 
    AWS_BUCKET_NAME=AWS_BUCKET_NAME, 
    data_date=data_date
)

if data_exists:
    logger.info("Pipeline stopped because specified date's data is already present in S3.")
    sys.exit(0)

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
        logger.info("Pipeline successfully run 🐸👌")
    else:
        logger.error("Pipeline failed during the Load stage.")
        
else:
    logger.error("Pipeline failed during the Extract stage. Load aborted.")