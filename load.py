import os
import json
import logging
from dotenv import load_dotenv
import boto3

load_dotenv()

AWS_ACCESS_KEY=os.getenv('AWS_ACCESS_KEY')
AWS_SECRET_ACCESS_KEY=os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_BUCKET_NAME=os.getenv('AWS_BUCKET_NAME')

data_dir = 'data'
file_location = os.listdir(data_dir)

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

#first variable of s3_client.upload_file is where the file is locally, second is bucket, third is rename it when it gets to S3
for file in file_location:
    to_upload = f'{data_dir}/{file}'
    s3_client.upload_file(to_upload, AWS_BUCKET_NAME, file)
    os.remove(to_upload)