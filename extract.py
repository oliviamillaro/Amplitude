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

data_dir = 'raw_data'
os.makedirs(data_dir,exist_ok=True)
filename = f'{data_dir}/{timestamp}.zip'

api_key=os.getenv('AMP_API_KEY')
secret_key=os.getenv('AMP_SECRET_KEY')

url='https://analytics.eu.amplitude.com/api/2/export'
params = {
    'start': '20261012T13',
    'end': '20261012T14'
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
            break

        elif status_code == 429 or status_code >= 500:
                    if attempts == max_attempts:
                        print(f"Max attempts reached. Status {status_code}. Investigate further.")
                        break
                        
                    print(f"Attempt {attempts} failed (Status {status_code}). Retrying in {sleep_time} seconds")
                    time.sleep(sleep_time)
                    
                    attempts += 1
                    sleep_time *= 2

        elif status_code == 404:
            print("Status 404: No data exists for this time range. Select a different time range")
            break
            
        else:
            print(f"Error {status_code}: {response.text}")
            break


"""while attempts <= max_attempts:
    response = requests.get(url, params=params, auth=(api_key, secret_key))
    status_code = response.status_code

    if response.status_code == 200:
        data = response.content
        with open(filename, 'wb') as file:
            file.write(data)
        print(f'File {filename} saved successfully :)')

# Creating a temporary directory
#temp_dir = tempfile.mkdtemp()

temp_dir = 'temptemp'
os.makedirs(temp_dir,exist_ok=True)

# opening the zip file, 'r' = read mode, extracting what is in it to a temp directory
with zipfile.ZipFile(filename, 'r') as zip_ref:
    zip_ref.extractall(temp_dir)

#this gets the random filename that is saved within the zip which then contains .json.gz
contents = os.listdir(temp_dir)
print(contents)"""