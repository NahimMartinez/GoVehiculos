from django.conf import settings
from django.db import models
from vehiculos.models import Vehiculo

# Create your models here.
class EstadoReserva(models.Model):
    nombre = models.CharField(max_length=25)

class MetodoPago(models.Model):
    nombre = models.CharField(max_length=30)

class Reserva(models.Model):
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    fecha_reserva = models.DateTimeField(auto_now_add=True)

    #Relaciones
    estado_reserva = models.ForeignKey(EstadoReserva, on_delete=models.SET_NULL, null=True)
    cliente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.SET_NULL, null=True)

class Pago(models.Model):
    fecha_pago = models.DateTimeField(auto_now_add=True)
    comprobante_transaccion = models.CharField(max_length=100)

    #Relaciones
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.SET_NULL, null=True)
    reserva = models.ForeignKey(Reserva, on_delete=models.SET_NULL, null=True)

