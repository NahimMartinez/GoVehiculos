from django.urls import path, include
from rest_framework import routers
from usuarios import views

router = routers.DefaultRouter() # Creamos un router para registrar las rutas de la API REST de usuarios
router.register(r'usuarios', views.UsuarioViewSet) # Registramos la ruta 'usuarios' para que apunte al viewset UsuarioViewSet, lo que permitirá listar, crear, actualizar o eliminar usuarios a través de la API REST

urlpatterns = [
    path('', include(router.urls)), # Incluimos las rutas del router en las URLs de la aplicación de usuarios
]