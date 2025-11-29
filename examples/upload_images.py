import logging
from igitur import GaudeamDriveFolder, GaudeamSession, GaudeamResizedImageUploader
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

session = GaudeamSession.with_user_auth("your@email.de", "yourpassword")

# Get the folder you want to upload to
gaudeam_folder = GaudeamDriveFolder(session, 35234)

# Create the uploader instance
uploader = GaudeamResizedImageUploader()

# Add file names to skip, if this is pressent in a file name it will be skipped. 
uploader.add_skip_file_name("komprimiert")

# upload all images from a folder, resizing them before upload
uploader.upload_folder_resized("/your/source/path/of/images", gaudeam_folder)
