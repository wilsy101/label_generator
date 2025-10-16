from django import forms
from .models import CSVUpload

class CSVUploadForm(forms.ModelForm):
    class Meta:
        model = CSVUpload
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={'accept': '.csv', 'class': 'form-control'})
        }
