from rest_framework import serializers

from .models import Reserva


class ReservaCreateSerializer(serializers.Serializer):
    vehiculo_id = serializers.IntegerField(min_value=1)
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()


class ReservaSerializer(serializers.ModelSerializer):
    estado = serializers.CharField(source='estado_reserva.nombre', read_only=True)
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
        )
