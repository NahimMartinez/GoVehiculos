# from django.shortcuts import render
from rest_framework import viewsets
from .serializer import UsuarioSerializer
from .models import Usuario
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import Group
from django.contrib.auth import authenticate, login, logout
from .forms import RegistroUsuarioForm, EditarUsuarioForm

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

            # 3. Agregar al grupo elegido si existe
            grupo = Group.objects.filter(name=rol_elegido).first()
            if grupo:
                nuevo_usuario.groups.add(grupo)
            
            return redirect('login') # Mandar a iniciar sesión
    else:
        form = RegistroUsuarioForm()
        
    return render(request, 'usuarios/registro.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Autenticar usando email como username (ya que EMAIL es el USERNAME_FIELD)
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('inicio')  # Redirigir a la página de inicio
        else:
            context = {'error': 'Email o contraseña incorrectos'}
            return render(request, 'usuarios/login.html', context)
    
    return render(request, 'usuarios/login.html')

def logout_view(request):
    logout(request)
    return redirect('inicio')

def abm_usuarios_view(request):
    usuarios = Usuario.objects.filter(is_superuser=False)

    contexto = {
        'usuarios': usuarios 
    }

    return render(request, 'usuarios/abm_usuarios.html', contexto)


def editar_usuario_view(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id, is_superuser=False)

    if request.method == 'POST':
        form = EditarUsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            usuario_actualizado = form.save()
            rol_elegido = form.cleaned_data.get('rol')
            grupo = Group.objects.filter(name=rol_elegido).first()

            usuario_actualizado.groups.clear()
            if grupo:
                usuario_actualizado.groups.add(grupo)

            return redirect('abm_usuarios')
    else:
        form = EditarUsuarioForm(instance=usuario)

    return render(request, 'usuarios/editar_usuario.html', {
        'form': form,
        'usuario': usuario,
    })