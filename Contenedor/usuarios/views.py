# from django.shortcuts import render
from rest_framework import viewsets
from .serializer import UsuarioSerializer
from .models import Usuario

# Create your views here.

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all() # Obtenemos todos los objetos del modelo Usuario para que puedan ser listados, creados, actualizados o eliminados a través de la API REST
    serializer_class = UsuarioSerializer # Especificamos que el serializer a utilizar para convertir los objetos del modelo Usuario a JSON es el UsuarioSerializer que definimos en el archivo serializer.py

