from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from django.contrib.staticfiles.storage import staticfiles_storage

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('labels.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
] 
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
