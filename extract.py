import os
import json
from datetime import datetime, timedelta
import time
import logging
import zipfile
import gzip
import shutil
import tempfile
import requests
import dotenv

dotenv.load_dotenv()

# 1. Calculate yesterday's date for the API parameters
yesterday = datetime.now() - timedelta(days=1)
start_param = yesterday.strftime('%Y%m%dT00')
end_param = yesterday.strftime('%Y%m%dT23')

# 2. Create strings for BOTH what the data represents AND when it was extracted
data_date = yesterday.strftime('%Y-%m-%d')
extraction_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

# 3. Combine them into one super-descriptive label!
file_label = f"data_{data_date}_extracted_{extraction_time}"

# 4. Set up logs directory using the new label
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
log_filename = f'{log_dir}/{file_label}.log'

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
filename = f'{data_dir}/{file_label}.zip'

api_key=os.getenv('AMP_API_KEY')
secret_key=os.getenv('AMP_SECRET_KEY')

#Parameter set to extract 1 full day of data, yesterday
url='https://analytics.eu.amplitude.com/api/2/export'
params = {
    'start': start_param,
    'end': end_param
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

            #temp directory creation
            temp_dir = tempfile.mkdtemp()
            print(f"Unzipped outer box into {temp_dir}")
            logger.info(f"Unzipped outer box into {temp_dir}")

            # Create local output directory for the final JSONs
            json_dir = "raw_json"
            os.makedirs(json_dir, exist_ok=True)

            #unzip the downloaded file into temptemp
            with zipfile.ZipFile(filename, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

           # Locate Target Folder safely (ignoring hidden files)
            day_folder = next(f for f in os.listdir(temp_dir) if f.isdigit())
            day_path = os.path.join(temp_dir, day_folder)

            # Directory Walking and Second Level Extraction
            for root, _, files in os.walk(day_path):
                for current_file in files:
                    if current_file.endswith('.gz'):
                    
                        # Build the file paths
                        gz_path = os.path.join(root, current_file)
                        json_filename = current_file[:-3]  # Slices off the last 3 characters (".gz")
                        output_path = os.path.join(json_dir, json_filename)
                        
                        # Unpack the .gz to .json
                        with gzip.open(gz_path, 'rb') as gz_file, open(output_path, 'wb') as out_file:
                            shutil.copyfileobj(gz_file, out_file)
                            
                        print(f"Extracted JSON: {json_filename}")
                        logger.info(f"Extracted JSON: {json_filename}")

            # Cleanup: Delete the true temporary directory and its contents
            shutil.rmtree(temp_dir) 
            print("Temporary workspace cleaned up.")
            logger.info("Temporary workspace cleaned up.")

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