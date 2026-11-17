import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
import boto3

#making logs file if it doesn't already exist
os.makedirs('logs', exist_ok=True)

#generate timestamp for the log filename
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

handlers=[
    logging.FileHandler(f"logs/amplitude_pipeline_{timestamp}.log"),  #saves to logs
    logging.StreamHandler()                                           #prints to terminal
]
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=handlers
)

load_dotenv()

AWS_ACCESS_KEY=os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_ACCESS_KEY=os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_BUCKET_NAME=os.getenv('AWS_BUCKET_NAME')

data_dir = 'raw_json'
file_location = os.listdir(data_dir)

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)
logging.info("Successfully connected to S3.")

#first variable of s3_client.upload_file is where the file is locally, second is bucket, third is rename it when it gets to S3
for file in file_location:
    #makes sure to only download jsons, no hidden extra files
    if file.endswith('.json'):
        to_upload = f'{data_dir}/{file}'
        
        #wrapping in try/except for uploading
        try:
            logging.info(f"Attempting to upload {file}...")
            s3_client.upload_file(to_upload, AWS_BUCKET_NAME, file)
            logging.info(f"Successfully uploaded {file}")
            os.remove(to_upload)
            
        except Exception as e:
            logging.error(f"Failed to upload {file}. Error: {e}")