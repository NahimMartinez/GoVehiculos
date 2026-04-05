# from django.shortcuts import render
from rest_framework import viewsets
from .serializer import UsuarioSerializer
from .models import Usuario
from django.shortcuts import render, redirect
from django.contrib.auth.models import Group
from forms import RegistroUsuarioForm

# Create your views here.

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all() # Obtenemos todos los objetos del modelo Usuario para que puedan ser listados, creados, actualizados o eliminados a través de la API REST
    serializer_class = UsuarioSerializer # Especificamos que el serializer a utilizar para convertir los objetos del modelo Usuario a JSON es el UsuarioSerializer que definimos en el archivo serializer.py

def registro_view(request):
    if request.method == 'POST':
        form = RegistroUsuarioForm(request.POST)
        if form.is_valid():
            # 1. Guardar el usuario en la base de datos
            nuevo_usuario = form.save()
            
            # 2. Leer que rol eligio en el formulario
            rol_elegido = form.cleaned_data.get('rol')
            
            # 3. Agregar en el grupo elegido 
            if rol_elegido == 'cliente':
                grupo = Group.objects.get(name='Clientes')
            else:
                grupo = Group.objects.get(name='Socios')
                
            nuevo_usuario.groups.add(grupo)
            
            return redirect('login') # Mandar a iniciar sesión
    else:
        form = RegistroUsuarioForm()
        
    return render(request, 'usuarios/registro.html', {'form': form})