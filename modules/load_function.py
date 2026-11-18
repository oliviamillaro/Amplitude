import os
import boto3
import logging

#sets up the logger for this specific function
logger = logging.getLogger(__name__)

def load_to_s3(AWS_ACCESS_KEY: str, AWS_SECRET_ACCESS_KEY: str, AWS_BUCKET_NAME: str, data_dir: str) -> bool:
    """Uploads extracted JSON files from a local directory to an AWS S3 bucket.

    Args:
        AWS_ACCESS_KEY (str): Key value (get value from your .env in main)
        AWS_SECRET_ACCESS_KEY (str): Secret value (get value from your .env in main)
        AWS_BUCKET_NAME (str): Bucket name (get value from your .env in main)
        data_dir (str): Filepath where the data was extracted to
        
    Returns:
        bool: True if all JSON files upload successfully, False if any fail.
    """
    
    file_location = os.listdir(data_dir)

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        logger.info("Successfully connected to S3.")

        # first variable of s3_client.upload_file is where the file is locally, second is bucket, third is rename it when it gets to S3
        for file in file_location:
            # makes sure to only download jsons, no hidden extra files
            if file.endswith('.json'):
                to_upload = f'{data_dir}/{file}'
                
                # wrapping in try/except for uploading
                try:
                    logger.info(f"Attempting to upload {file}...")
                    s3_client.upload_file(to_upload, AWS_BUCKET_NAME, file)
                    logger.info(f"Successfully uploaded {file}")
                    os.remove(to_upload)
                    
                except Exception as e:
                    logger.error(f"Failed to upload {file}. Error: {e}")
                    return False # Instantly fail the orchestration step if a file fails to upload
                    
        return True
        
    except Exception as e:
        logger.error(f"Error connecting to S3: {e}")
        return False