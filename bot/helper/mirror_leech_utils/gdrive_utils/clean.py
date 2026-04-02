from logging import getLogger
from googleapiclient.errors import HttpError
from tenacity import RetryError
from bot.helper.mirror_leech_utils.gdrive_utils.helper import GoogleDriveHelper

LOGGER = getLogger(__name__)

class GoogleDriveClean(GoogleDriveHelper):
    def __init__(self):
        super().__init__()
        self.is_cancelled = False

    def drive_clean(self, link, user_id, trash=False):
        try:
            file_id = self.get_id_from_url(link, user_id)
        except (KeyError, IndexError):
            return "Google Drive ID could not be found in the provided link"
        self.service = self.authorize()
        LOGGER.info(f"Cleaning folder ID: {file_id}")
        try:
            return self._proceed_clean(file_id, trash)
        except Exception as err:
            if isinstance(err, RetryError):
                LOGGER.info(f"Total Attempts: {err.last_attempt.attempt_number}")
                err = err.last_attempt.exception()
            err = str(err).replace(">", "").replace("<", "")
            if "File not found" in err:
                if not self.alt_auth and self.use_sa:
                    self.alt_auth = True
                    self.use_sa = False
                    LOGGER.error("File not found. Trying with token.pickle...")
                    return self.drive_clean(link, user_id, trash)
                msg = "File not found."
            else:
                msg = f"Error.\n{err}"
        return msg

    def _proceed_clean(self, folder_id, trash=False):
        files = self.get_files_by_folder_id(folder_id)
        if len(files) == 0:
            return "Folder is empty or not found."

        deleted = 0
        for filee in files:
            if self.is_cancelled:
                return f"Cancelled Drive Clean. Processed {deleted} files."
            try:
                shortcut_details = filee.get("shortcutDetails")
                if shortcut_details is not None:
                    mime_type = shortcut_details["targetMimeType"]
                    file_id = shortcut_details["targetId"]
                else:
                    mime_type = filee.get("mimeType")
                    file_id = filee["id"]

                if mime_type == self.G_DRIVE_DIR_MIME_TYPE:
                    self._proceed_clean(file_id, trash)
                else:
                    if trash:
                        self.service.files().update(fileId=file_id, body={'trashed': True}, supportsAllDrives=True).execute()
                    else:
                        self.service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
                    deleted += 1
            except HttpError as err:
                LOGGER.error(f"Error deleting {filee['name']}: {err}")

        return f"Successfully processed {deleted} files."
