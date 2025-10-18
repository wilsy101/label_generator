import os
from django.core.files.storage import FileSystemStorage

class OverwriteStorage(FileSystemStorage):
    """Storage that overwrites existing files instead of renaming them."""
    def get_available_name(self, name, max_length=None):
        # If the file exists, remove it before saving a new one
        if self.exists(name):
            os.remove(os.path.join(self.location, name))
        return name