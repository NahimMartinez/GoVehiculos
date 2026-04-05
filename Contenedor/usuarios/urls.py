from django.urls import path, include
from rest_framework import routers
from usuarios import views
from . import views
from django.contrib.auth.views import LoginView

router = routers.DefaultRouter() # Creamos un router para registrar las rutas de la API REST de usuarios
router.register(r'usuarios', views.UsuarioViewSet) # Registramos la ruta 'usuarios' para que apunte al viewset UsuarioViewSet, lo que permitirá listar, crear, actualizar o eliminar usuarios a través de la API REST

urlpatterns = [
    path('', include(router.urls)), # Incluimos las rutas del router en las URLs de la aplicación de usuarios
    path('registro/', views.registro_view, name='registro'), # Agregamos una ruta para la vista de registro de usuarios, que se llamará 'registro' y apuntará a la función registro_view en views.py
]