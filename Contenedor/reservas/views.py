import json

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import ReservarVehiculoForm
from .models import EstadoReserva, MetodoPago, Pago, Reserva
from .serializer import (
    EstadoReservaSerializer,
    MetodoPagoSerializer,
    PagoSerializer,
    ReservaAdminWriteSerializer,
    ReservaCreateSerializer,
    ReservaSerializer,
)
from usuarios.signals import ROLE_CLIENTE
from vehiculos.models import Vehiculo


def reservar_view(request):
    return render(request, 'reservas/reserva.html')


def _usuario_es_cliente(user):
    return user.groups.filter(name=ROLE_CLIENTE).exists()


def _usuario_es_admin(user):
    return user.is_superuser or user.is_staff


def _obtener_estado(nombre_estado):
    estado, _ = EstadoReserva.objects.get_or_create(nombre=nombre_estado)
    return estado


def _reserva_esta_cancelada(reserva):
    if not reserva.estado_reserva:
        return False
    return reserva.estado_reserva.nombre.strip().lower() == 'cancelada'


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

        estado_pendiente = _obtener_estado('Pendiente')
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

    def get_serializer_class(self):
        if self.action == 'create':
            return ReservaCreateSerializer
        if self.action in ('update', 'partial_update'):
            return ReservaAdminWriteSerializer
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

    def update(self, request, *args, **kwargs):
        if not _usuario_es_admin(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo administradores pueden editar reservas.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not _usuario_es_admin(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo administradores pueden editar reservas.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        reserva = self.get_object()
        es_admin = _usuario_es_admin(request.user)

        if not es_admin and reserva.cliente_id != request.user.id:
            return Response(
                {'ok': False, 'mensaje': 'No tienes permisos para eliminar esta reserva.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if _reserva_esta_cancelada(reserva):
            return Response(
                {'ok': True, 'mensaje': 'La reserva ya se encuentra cancelada.'},
                status=status.HTTP_200_OK,
            )

        if not es_admin:
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


class EstadoReservaViewSet(viewsets.ModelViewSet):
    queryset = EstadoReserva.objects.all().order_by('id')
    serializer_class = EstadoReservaSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        if not _usuario_es_admin(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo administradores pueden crear estados.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not _usuario_es_admin(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo administradores pueden editar estados.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not _usuario_es_admin(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo administradores pueden editar estados.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not _usuario_es_admin(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo administradores pueden eliminar estados.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


class MetodoPagoViewSet(viewsets.ModelViewSet):
    queryset = MetodoPago.objects.all().order_by('id')
    serializer_class = MetodoPagoSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        if not _usuario_es_admin(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo administradores pueden crear metodos de pago.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not _usuario_es_admin(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo administradores pueden editar metodos de pago.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not _usuario_es_admin(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo administradores pueden editar metodos de pago.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not _usuario_es_admin(request.user):
            return Response(
                {'ok': False, 'mensaje': 'Solo administradores pueden eliminar metodos de pago.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


class PagoViewSet(viewsets.ModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Pago.objects.select_related('metodo_pago', 'reserva', 'reserva__cliente').order_by('-fecha_pago')

        if _usuario_es_admin(self.request.user):
            return queryset

        return queryset.filter(reserva__cliente=self.request.user)

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

        if not _usuario_es_admin(request.user) and reserva.cliente_id != request.user.id:
            return Response(
                {'ok': False, 'mensaje': 'No puedes registrar pagos para reservas de otro usuario.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            pago = serializer.save()

            estado_actual = reserva.estado_reserva.nombre.strip().lower() if reserva.estado_reserva else ''
            if estado_actual == 'pendiente':
                reserva.estado_reserva = _obtener_estado('Confirmada')
                reserva.save(update_fields=['estado_reserva'])

        return Response(
            {'ok': True, 'mensaje': 'Pago registrado correctamente.', 'pago': PagoSerializer(pago).data},
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        pago = self.get_object()
        if not _usuario_es_admin(request.user):
            if pago.reserva is None or pago.reserva.cliente_id != request.user.id:
                return Response(
                    {'ok': False, 'mensaje': 'No tienes permisos para editar este pago.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = self.get_serializer(pago, data=request.data)
        if not serializer.is_valid():
            return Response(
                {'ok': False, 'errores': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reserva_destino = serializer.validated_data.get('reserva', pago.reserva)
        if not _usuario_es_admin(request.user):
            if reserva_destino is None or reserva_destino.cliente_id != request.user.id:
                return Response(
                    {'ok': False, 'mensaje': 'No puedes asociar el pago a una reserva de otro usuario.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        pago = self.get_object()
        if not _usuario_es_admin(request.user):
            if pago.reserva is None or pago.reserva.cliente_id != request.user.id:
                return Response(
                    {'ok': False, 'mensaje': 'No tienes permisos para editar este pago.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = self.get_serializer(pago, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {'ok': False, 'errores': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reserva_destino = serializer.validated_data.get('reserva', pago.reserva)
        if not _usuario_es_admin(request.user):
            if reserva_destino is None or reserva_destino.cliente_id != request.user.id:
                return Response(
                    {'ok': False, 'mensaje': 'No puedes asociar el pago a una reserva de otro usuario.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        pago = self.get_object()
        if not _usuario_es_admin(request.user):
            if pago.reserva is None or pago.reserva.cliente_id != request.user.id:
                return Response(
                    {'ok': False, 'mensaje': 'No tienes permisos para eliminar este pago.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return super().destroy(request, *args, **kwargs)
