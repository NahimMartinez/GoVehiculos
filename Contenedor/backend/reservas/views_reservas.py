import json
from datetime import time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from usuarios.signals import ROLE_CLIENTE, ROLE_SOCIO
from vehiculos.models import Vehiculo

from .forms import ReservarVehiculoForm
from .models import EstadoReserva, Pago, Reserva

# =====================================================================
# CONSTANTES
# =====================================================================
CHECKOUT_TIMEOUT_MINUTOS = 30
HORAS_ANTELACION_CANCELACION = 24



def _usuario_valido(user):
    """Verifica si un usuario es apto para reservar (debe pertenecer a grupo Cliente o Socio)."""
    return user.groups.filter(name__in=[ROLE_CLIENTE, ROLE_SOCIO]).exists()


def _obtener_estado(nombre_estado):
    """Obtiene el estado de reserva por nombre y lo crea si aún no existe en el catálogo."""
    estado = EstadoReserva.objects.filter(nombre=nombre_estado).order_by('id').first()
    if estado is None:
        estado = EstadoReserva.objects.create(nombre=nombre_estado)
    return estado


def _reserva_tiene_estado(reserva, nombre_estado):
    """Verifica si la reserva tiene un estado específico (comparación case-insensitive)."""
    if not reserva.estado_reserva:
        return False
    return reserva.estado_reserva.nombre.strip().lower() == nombre_estado.strip().lower()


def _reserva_ya_vencio(reserva):
    """Comprueba si la reserva ya superó su fecha de fin comparándola con la fecha actual."""
    return reserva.fecha_fin < timezone.localdate()


def _finalizar_reservas_vencidas(reservas_qs):
    """Actualiza masivamente el estado a 'Finalizada' para reservas vencidas."""
    estado_finalizada = _obtener_estado('Finalizada')
    return reservas_qs.filter(fecha_fin__lt=timezone.localdate()).exclude(
        estado_reserva__nombre__iexact='Cancelada',
    ).exclude(
        estado_reserva__nombre__iexact='Finalizada',
    ).update(estado_reserva=estado_finalizada)


def _cancelar_reservas_pendientes_expiradas(reservas_qs):
    """Cancela masivamente las reservas pendientes cuyo plazo de checkout ya expiró."""
    estado_cancelada = _obtener_estado('Cancelada')
    ahora = timezone.now()
    return reservas_qs.filter(
        estado_reserva__nombre__iexact='Pendiente',
        checkout_expira_en__isnull=False,
        checkout_expira_en__lt=ahora,
    ).update(estado_reserva=estado_cancelada)


def _solicitud_prefiere_json(request):
    """Verifica si la solicitud entrante indica preferencia por una respuesta JSON."""
    return bool(request.content_type and 'application/json' in request.content_type)


def _payload_reserva(request):
    """Extrae los datos de la solicitud desde JSON o desde POST tradicional."""
    if request.content_type and 'application/json' in request.content_type:
        try:
            body = request.body.decode('utf-8') if request.body else '{}'
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
    return request.POST


def _reserva_a_dict(reserva):
    """Convierte una instancia de Reserva en un diccionario serializable para JSON."""
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


def _contexto_reserva_base(request, *, vehiculo_seleccionado=None, datos_formulario=None, reserva=None, mensaje_reserva=None, tipo_reserva=None, errores=None):
    """Construye el contexto base para renderizar la plantilla HTML de reservas."""
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


def _respuesta_reserva(request, *, ok, mensaje, status_code, reserva=None, errores=None, datos_formulario=None, vehiculo_seleccionado=None):
    """Retorna JSON o HTML según la preferencia de la solicitud."""
    if _solicitud_prefiere_json(request):
        payload = {'ok': ok, 'mensaje': mensaje}
        if reserva is not None:
            payload['reserva'] = reserva
        if errores:
            payload['errores'] = errores
        return JsonResponse(payload, status=status_code)

    contexto = _contexto_reserva_base(
        request,
        vehiculo_seleccionado=vehiculo_seleccionado,
        datos_formulario=datos_formulario,
        reserva=reserva,
        mensaje_reserva=mensaje,
        tipo_reserva='success' if ok else 'error',
        errores=errores,
    )
    return render(request, 'reservas/reserva.html', contexto, status=status_code)


def _crear_reserva_en_transaccion(usuario, vehiculo, fecha_inicio, fecha_fin):
    """Crea una reserva con transacción atómica y bloqueo de vehículo."""
    if vehiculo.duenio_id == usuario.id:
        return None, 'No puedes reservar un vehiculo propio.'

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

        conflicto_cliente = Reserva.objects.con_solapamiento_cliente(
            cliente=usuario,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        ).exists()

        if conflicto_cliente:
            return (
                None,
                'Ya tienes una reserva activa en este rango de fechas. Solo puedes reservar un vehiculo a la vez.',
            )

        cantidad_dias = (fecha_fin - fecha_inicio).days
        reservas_activas = Reserva.objects.en_estados_bloqueantes().filter(cliente=usuario)
        dias_acumulados = sum((res.fecha_fin - res.fecha_inicio).days for res in reservas_activas)

        if dias_acumulados + cantidad_dias > 30:
            return (
                None,
                'No puedes exceder el límite máximo de 30 días totales de reserva.',
            )

        estado_pendiente = _obtener_estado('Pendiente')
        monto_base = cantidad_dias * vehiculo_bloqueado.precio_x_dia

        reserva = Reserva.objects.create(
            monto_total=Decimal(str(monto_base)).quantize(Decimal('0.01')),
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            estado_reserva=estado_pendiente,
            cliente=usuario,
            vehiculo=vehiculo_bloqueado,
            checkout_expira_en=timezone.now() + timedelta(minutes=CHECKOUT_TIMEOUT_MINUTOS),
        )

    return reserva, None


# =====================================================================
# VIEWS
# =====================================================================

def detalle_reserva_view(request, reserva_id):
    """GET: Muestra todos los detalles de una reserva."""
    if not request.user.is_authenticated:
        return redirect('login')

    reserva = get_object_or_404(
        Reserva.objects.select_related('estado_reserva', 'vehiculo', 'vehiculo__modelo', 'vehiculo__modelo__marca', 'cliente'),
        id=reserva_id, cliente=request.user,
    )

    pago = Pago.objects.select_related('metodo_pago', 'franquicia', 'reembolso').filter(reserva=reserva).first()

    contexto = {
        'reserva': reserva,
        'pago': pago,
        'usuario': request.user,
    }

    return render(request, 'reservas/detalle_reserva.html', contexto)

def obtener_reservas_usuario_view(request):
    """
    Vista que obtiene y muestra las reservas del usuario actual.
    Separa las reservas en 'activas' (pendientes o confirmadas) y el 'historial'
    (las que ya finalizaron o fueron canceladas).
    """
    reservas_usuario = Reserva.objects.filter(cliente=request.user)
    _finalizar_reservas_vencidas(reservas_usuario)
    _cancelar_reservas_pendientes_expiradas(reservas_usuario)

    reservas = Reserva.objects.select_related(
        'estado_reserva', 'vehiculo', 'vehiculo__modelo', 'vehiculo__modelo__marca'
    ).filter(cliente=request.user).order_by('-fecha_reserva')

    activos = reservas.filter(Q(estado_reserva__nombre__iexact='Pendiente') | Q(estado_reserva__nombre__iexact='Confirmada'))
    historial = reservas.exclude(id__in=activos.values_list('id', flat=True))

    contexto = {
        'activos': activos,
        'historial': historial,
    }

    return render(request, 'reservas/mis_reservas.html', contexto)


def reservar_view(request):
    """GET: Muestra el formulario de reserva de vehículo."""
    mensaje_reserva = None

    if not request.user.is_authenticated:
        mensaje_reserva = 'Debes iniciar sesion para reservar.'
    elif not _usuario_valido(request.user):
        mensaje_reserva = 'Solo los usuarios con rol Cliente/Socio pueden reservar.'

    contexto = _contexto_reserva_base(request, mensaje_reserva=mensaje_reserva)
    return render(request, 'reservas/reserva.html', contexto)


@require_POST
def crear_reserva_view(request):
    """Procesa la creación de una nueva reserva desde HTML o JSON."""
    if not request.user.is_authenticated:
        return _respuesta_reserva(request, ok=False, mensaje='Debes iniciar sesion para reservar.', status_code=401)

    if not _usuario_valido(request.user):
        return _respuesta_reserva(request, ok=False, mensaje='Solo los usuarios con rol Cliente/Socio pueden reservar.', status_code=403)

    payload = _payload_reserva(request)
    if payload is None:
        return _respuesta_reserva(request, ok=False, mensaje='El cuerpo de la solicitud es invalido.', status_code=400)

    form = ReservarVehiculoForm(payload)
    if not form.is_valid():
        return _respuesta_reserva(
            request,
            ok=False,
            mensaje='Revisa los campos del formulario.',
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

    return redirect('checkout', reserva_id=reserva.id)


def cancelar_reserva_view(request, reserva_id):
    """Cancela una reserva existente siguiendo la política de estado y antelación."""
    if request.method == 'POST':
        reserva = get_object_or_404(Reserva, id=reserva_id, cliente=request.user)

        if _reserva_ya_vencio(reserva):
            if not _reserva_tiene_estado(reserva, 'Finalizada'):
                reserva.estado_reserva = _obtener_estado('Finalizada')
                reserva.save(update_fields=['estado_reserva'])
            messages.error(request, 'Esta reserva ya finalizó, por lo que no se puede cancelar.')
            return redirect('mis_reservas')

        if _reserva_tiene_estado(reserva, 'Pendiente'):
            reserva.estado_reserva = _obtener_estado('Cancelada')
            reserva.save(update_fields=['estado_reserva'])
            messages.success(request, f'La reserva de {reserva.vehiculo.modelo} fue cancelada correctamente.')
            return redirect('mis_reservas')

        if _reserva_tiene_estado(reserva, 'Confirmada'):
            horas_restantes = (
                timezone.datetime.combine(reserva.fecha_inicio, time.min, tzinfo=timezone.get_current_timezone())
                - timezone.now()
            ).total_seconds() / 3600

            if horas_restantes < HORAS_ANTELACION_CANCELACION:
                messages.error(
                    request,
                    f'No se puede cancelar esta reserva. La politica de cancelacion requiere '
                    f'al menos {HORAS_ANTELACION_CANCELACION} horas de antelacion antes del inicio.'
                )
                return redirect('mis_reservas')

            reserva.estado_reserva = _obtener_estado('Cancelada')
            reserva.save(update_fields=['estado_reserva'])
            
            messages.success(request, f'La reserva de {reserva.vehiculo.modelo} fue cancelada correctamente.')
            return redirect('mis_reservas')

        messages.error(request, 'Esta reserva no se puede cancelar en su estado actual.')

    return redirect('mis_reservas')
