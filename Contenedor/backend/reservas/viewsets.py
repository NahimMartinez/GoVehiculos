from datetime import time

from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import ReservarVehiculoForm
from .views_resevas import HORAS_ANTELACION_CANCELACION, _crear_reserva_en_transaccion, _obtener_estado, _reserva_tiene_estado, _usuario_valido
from .views_pago import _crear_reembolso_reserva, _procesar_pago_reserva
from .models import EstadoReserva, FranquiciaTarjeta, MetodoPago, Pago, Reserva
from .serializer import (
    EstadoReservaSerializer,
    FranquiciaTarjetaSerializer,
    MetodoPagoSerializer,
    PagoSerializer,
    ReservaCreateSerializer,
    ReservaSerializer,
)


class ReservaViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """ViewSet para gestionar las reservas a través de la API REST."""
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

        if _reserva_tiene_estado(reserva, 'Cancelada'):
            return Response(
                {'ok': True, 'mensaje': 'La reserva ya se encuentra cancelada.'},
                status=status.HTTP_200_OK,
            )

        if _reserva_tiene_estado(reserva, 'Confirmada'):
            horas_restantes = (
                timezone.datetime.combine(reserva.fecha_inicio, time.min, tzinfo=timezone.get_current_timezone())
                - timezone.now()
            ).total_seconds() / 3600

            if horas_restantes < HORAS_ANTELACION_CANCELACION:
                return Response(
                    {
                        'ok': False,
                        'mensaje': f'Solo puedes cancelar la reserva hasta {HORAS_ANTELACION_CANCELACION} horas antes de la fecha de inicio.',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                reserva.estado_reserva = _obtener_estado('Cancelada')
                reserva.save(update_fields=['estado_reserva'])
                reembolso = _crear_reembolso_reserva(reserva)

            data = {'ok': True, 'mensaje': 'Reserva cancelada correctamente.', 'reserva': ReservaSerializer(reserva).data}
            if reembolso:
                data['reembolso'] = {
                    'monto': str(reembolso.monto),
                    'comprobante': reembolso.comprobante_transaccion,
                }
            return Response(data, status=status.HTTP_200_OK)

        reserva.estado_reserva = _obtener_estado('Cancelada')
        reserva.save(update_fields=['estado_reserva'])

        return Response(
            {'ok': True, 'mensaje': 'Reserva cancelada correctamente.', 'reserva': ReservaSerializer(reserva).data},
            status=status.HTTP_200_OK,
        )


class EstadoReservaViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint para listar los posibles estados de una reserva (solo lectura)."""
    queryset = EstadoReserva.objects.all().order_by('id')
    serializer_class = EstadoReservaSerializer
    permission_classes = [IsAuthenticated]


class MetodoPagoViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint para obtener los métodos de pago disponibles (solo lectura)."""
    queryset = MetodoPago.objects.all().order_by('id')
    serializer_class = MetodoPagoSerializer
    permission_classes = [IsAuthenticated]


class FranquiciaTarjetaViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint para obtener las franquicias de tarjeta de crédito soportadas (solo lectura)."""
    queryset = FranquiciaTarjeta.objects.all().order_by('nombre')
    serializer_class = FranquiciaTarjetaSerializer
    permission_classes = [IsAuthenticated]


class PagoViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """ViewSet para manejar pagos de reservas a través de la API REST."""
    serializer_class = PagoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Pago.objects.select_related('metodo_pago', 'franquicia', 'reserva', 'reserva__cliente').filter(
            reserva__cliente=self.request.user
        ).order_by('-fecha_pago')

    def create(self, request, *args, **kwargs):
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

        if _reserva_tiene_estado(reserva, 'Cancelada'):
            return Response(
                {'ok': False, 'mensaje': 'No se puede registrar un pago sobre una reserva cancelada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Pago.objects.filter(reserva=reserva).exists():
            return Response(
                {'ok': False, 'mensaje': 'La reserva ya tiene un pago registrado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            metodo_pago = MetodoPago.objects.get(id=metodo_pago_id)
        except (MetodoPago.DoesNotExist, ValueError, TypeError):
            return Response(
                {'ok': False, 'mensaje': 'Debes indicar un metodo de pago valido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        franquicia_id = datos_pago.get('franquicia_id')

        pago, monto_final, resultado_pago, error = _procesar_pago_reserva(
            reserva, metodo_pago.nombre, datos_pago, franquicia_id,
        )

        if error:
            return Response(error, status=status.HTTP_400_BAD_REQUEST)

        mensaje_exito = f"{resultado_pago.get('mensaje', '')} Pago registrado correctamente."
        return Response(
            {'ok': True, 'mensaje': mensaje_exito.strip(), 'pago': PagoSerializer(pago).data},
            status=status.HTTP_201_CREATED,
        )
