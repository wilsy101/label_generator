from django.db import models
import os

class CSVUpload(models.Model):
    file = models.FileField(upload_to='csv_uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"CSV Upload {self.id} - {self.uploaded_at}"

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
