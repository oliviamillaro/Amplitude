import logging
import boto3

logger = logging.getLogger(__name__)

def s3_check(AWS_ACCESS_KEY: str, AWS_SECRET_ACCESS_KEY: str, AWS_BUCKET_NAME: str, data_date: str) -> bool:
    """Checks the AWS S3 bucket to see if data for the target date has already been extracted.

    Args:
        AWS_ACCESS_KEY (str): AWS Access Key ID (get value from your .env in main)
        AWS_SECRET_ACCESS_KEY (str): AWS Secret Access Key (get value from your .env in main)
        AWS_BUCKET_NAME (str): AWS S3 Bucket name (get value from your .env in main)
        data_date (str): The formatted date string (YYYY-MM-DD) to look for in the S3 filenames

    Returns:
        bool: True if the data already exists in S3, False if it is missing or if the check fails
    """
    logger.info("Checking S3 for existing data...")
    
    try:
        #setting up s3 client using AWS credentials
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

        #list of objects currently sitting in the bucket
        s3_response = s3_client.list_objects_v2(Bucket=AWS_BUCKET_NAME)
        
        if 'Contents' in s3_response:
            #loops through every file currently in the bucket
            for obj in s3_response['Contents']:
                #for each file checks whether the data_date is in the filename
                if data_date in obj['Key']:
                    logger.info(f"Data for {data_date} is already in S3. Skipping data extraction.")
                    return True 
                    
        #returns False if it checks all files and finds no match
        return False
        
    #if AWS credentials don't work or S3 is down, log the error but still try to get the data        
    except Exception as e:
        logger.warning(f"Failed to check S3: {e}. Proceeding with API extraction anyway.")
        return False