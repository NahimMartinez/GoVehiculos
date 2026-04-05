from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from vehiculos.views import index

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='inicio'),
    path('api/v1/', include('usuarios.urls')), # Incluimos las URLs de la aplicación de usuarios para que estén disponibles en la ruta 'api/'
]

# Si estamos en modo desarrollo (DEBUG = True), lleva los archivos a la carpeta media.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)