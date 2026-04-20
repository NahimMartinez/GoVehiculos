from rest_framework import viewsets
from .serializer import UsuarioSerializer
from .models import Usuario
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import Group
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import RegistroUsuarioForm, EditarUsuarioForm

"""
Vistas de gestión de usuarios.

Este módulo contiene las vistas para autenticación (registro, login, logout)
y administración de usuarios (ABM: Alta, Baja y Modificación).

Vistas principales:
- registro_view: Formulario de registro de nuevos usuarios
- login_view: Autenticación de usuarios existentes
- logout_view: Cierre de sesión
- abm_usuarios_view: Panel de administración de usuarios con búsqueda, filtros y paginación
- editar_usuario_view: Edición de datos y rol de un usuario
- suspender_usuario_view: Desactivación de usuario
- reactivar_usuario_view: Reactivación de usuario desactivado
"""

class UsuarioViewSet(viewsets.ModelViewSet):
    """ViewSet de API REST para gestión de usuarios.
    
    Permite listar, crear, actualizar y eliminar usuarios a través de endpoints REST.
    Utiliza el serializador UsuarioSerializer para convertir objetos Usuario a JSON.
    """
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer


def _obtener_filtros_abm(request):
    """Extrae los parámetros de filtro desde la solicitud GET.
    
    Lee los parámetros 'q' (búsqueda) y 'grupo' del request y retorna
    un diccionario con los valores normalizados (sin espacios en blanco).
    
    """
    return {
        'busqueda': request.GET.get('q', '').strip(),
        'grupo': request.GET.get('grupo', '').strip(),
    }


def _filtrar_usuarios_abm(filtros):
    """Filtra el queryset de usuarios según los criterios especificados.
    
    Aplica filtros de búsqueda (por usuario, email o nombre de grupo) y
    filtro por grupo específico. Excluye superusuarios y ordena por fecha
    de registro (más recientes primero).
    
    """
    usuarios_qs = Usuario.objects.filter(is_superuser=False)

    if filtros['busqueda']:
        usuarios_qs = usuarios_qs.filter(
            Q(username__icontains=filtros['busqueda'])
            | Q(email__icontains=filtros['busqueda'])
            | Q(groups__name__icontains=filtros['busqueda'])
        )

    if filtros['grupo']:
        usuarios_qs = usuarios_qs.filter(groups__name=filtros['grupo'])

    return usuarios_qs.distinct().order_by('-date_joined')


def _paginar_usuarios_abm(request, usuarios_qs, por_pagina=10):
    """Pagina un queryset de usuarios según el número de página solicitado.
    
    Crea un paginador y obtiene la página especificada. Si la página no existe
    o no es válida, retorna la primera página.
    
    """
    paginator = Paginator(usuarios_qs, por_pagina)
    numero_pagina = request.GET.get('page')
    usuarios = paginator.get_page(numero_pagina)
    return paginator, usuarios


def _construir_parametros_consulta_abm(request):
    """Construye una cadena de parámetros GET sin el parámetro 'page'.
    
    Copia los parámetros GET de la solicitud, remueve el parámetro 'page'
    y retorna la cadena codificada para usarla en links de paginación.
    Esto asegura que los filtros se mantengan al navegar entre páginas.
    
    """
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return query_params.urlencode()

def registro_view(request):
    """Vista para el registro de nuevos usuarios.
    
    - GET: Muestra el formulario de registro vacío.
    - POST: Procesa el formulario, crea el usuario, asigna el grupo (rol)
      seleccionado y redirige a login.
      
    """
    if request.method == 'POST':
        usuario = request.user if request.user.is_authenticated else None
        form = RegistroUsuarioForm(request.POST, usuario_logueado=usuario)
        if form.is_valid():
            # Guardar el nuevo usuario en la base de datos
            nuevo_usuario = form.save()
            
            # Obtener el rol seleccionado en el formulario
            rol_elegido = form.cleaned_data.get('rol')

            # Asignar el grupo (rol) al usuario si existe
            grupo = Group.objects.filter(name=rol_elegido).first()
            if grupo:
                nuevo_usuario.groups.add(grupo)
            
            return redirect('login')
    else:
        usuario = request.user if request.user.is_authenticated else None
        form = RegistroUsuarioForm(usuario_logueado=usuario)
        
    return render(request, 'usuarios/registro.html', {'form': form})

def login_view(request):
    """Vista para autenticación (login) de usuarios.
    
    - GET: Muestra el formulario de login.
    - POST: Valida credenciales (email y contraseña), autentica el usuario
      e inicia la sesión. Si las credenciales son inválidas, retorna error.
      
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Autenticar usando email como username (EMAIL es el USERNAME_FIELD)
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('inicio')
        else:
            context = {'error': 'Email o contraseña incorrectos'}
            return render(request, 'usuarios/login.html', context)
    
    return render(request, 'usuarios/login.html')

def logout_view(request):
    """Vista para cerrar la sesión del usuario actual.
    
    Limpia la sesión del usuario autenticado y redirige a la página de inicio.
    
    """
    logout(request)
    return redirect('inicio')

def abm_usuarios_view(request):
    """Panel de Administración de Usuarios (ABM).
    
    Vista principal para gestionar usuarios. Permite:
    - Búsqueda global por username, email o nombre de grupo
    - Filtrado por grupo específico
    - Paginación de resultados (10 usuarios por página)
    - Ver estado (activo/suspendido) de cada usuario
    - Acciones: editar, suspender, reactivar
    
    Los parámetros de filtro se preservan al navegar entre páginas.

    """
    # Obtener y validar filtros desde los parámetros GET
    filtros = _obtener_filtros_abm(request)
    
    # Aplicar filtros al queryset base de usuarios
    usuarios_qs = _filtrar_usuarios_abm(filtros)
    
    # Paginar resultados (10 usuarios por página)
    paginador, usuarios = _paginar_usuarios_abm(request, usuarios_qs)

    # Construir contexto para la plantilla
    contexto = {
        'usuarios': usuarios,
        'page_obj': usuarios,
        'paginator': paginador,
        'busqueda': filtros['busqueda'],
        'grupo_seleccionado': filtros['grupo'],
        'grupos_disponibles': Group.objects.order_by('name'),
        'current_query_params': _construir_parametros_consulta_abm(request),
    }

    return render(request, 'usuarios/abm_usuarios.html', contexto)


def editar_usuario_view(request, usuario_id):
    """Vista para editar datos y rol de un usuario.
    
    - GET: Muestra el formulario pre-llenado con datos actuales del usuario.
    - POST: Valida y guarda los cambios (datos personales y nuevo rol/grupo).
    
    Si el usuario que edita es administrador, puede cambiar el rol a Administrador.

      
    """
    usuario = get_object_or_404(Usuario, id=usuario_id, is_superuser=False)

    if request.method == 'POST':
        form = EditarUsuarioForm(request.POST, instance=usuario, usuario_logueado=request.user)
        if form.is_valid():
            # Guardar cambios de datos personales
            usuario_actualizado = form.save()
            
            # Obtener el nuevo rol seleccionado
            rol_elegido = form.cleaned_data.get('rol')
            grupo = Group.objects.filter(name=rol_elegido).first()

            # Actualizar grupos: limpiar antiguos y asignar el nuevo
            usuario_actualizado.groups.clear()
            if grupo:
                usuario_actualizado.groups.add(grupo)

            return redirect('abm_usuarios')
    else:
        form = EditarUsuarioForm(instance=usuario, usuario_logueado=request.user)

    return render(request, 'usuarios/editar_usuario.html', {
        'form': form,
        'usuario': usuario,
    })


def suspender_usuario_view(request, usuario_id):
    """Vista para desactivar (suspender) un usuario.
    
    Solo funciona con POST y no permite suspender el usuario actualmente
    autenticado (para evitar que un admin se bloquee a sí mismo).
    
    """
    usuario = get_object_or_404(Usuario, id=usuario_id, is_superuser=False)

    if request.method == 'POST' and usuario != request.user:
        usuario.is_active = False
        usuario.save(update_fields=['is_active'])

    return redirect('abm_usuarios')


def reactivar_usuario_view(request, usuario_id):
    """Vista para reactivar un usuario desactivado.
    
    Solo funciona con POST y no permite reactivar el usuario actualmente
    autenticado (aunque esta restricción es menos crítica que en suspender).
    
    """
    usuario = get_object_or_404(Usuario, id=usuario_id, is_superuser=False)

    if request.method == 'POST' and usuario != request.user:
        usuario.is_active = True
        usuario.save(update_fields=['is_active'])

    return redirect('abm_usuarios')