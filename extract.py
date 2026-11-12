import os
import json
from datetime import datetime
import time
import logging
import zipfile
import gzip
import shutil
import tempfile
import requests
import dotenv

dotenv.load_dotenv()

#Making the timestamp to use later for file name, changing it to a string
timestamp = datetime.now().strftime('%Y-%m-%d %H-%M-%S')

#setting up logs directory
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
log_filename = f'{log_dir}/{timestamp}.log'

#configuring logs
logging.basicConfig(
    filename = log_filename,
    format ='%(asctime)s - %(levelname)s - %(message)s',
    level = logging.INFO
)

#putting config info into logger and printing success
logger = logging.getLogger()
logger.info('Logger successfully initialised.')

data_dir = 'raw_zips'
os.makedirs(data_dir,exist_ok=True)
filename = f'{data_dir}/{timestamp}.zip'

api_key=os.getenv('AMP_API_KEY')
secret_key=os.getenv('AMP_SECRET_KEY')

#Parameter set to extract 1 full day of data
url='https://analytics.eu.amplitude.com/api/2/export'
params = {
    'start': '20261012T00',
    'end': '20261012T23'
}

#Setting up variables for attempts while loop
attempts = 1
max_attempts = 3
sleep_time = 30

while attempts <= max_attempts:
        response = requests.get(url, params=params, auth=(api_key, secret_key))
        status_code = response.status_code

        if status_code == 200:
            print(f"Code 200: successful. Attempt {attempts} worked.")
            logger.info(f"Code 200: successful. Attempt {attempts} worked.")
            
            data = response.content
            with open(filename, 'wb') as file:
                file.write(data)
            print(f'File {filename} saved successfully :)')
            logger.info(f'File {filename} saved successfully')

            #temp file made so i can see the unzipping is working instead of temp directory for now
            temp_dir = 'temptemp'
            os.makedirs(temp_dir, exist_ok=True)

            #unzip the downloaded file into temptemp
            with zipfile.ZipFile(filename, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            #getting the randomly named folder inside temptemp
            contents = os.listdir(temp_dir)
            print(f"Unzipped contents: {contents} inside temp file")
            logger.info(f"Unzipped contents: {contents}")

            break

        elif status_code == 429 or status_code >= 500:
                    if attempts == max_attempts:
                        print(f"Max attempts reached. Status {status_code}. Investigate further.")
                        logger.warning(f"Max attempts reached. Status {status_code}. Investigate further.")
                        break
                        
                    print(f"Attempt {attempts} failed (Status {status_code}). Retrying in {sleep_time} seconds")
                    logger.error(f"Attempt {attempts} failed (Status {status_code}). Retrying in {sleep_time} seconds")
                    time.sleep(sleep_time)
                    
                    attempts += 1
                    sleep_time *= 2

        elif status_code == 404:
            print("Status 404: No data exists for this time range. Select a different time range")
            logger.warning("Status 404: No data exists for this time range. Select a different time range")
            break
            
        else:
            print(f"Error {status_code}: {response.text}")
            logger.error(f"Error {status_code}: {response.text}")
            break