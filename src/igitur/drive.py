from __future__ import annotations
import logging
import typing
import json
import xml.etree.ElementTree as ET
import tempfile
from PIL import Image
from pathlib import Path

import requests

from .core import IgiturError
from .session import GaudeamSession


class GaudeamDriveFolder:

    DIRECTORY_LIST_LIMIT = 80

    def __init__(self, session: GaudeamSession, folder_id: str, properties = None):
        self._session = session
        self._folder_id = folder_id
        if properties is None:
            self._properties = self._get_properties()
        else:
            self._properties = properties

    def _get_properties(self) -> dict:
        url = f"{self._session.url()}/api/v1/drive/folders/{self._folder_id}"
        response = self._session.client().get(url)
        if response.status_code == 200:
            return response.json()
        else:
            raise IgiturError(f"Error fetching drive folder properties for folder '{self._folder_id}': {response.status_code}, {response.text}")

    def _properties_force_refresh(self) -> None:
        self._properties = self._get_properties()

    def get_name(self) -> str:
        """Gets the name of the folder

        Returns:
            str: Name of the folder
        """
        return self._properties.get("name", None)

    def create_sub_folder(self, name: str, description: str = "") -> GaudeamDriveFolder:
        """Creates a new folder with the same rights as the parent. 

        Args:
            name (str): Name of the new folder
            description (str, optional): Optional description of the folder. Defaults to "".

        Returns:
            GaudeamDriveFolder: The newly created folder
        """
        logging.debug(json.dumps(self._properties, indent=4))
        owner_type = self._properties["owner_type"]
        owner_id_from_parent = self._properties["owner_id"]
        logging.debug(f"Creating sub-folder '{name}' in folder '{self.get_name()}' owned by '{owner_type}' with owner ID '{owner_id_from_parent}'")
        data = {
            "inode": {
                "description": description,
                "name": name,
                "ordering": [
                    "<name"
                ],
                "owner_id": owner_id_from_parent, 
                #"owner_type": "Group",
                "parent_id": self._folder_id, # folder_id from parent folder
                #"restrict_to_id": restrict_to_id_from_parent, # restrict to access group id
                "type": "Folder"
            }
        }
        # parent owner is a group, we copy the settings
        
        if owner_type == "Group":
            restrict_to_id_from_parent = self._properties["restrict_to"]["id"]
            data["inode"]["owner_type"] = "Group"
            data["inode"]["restrict_to_id"] = restrict_to_id_from_parent
        # parent owner is a Member, we copy member settings
        elif owner_type == "GroupMember":
            data["inode"]["owner_type"] = "GroupMember"
            data["inode"]["restrict_to_id"] = None
        elif owner_type is None:
            data["inode"]["owner_type"] = None
            data["inode"]["restrict_to_id"] = None
        else:
            raise IgiturError("cannot create file as parent is not owned by GroupMember or Group")

        url = f"{self._session.url()}/api/v1/drive/folders"
        response = self._session.client().post(url, json=data)
        if response.status_code == 200:
            self._properties_force_refresh()
            new_folder_id = response.json()["id"]
            logging.debug(f"Created sub-folder '{name}' with ID: {new_folder_id}")
            return GaudeamDriveFolder(self._session, new_folder_id)
        else:
            raise IgiturError(f"Error creating sub-folder: {response.status_code}, {response.text}")

    def get_sub_folders(self) -> typing.List[GaudeamDriveFolder]:
        """Returns a lift of sub folders in the current folder. 

        Returns:
            typing.List[GaudeamDriveFolder]: List of sub folders
        """
        offset = 0
        results = []

        while True:
            url = f"{self._session.url()}/api/v1/drive/folders?parent_id={self._folder_id}&order=%3Ename&offset={offset}&limit={self.DIRECTORY_LIST_LIMIT}"
            response = self._session.client().get(url)

            if response.status_code != 200:
                raise IgiturError(f"Error fetching folder contents: {response.status_code}, {response.text}")

            batch = response.json().get("results", [])
            if not batch or len(batch) == 0:
                break  # no more results

            for entry in batch:
                entry_type = entry.get("type")
                if entry_type in ["Folder", "Gallery"]:
                    folder = GaudeamDriveFolder(self._session, entry["id"], entry)
                    results.append(folder)

            # move to next page
            offset += self.DIRECTORY_LIST_LIMIT
            if len(batch) < self.DIRECTORY_LIST_LIMIT:
                break
        return results

    def get_files(self) -> typing.List[GaudeamDriveFile]:
        """Gets a list of files in the folder

        Returns:
            typing.List[GaudeamDriveFile]: List of files
        """
        offset = 0
        results = []

        while True:
            url = f"{self._session.url()}/api/v1/drive/folders?parent_id={self._folder_id}&order=%3Ename&offset={offset}&limit={self.DIRECTORY_LIST_LIMIT}"
            response = self._session.client().get(url)

            if response.status_code != 200:
                raise IgiturError(f"Error fetching files from folder: {response.status_code}, {response.text}")

            batch = response.json().get("results", [])
            if not batch:
                break  # no more results

            for entry in batch:
                entry_type = entry.get("type")
                if entry_type in ["Photo", "DriveFile"]:
                    file_entry = GaudeamDriveFile(self._session, entry["id"], entry)
                    results.append(file_entry)
            if len(batch) < self.DIRECTORY_LIST_LIMIT:
                break
            # move to next batch
            offset += self.DIRECTORY_LIST_LIMIT

        return results

    def delete(self) -> bool:
        """Deletes the folder including all files. 

        Returns:
            bool: True if deletion was successful
        """
        url = f"{self._session.url()}/api/v1/drive/folders/{self._folder_id}"
        response = self._session.client().delete(url)
        if response.status_code == 200:
            return True
        else:
            raise IgiturError(f"Error deleting folder: {response.status_code}, {response.text}")

    def delete_content(self) -> bool:
        """Deletes the content of a folder

        Returns:
            bool: True if all files and folders could be deleted
        """
        success = True
        for folder in self.get_sub_folders():
            folder_name = folder.get_name()
            logging.info(f"Deleting folder: {folder_name}")
            if not folder.delete():
                logging.warning(f"Could not delete folder '{folder_name}'")
                success = False
        for file in self.get_files():
            file_name = file.get_name()
            logging.info(f"Deleting folder: {file_name}")
            if not file.delete():
                logging.warning(f"Could not delete file '{file_name}'")
                success = False
        return success

    def _mime_type_from_filename(self, filename: str) -> str:
        extension = filename.split(".")[-1].lower()
        mime_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "bmp": "image/bmp",
            "tiff": "image/tiff",
            "mp4": "video/mp4",
            "mov": "video/quicktime",
            "avi": "video/x-msvideo",
            "mkv": "video/x-matroska",
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "ppt": "application/vnd.ms-powerpoint",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            # add more as needed
        }
        # default to binary stream
        return mime_types.get(extension, "application/octet-stream")

    def get_size(self) -> int:
        """Returns the file size of the folder including all sub folders. 

        Returns:
            int: The file size of the folder.
        """
        size = 0
        for sub_folder in self.get_sub_folders():
            size += sub_folder.get_size()
        for file in self.get_files():
            size += file.get_size()
        return size

    def upload_folder(self, local_folder_path: Path|str) -> bool:
        """Uploads a local folder to the Gaudeam folder. 
        It skips all files that already exist with the same 'download name'. 

        Args:
            local_folder_path (Path | str): Local path of the folder to upload

        Returns:
            bool: True if upload was successful
        """
        local_folder_path = Path(local_folder_path)
        if not local_folder_path.is_dir():
            logging.error(f"Local path is not a directory: {local_folder_path}")
            return False
        for entry in local_folder_path.iterdir():
            if entry.is_file():
                for file_in_folder in self.get_files():
                    if file_in_folder.get_download_name() == entry.name:
                        logging.info(f"File already exists in remote folder, skipping upload: {entry}")
                        break
                else:
                    logging.info(f"Uploading file: {entry} to folder: {self.get_name()}")
                    success = self.upload_file(entry)
                    if not success:
                        logging.error(f"Failed to upload file: {entry}")
                        return False
            elif entry.is_dir():
                # check if folder already exists
                # if exists -> use existing and continue upload into it
                # if not -> create folder and continue upload into it
                for sub_folder in self.get_sub_folders():
                    if sub_folder.get_name() == entry.name:
                        logging.info(f"Sub-folder already exists in remote folder, using existing folder: {entry.name}")
                        new_remote_folder = sub_folder
                        break
                else:
                    logging.info(f"Creating sub-folder: {entry.name} in folder: {self.get_name()}")
                    new_remote_folder = self.create_sub_folder(entry.name)
                    if new_remote_folder is None:
                        logging.error(f"Failed to create sub-folder: {entry.name}")
                        return False
                success = new_remote_folder.upload_folder(entry)
                if not success:
                    logging.error(f"Failed to upload folder: {entry}")
                    return False
        return True

    def upload_file(self, file_path: Path|str) -> bool:
        """Uploads a specific file to this folder. 

        Args:
            file_path (Path | str): The local file path to the file to upload

        Returns:
            bool: True if the upload was successful
        """
        file_path = Path(file_path)
        # get upload signature
        url = f"{self._session.url()}/api/v1/drive/sign"
        response = self._session.client().post(url)
        if response.status_code != 200:
            logging.error(f"Error getting upload signature: {response.status_code}, {response.text}")
            return False
        sign_data = response.json()
        logging.debug(f"Upload sign data: {json.dumps(sign_data, indent=2)}")

        # upload file
        post_endpoint = sign_data["postEndpoint"]
        signature = sign_data["signature"]

        files = {'file': open(file_path, 'rb')}

        upload_response = requests.post(post_endpoint, data=signature, files=files)
        if upload_response.status_code != 201: # created
            logging.error(f"Error uploading file: {upload_response.status_code}, {upload_response.text}")
            return False
        #logging.debug(f"File uploaded response: {upload_response.status_code}, {upload_response.text}")
        xml_response = upload_response.text

        # register file upload at gaudeam
        xml_response_root = ET.fromstring(xml_response)

        location = xml_response_root.find("Location").text
        bucket = xml_response_root.find("Bucket").text
        key = xml_response_root.find("Key").text
        etag = xml_response_root.find("ETag").text.strip('"')  # remove quotes around ETag

        print("Location:", location)
        print("Bucket:", bucket)
        print("Key:", key)
        print("ETag:", etag)

        upload_url = f"{self._session.url()}/api/v1/drive/uploaded_files"
        path = Path(file_path)
        filename_without_ext = path.stem
        filename_with_ext = path.name

        data = {
            "inode": {
                "content_type": self._mime_type_from_filename(filename_with_ext),
                "name": filename_without_ext, # Gaudeam usually skips the extension in the name
                "parent_id": self._folder_id,
                "physically_created_at": "",
                "stored_file": key,
                # only for images
                #"height": 4080,
                #"width": 3072,
            }
        }
        upload_response = self._session.client().post(upload_url, json=data)
        if upload_response.status_code != 200:
            logging.error(f"Error confirming uploaded file: {upload_response.status_code}, {upload_response.text}")
            return False
        #logging.debug(f"Uploaded file confirmation response: {upload_response.status_code}, {upload_response.text}")
        return True

    def download(self, destination_path: Path|str) -> bool:
        """Downloads the whole folder including sub folders and files to a local folder. 
        It skips files that already exist based on 'download name'. 

        Args:
            destination_path (Path | str): Destination path to download to. 

        Returns:
            bool: True if the download was successful
        """
        destination_folder = Path(destination_path)

        if not destination_folder.exists():
            logging.info(f"Destination does not exist yet, creating '{destination_folder}'")
            destination_folder.mkdir(parents=True)
        
        if not destination_folder.is_dir():
            raise IgiturError(f"Destination path is not a directory: {destination_folder}")

        for sub_folder in self.get_sub_folders():
            folder_name = sub_folder.get_name()
            sub_folder.download(destination_folder / folder_name)

        for file_in_folder in self.get_files():
            file_name = file_in_folder.get_download_name()
            destination_file = destination_folder / file_name
            if destination_file.exists():
                logging.info(f"Skipping '{destination_file}' - already exists")
                continue
            # download file
            logging.info(f"Downloading '{destination_file}'")
            file_in_folder.download(destination_file)
class GaudeamDriveFile:
    """A file on gaudeam drive. 
    """
    def __init__(self, session: GaudeamSession, file_id: str, properties = None):
        self._session = session
        self._file_id = file_id
        if properties is None:
            self._properties = self._get_properties()
        else:
            self._properties = properties

    def _get_properties(self) -> dict:
        url = f"{self._session.url()}/api/v1/drive/folders/{self._file_id}"
        response = self._session.client().get(url)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Error fetching folder properties: {response.status_code}, {response.text}")
            return {}

    def _properties_force_refresh(self) -> None:
        self._properties = self._get_properties()

    def get_name(self) -> str:
        """Returns the human readable name on gaudeam, usually without file extensions

        Returns:
            str: name of the file on gaudeam. 
        """
        return self._properties.get("name", None)

    def get_properties(self) -> dict:
        return self._properties

    def get_download_name(self) -> str:
        """Returns the download name of the file. This is the original file name with the full file extension. 

        Returns:
            str: The download name. 
        """
        return self._properties.get("download_name", None)

    def get_size(self) -> int:
        """Returns the filesize in bytes. 

        Returns:
            int: filesize in bytes
        """
        return self._properties["file_size"]

    def download(self, file_path: str|Path) -> bool:
        """Downloads a file to a local path

        Args:
            file_path (str | Path): The path to save the file to

        Returns:
            bool: True if the download was successful.
        """
        url = f"{self._session.url()}/drive/uploaded_files/{self._file_id}/download"
        response = self._session.client().get(url)

        # TODO: error handling

        # Save as binary file
        with open(file_path, "wb") as f:
            f.write(response.content)
        return True

    def delete(self) -> bool:
        """Deletes a file from the drive

        Returns:
            bool: True if the deletion was successful
        """
        url = f"{self._session.url()}/api/v1/drive/uploaded_files/{self._file_id}"
        response = self._session.client().delete(url)
        if response.status_code == 200:
            return True
        else:
            logging.error(f"Error deleting file: {response.status_code}, {response.text}")
            return False

class GaudeamDrive:
    def __init__(self, session: GaudeamSession):
        self._session = session

    def get_sub_folders(self) -> list[GaudeamDriveFolder]:
        url = f"{self._session.url()}/api/v1/drive/categories"
        response = self._session.client().get(url)
        if response.status_code == 200:
            return response.json()["results"]
        else:
            logging.error(f"Error fetching folders: {response.status_code}, {response.text}")
            return []

    def delete_folder(self, folder_id: str) -> bool:
        url = f"{self._session.url()}/api/v1/drive/folders/{folder_id}"
        response = self._session.client().delete(url)
        if response.status_code == 200:
            return True
        else:
            logging.error(f"Error deleting folder: {response.status_code}, {response.text}")
            return False

class GaudeamResizedImageUploader():
    def __init__(self, max_width: int = 2000, max_height: int = 2000, jpeg_quality = 90):
        self._max_width = max_width
        self._max_height = max_height
        self._jpeg_quality = jpeg_quality
        self._skip_file_names = []
        self._allowed_extensions = [".jpg", ".jpeg", ".png"]

    def add_skip_file_name(self, skip_file_name: str):
        self._skip_file_names.append(skip_file_name)

    def save_as_jpeg_resized(self, input_path, output_path):
        img = Image.open(input_path)

        # Keep aspect ratio
        img.thumbnail((self._max_width, self._max_height), Image.Resampling.LANCZOS)

        # Ensure no alpha channel (JPEG doesn’t support transparency)
        if img.mode in ("RGBA", "LA"):
            img = img.convert("RGB")

        img.save(output_path, format="JPEG", quality=self._jpeg_quality)

    def _in_allowed_extensions(self, file_path: Path) -> bool:
        source_extension = file_path.suffix.lower()
        ## skip files based on extension
        return source_extension in self._allowed_extensions

    def _in_skip_files(self, file_path: Path) -> bool:
        file_name = str(file_path.name)
        for skip_file_name in self._skip_file_names:
            if str(skip_file_name).lower() in file_name.lower():
                # skip files that contain the substring which is in skipfile in the file name
                return True
        return False

    def _file_name_exists(self, file_name: str,  gaudeam_files_in_folder: typing.List[GaudeamDriveFile]):
        for file_in_folder in gaudeam_files_in_folder:
            if file_in_folder.get_download_name() == file_name:
                return True
        return False

    def delete_duplicates(self, gaudeam_folder: GaudeamDriveFolder, dry_run = False):
        sub_folders = gaudeam_folder.get_sub_folders()
        sub_folders = sorted(sub_folders, key=lambda f: f.get_name())

        # clean duplicate folders
        if len(sub_folders) > 0:
            first_folder = sub_folders.pop(0)
            while len(sub_folders) > 0:
                next_folder = sub_folders.pop(0)
                if first_folder.get_name() == next_folder.get_name():
                    # duplicate, eliminate
                    if not dry_run:
                        logging.warning(f"Duplicate folder '{next_folder.get_name()} - deleting'")
                        next_folder.delete()
                    else:
                        logging.info(f"[DRY RUN] Duplicate folder '{next_folder.get_name()}'")
                else: 
                    # they are different, so we eliminated all duplicates
                    first_folder = next_folder

        sub_files = gaudeam_folder.get_files()
        sub_files = sorted(sub_files, key=lambda f: f.get_name())

        # clean duplicate files
        if len(sub_files) > 0:
            first_file = sub_files.pop(0)
            while len(sub_files) > 0:
                next_file = sub_files.pop(0)
                if first_file.get_name() == next_file.get_name():
                    # duplicate, eliminate
                    if not dry_run:
                        logging.warning(f"Duplicate file '{next_file.get_name()} - deleting'")
                        next_file.delete()
                    else:
                        logging.info(f"[DRY RUN] Duplicate file '{next_file.get_name()}'")
                else: 
                    # they are different, so we elimnated all duplicates
                    first_file = next_file
        
        # now reread and run on the leftover
        sub_folders = gaudeam_folder.get_sub_folders()
        for sub_folder in sub_folders:
            self.delete_duplicates(sub_folder, dry_run)

    def delete_empty_sub_folders(self, gaudeam_folder: GaudeamDriveFolder, dry_run = False):
        sub_folders = gaudeam_folder.get_sub_folders()
        if len(sub_folders) > 0:
            # if we have folders we have to go in deep first
            for sub_folder in sub_folders:
                self.delete_empty_sub_folders(sub_folder, dry_run)
            # refresh the folders, we might have deleted some
            sub_folders = gaudeam_folder.get_sub_folders()
        files = gaudeam_folder.get_files()
        if len(sub_folders) + len(files) == 0:
            # empty
            if not dry_run:
                logging.warning(f"Empty folder: {gaudeam_folder.get_name()} - deleting")
                gaudeam_folder.delete()
            else:
                logging.info(f"[DRY RUN] Empty folder: {gaudeam_folder.get_name()}")
            return

    def delete_remote_orphan_files(self, local_folder_path: Path|str, gaudeam_folder: GaudeamDriveFolder, dry_run = False):
        local_folder_path = Path(local_folder_path)
        local_sub_folders = [
                            item.name
                            for item in local_folder_path.iterdir()
                            if item.is_dir()
                        ]
        local_target_file_names = [
                            self._get_target_name_from_file_path(item)
                            for item in local_folder_path.iterdir()
                            if item.is_file() \
                                and self._in_allowed_extensions(item) \
                                and not self._in_skip_files(item)
                        ]
        for gaudeam_sub_folder in gaudeam_folder.get_sub_folders():
            gaudeam_sub_folder_name = gaudeam_sub_folder.get_name()
            if gaudeam_sub_folder_name not in local_sub_folders:
                # folder does not exist locally -> delete
                if not dry_run:
                    logging.warning(f"Deleting gaudeam folder '{gaudeam_sub_folder_name}' because it's not in {local_folder_path}")
                    gaudeam_sub_folder.delete()
                else:
                    logging.info(f"[DRY_RUN] Deleting gaudeam folder '{gaudeam_sub_folder_name}' because it's not in {local_folder_path}")
            else:
                # folder exists locally -> check it's sub contents
                sub_folder_path = local_folder_path / gaudeam_sub_folder_name
                self.delete_remote_orphan_files(sub_folder_path, gaudeam_sub_folder)

        for gaudeam_sub_file in gaudeam_folder.get_files():
            gaudeam_sub_file_name = gaudeam_sub_file.get_download_name()
            if gaudeam_sub_file_name not in local_target_file_names:
                if not dry_run:
                    logging.warning(f"Deleting gaudeam file '{gaudeam_sub_file_name}' because it's not derived from a file in {local_folder_path}")
                    gaudeam_sub_file.delete()
                else:
                    logging.info(f"[DRY_RUN] Deleting gaudeam file '{gaudeam_sub_file_name}' because it's not derived from a file in {local_folder_path}")

    def _get_target_name_from_file_path(self, local_file_path: Path):
        local_file_path = Path(local_file_path)
        target_extension = ".jpg"
        target_name = local_file_path.stem + target_extension
        return target_name

    def upload_folder_resized(self, local_folder_path: Path|str, gaudeam_folder: GaudeamDriveFolder) -> bool:
        local_folder_path = Path(local_folder_path)
        if not local_folder_path.is_dir():
            logging.error(f"Local path is not a directory: {local_folder_path}")
            return False
        # get the files that already exist in the folder
        gaudeam_files_in_folder = gaudeam_folder.get_files()
        gaudeam_sub_folders_in_folder = gaudeam_folder.get_sub_folders()
        for entry in local_folder_path.iterdir():
            if entry.is_file():
                ## skip files based on extension
                if not self._in_allowed_extensions(entry):
                    # skip files like videos, that we don't want to upload
                    logging.info(f"Skipping: {entry}: File type is not in processing list ({self._allowed_extensions})")
                    continue

                ## skip files based on name blacklist
                if self._in_skip_files(entry):
                    logging.info(f"Skipping: {entry}: File name is skipped because it contains a blacklisted name ({self._skip_file_names}), ")
                    continue

                ## skip files if they already exist remotely
                target_name = self._get_target_name_from_file_path(entry)
                if self._file_name_exists(target_name, gaudeam_files_in_folder):
                    logging.info(f"Skipping: {entry}: File already exists in remote folder as '{target_name}'")
                    continue

                # if not exists, upload shrinked version
                with tempfile.TemporaryDirectory() as tmpdirname:
                    target_path = Path(tmpdirname) / target_name
                    logging.info(f"Resizing file: {entry} as: {target_path}")
                    self.save_as_jpeg_resized(entry, target_path)
                    logging.info(f"Uploading file: {target_path} to folder: {gaudeam_folder.get_name()}")
                    success = gaudeam_folder.upload_file(target_path)
                    if not success:
                        logging.error(f"Failed to upload file: {target_path}")
                        return False
            elif entry.is_dir():
                for sub_folder in gaudeam_sub_folders_in_folder:
                    if sub_folder.get_name() == entry.name:
                        logging.info(f"Sub-folder already exists in remote folder, using existing folder: {entry.name}")
                        new_remote_folder = sub_folder
                        break
                else:
                    logging.info(f"Creating sub-folder: {entry.name} in folder: {gaudeam_folder.get_name()}")
                    new_remote_folder = gaudeam_folder.create_sub_folder(entry.name)
                    if new_remote_folder is None:
                        logging.error(f"Failed to create sub-folder: {entry.name}")
                        return False
                success = self.upload_folder_resized(entry, new_remote_folder)
                if not success:
                    logging.error(f"Failed to upload folder: {entry.path}")
                    return False
        return True
