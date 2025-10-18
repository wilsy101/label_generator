from django.db import models
from django.conf import settings
from .storage import OverwriteStorage
import os

# --- Custom Overwrite Function (Keep this as it defines the non-unique path) ---
def overwrite_filename(instance, filename):
    if isinstance(instance, CSVUpload):
        upload_dir = 'csv_uploads'
    elif isinstance(instance, BarcodeImage):
        upload_dir = 'barcode_images'
    else:
        upload_dir = 'misc_uploads'
    return os.path.join(upload_dir, filename)



def delete_existing_file(path):
    """Safely delete file if it exists."""
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.exists(full_path):
        os.remove(full_path)


class CSVUpload(models.Model):
    file = models.FileField(upload_to=overwrite_filename, storage=OverwriteStorage())
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return f"CSV Upload {self.id} - {self.uploaded_at}"

    def delete(self, *args, **kwargs):
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)

class BarcodeImage(models.Model):
    upload = models.ForeignKey(CSVUpload, on_delete=models.CASCADE, related_name='barcodes')
    image = models.ImageField(upload_to=overwrite_filename, storage=OverwriteStorage())
    filename = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        if self.image and not self.filename:
            self.filename = os.path.basename(self.image.name)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.image:
            self.image.delete(save=False)
        super().delete(*args, **kwargs)

class ProductLabel(models.Model):
    csv_upload = models.ForeignKey(CSVUpload, on_delete=models.CASCADE, related_name='labels')
    product_name = models.CharField(max_length=255)
    mrp = models.CharField(max_length=50)
    quality = models.CharField(max_length=100, blank=True)
    size = models.CharField(max_length=50, blank=True)
    net_quantity = models.CharField(max_length=100)
    product_code = models.CharField(max_length=100)
    design_color = models.CharField(max_length=100)
    mfg_month = models.CharField(max_length=20)
    mfg_year = models.CharField(max_length=4)
    gtin = models.CharField(max_length=14)
    manufacturer = models.TextField()
    image = models.ImageField(upload_to='labels/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.product_name} - {self.product_code}"
