from rest_framework import serializers

from .models import EstadoReserva, MetodoPago, Pago, Reserva


class EstadoReservaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoReserva
        fields = ('id', 'nombre')


class MetodoPagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetodoPago
        fields = ('id', 'nombre')


class ReservaCreateSerializer(serializers.Serializer):
    vehiculo_id = serializers.IntegerField(min_value=1)
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()


class ReservaAdminWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reserva
        fields = ('id', 'estado_reserva', 'monto_total', 'fecha_inicio', 'fecha_fin', 'cliente', 'vehiculo')


class ReservaSerializer(serializers.ModelSerializer):
    estado = serializers.CharField(source='estado_reserva.nombre', read_only=True)
    estado_reserva_id = serializers.IntegerField(source='estado_reserva.id', read_only=True)
    vehiculo_id = serializers.IntegerField(source='vehiculo.id', read_only=True)
    cliente_id = serializers.IntegerField(source='cliente.id', read_only=True)

    class Meta:
        model = Reserva
        fields = (
            'id',
            'vehiculo_id',
            'cliente_id',
            'fecha_inicio',
            'fecha_fin',
            'fecha_reserva',
            'monto_total',
            'estado',
            'estado_reserva_id',
        )


class PagoSerializer(serializers.ModelSerializer):
    metodo_pago_nombre = serializers.CharField(source='metodo_pago.nombre', read_only=True)

    class Meta:
        model = Pago
        fields = ('id', 'fecha_pago', 'comprobante_transaccion', 'metodo_pago', 'metodo_pago_nombre', 'reserva')
        read_only_fields = ('fecha_pago',)
