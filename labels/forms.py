from django.db import transaction
from django import forms
from django.core.exceptions import ValidationError
from .models import CSVUpload, BarcodeImage

class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class CSVUploadForm(forms.ModelForm):
    barcode_images = forms.CharField(  # <--- Change field type to CharField
        required=False,
        widget=MultiFileInput(attrs={
            'multiple': True,
            'accept': 'image/*',
            'class': 'form-control',
        }),
        label='Upload Barcode Images (optional)',
    )

    class Meta:
        model = CSVUpload
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'accept': '.csv',
                'class': 'form-control',
            })
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        print(f"File: {file}")
        if file:
            if not file.name.lower().endswith('.csv'):
                raise ValidationError('File must be a CSV.')
            if file.content_type not in ['text/csv', 'application/csv', 'application/octet-stream']:
                raise ValidationError('Invalid file type. Please upload a CSV file.')
            if file.size > 10 * 1024 * 1024:
                raise ValidationError('File size exceeds 10MB limit.')
        return file

    def clean_barcode_images(self):
        print("Clean barcode images called")
        print(f"Raw barcode images: {self.files}")
        files = self.files.getlist('barcode_images')
        print(f"Cleaned barcode images: {files}")
        if not files:
            return []
        for file in files:
            if file:
                if not file.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    raise ValidationError(f'File {file.name} must be a PNG, JPEG, or GIF image.')
                if file.content_type not in ['image/png', 'image/jpeg', 'image/gif']:
                    raise ValidationError(f'File {file.name} is not a valid image type.')
                if file.size > 5 * 1024 * 1024:
                    raise ValidationError(f'File {file.name} exceeds 5MB limit.')
        return files
    
    @transaction.atomic
    def save(self, commit=True):
        # 1. Save the CSVUpload instance (parent object)
        csv_upload_instance = super().save(commit=commit)

        if commit:
            barcode_files = self.cleaned_data.get('barcode_images')
            
            if barcode_files:
                # 2. FIX: Retrieve existing barcodes and map them by filename.
                # This uses a dictionary comprehension and avoids the use of in_bulk().
                existing_barcodes_query = BarcodeImage.objects.filter(
                    upload=csv_upload_instance
                ).values('filename', 'id', 'image') 
                
                # Create a mapping: {filename: BarcodeImage_ID}
                # Note: We only need the ID to retrieve the full instance for deletion.
                # Since multiple uploads might have the same name, we only map to one, 
                # which is fine as we only need to delete ONE conflicting record.
                existing_barcodes_map = {
                    item['filename']: item['id'] for item in existing_barcodes_query
                }
                
                # List to hold instances that need deletion (to be fetched once)
                ids_to_delete = []

                for file in barcode_files:
                    filename = file.name
                    
                    # A. Check if a record with this filename already exists for this upload
                    if filename in existing_barcodes_map:
                        ids_to_delete.append(existing_barcodes_map[filename])
                        
                    # B. Create the new BarcodeImage record.
                    # We create the new one first, then handle the deletion of the old one
                    # to keep the logic clean and safe within the transaction.
                    BarcodeImage.objects.create(
                        upload=csv_upload_instance,
                        image=file 
                    )

                # 3. Perform Deletion: Retrieve and delete the full instances.
                # This must happen BEFORE the new files are fully saved to clear the path.
                if ids_to_delete:
                    # Retrieve the actual model instances to ensure .delete() calls the file cleanup
                    instances_to_delete = BarcodeImage.objects.filter(id__in=ids_to_delete)
                    
                    # Call delete on each instance to trigger the model's delete() 
                    # method, which handles physical file cleanup.
                    for instance in instances_to_delete:
                        print(f"Deleting old BarcodeImage instance and file for: {instance.filename}")
                        instance.delete() # Triggers file deletion via model method
        
        return csv_upload_instance
    