from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.conf import settings
from .models import CSVUpload, ProductLabel
from .forms import CSVUploadForm
from .utils import process_csv, generate_label_image, create_zip_export, create_pdf_export
import os

def upload_csv(request):
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_upload = form.save()
            # Process CSV and generate labels
            process_csv(csv_upload)
            return redirect('label_list', upload_id=csv_upload.id)
    else:
        form = CSVUploadForm()
    
    uploads = CSVUpload.objects.all().order_by('-uploaded_at')
    return render(request, 'labels/upload.html', {'form': form, 'uploads': uploads})

def label_list(request, upload_id):
    csv_upload = get_object_or_404(CSVUpload, id=upload_id)
    labels = csv_upload.labels.all()
    return render(request, 'labels/label_list.html', {
        'csv_upload': csv_upload,
        'labels': labels
    })

def export_zip(request, upload_id):
    csv_upload = get_object_or_404(CSVUpload, id=upload_id)
    zip_file = create_zip_export(csv_upload)
    
    response = FileResponse(open(zip_file, 'rb'), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="labels_{upload_id}.zip"'
    return response

def export_pdf(request, upload_id):
    csv_upload = get_object_or_404(CSVUpload, id=upload_id)
    pdf_file = create_pdf_export(csv_upload)
    
    response = FileResponse(open(pdf_file, 'rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="labels_{upload_id}.pdf"'
    return response

def regenerate_labels(request, upload_id):
    csv_upload = get_object_or_404(CSVUpload, id=upload_id)
    # Delete old images
    for label in csv_upload.labels.all():
        if label.image and os.path.exists(label.image.path):
            os.remove(label.image.path)
    # Regenerate
    process_csv(csv_upload)
    return redirect('label_list', upload_id=upload_id)
