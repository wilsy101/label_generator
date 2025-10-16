from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_csv, name='upload_csv'),
    path('labels/<int:upload_id>/', views.label_list, name='label_list'),
    path('export/zip/<int:upload_id>/', views.export_zip, name='export_zip'),
    path('export/pdf/<int:upload_id>/', views.export_pdf, name='export_pdf'),
    path('regenerate/<int:upload_id>/', views.regenerate_labels, name='regenerate_labels'),
]