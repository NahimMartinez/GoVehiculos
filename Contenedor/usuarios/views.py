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
    
    Lee los parámetros 'q' (búsqueda) y 'grupo' del request y normaliza
    los valores removiendo espacios en blanco adicionales para evitar
    inconsistencias en los filtros.
    
    """
    # Obtener parámetro 'q' del query string para búsqueda de usuarios
    busqueda = request.GET.get('q', '').strip()
    # Obtener parámetro 'grupo' del query string para filtrar por grupo específico
    grupo = request.GET.get('grupo', '').strip()
    
    return {
        'busqueda': busqueda,
        'grupo': grupo,
    }


def _filtrar_usuarios_abm(filtros):
    """Filtra el queryset de usuarios según los criterios especificados.
    
    Aplica filtros de búsqueda (por usuario, email o nombre de grupo) y
    filtro por grupo específico. Excluye superusuarios y ordena por fecha
    de registro de forma descendente (más recientes primero).
    
    """
    # Obtener todos los usuarios que NO sean superusuarios
    usuarios_qs = Usuario.objects.filter(is_superuser=False)

    # Si hay término de búsqueda, filtrar por username, email o nombre del grupo
    if filtros['busqueda']:
        usuarios_qs = usuarios_qs.filter(
            # Buscar en nombre de usuario (insensible a mayúsculas/minúsculas)
            Q(username__icontains=filtros['busqueda'])
            # O buscar en correo electrónico
            | Q(email__icontains=filtros['busqueda'])
            # O buscar en el nombre del grupo asignado al usuario
            | Q(groups__name__icontains=filtros['busqueda'])
        )

    # Si hay grupo específico seleccionado, filtrar solo usuarios de ese grupo
    if filtros['grupo']:
        usuarios_qs = usuarios_qs.filter(groups__name=filtros['grupo'])

    # Eliminar duplicados por uniones múltiples y ordenar por fecha de registro (descendente)
    return usuarios_qs.distinct().order_by('-date_joined')


def _paginar_usuarios_abm(request, usuarios_qs, por_pagina=10):
    """Pagina un queryset de usuarios según el número de página solicitado.
    
    Crea un paginador para dividir el queryset en páginas con cantidad
    especificada. Si la página no existe o es inválida, maneja la situación
    de forma automática sin lanzar error.
    
    """
    # Crear instancia del paginador con el queryset y cantidad de items por página
    paginator = Paginator(usuarios_qs, por_pagina)
    # Obtener el número de página desde los parámetros GET
    numero_pagina = request.GET.get('page')
    # Obtener la página específica (o primera si no es válida)
    usuarios = paginator.get_page(numero_pagina)
    # Retornar el paginador y los usuarios de esa página
    return paginator, usuarios


def _construir_parametros_consulta_abm(request):
    """Construye una cadena de parámetros GET sin el parámetro 'page'.
    
    Copia los parámetros GET actuales, remueve el parámetro 'page' para
    que la paginación funcione correctamente, y retorna la cadena codificada.
    Esto permite mantener filtros y búsquedas activos al cambiar de página.
    
    """
    # Realizar copia de parámetros GET para no modificar los originales
    query_params = request.GET.copy()
    # Remover el parámetro 'page' si existe para evitar conflictos
    query_params.pop('page', None)
    # Codificar los parámetros restantes a formato de query string
    return query_params.urlencode()

def registro_view(request):
    """Vista para el registro de nuevos usuarios.
    
    En solicitudes GET muestra el formulario de registro vacío. En POST procesa
    el envío: valida datos, crea el usuario, asigna el rol seleccionado como grupo
    y redirige a la página de login.
      
    """
    if request.method == 'POST':
        # Obtener usuario logueado actual (None si no está autenticado)
        usuario = request.user if request.user.is_authenticated else None
        # Crear formulario con datos del POST y usuario logueado para validaciones
        form = RegistroUsuarioForm(request.POST, usuario_logueado=usuario)
        if form.is_valid():
            # Guardar el nuevo usuario en la base de datos sin commit automático
            nuevo_usuario = form.save()
            
            # Extraer el rol seleccionado en el formulario del usuario
            rol_elegido = form.cleaned_data.get('rol')

            # Buscar el grupo en Django que coincida con el rol elegido
            grupo = Group.objects.filter(name=rol_elegido).first()
            # Si el grupo existe, asignarlo al nuevo usuario
            if grupo:
                nuevo_usuario.groups.add(grupo)
            
            # Redirigir a la página de login para que ingrese con sus credenciales
            return redirect('login')
    else:
        # Para solicitud GET, obtener usuario logueado si existe
        usuario = request.user if request.user.is_authenticated else None
        # Crear formulario vacío con contexto de usuario logueado
        form = RegistroUsuarioForm(usuario_logueado=usuario)
        
    # Renderizar template con el formulario de registro
    return render(request, 'usuarios/registro.html', {'form': form})

def login_view(request):
    """Vista para autenticación (login) de usuarios.
    
    En GET muestra el formulario de login. En POST valida las credenciales
    (email y contraseña), autentica el usuario e inicia la sesión. Si las
    credenciales son inválidas, muestra un mensaje de error.
      
    """
    if request.method == 'POST':
        # Obtener email enviado por el formulario
        email = request.POST.get('email')
        # Obtener contraseña enviada por el formulario
        password = request.POST.get('password')
        
        # Autenticar usando email como username (el modelo Usuario usa EMAIL como USERNAME_FIELD)
        user = authenticate(request, username=email, password=password)
        
        # Si la autenticación fue exitosa
        if user is not None:
            # Iniciar la sesión del usuario autenticado
            login(request, user)
            # Redirigir a la página de inicio
            return redirect('inicio')
        else:
            # Si falló autenticación, mostrar error en el contexto
            context = {'error': 'Email o contraseña incorrectos'}
            # Renderizar template de login nuevamente con el mensaje de error
            return render(request, 'usuarios/login.html', context)
    
    # Para solicitud GET, mostrar el formulario de login vacío
    return render(request, 'usuarios/login.html')

def logout_view(request):
    """Vista para cerrar la sesión del usuario actual.
    
    Limpia la sesión del usuario autenticado, destruye sus datos de sesión
    y redirige a la página de inicio.
    
    """
    # Cerrar la sesión del usuario autenticado
    logout(request)
    # Redirigir a la página de inicio
    return redirect('inicio')

def abm_usuarios_view(request):
    """Panel de Administración de Usuarios (ABM).
    
    Vista principal para gestionar usuarios. Proporciona funcionalidades de:
    - Búsqueda global por username, email o nombre de grupo
    - Filtrado por grupo específico
    - Paginación de resultados (10 usuarios por página)
    - Visualización del estado (activo/suspendido) de cada usuario
    - Enlaces para editar, suspender o reactivar usuarios
    
    Los parámetros de filtro y búsqueda se preservan al navegar entre páginas.

    """
    # Extraer parámetros de búsqueda y filtro del query string (q y grupo)
    filtros = _obtener_filtros_abm(request)
    
    # Aplicar los filtros al queryset base para obtener usuarios coincidentes
    usuarios_qs = _filtrar_usuarios_abm(filtros)
    
    # Dividir los resultados en páginas de 10 usuarios cada una
    paginador, usuarios = _paginar_usuarios_abm(request, usuarios_qs)

    # Preparar diccionario con datos necesarios para la plantilla
    contexto = {
        # Usuarios de la página actual
        'usuarios': usuarios,
        # Objeto página para usar en template (compatible con Django)
        'page_obj': usuarios,
        # Objeto paginador para generar links de navegación
        'paginator': paginador,
        # Término de búsqueda actual para pre-rellenar el input
        'busqueda': filtros['busqueda'],
        # Grupo seleccionado actualmente para el filtro
        'grupo_seleccionado': filtros['grupo'],
        # Lista de todos los grupos disponibles para el dropdown de filtros
        'grupos_disponibles': Group.objects.order_by('name'),
        # Parámetros GET codificados sin la página (para links de paginación)
        'current_query_params': _construir_parametros_consulta_abm(request),
    }

    # Renderizar el template de administración de usuarios con el contexto
    return render(request, 'usuarios/abm_usuarios.html', contexto)


def editar_usuario_view(request, usuario_id):
    """Vista para editar datos y rol de un usuario.
    
    En GET muestra el formulario pre-llenado con datos actuales del usuario.
    En POST valida y guarda los cambios en datos personales y en el rol/grupo
    asignado. Si el usuario que edita es administrador, puede cambiar roles.

      
    """
    # Obtener el usuario por ID (garantizar que no sea superusuario)
    usuario = get_object_or_404(Usuario, id=usuario_id, is_superuser=False)

    if request.method == 'POST':
        # Crear formulario con datos POST y la instancia de usuario a editar
        form = EditarUsuarioForm(request.POST, instance=usuario, usuario_logueado=request.user)
        if form.is_valid():
            # Guardar cambios en datos personales (nombre, email, etc.)
            usuario_actualizado = form.save()
            
            # Extraer el nuevo rol seleccionado en el formulario
            rol_elegido = form.cleaned_data.get('rol')
            # Buscar el grupo que corresponde al rol elegido
            grupo = Group.objects.filter(name=rol_elegido).first()

            # Remover todos los grupos existentes del usuario
            usuario_actualizado.groups.clear()
            # Asignar el nuevo grupo si existe
            if grupo:
                usuario_actualizado.groups.add(grupo)

            # Redirigir al panel de administración de usuarios
            return redirect('abm_usuarios')
    else:
        # Para solicitud GET, crear formulario pre-llenado con datos actuales
        form = EditarUsuarioForm(instance=usuario, usuario_logueado=request.user)

    # Renderizar formulario de edición con el usuario actual
    return render(request, 'usuarios/editar_usuario.html', {
        'form': form,
        'usuario': usuario,
    })


def suspender_usuario_view(request, usuario_id):
    """Vista para desactivar (suspender) un usuario.
    
    Solo funciona con solicitudes POST y contiene protección para evitar
    que el usuario autenticado se suspenda a sí mismo, previniendo bloqueos
    accidentales de administradores.
    
    """
    # Obtener el usuario a suspender (garantizar que no sea superusuario)
    usuario = get_object_or_404(Usuario, id=usuario_id, is_superuser=False)

    # Verificar que sea POST y que no sea el usuario actualmente autenticado
    if request.method == 'POST' and usuario != request.user:
        # Marcar el usuario como inactivo
        usuario.is_active = False
        # Guardar solo el campo is_active para optimizar la base de datos
        usuario.save(update_fields=['is_active'])

    # Redirigir al panel de administración de usuarios
    return redirect('abm_usuarios')


def reactivar_usuario_view(request, usuario_id):
    """Vista para reactivar un usuario desactivado.
    
    Solo funciona con solicitudes POST y contiene la misma protección que
    suspender_usuario_view por consistencia, aunque la restricción sea menos
    crítica en esta operación.
    
    """
    # Obtener el usuario a reactivar (garantizar que no sea superusuario)
    usuario = get_object_or_404(Usuario, id=usuario_id, is_superuser=False)

    # Verificar que sea POST y que no sea el usuario actualmente autenticado
    if request.method == 'POST' and usuario != request.user:
        # Marcar el usuario como activo nuevamente
        usuario.is_active = True
        # Guardar solo el campo is_active para optimizar la base de datos
        usuario.save(update_fields=['is_active'])

    # Redirigir al panel de administración de usuarios
    return redirect('abm_usuarios')