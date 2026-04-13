import json

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .forms import ReservarVehiculoForm
from .models import EstadoReserva, Reserva
from usuarios.signals import ROLE_CLIENTE
from vehiculos.models import Vehiculo


# Vista para mostrar el formulario de reserva de vehículos. Esta vista renderiza una plantilla HTML que contiene el formulario para que los usuarios puedan seleccionar un vehículo, las fechas de inicio y fin de la reserva, y luego enviar la solicitud para crear una nueva reserva.
def reservar_view(request): 
    return render(request, 'reservas/reserva.html') # Método GET para mostrar el formulario de reserva. La plantilla 'reservas/reserva.html' debe contener el formulario que los usuarios utilizarán para ingresar los detalles de la reserva, como el vehículo que desean reservar y las fechas de inicio y fin de la reserva. Al enviar el formulario, se espera que se realice una solicitud POST a la vista crear_reserva_view para procesar la creación de la reserva.

# Función auxiliar para extraer el payload de la solicitud, ya sea desde el cuerpo de la solicitud JSON o desde los datos POST tradicionales. Esto permite que la vista crear_reserva_view pueda manejar solicitudes tanto con contenido JSON como con datos de formulario estándar.
def _payload_reserva(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            body = request.body.decode('utf-8') if request.body else '{}'
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    return request.POST

# Vista para crear una nueva reserva de vehículo. Esta vista maneja solicitudes POST, valida los datos recibidos utilizando el formulario ReservarVehiculoForm, verifica la disponibilidad del vehículo para las fechas solicitadas y, si todo es correcto, crea una nueva reserva en la base de datos. La respuesta se devuelve en formato JSON, indicando si la reserva fue creada exitosamente o si hubo algún error durante el proceso.
@require_POST
def crear_reserva_view(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {'ok': False, 'mensaje': 'Debes iniciar sesion para reservar.'},
            status=401,
        )

    if not request.user.groups.filter(name=ROLE_CLIENTE).exists():
        return JsonResponse(
            {'ok': False, 'mensaje': 'Solo los usuarios con rol Cliente pueden reservar.'},
            status=403,
        )

    payload = _payload_reserva(request)
    if payload is None:
        return JsonResponse(
            {'ok': False, 'mensaje': 'El cuerpo de la solicitud JSON es invalido.'},
            status=400,
        )

    form = ReservarVehiculoForm(payload)
    if not form.is_valid():
        return JsonResponse(
            {'ok': False, 'errores': form.errors.get_json_data()},
            status=400,
        )

    vehiculo = form.cleaned_data['vehiculo']
    fecha_inicio = form.cleaned_data['fecha_inicio']
    fecha_fin = form.cleaned_data['fecha_fin']

    if vehiculo.duenio_id == request.user.id:
        return JsonResponse(
            {'ok': False, 'mensaje': 'No puedes reservar un vehiculo propio.'},
            status=400,
        )
    # Utilizamos una transacción atómica para garantizar que la verificación de disponibilidad y la creación de la reserva se realicen de manera segura, evitando "condiciones de carrera". Al usar select_for_update() al consultar el vehículo, bloqueamos esa fila en la base de datos para otras transacciones hasta que se complete la transacción actual, lo que ayuda a prevenir que múltiples usuarios reserven el mismo vehículo para el mismo rango de fechas al mismo tiempo. Si el vehículo ya no está disponible o si hay un conflicto de fechas con una reserva existente, se devuelve una respuesta JSON indicando el error correspondiente.
    with transaction.atomic():
        vehiculo_bloqueado = Vehiculo.objects.select_for_update().filter(
            id=vehiculo.id,
            activo=True,
            esta_aprobado=True,
        ).first()

        if vehiculo_bloqueado is None:
            return JsonResponse(
                {'ok': False, 'mensaje': 'El vehiculo ya no esta disponible para reservar.'},
                status=400,
            )

        # Verificamos si existe alguna reserva en estados bloqueantes (Pendiente o Confirmada) que se solape con el vehículo y las fechas solicitadas. Si existe un conflicto, significa que alguien más ha reservado el vehículo para ese rango de fechas, por lo que se devuelve una respuesta JSON indicando que el vehículo no está disponible para esas fechas.
        existe_conflicto = Reserva.objects.con_solapamiento(
            vehiculo=vehiculo_bloqueado,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        ).exists()

        if existe_conflicto:
            return JsonResponse(
                {
                    'ok': False,
                    'mensaje': 'Alguien más rápido acaba de reservar este vehículo para esas fechas. Por favor, intenta con otro rango.',
                },
                status=400,
            )

        # Si no hay conflictos, procedemos a crear la reserva. Calculamos el monto total de la reserva multiplicando la cantidad de días por el precio por día del vehículo. Luego, creamos una nueva instancia de Reserva con los datos correspondientes, incluyendo el estado inicial de "Pendiente", el cliente que realiza la reserva y el vehículo reservado. Finalmente, devolvemos una respuesta JSON indicando que la reserva fue creada correctamente, junto con los detalles de la reserva recién creada.
        estado_pendiente, _ = EstadoReserva.objects.get_or_create(nombre='Pendiente')
        cantidad_dias = (fecha_fin - fecha_inicio).days
        monto_total = cantidad_dias * vehiculo_bloqueado.precio_x_dia

        # Al crear la reserva dentro de la transacción atómica y después de haber bloqueado el vehículo con select_for_update(), garantizamos que la reserva se cree de manera segura sin que otra transacción pueda interferir con el mismo vehículo y rango de fechas, evitando así posibles conflictos de reservas simultáneas.
        reserva = Reserva.objects.create(
            monto_total=monto_total,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            estado_reserva=estado_pendiente,
            cliente=request.user,
            vehiculo=vehiculo_bloqueado,
        )

    return JsonResponse(
        {
            'ok': True,
            'mensaje': 'Reserva creada correctamente.',
            'reserva': {
                'id': reserva.id,
                'vehiculo_id': reserva.vehiculo_id,
                'fecha_inicio': reserva.fecha_inicio.isoformat(),
                'fecha_fin': reserva.fecha_fin.isoformat(),
                'monto_total': str(reserva.monto_total),
                'estado': reserva.estado_reserva.nombre if reserva.estado_reserva else None,
            },
        },
        status=201,
    )
