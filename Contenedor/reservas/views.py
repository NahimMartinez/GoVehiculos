import json

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import ReservarVehiculoForm
from .models import EstadoReserva, Reserva
from .serializer import ReservaCreateSerializer, ReservaSerializer
from usuarios.signals import ROLE_CLIENTE
from vehiculos.models import Vehiculo


def reservar_view(request):
    return render(request, 'reservas/reserva.html')


def _usuario_es_cliente(user):
    return user.groups.filter(name=ROLE_CLIENTE).exists()


def _reserva_a_dict(reserva):
    return {
        'id': reserva.id,
        'vehiculo_id': reserva.vehiculo_id,
        'cliente_id': reserva.cliente_id,
        'fecha_inicio': reserva.fecha_inicio.isoformat(),
        'fecha_fin': reserva.fecha_fin.isoformat(),
        'monto_total': str(reserva.monto_total),
        'estado': reserva.estado_reserva.nombre if reserva.estado_reserva else None,
        'fecha_reserva': reserva.fecha_reserva.isoformat(),
    }


def _crear_reserva_en_transaccion(usuario, vehiculo, fecha_inicio, fecha_fin):
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
                'Alguien mas rapido acaba de reservar este vehiculo para esas fechas. Por favor, intenta con otro rango.',
            )

        estado_pendiente, _ = EstadoReserva.objects.get_or_create(nombre='Pendiente')
        cantidad_dias = (fecha_fin - fecha_inicio).days
        monto_total = cantidad_dias * vehiculo_bloqueado.precio_x_dia

        reserva = Reserva.objects.create(
            monto_total=monto_total,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            estado_reserva=estado_pendiente,
            cliente=usuario,
            vehiculo=vehiculo_bloqueado,
        )

    return reserva, None


def _payload_reserva(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            body = request.body.decode('utf-8') if request.body else '{}'
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    return request.POST


@require_POST
def crear_reserva_view(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {'ok': False, 'mensaje': 'Debes iniciar sesion para reservar.'},
            status=401,
        )

    if not _usuario_es_cliente(request.user):
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
    reserva, mensaje_error = _crear_reserva_en_transaccion(
        usuario=request.user,
        vehiculo=vehiculo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    if mensaje_error:
        return JsonResponse(
            {'ok': False, 'mensaje': mensaje_error},
            status=400,
        )

    return JsonResponse(
        {
            'ok': True,
            'mensaje': 'Reserva creada correctamente.',
            'reserva': _reserva_a_dict(reserva),
        },
        status=201,
    )


class ReservaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return ReservaCreateSerializer
        return ReservaSerializer

    def get_queryset(self):
        queryset = Reserva.objects.select_related('estado_reserva', 'vehiculo', 'cliente').order_by('-fecha_reserva')

        if self.request.user.is_superuser or self.request.user.is_staff:
            return queryset

        return queryset.filter(cliente=self.request.user)

    def create(self, request, *args, **kwargs):
        if not _usuario_es_cliente(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo los usuarios con rol Cliente pueden reservar.'},
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
            {'ok': True, 'mensaje': 'Reserva creada correctamente.', 'reserva': serializer.data},
            status=status.HTTP_201_CREATED,
        )
