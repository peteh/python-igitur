# Igitur an unofficial CLI Tool and Python Library for Gaudeam

## Installation

Create a virtual environment and install the tool into it.

**Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install git+https://github.com/peteh/python-igitur.git
```

**Windows:**

Windows Command Prompt:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install git+https://github.com/peteh/python-igitur.git
```

Windows Powershell:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install git+https://github.com/peteh/python-igitur.git
```

## Usage

### Login

First your have to login into Gaudeam using the `login` command. The app will ask you for your email and your login password for gaudeam. Then it will create an active session and you can run other commands.

```bash
igitur login
```

### Check Login Status

To check if your session status you can use the `status` command.

```bash
igitur status
```

The result will show you what instance you are logged in to and your user account.

```bash
Logged in as x@y.de at https://instance.gaudeam.de
```

### Logout

To log out, just use the `logout` command.

```bash
igitur logout
```

### Download Folders

You can download the full content of a folder directly using the `download` command. To get the actual folder id, open the folder in your browser and check the URL:

`https://instance.gaudeam.de/drive/folders/FOLDERID`

Now you can download using following command:

```bash
igitur download FOLDERID DESTINATIONPATH
```

Example:

```bash
igitur download 1337 ./local/destination/path/
```

Now all files from the gaudeam folder will be downloaded. If a file already exists locally it will be skipped. Thus, if anything goes wrong during downloading a big folder, the tool will automatically resume non-downloaded files.

### Upload Files and Folders

You can upload files and folders to a folder on Gaudeam using the `upload` command. If the source is a folder the content of this folder will be uploaded. If the source is a file the file will be uploaded to the destination folder on Gaudeam.

If a file already exists at the destination folder it will be skipped.

```bash
igitur upload FOLDERID ./local/source/folder/
```

or as single file upload:

```bash
igitur upload FOLDERID ./local/source/file.ext
```

## Upload Image Galleries

The `upload-images` command is a special function to create galleries while uploading compressed versions of the original images. The file is locally compressed and uploaded in the same structure as the source folder. If a file already exists at the destination it is skipped. Thus, you can upload big galleries in multiple sessions without losing images.

```bash
igitur upload-images FOLDERID ./local/source/folder/
```

## Development

To develop on the app, you can install it as a in-place package which will reflect all code changes directly in your virtual environment.

```bash
pip install -e .
```
