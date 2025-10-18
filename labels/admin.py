from django.contrib import admin
from .models import CSVUpload, ProductLabel, BarcodeImage


admin.site.register(CSVUpload)
admin.site.register(ProductLabel)
admin.site.register(BarcodeImage)
# Register your models here.
