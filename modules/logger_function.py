import os
import logging

def setup_logging(log_filename: str):
    """Configures logging to output to both a single file and the terminal.

    Args:
        log_filename (str): The name of the log file to be created (generate this with a timestamp in main)
    """
    
    #create logs directory if it doesn't already exist
    os.makedirs('logs', exist_ok=True)
    
    #defines where logs are sent - to the log file as well as to terminal
    handlers = [
        logging.FileHandler(f"logs/{log_filename}"),
        logging.StreamHandler()
    ]
    
    #configuring logs
    logging.basicConfig(
        format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=handlers,
        force=True 
    )
    
    #confirmation of log setup
    logger = logging.getLogger(__name__)
    logger.info('Logger successfully initialised. All modules will report here.')
    
    return logging.getLogger()