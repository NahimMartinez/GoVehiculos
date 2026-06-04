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
    path('auth/', include('usuarios.urls')), # URLs de autenticación (registro, login, logout)
    path('api-auth/', include('rest_framework.urls')), # Login/logout de la interfaz browsable de DRF
    path('api/', include('usuarios.api_urls')), # URLs exclusivas de la API REST
    path('api/', include('reservas.api_urls')), # URLs API REST de reservas
    path('schema/', schema_view, name='openapi-schema'),
    path('vehiculos/', include('vehiculos.urls')),
    path('reservas/', include('reservas.urls')),
]


# Si estamos en modo desarrollo (DEBUG = True), lleva los archivos a la carpeta media.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)