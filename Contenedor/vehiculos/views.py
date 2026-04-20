from django.shortcuts import render, redirect, get_object_or_404
from vehiculos.models import Vehiculo
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from reservas.models import Reserva
from .forms import VehiculoForm

# Funciones auxiliares
def buscar_vehiculo(matricula):
    """Busca vehículos activos por matrícula (case-insensitive).
    
    Realiza una búsqueda de vehículos filtrados por matrícula sin importar
    mayúsculas/minúsculas y que estén marcados como activos.
    
    """
    # Filtrar vehículos activos con matrícula que coincida sin importar mayúsculas
    return Vehiculo.objects.filter(matricula__iexact=matricula, activo=True)


def obtener_vehiculo(matricula):
    """Obtiene el primer vehículo activo que coincida con la matrícula.
    
    Busca el vehículo activo con la matrícula especificada y retorna
    el primero si existe, o None si no hay coincidencias.
    
    """
    # Buscar vehículos y obtener el primero (o None)
    return buscar_vehiculo(matricula).first()


def validar_datos(datos):
    """Valida que los datos de un formulario sean válidos.
    
    Ejecuta las validaciones del formulario Django y verifica que todos
    los campos requeridos y opcionales cumplan con sus restricciones.
    
    """
    # Ejecutar validación del formulario Django
    return datos.is_valid()


def modificar_datos(datos):
    """Guarda los datos de un formulario en la base de datos.
    
    Persiste los cambios del formulario (modelo) en la base de datos.
    
    """
    # Guardar los datos del formulario en la base de datos
    datos.save()
    # Retornar el objeto guardado
    return datos


def obtener_vehiculo_del_usuario(vehiculo_id, usuario):
    """Obtiene un vehículo por ID verificando pertenencia al usuario.
    
    Busca un vehículo activo por su ID que pertenezca al usuario especificado.
    Si no existe o no le pertenece al usuario, lanza error.
    
    """
    # Obtener el vehículo por ID que pertenezca al usuario y esté activo (404 si no existe)
    return get_object_or_404(Vehiculo, id=vehiculo_id, duenio=usuario, activo=True)


def obtener_vehiculo_a_editar(request):
    """Obtiene el vehículo a editar desde parámetro GET 'edit' o POST 'vehiculo_id'.
    
    Lee el parámetro GET 'edit' en solicitudes iniciales o POST 'vehiculo_id' cuando
    el formulario retorna con errores de validación. Verifica que el vehículo 
    le pertenece al usuario autenticado y está activo.
    
    """
    # Obtener el parámetro 'edit' del query string (URL) en GET
    vehiculo_id = request.GET.get('edit')
    
    # Si es POST y no encontró en GET, buscar en campo oculto del formulario
    if not vehiculo_id and request.method == 'POST':
        vehiculo_id = request.POST.get('vehiculo_id')

    # Si no hay ID de vehículo para editar, retornar None
    if not vehiculo_id:
        return None

    # Obtener el vehículo verificando que le pertenezca al usuario autenticado
    return obtener_vehiculo_del_usuario(vehiculo_id, request.user)


def preparar_formulario_vehiculo(request, vehiculo_a_editar=None):
    """Prepara un formulario de vehículo según el método HTTP y contexto de edición.
    
    En POST retorna formulario con datos enviados para validación. En GET retorna
    formulario pre-llenado (si es edición) o vacío (si es creación).
    
    """
    if request.method == 'POST':
        # Si estamos editando un vehículo
        if vehiculo_a_editar:
            # Crear formulario con datos POST y archivos, vinculado a la instancia existente
            return VehiculoForm(request.POST, request.FILES, instance=vehiculo_a_editar)
        # Si es creación de nuevo vehículo
        # Crear formulario vacío con datos POST para validar
        return VehiculoForm(request.POST, request.FILES)

    # Para solicitud GET
    # Si hay vehículo a editar
    if vehiculo_a_editar:
        # Crear formulario pre-llenado con datos actuales del vehículo
        return VehiculoForm(instance=vehiculo_a_editar)

    # Si es creación, crear formulario completamente vacío
    return VehiculoForm()


def procesar_baja_vehiculo(request):
    """Procesa la eliminación lógica de un vehículo del usuario.
    
    Verifica que no haya reservas futuras antes de dar de baja. Si hay reservas
    vigentes o futuras, muestra error y no permite la eliminación. Si todo está
    bien, marca el vehículo como inactivo.
    
    """
    # Obtener el ID del vehículo a eliminar desde el formulario POST
    vehiculo_id = request.POST.get('vehiculo_id')
    # Obtener el vehículo verificando que pertenezca al usuario
    vehiculo_a_eliminar = obtener_vehiculo_del_usuario(vehiculo_id, request.user)

    # Buscar si hay reservas con fecha de fin en el futuro o actual
    hay_reservas_futuras = Reserva.objects.filter(
        # Reservas del vehículo específico
        vehiculo=vehiculo_a_eliminar,
        # Con fecha final mayor o igual a hoy
        fecha_fin__gte=timezone.now().date()
    ).exists()

    # Si hay reservas vigentes o futuras
    if hay_reservas_futuras:
        # Mostrar mensaje de error al usuario
        messages.error(request, 'No se puede eliminar el vehículo porque tiene reservas vigentes o futuras.')
        # Redirigir sin hacer cambios
        return redirect('mis_vehiculos')

    # Marcar el vehículo como inactivo (baja lógica)
    vehiculo_a_eliminar.activo = False
    # Guardar solo el campo activo para optimizar la base de datos
    vehiculo_a_eliminar.save(update_fields=['activo'])
    # Mostrar mensaje de éxito
    messages.success(request, 'Vehículo eliminado correctamente.')
    # Redirigir a la lista de vehículos
    return redirect('mis_vehiculos')


def procesar_formulario_vehiculo(request, vehiculo_a_editar=None):
    """Procesa la validación y guardado del formulario de vehículos.
    
    Prepara el formulario, valida los datos, asigna dueño si es creación,
    guarda en base de datos y muestra mensaje de éxito o error según corresponda.
    
    """
    # Preparar el formulario con datos del request
    form = preparar_formulario_vehiculo(request, vehiculo_a_editar)

    # Validar que todos los campos cumplan requisitos
    if not validar_datos(form):
        # Si hay errores de validación, retornar formulario y flag de fallo
        return form, False

    # Guardar el objeto del formulario en memoria sin guardar a BD todavía
    nuevo_vehiculo = form.save(commit=False)

    # Si es creación (no hay vehículo a editar)
    if vehiculo_a_editar is None:
        # Asignar el usuario autenticado como dueño del vehículo
        nuevo_vehiculo.duenio = request.user

    # Guardar el vehículo en la base de datos
    modificar_datos(nuevo_vehiculo)

    # Mostrar mensaje de éxito apropiado según si es edición o creación
    if vehiculo_a_editar:
        # Mensaje para actualización
        messages.success(request, 'Vehículo actualizado')
    else:
        # Mensaje para creación
        messages.success(request, 'Vehículo registrado')

    # Retornar formulario y flag indicando guardado exitoso
    return form, True

# Create your views here.
def index(request):
    """Vista de inicio que muestra los 6 vehículos más populares.
    
    Obtiene los vehículos activos ordenados por cantidad de reservas (descendente)
    y retorna los 6 primeros para mostrar como destacados en la página de inicio.
    
    """
    # Obtener vehículos activos y anotar cantidad de reservas de cada uno
    vehiculos = Vehiculo.objects.filter(activo=True).annotate(num_reservas=Count('reserva')).order_by('-num_reservas')[:6]
    # Limitar a los 6 más reservados para mostrar como destacados

    # Preparar diccionario con datos para la plantilla
    contexto = {
        'vehiculos_destacados': vehiculos
    }

    # Renderizar template de inicio con los vehículos destacados
    return render(request, 'index.html', contexto)

def listar_vehiculos_view(request):
    """Vista que lista todos los vehículos activos disponibles para reservar.
    
    Obtiene el conjunto completo de vehículos activos y los pasa a la plantilla
    de reserva para que el usuario pueda visualizar y seleccionar vehículos
    disponibles.
    
    """
    # Obtener todos los vehículos que están marcados como activos
    vehiculos = Vehiculo.objects.filter(activo=True)

    # Preparar diccionario con todos los vehículos para la plantilla
    contexto = {
        'vehiculos': vehiculos
    }

    # Renderizar template de reserva con la lista completa de vehículos
    return render(request, 'vehiculos/reservar_vehiculos.html', contexto)

def mostrar_detalle_view(request, vehiculo_id):
    """Vista que muestra el detalle completo de un vehículo específico.
    
    Obtiene un vehículo activo por su ID y verifica si el usuario autenticado
    es el dueño del vehículo para mostrar opciones de edición. Si el vehículo
    no existe o está inactivo, retorna error.
    
    """
    # Obtener el vehículo por ID que esté activo (404 si no existe o está inactivo)
    vehiculo = get_object_or_404(Vehiculo, id=vehiculo_id, activo=True)
    # Verificar si el usuario autenticado es el dueño del vehículo
    puede_editar = request.user.is_authenticated and vehiculo.duenio_id == request.user.id

    # Preparar contexto con datos del vehículo y permisos de edición
    contexto = {
        'vehiculo': vehiculo,
        'puede_editar': puede_editar,
    }

    # Renderizar template de detalle del vehículo
    return render(request, 'vehiculos/detalle_vehiculo.html', contexto)

@login_required
def visualizar_flota_view(request):
    """Vista principal para la gestión de la flota de vehículos del usuario.
    
    Panel donde el usuario propietario puede crear, editar y eliminar vehículos
    de su flota. En GET muestra la lista de vehículos con formulario de creación/edición.
    En POST procesa las acciones: crear, actualizar o dar de baja vehículos.
    
    Requiere estar autenticado (decorador @login_required).
    
    """
    # Obtener el vehículo a editar desde parámetro GET 'edit' (None si es creación)
    vehiculo_a_editar = obtener_vehiculo_a_editar(request)

    # Procesar solicitudes POST
    if request.method == 'POST':
        # Obtener el tipo de acción del formulario
        accion = request.POST.get('accion')

        # Si la acción es eliminar
        if accion == 'eliminar':
            # Procesar eliminación (baja) del vehículo
            return procesar_baja_vehiculo(request)

        # Procesar creación o edición del vehículo
        form, guardado = procesar_formulario_vehiculo(request, vehiculo_a_editar)

        # Si el guardado fue exitoso
        if guardado:
            # Redirigir a la misma página para refrescar la lista
            return redirect('mis_vehiculos')
    else:
        # Para solicitud GET, preparar formulario vacío o pre-llenado
        form = preparar_formulario_vehiculo(request, vehiculo_a_editar)

    # Obtener todos los vehículos activos del usuario autenticado
    vehiculos_del_socio = Vehiculo.objects.filter(duenio=request.user, activo=True)

    # Preparar contexto con lista de vehículos, formulario y estado de edición
    contexto = {
        'mis_vehiculos': vehiculos_del_socio,
        'form': form,
        'vehiculo_a_editar': vehiculo_a_editar,
    }
    # Renderizar template del panel de gestión de flota
    return render(request, 'vehiculos/mis_vehiculos.html', contexto)


# Alias para mantener compatibilidad con referencias anteriores.
# Permite usar mis_vehiculos_view como sinónimo de visualizar_flota_view
mis_vehiculos_view = visualizar_flota_view

def inicio_view(request):
    """Alias de compatibilidad para la vista de inicio.
    
    Mantiene compatibilidad si se referencia como 'inicio_view' en lugar
    de 'index'. Simplemente delega a la función index.
    
    """
    # Llamar a index para mostrar la página de inicio
    return index(request)