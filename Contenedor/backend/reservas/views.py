import json
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib import messages
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from datetime import datetime, time, timedelta

from .forms import CheckoutPagoForm, ReservarVehiculoForm
from .models import EstadoReserva, FranquiciaTarjeta, MetodoPago, Pago, Reserva
from .serializer import (
    EstadoReservaSerializer,
    FranquiciaTarjetaSerializer,
    MetodoPagoSerializer,
    PagoSerializer,
    ReservaCreateSerializer,
    ReservaSerializer,
)
from usuarios.signals import ROLE_CLIENTE, ROLE_SOCIO
from vehiculos.models import Vehiculo

from .estrategias import (
    ContextoPago,
    obtener_estrategia_pago,
)
from decimal import Decimal


def obtener_reservas_usuario_view(request):
    _finalizar_reservas_vencidas(Reserva.objects.filter(cliente=request.user))

    reservas = Reserva.objects.select_related('estado_reserva', 'vehiculo', 'vehiculo__modelo', 'vehiculo__modelo__marca').filter(cliente=request.user).order_by('-fecha_reserva')

    activos = reservas.filter(Q(estado_reserva__nombre__iexact='Pendiente') | Q(estado_reserva__nombre__iexact='Confirmada'))
    historial = reservas.exclude(id__in=activos.values_list('id', flat=True))

    contexto = {
        'activos': activos,
        'historial': historial,
    }

    return render(request, 'reservas/mis_reservas.html', contexto)

def obtener_metodos_de_pago():
    return MetodoPago.objects.all()

# Método GET para mostrar el formulario de reserva de vehículo. Esta vista renderiza una plantilla HTML que contiene el formulario para que los usuarios puedan ingresar los detalles de su reserva, como el vehículo que desean reservar, las fechas de inicio y fin, etc. La plantilla 'reservas/reserva.html' se encargará de mostrar el formulario y manejar la interacción del usuario para enviar la solicitud de reserva.
def reservar_view(request):
    usuario = request.user
    puede_reservar = request.user.is_authenticated and _usuario_valido(request.user)
    mensaje_reserva = None

    if not request.user.is_authenticated:
        mensaje_reserva = 'Debes iniciar sesion para reservar.'
    elif not puede_reservar:
        mensaje_reserva = 'Solo los usuarios con rol Cliente/Socio pueden reservar.'

    vehiculos_disponibles = Vehiculo.objects.select_related('modelo', 'modelo__marca').filter(
        activo=True,
        esta_aprobado=True,
    ).order_by('modelo__marca__nombre', 'modelo__nombre', 'matricula')

    vehiculo_seleccionado = None
    vehiculo_id = request.GET.get('vehiculo_id')
    if vehiculo_id:
        vehiculo_seleccionado = vehiculos_disponibles.filter(id=vehiculo_id).first()

    contexto = {
        'usuario': usuario,
        'vehiculos_disponibles': vehiculos_disponibles,
        'vehiculo_seleccionado': vehiculo_seleccionado,
        'puede_reservar': puede_reservar,
        'mensaje_reserva': mensaje_reserva,
    }

    return render(request, 'reservas/reserva.html', contexto)

# Método para verificar si un usuario es apto para reservar
def _usuario_valido(user):
    return user.groups.filter(name__in=[ROLE_CLIENTE, ROLE_SOCIO]).exists()

# Obtiene el estado de reserva por nombre y lo crea si aún no existe en el catálogo.
def _obtener_estado(nombre_estado):
    estado = EstadoReserva.objects.filter(nombre=nombre_estado).order_by('id').first()
    if estado is None:
        estado = EstadoReserva.objects.create(nombre=nombre_estado)
    return estado


def _reserva_esta_finalizada(reserva):
    if not reserva.estado_reserva:
        return False
    return reserva.estado_reserva.nombre.strip().lower() == 'finalizada'


def _reserva_ya_vencio(reserva):
    return reserva.fecha_fin < timezone.localdate()


def _finalizar_reservas_vencidas(reservas_qs):
    estado_finalizada = _obtener_estado('Finalizada')
    return reservas_qs.filter(fecha_fin__lt=timezone.localdate()).exclude(
        estado_reserva__nombre__iexact='Cancelada',
    ).exclude(
        estado_reserva__nombre__iexact='Finalizada',
    ).update(estado_reserva=estado_finalizada)

def cancelar_reserva_view(request, reserva_id):
    if request.method == 'POST':
        #  Recuperamos la reserva asegurándonos de que pertenezca al usuario logueado 
        reserva = get_object_or_404(Reserva, id=reserva_id, cliente=request.user)

        if _reserva_ya_vencio(reserva):
            if not _reserva_esta_finalizada(reserva):
                reserva.estado_reserva = _obtener_estado('Finalizada')
                reserva.save(update_fields=['estado_reserva'])

            messages.error(request, 'Esta reserva ya finalizó, por lo que no se puede cancelar.')
            return redirect('mis_reservas')
        
        # Obtenemos el estado "Cancelada"
        try:
            estado_cancelada = EstadoReserva.objects.get(nombre__iexact='Cancelada')
        except EstadoReserva.DoesNotExist:
            messages.error(request, 'Error del sistema: El estado "Cancelada" no existe.')
            return redirect('mis_reservas')

        reserva.estado_reserva = estado_cancelada
        reserva.save()
        messages.success(request, f'La reserva de {reserva.vehiculo.modelo} fue cancelada correctamente.')
            
    return redirect('mis_reservas')

# Devuelve True si la reserva tiene estado Cancelada (manejando también el caso sin estado).
def _reserva_esta_cancelada(reserva):
    if not reserva.estado_reserva:
        return False
    return reserva.estado_reserva.nombre.strip().lower() == 'cancelada'

# Convierte una instancia de Reserva en un diccionario serializable para respuestas JSON.
def _reserva_a_dict(reserva):
    return {
        'id': reserva.id,
        'vehiculo_id': reserva.vehiculo_id,
        'cliente_id': reserva.cliente_id,
        'fecha_inicio': reserva.fecha_inicio.isoformat(),
        'fecha_fin': reserva.fecha_fin.isoformat(),
        'monto_total': str(reserva.monto_total),
        'estado': reserva.estado_reserva.nombre if reserva.estado_reserva else None,
        'estado_reserva_id': reserva.estado_reserva_id,
        'fecha_reserva': reserva.fecha_reserva.isoformat(),
    }


def _crear_reserva_en_transaccion(usuario, vehiculo, fecha_inicio, fecha_fin):
    if vehiculo.duenio_id == usuario.id:
        return None, 'No puedes reservar un vehiculo propio.'

    # Utilizamos una transacción atómica para garantizar que la verificación de disponibilidad y la creación de la reserva se realicen de manera segura y sin condiciones de carrera. Al usar select_for_update() al consultar el vehículo, bloqueamos esa fila en la base de datos para evitar que otros procesos puedan reservar el mismo vehículo al mismo tiempo, lo que ayuda a garantizar la consistencia de los datos y evitar conflictos de reservas.
    with transaction.atomic():
        vehiculo_bloqueado = Vehiculo.objects.select_for_update().filter(
            id=vehiculo.id,
            activo=True,
            esta_aprobado=True,
        ).first()

        if vehiculo_bloqueado is None:
            return None, 'El vehiculo ya no esta disponible para reservar.'

        existe_conflicto = Reserva.objects.con_solapamiento(
            vehiculo=vehiculo_bloqueado,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        ).exists()

        if existe_conflicto:
            return (
                None,
                'Alguien mas reservó este vehiculo para esas fechas. Por favor, intenta con otro rango.',
            )

        estado_pendiente = _obtener_estado('Pendiente')
        cantidad_dias = (fecha_fin - fecha_inicio).days

        # Calculamos el monto base de la reserva (días × precio por día). El recargo/descuento por método de pago se aplica en el checkout.
        monto_base = cantidad_dias * vehiculo_bloqueado.precio_x_dia

        reserva = Reserva.objects.create(
            monto_total=Decimal(str(monto_base)).quantize(Decimal('0.01')),
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            estado_reserva=estado_pendiente,
            cliente=usuario,
            vehiculo=vehiculo_bloqueado,
        )

    return reserva, None

# El método _payload_reserva se encarga de extraer los datos de la solicitud, ya sea desde el cuerpo JSON o desde los datos POST tradicionales. Esto permite que la vista crear_reserva_view pueda manejar solicitudes tanto con contenido JSON (por ejemplo, desde una API) como con datos de formulario estándar (por ejemplo, desde un formulario HTML), lo que hace que la vista sea más flexible y compatible con diferentes tipos de clientes.
def _payload_reserva(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            body = request.body.decode('utf-8') if request.body else '{}'
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    return request.POST


def _solicitud_prefiere_json(request):
    return bool(request.content_type and 'application/json' in request.content_type)


def _contexto_reserva_base(request, *, vehiculo_seleccionado=None, datos_formulario=None, reserva=None, mensaje_reserva=None, tipo_reserva=None, errores=None):
    vehiculos_disponibles = Vehiculo.objects.select_related('modelo', 'modelo__marca').filter(
        activo=True,
        esta_aprobado=True,
    ).order_by('modelo__marca__nombre', 'modelo__nombre', 'matricula')

    if vehiculo_seleccionado is None:
        vehiculo_id = request.GET.get('vehiculo_id')
        if vehiculo_id:
            vehiculo_seleccionado = vehiculos_disponibles.filter(id=vehiculo_id).first()

    return {
        'usuario': request.user,
        'vehiculos_disponibles': vehiculos_disponibles,
        'vehiculo_seleccionado': vehiculo_seleccionado,
        'puede_reservar': request.user.is_authenticated and _usuario_valido(request.user),
        'mensaje_reserva': mensaje_reserva,
        'tipo_reserva': tipo_reserva,
        'reserva_creada': reserva,
        'errores_reserva': errores or {},
        'datos_formulario': datos_formulario or {},
    }


def _respuesta_reserva_html(request, *, mensaje_reserva, tipo_reserva='error', reserva=None, errores=None, datos_formulario=None, vehiculo_seleccionado=None, status_code=200):
    contexto = _contexto_reserva_base(
        request,
        vehiculo_seleccionado=vehiculo_seleccionado,
        datos_formulario=datos_formulario,
        reserva=reserva,
        mensaje_reserva=mensaje_reserva,
        tipo_reserva=tipo_reserva,
        errores=errores,
    )
    return render(request, 'reservas/reserva.html', contexto, status=status_code)


def _respuesta_reserva(request, *, ok, mensaje, status_code, reserva=None, errores=None, datos_formulario=None, vehiculo_seleccionado=None):
    if _solicitud_prefiere_json(request):
        payload = {'ok': ok, 'mensaje': mensaje}
        if reserva is not None:
            payload['reserva'] = reserva
        if errores:
            payload['errores'] = errores
        return JsonResponse(payload, status=status_code)

    return _respuesta_reserva_html(
        request,
        mensaje_reserva=mensaje,
        tipo_reserva='success' if ok else 'error',
        reserva=reserva,
        errores=errores,
        datos_formulario=datos_formulario,
        vehiculo_seleccionado=vehiculo_seleccionado,
        status_code=status_code,
    )


@require_POST
def crear_reserva_view(request):
    if not request.user.is_authenticated:
        return _respuesta_reserva(
            request,
            ok=False,
            mensaje='Debes iniciar sesion para reservar.',
            status_code=401,
        )

    if not _usuario_valido(request.user):
        return _respuesta_reserva(
            request,
            ok=False,
            mensaje='Solo los usuarios con rol Cliente/Socio pueden reservar.',
            status_code=403,
        )

    payload = _payload_reserva(request)
    if payload is None:
        return _respuesta_reserva(
            request,
            ok=False,
            mensaje='El cuerpo de la solicitud es invalido.',
            status_code=400,
        )

    form = ReservarVehiculoForm(payload)
    if not form.is_valid():
        return _respuesta_reserva(
            request,
            ok=False,
            mensaje='Revisá los campos del formulario.',
            status_code=400,
            errores=form.errors.get_json_data(),
            datos_formulario=payload,
        )

    vehiculo = form.cleaned_data['vehiculo']
    fecha_inicio = form.cleaned_data['fecha_inicio']
    fecha_fin = form.cleaned_data['fecha_fin']
    reserva, mensaje_error = _crear_reserva_en_transaccion(
        usuario=request.user,
        vehiculo=vehiculo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    if mensaje_error:
        return _respuesta_reserva(
            request,
            ok=False,
            mensaje=mensaje_error,
            status_code=400,
            datos_formulario=payload,
            vehiculo_seleccionado=vehiculo,
        )

    if _solicitud_prefiere_json(request):
        return _respuesta_reserva(
            request,
            ok=True,
            mensaje='Reserva creada correctamente. Proceda al checkout.',
            status_code=201,
            reserva=_reserva_a_dict(reserva),
            vehiculo_seleccionado=vehiculo,
        )

    # Redirige automáticamente al checkout para completar el pago
    return redirect('checkout', reserva_id=reserva.id)



# VISTAS DE CHECKOUT
def checkout_view(request, reserva_id):
    """GET: Renderiza la página de checkout con la info de la reserva y los métodos de pago."""
    if not request.user.is_authenticated:
        return redirect('login')

    reserva = get_object_or_404(
        Reserva.objects.select_related('estado_reserva', 'vehiculo', 'vehiculo__modelo', 'vehiculo__modelo__marca', 'cliente'),
        id=reserva_id,
        cliente=request.user,
    )

    # Solo se puede hacer checkout de reservas pendientes
    if not reserva.estado_reserva or reserva.estado_reserva.nombre.strip().lower() != 'pendiente':
        messages.error(request, 'Esta reserva no está pendiente de pago.')
        return redirect('mis_reservas')

    metodos = obtener_metodos_de_pago()
    franquicias = FranquiciaTarjeta.objects.all().order_by('nombre')

    # Preparar franquicias como JSON para el JS dinámico
    franquicias_data = []
    for f in franquicias:
        franquicias_data.append({
            'id': f.id,
            'nombre': f.nombre,
            'tipo': f.tipo,
        })

    import json as json_lib
    contexto = {
        'reserva': reserva,
        'metodos': metodos,
        'franquicias': franquicias,
        'franquicias_json': json_lib.dumps(franquicias_data),
        'usuario': request.user,
    }

    return render(request, 'reservas/checkout.html', contexto)


@require_POST
def procesar_checkout_view(request, reserva_id):
    """POST: Procesa el pago del checkout usando el patrón Strategy."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'mensaje': 'Debes iniciar sesión.'}, status=401)

    reserva = get_object_or_404(
        Reserva.objects.select_related('estado_reserva', 'vehiculo', 'cliente'),
        id=reserva_id,
        cliente=request.user,
    )

    # Solo se puede pagar reservas pendientes
    if not reserva.estado_reserva or reserva.estado_reserva.nombre.strip().lower() != 'pendiente':
        return JsonResponse({'ok': False, 'mensaje': 'Esta reserva no está pendiente de pago.'}, status=400)

    # Parsear el body como JSON
    try:
        body = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'mensaje': 'Datos de solicitud inválidos.'}, status=400)

    metodo_pago_nombre = body.get('metodo_pago_nombre', '')
    datos_pago = body.get('datos_pago', {})
    franquicia_id = body.get('franquicia_id') or datos_pago.get('franquicia_id')

    # Validar el método de pago
    try:
        estrategia = obtener_estrategia_pago(metodo_pago_nombre)
    except ValueError as e:
        return JsonResponse({'ok': False, 'mensaje': str(e)}, status=400)

    # Inyectar franquicia_id en datos_pago para la validación de la estrategia
    if franquicia_id:
        datos_pago['franquicia_id'] = franquicia_id

    # Validar datos de pago con la estrategia
    resultado_validacion = estrategia.validar_datos(datos_pago)
    if not resultado_validacion['valido']:
        return JsonResponse({
            'ok': False,
            'mensaje': 'Revisá los datos de pago.',
            'errores': resultado_validacion['errores'],
        }, status=400)

    # Calcular el monto final con recargo/descuento
    contexto_pago = ContextoPago(estrategia)
    monto_final = contexto_pago.ejecutar_estrategia(reserva.monto_total).quantize(Decimal('0.01'))

    # Procesar el pago (simulación)
    resultado_pago = contexto_pago.procesar_pago(datos_pago)

    if not resultado_pago['exito']:
        return JsonResponse({
            'ok': False,
            'mensaje': resultado_pago['mensaje'],
        }, status=400)

    # Obtener el MetodoPago del catálogo
    metodo_pago_obj = MetodoPago.objects.filter(nombre__iexact=metodo_pago_nombre).first()
    if not metodo_pago_obj:
        # Crearlo si no existe (por robustez)
        metodo_pago_obj = MetodoPago.objects.create(nombre=metodo_pago_nombre)

    # Obtener franquicia si aplica
    franquicia_obj = None
    detalle = resultado_pago.get('detalle', {})
    if franquicia_id:
        franquicia_obj = FranquiciaTarjeta.objects.filter(id=franquicia_id).first()

    # Crear pago y confirmar reserva atómicamente
    with transaction.atomic():
        pago = Pago.objects.create(
            reserva=reserva,
            metodo_pago=metodo_pago_obj,
            comprobante_transaccion=resultado_pago['comprobante'],
            monto=monto_final,
            franquicia=franquicia_obj,
            nombre_titular=detalle.get('nombre_titular', datos_pago.get('titular_cuenta', '')),
            ultimos_4_digitos=detalle.get('ultimos_4_digitos', ''),
            metodo_detalle=detalle.get('cbu_cvu_parcial', ''),
        )

        # Actualizar monto_total de la reserva con el recargo/descuento aplicado
        reserva.monto_total = monto_final
        reserva.estado_reserva = _obtener_estado('Confirmada')
        reserva.save(update_fields=['estado_reserva', 'monto_total'])

    return JsonResponse({
        'ok': True,
        'mensaje': resultado_pago['mensaje'],
        'pago': {
            'id': pago.id,
            'comprobante': pago.comprobante_transaccion,
            'monto': str(pago.monto),
        },
        'redirect_url': f'/reservas/checkout/{reserva.id}/exitoso/',
    }, status=201)


@require_POST
def cancelar_checkout_view(request, reserva_id):
    """POST: El usuario cancela el pago en el checkout. La reserva pasa a Cancelada."""
    if not request.user.is_authenticated:
        return redirect('login')

    reserva = get_object_or_404(Reserva, id=reserva_id, cliente=request.user)

    if reserva.estado_reserva and reserva.estado_reserva.nombre.strip().lower() == 'pendiente':
        reserva.estado_reserva = _obtener_estado('Cancelada')
        reserva.save(update_fields=['estado_reserva'])
        messages.info(request, 'Has cancelado el pago. La reserva fue liberada.')
    else:
        messages.error(request, 'Esta reserva no se puede cancelar desde el checkout.')

    return redirect('mis_reservas')


def checkout_exitoso_view(request, reserva_id):
    """GET: Página de confirmación post-pago exitoso."""
    if not request.user.is_authenticated:
        return redirect('login')

    reserva = get_object_or_404(
        Reserva.objects.select_related('estado_reserva', 'vehiculo', 'vehiculo__modelo', 'vehiculo__modelo__marca', 'cliente'),
        id=reserva_id,
        cliente=request.user,
    )

    pago = Pago.objects.select_related('metodo_pago', 'franquicia').filter(reserva=reserva).first()

    contexto = {
        'reserva': reserva,
        'pago': pago,
        'usuario': request.user,
    }

    return render(request, 'reservas/checkout_exitoso.html', contexto)


# VIEWSETS DE LA API REST
class ReservaViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return ReservaCreateSerializer
        return ReservaSerializer

    def get_queryset(self):
        return Reserva.objects.select_related('estado_reserva', 'vehiculo', 'cliente').filter(
            cliente=self.request.user
        ).order_by('-fecha_reserva')

    def create(self, request, *args, **kwargs):
        if not _usuario_valido(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo los usuarios con rol Cliente/Socio pueden reservar.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        input_serializer = self.get_serializer(data=request.data)
        if not input_serializer.is_valid():
            return Response(
                {'ok': False, 'errores': input_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        form = ReservarVehiculoForm(input_serializer.validated_data)
        if not form.is_valid():
            return Response(
                {'ok': False, 'errores': form.errors.get_json_data()},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reserva, mensaje_error = _crear_reserva_en_transaccion(
            usuario=request.user,
            vehiculo=form.cleaned_data['vehiculo'],
            fecha_inicio=form.cleaned_data['fecha_inicio'],
            fecha_fin=form.cleaned_data['fecha_fin'],
        )
        if mensaje_error:
            return Response(
                {'ok': False, 'mensaje': mensaje_error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ReservaSerializer(reserva, context=self.get_serializer_context())
        return Response(
            {'ok': True, 'mensaje': 'Reserva creada correctamente. Proceda al checkout.', 'reserva': serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        reserva = self.get_object()
        if reserva.cliente_id != request.user.id:
            return Response(
                {'ok': False, 'mensaje': 'No tienes permisos para eliminar esta reserva.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if _reserva_esta_cancelada(reserva):
            return Response(
                {'ok': True, 'mensaje': 'La reserva ya se encuentra cancelada.'},
                status=status.HTTP_200_OK,
            )

        hoy = timezone.localdate()
        if reserva.fecha_inicio <= hoy:
            return Response(
                {
                    'ok': False,
                    'mensaje': 'Solo puedes cancelar la reserva hasta un dia antes de la fecha de inicio.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reserva.estado_reserva = _obtener_estado('Cancelada')
        reserva.save(update_fields=['estado_reserva'])

        return Response(
            {'ok': True, 'mensaje': 'Reserva cancelada correctamente.', 'reserva': ReservaSerializer(reserva).data},
            status=status.HTTP_200_OK,
        )


class EstadoReservaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EstadoReserva.objects.all().order_by('id')
    serializer_class = EstadoReservaSerializer
    permission_classes = [IsAuthenticated]


class MetodoPagoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MetodoPago.objects.all().order_by('id')
    serializer_class = MetodoPagoSerializer
    permission_classes = [IsAuthenticated]


class FranquiciaTarjetaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FranquiciaTarjeta.objects.all().order_by('nombre')
    serializer_class = FranquiciaTarjetaSerializer
    permission_classes = [IsAuthenticated]


class PagoViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PagoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Pago.objects.select_related('metodo_pago', 'franquicia', 'reserva', 'reserva__cliente').filter(
            reserva__cliente=self.request.user
        ).order_by('-fecha_pago')

    def create(self, request, *args, **kwargs):
        """API endpoint para procesar pagos. Usa el patrón Strategy para validar y procesar."""
        reserva_id = request.data.get('reserva')
        metodo_pago_id = request.data.get('metodo_pago')
        datos_pago = request.data.get('datos_pago', {})

        if not reserva_id:
            return Response(
                {'ok': False, 'mensaje': 'Debes indicar una reserva para registrar el pago.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reserva = Reserva.objects.select_related('estado_reserva').get(id=reserva_id, cliente=request.user)
        except Reserva.DoesNotExist:
            return Response(
                {'ok': False, 'mensaje': 'Reserva no encontrada.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if _reserva_esta_cancelada(reserva):
            return Response(
                {'ok': False, 'mensaje': 'No se puede registrar un pago sobre una reserva cancelada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Pago.objects.filter(reserva=reserva).exists():
            return Response(
                {'ok': False, 'mensaje': 'La reserva ya tiene un pago registrado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Obtener método de pago
        try:
            metodo_pago = MetodoPago.objects.get(id=metodo_pago_id)
        except (MetodoPago.DoesNotExist, ValueError, TypeError):
            return Response(
                {'ok': False, 'mensaje': 'Debes indicar un metodo de pago valido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Obtener y usar la estrategia
        try:
            estrategia = obtener_estrategia_pago(metodo_pago.nombre)
        except ValueError as e:
            return Response(
                {'ok': False, 'mensaje': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validar datos de pago
        resultado_validacion = estrategia.validar_datos(datos_pago)
        if not resultado_validacion['valido']:
            return Response(
                {'ok': False, 'mensaje': 'Datos de pago inválidos.', 'errores': resultado_validacion['errores']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calcular monto final
        contexto_pago = ContextoPago(estrategia)
        monto_final = contexto_pago.ejecutar_estrategia(reserva.monto_total).quantize(Decimal('0.01'))

        # Procesar pago
        resultado_pago = contexto_pago.procesar_pago(datos_pago)
        if not resultado_pago['exito']:
            return Response(
                {'ok': False, 'mensaje': resultado_pago.get('mensaje')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Obtener franquicia si aplica
        franquicia_obj = None
        franquicia_id = datos_pago.get('franquicia_id')
        if franquicia_id:
            franquicia_obj = FranquiciaTarjeta.objects.filter(id=franquicia_id).first()

        detalle = resultado_pago.get('detalle', {})

        with transaction.atomic():
            pago = Pago.objects.create(
                reserva=reserva,
                metodo_pago=metodo_pago,
                comprobante_transaccion=resultado_pago['comprobante'],
                monto=monto_final,
                franquicia=franquicia_obj,
                nombre_titular=detalle.get('nombre_titular', datos_pago.get('titular_cuenta', '')),
                ultimos_4_digitos=detalle.get('ultimos_4_digitos', ''),
                metodo_detalle=detalle.get('cbu_cvu_parcial', ''),
            )

            estado_actual = reserva.estado_reserva.nombre.strip().lower() if reserva.estado_reserva else ''
            if estado_actual == 'pendiente':
                reserva.monto_total = monto_final
                reserva.estado_reserva = _obtener_estado('Confirmada')
                reserva.save(update_fields=['estado_reserva', 'monto_total'])

        mensaje_exito = f"{resultado_pago.get('mensaje', '')} Pago registrado correctamente."
        return Response(
            {'ok': True, 'mensaje': mensaje_exito.strip(), 'pago': PagoSerializer(pago).data},
            status=status.HTTP_201_CREATED,
        )
