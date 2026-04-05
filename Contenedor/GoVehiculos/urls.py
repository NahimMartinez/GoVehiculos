from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from vehiculos.views import index
from rest_framework.schemas import get_schema_view

schema_view = get_schema_view(
    title='API GoVehiculos',
    description='Esquema OpenAPI de la API REST',
    version='1.0.0',
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='inicio'),
    path('api/v1/', include('usuarios.urls')), # Incluimos las URLs de la aplicación de usuarios para que estén disponibles en la ruta 'api/'
    path('schema/', schema_view, name='openapi-schema'),
]


# Si estamos en modo desarrollo (DEBUG = True), lleva los archivos a la carpeta media.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)