import json
from decimal import Decimal

from django.db import transaction

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .estrategias import ContextoPago, obtener_estrategia_pago
from .models import FranquiciaTarjeta, MetodoPago, Pago, Reserva
from .views_reservas import _obtener_estado, _reserva_tiene_estado


def _procesar_pago_reserva(reserva, metodo_pago_nombre, datos_pago, franquicia_id=None):
    """Procesa un pago de reserva usando la estrategia configurada."""
    try:
        estrategia = obtener_estrategia_pago(metodo_pago_nombre)
    except ValueError as e:
        return None, None, None, {'ok': False, 'mensaje': str(e)}

    if franquicia_id:
        datos_pago['franquicia_id'] = franquicia_id

    resultado_validacion = estrategia.validar_datos(datos_pago)
    if not resultado_validacion['valido']:
        return None, None, None, {
            'ok': False,
            'mensaje': 'Revisa los datos de pago.',
            'errores': resultado_validacion['errores'],
        }

    contexto_pago = ContextoPago(estrategia)
    monto_final = contexto_pago.ejecutar_estrategia(reserva.monto_total).quantize(Decimal('0.01'))
    resultado_pago = contexto_pago.procesar_pago(datos_pago)

    if not resultado_pago['exito']:
        return None, None, None, {'ok': False, 'mensaje': resultado_pago['mensaje']}

    metodo_pago_obj = MetodoPago.objects.filter(nombre__iexact=metodo_pago_nombre).first()
    if not metodo_pago_obj:
        metodo_pago_obj = MetodoPago.objects.create(nombre=metodo_pago_nombre)

    franquicia_obj = None
    detalle = resultado_pago.get('detalle', {})
    if franquicia_id:
        franquicia_obj = FranquiciaTarjeta.objects.filter(id=franquicia_id).first()

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

        reserva.monto_total = monto_final
        reserva.estado_reserva = _obtener_estado('Confirmada')
        reserva.save(update_fields=['estado_reserva', 'monto_total'])

    return pago, monto_final, resultado_pago, None





# =====================================================================
# VISTAS DE CHECKOUT Y PAGO
# =====================================================================

def checkout_view(request, reserva_id):
    """GET: Renderiza la página de checkout con la info de la reserva y los métodos de pago."""
    if not request.user.is_authenticated:
        return redirect('login')

    reserva = get_object_or_404(
        Reserva.objects.select_related('estado_reserva', 'vehiculo', 'vehiculo__modelo', 'vehiculo__modelo__marca', 'cliente'),
        id=reserva_id, cliente=request.user,
    )

    if not _reserva_tiene_estado(reserva, 'Pendiente'):
        messages.error(request, 'Esta reserva no esta pendiente de pago.')
        return redirect('mis_reservas')

    if reserva.checkout_expira_en and timezone.now() > reserva.checkout_expira_en:
        reserva.estado_reserva = _obtener_estado('Cancelada')
        reserva.save(update_fields=['estado_reserva'])
        messages.error(request, 'El tiempo para completar el pago ha expirado. La reserva fue cancelada automaticamente.')
        return redirect('mis_reservas')

    metodos = MetodoPago.objects.all()
    franquicias = FranquiciaTarjeta.objects.all().order_by('nombre')

    franquicias_data = [{'id': f.id, 'nombre': f.nombre, 'tipo': f.tipo} for f in franquicias]

    segundos_restantes = 0
    if reserva.checkout_expira_en:
        delta = reserva.checkout_expira_en - timezone.now()
        segundos_restantes = max(0, int(delta.total_seconds()))

    contexto = {
        'reserva': reserva,
        'metodos': metodos,
        'franquicias': franquicias,
        'franquicias_json': json.dumps(franquicias_data),
        'usuario': request.user,
        'segundos_restantes': segundos_restantes,
    }

    return render(request, 'reservas/checkout.html', contexto)


@require_POST
def procesar_checkout_view(request, reserva_id):
    """POST: Procesa el pago del checkout usando el patrón Strategy."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'mensaje': 'Debes iniciar sesion.'}, status=401)

    reserva = get_object_or_404(
        Reserva.objects.select_related('estado_reserva', 'vehiculo', 'cliente'),
        id=reserva_id, cliente=request.user,
    )

    if not _reserva_tiene_estado(reserva, 'Pendiente'):
        return JsonResponse({'ok': False, 'mensaje': 'Esta reserva no esta pendiente de pago.'}, status=400)

    if reserva.checkout_expira_en and timezone.now() > reserva.checkout_expira_en:
        reserva.estado_reserva = _obtener_estado('Cancelada')
        reserva.save(update_fields=['estado_reserva'])
        return JsonResponse({
            'ok': False,
            'mensaje': 'El tiempo para completar el pago ha expirado. La reserva fue cancelada.',
        }, status=400)

    try:
        body = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'mensaje': 'Datos de solicitud invalidos.'}, status=400)

    metodo_pago_nombre = body.get('metodo_pago_nombre', '')
    datos_pago = body.get('datos_pago', {})
    franquicia_id = body.get('franquicia_id') or datos_pago.get('franquicia_id')

    pago, monto_final, resultado_pago, error = _procesar_pago_reserva(
        reserva, metodo_pago_nombre, datos_pago, franquicia_id,
    )

    if error:
        return JsonResponse(error, status=400)

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

    if _reserva_tiene_estado(reserva, 'Pendiente'):
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
        id=reserva_id, cliente=request.user,
    )

    pago = Pago.objects.select_related('metodo_pago', 'franquicia').filter(reserva=reserva).first()

    contexto = {
        'reserva': reserva,
        'pago': pago,
        'usuario': request.user,
    }

    return render(request, 'reservas/checkout_exitoso.html', contexto)



