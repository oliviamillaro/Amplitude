import os
import time
import logging
import zipfile
import gzip
import shutil
import tempfile
import requests

logger = logging.getLogger(__name__)

def extract_function(AMP_API_KEY: str, AMP_SECRET_KEY: str, AMP_DATA_REGION: str, start_param: str, end_param: str, json_dir: str, file_label: str, max_attempts: int = 3, sleep_time: int = 30) -> bool:
    """Extracts compressed event data from Amplitude API, unzips it, and converts it to JSON.

    Args:
        AMP_API_KEY (str): Amplitude API key (get value from your .env in main)
        AMP_SECRET_KEY (str): Amplitude Secret key (get value from your .env in main)
        AMP_DATA_REGION (str): Amplitude Data Region (get value from your .env in main)
        start_param (str): Formatted start time string (e.g., '20261117T00')
        end_param (str): Formatted end time string (e.g., '20261117T23')
        json_dir (str): Directory to output the final extracted JSON files
        file_label (str): Dynamically generated label for naming the files
        max_attempts (int, optional): Number of times to retry on failure. Defaults to 3.
        sleep_time (int, optional): Seconds to wait between retries. Defaults to 30.

    Returns:
        bool: True if extraction and unzipping is fully successful, False otherwise.
    """
    
    url = 'https://analytics.eu.amplitude.com/api/2/export'
    params = {
        'start': start_param,
        'end': end_param
    }
    
    #ensure json directory for raw json files exists
    os.makedirs(json_dir, exist_ok=True)
    
    #attempt variable set to 1 as base
    attempts = 1

    while attempts <= max_attempts:
        response = requests.get(url, params=params, auth=(AMP_API_KEY, AMP_SECRET_KEY))
        status_code = response.status_code

        # success block
        if status_code == 200:
            logger.info(f"Code 200: successful. Attempt {attempts} worked.")

            #temp workspace for zips and unzipping
            with tempfile.TemporaryDirectory() as temp_dir:
                filename = os.path.join(temp_dir, f'{file_label}.zip')
                
                #saves downloaded zips into temp directory
                with open(filename, 'wb') as file:
                    file.write(response.content)
                logger.info(f'Temporary zip saved to {filename}')

                #unzips files inside temp directory
                with zipfile.ZipFile(filename, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                logger.info("Unzipped outer box successfully.")

                try:
                    #locate amplitude's randomly numbered inner folder
                    day_folder = next(f for f in os.listdir(temp_dir) if f.isdigit())
                    day_path = os.path.join(temp_dir, day_folder)

                    #loop through the folder, find .gz files and convert to .json
                    for root, _, files in os.walk(day_path):
                        for current_file in files:
                            if current_file.endswith('.gz'):
                                
                                # build the file paths for reading/writing
                                gz_path = os.path.join(root, current_file)
                                json_filename = current_file[:-3]
                                output_path = os.path.join(json_dir, json_filename)

                                # unpack the binary .gz to standard .json
                                with gzip.open(gz_path, 'rb') as gz_file, open(output_path, 'wb') as out_file:
                                    shutil.copyfileobj(gz_file, out_file)
                                    
                                logger.info(f"Extracted JSON: {json_filename}")
                                
                    logger.info("Temporary workspace and raw zip cleaned up.")
                    return True
                    
                except StopIteration:
                    logger.error("No numerical data folder found inside the Amplitude zip file.")
                    return False

        # rate limits or server issues with doubling backoff
        elif status_code == 429 or status_code >= 500:
            if attempts == max_attempts:
                logger.warning(f"Max attempts reached. Status {status_code}. Investigate further.")
                break
                
            logger.error(f"Attempt {attempts} failed (Status {status_code}). Retrying in {sleep_time} seconds")
            time.sleep(sleep_time)
            
            attempts += 1
            sleep_time *= 2

        # no data
        elif status_code == 404:
            logger.warning("Status 404: No data exists for this time range.")
            break
            
        # other errors that require specific examination
        else:
            logger.error(f"Error {status_code}: {response.text}")
            break

    return False