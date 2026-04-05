from django.urls import path, include
from rest_framework import routers
from . import views
from django.contrib.auth.views import LoginView

router = routers.DefaultRouter() # Creamos un router para registrar las rutas de la API REST de usuarios
router.register(r'usuarios', views.UsuarioViewSet) # Registramos la ruta 'usuarios' para que apunte al viewset UsuarioViewSet

# Rutas de autenticación (vistas de formularios)
auth_patterns = [
    path('registro/', views.registro_view, name='registro'),
    path('login/', views.login_view, name='login'),
]

# Rutas de la API REST
api_patterns = [
    path('v1/', include(router.urls)),
]

urlpatterns = auth_patterns + api_patterns