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

from .forms import ReservarVehiculoForm
from .models import EstadoReserva, MetodoPago, Pago, Reserva
from .serializer import (
    EstadoReservaSerializer,
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
        'metodos': obtener_metodos_de_pago(),
    }

    return render(request, 'reservas/mis_reservas.html', contexto)

def obtener_metodos_de_pago():
    return MetodoPago.objects.all()

# Método GET para mostrar el formulario de reserva de vehículo. Esta vista renderiza una plantilla HTML que contiene el formulario para que los usuarios puedan ingresar los detalles de su reserva, como el vehículo que desean reservar, las fechas de inicio y fin, etc. La plantilla 'reservas/reserva.html' se encargará de mostrar el formulario y manejar la interacción del usuario para enviar la solicitud de reserva.
def reservar_view(request):
    usuario = request.user
    metodos = obtener_metodos_de_pago()
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
        'metodos': metodos,
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

        # Lógica de las 24 horas
        # Como fecha_inicio es un DateField, lo convertimos a DateTime (asumiendo que el día empieza a las 00:00)
        fecha_inicio_dt = timezone.make_aware(datetime.combine(reserva.fecha_inicio, time.min))
        ahora = timezone.now()
        
        tiempo_restante = fecha_inicio_dt - ahora
        
        # Validamos y ejecutamos
        if tiempo_restante >= timedelta(hours=24):
            reserva.estado_reserva = estado_cancelada
            reserva.save()
            messages.success(request, f'La reserva de {reserva.vehiculo.modelo} fue cancelada correctamente.')
        else:
            messages.error(request, 'Solo podés cancelar una reserva con al menos 24 horas de anticipación.')
            
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


def _crear_reserva_en_transaccion(usuario, vehiculo, fecha_inicio, fecha_fin, metodo_pago_estrategia):
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

        # Calculamos el monto total de la reserva multiplicando la cantidad de días por el precio por día del vehículo. Esto nos da el costo total que el cliente deberá pagar por la reserva, lo que es esencial para el proceso de pago y para mostrar al cliente el costo de su reserva antes de confirmarla.
        monto_base = cantidad_dias * vehiculo_bloqueado.precio_x_dia
        contexto_pago = ContextoPago(metodo_pago_estrategia)
        monto_total = contexto_pago.ejecutar_estrategia(monto_base).quantize(Decimal('0.01'))

        reserva = Reserva.objects.create(
            monto_total=monto_total,
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
        'metodos': obtener_metodos_de_pago(),
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
    metodo_pago_nombre = form.cleaned_data['metodo_pago_nombre']
    metodo_pago_estrategia = form.cleaned_data['metodo_pago_estrategia']
    reserva, mensaje_error = _crear_reserva_en_transaccion(
        usuario=request.user,
        vehiculo=vehiculo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        metodo_pago_estrategia=metodo_pago_estrategia,
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
            mensaje='Reserva creada correctamente.',
            status_code=201,
            reserva=_reserva_a_dict(reserva),
            vehiculo_seleccionado=vehiculo,
        )

    messages.success(request, 'Reserva creada correctamente.')
    return redirect('inicio')


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
            metodo_pago_estrategia=form.cleaned_data['metodo_pago_estrategia'],
        )
        if mensaje_error:
            return Response(
                {'ok': False, 'mensaje': mensaje_error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ReservaSerializer(reserva, context=self.get_serializer_context())
        return Response(
            {'ok': True, 'mensaje': 'Reserva creada correctamente.', 'reserva': serializer.data},
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


class PagoViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PagoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Pago.objects.select_related('metodo_pago', 'reserva', 'reserva__cliente').filter(
            reserva__cliente=self.request.user
        ).order_by('-fecha_pago')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'ok': False, 'errores': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reserva = serializer.validated_data.get('reserva')
        metodo_pago = serializer.validated_data.get('metodo_pago')
        if reserva is None:
            return Response(
                {'ok': False, 'mensaje': 'Debes indicar una reserva para registrar el pago.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if metodo_pago is None:
            return Response(
                {'ok': False, 'mensaje': 'Debes indicar un metodo de pago valido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if _reserva_esta_cancelada(reserva):
            return Response(
                {'ok': False, 'mensaje': 'No se puede registrar un pago sobre una reserva cancelada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if reserva.cliente_id != request.user.id:
            return Response(
                {'ok': False, 'mensaje': 'No puedes registrar pagos para reservas de otro usuario.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if Pago.objects.filter(reserva=reserva).exists():
            return Response(
                {'ok': False, 'mensaje': 'La reserva ya tiene un pago registrado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Regla de las 24 horas
        fecha_inicio_dt = timezone.make_aware(datetime.combine(reserva.fecha_inicio, time.min))
        ahora = timezone.now()
        tiempo_restante = fecha_inicio_dt - ahora

        if tiempo_restante < timedelta(hours=24):
            estado_cancelada = _obtener_estado('Cancelada')
            reserva.estado_reserva = estado_cancelada
            reserva.save(update_fields=['estado_reserva'])
            return Response(
                {'ok': False, 'mensaje': 'El tiempo para pagar expiró. Debías pagar con al menos 24 horas de anticipación. La reserva ha sido cancelada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Si estamos a tiempo, aplicamos la estrategia para simular/procesar el pago
        try:
            estrategia = obtener_estrategia_pago(metodo_pago.nombre)
        except ValueError as e:
            return Response(
                {'ok': False, 'mensaje': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contexto_pago = ContextoPago(estrategia)
        datos_pago = request.data.get('datos_pago', {})
        resultado_pago = contexto_pago.procesar_pago(datos_pago)

        if not resultado_pago.get('exito'):
            return Response(
                {'ok': False, 'mensaje': resultado_pago.get('mensaje')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            pago = serializer.save()

            estado_actual = reserva.estado_reserva.nombre.strip().lower() if reserva.estado_reserva else ''
            if estado_actual == 'pendiente':
                reserva.estado_reserva = _obtener_estado('Confirmada')
                reserva.save(update_fields=['estado_reserva'])

        mensaje_exito = f"{resultado_pago.get('mensaje', '')} Pago registrado correctamente."
        return Response(
            {'ok': True, 'mensaje': mensaje_exito.strip(), 'pago': PagoSerializer(pago).data},
            status=status.HTTP_201_CREATED,
        )
