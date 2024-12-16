import logging                  # for logging purposes import zipfile                  
import zipfile                  # for zipping/unzipping files
import os                       # for os related stuff, like walking through direcory structures
import requests                 # for downloading files over HTTP
import shutil                   # for removing non-empty directories


class DownloadGeoData:
    
    def __init__(self, filename="BeSt_Addresses_BE.zip", log_file="conversion.log", output_dir="output/", force=False):
        """
        Initialize the class with default filename and logger setup.
        """
        self.url = "https://opendata.bosa.be/download/best/best-full-latest.zip"
        self.filename = filename
        self.log_file = log_file
        self.output_dir = output_dir
        self.force = force
        
    def download_xml_geodata(self):
        """
        Download the XML Geodata from BOSA site.
        """
        self.logger.info(f"Starting download from {self.url}")
        try:
            response = requests.get(self.url, allow_redirects=True)
            response.raise_for_status()  # Raise exception for HTTP errors
        except requests.exceptions.RequestException as e:
            self.logger.fatal(f"Failed to download file: {e}")
            exit(1)

        try:
            with open(self.filename, 'wb') as file:
                file.write(response.content)
            self.logger.info(f"File downloaded successfully: {self.filename}")
        except IOError as e:
            self.logger.fatal(f"Error writing to file {self.filename}: {e}")
            exit(1)
    
    def unzip_recursive(self, zipped_file, to_folder, set_remove=True):
        """
        Recursively unzips files within a folder and extracts them to a target directory.
        """
        self.logger.debug(f"Unzipping {zipped_file} to {to_folder}")
        
        print(f'File before just getting zipped == {zipped_file}')
        
        with zipfile.ZipFile(zipped_file, 'r') as zfile:
            try:
                zfile.extractall(path=to_folder)
            except (zipfile.BadZipFile, IOError) as ziperror:
                self.logger.fatal("Tried unzipping {} but got stuck: {}".format(zipped_file, ziperror))
                exit(0)

        if set_remove:
            try:
                os.remove(zipped_file)
                self.logger.debug(f"Removed original zip file: {zipped_file}")
            except OSError as e:
                self.logger.warning(f"Failed to remove {zipped_file}: {e}")

        # Recursively process subdirectories for additional zip files
        for dir_name, _, file_list in os.walk(to_folder):
            for f in file_list:
                _base, file_extension = os.path.splitext(f)
                # Process only valid zip files
                nested_zip_path = os.path.join(dir_name, f)
                if file_extension.endswith('.zip') and zipfile.is_zipfile(nested_zip_path):
                    nested_zip_path = os.path.join(dir_name, f)
                    self.logger.debug(f"Found nested zip file: {nested_zip_path}")
                    print(f'File found for zip: {f}')
                    self.unzip_recursive(nested_zip_path, os.path.dirname(nested_zip_path))
                    
    
    def get_best_logger(self, log_file):
        """
        Setup and return a logger for the class.
        """
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        # File handler for logging to a file
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)

        # Console handler for logging to console
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)

        # Log message format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        # Add handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        return logger
    
    def build(self):
        """
        Start downloading all Geo Data for the PDOK database. 
        """        
        # Make the logger
        self.logger = self.get_best_logger(self.log_file)
        # Download the file
        self.logger.info("Start download")
        self.download_xml_geodata()
        self.logger.info("Download done")
        
        self.logger.info("Start extraction")
        # Check if the folder is empty
        if os.path.exists(self.output_dir) and os.path.isdir(self.output_dir) and os.listdir(self.output_dir):  # Returning a list that gives True
            # when --force is used, delete the folder an its contents
            if not shutil.rmtree.avoids_symlink_attacks:
                self.logger.warning("Your system is apparently susceptible to symlink attacks." +
                            "Consider not using the --force option, or upgrading your system.")
            self.logger.warning("Removing output directory and all files within")
            try:
                shutil.rmtree(self.output_dir)
            except IOError as ioe:
                self.logger.fatal("Could not delete output directory {}".format(ioe))
                exit(0)
            self.logger.info("Done")
            
        self.unzip_recursive(self.filename,self.output_dir,False)
        self.logger.info("Done")