from django.conf import settings
from django.db import models
from django.db.models import Q
from vehiculos.models import Vehiculo

# Create your models here.
class EstadoReserva(models.Model):
    nombre = models.CharField(max_length=25, unique=True)

    def __str__(self):
        return self.nombre

class MetodoPago(models.Model):
    nombre = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return self.nombre


# QuerySet es una implementación personalizada para el modelo Reserva, con métodos específicos para filtrar reservas en estados bloqueantes y con solapamiento de fechas.
class ReservaQuerySet(models.QuerySet):
    # Filtro para obtener reservas que están en estados bloqueantes, es decir, aquellas que tienen un estado de reserva con nombre "Pendiente" o "Confirmada". Esto es útil para identificar reservas que podrían afectar la disponibilidad de un vehículo, ya que estas reservas aún no han sido canceladas o completadas.
    def en_estados_bloqueantes(self):
        return self.filter(
            Q(estado_reserva__nombre__iexact='Pendiente')
            | Q(estado_reserva__nombre__iexact='Confirmada')
        ).exclude(estado_reserva__nombre__iexact='Cancelada')
    

    # Filtro para obtener reservas que se solapan con un vehículo y un rango de fechas dado. Esto es útil para verificar la disponibilidad de un vehículo antes de crear una nueva reserva. Por ejemplo, si alguien intenta reservar un vehículo del 10 al 15 de junio, este método puede verificar si ya existe una reserva para ese vehículo que se solape con esas fechas (por ejemplo, del 12 al 18 de junio), lo que indicaría que el vehículo no está disponible para el nuevo rango de fechas.
    def con_solapamiento(self, vehiculo, fecha_inicio, fecha_fin):
        
        return self.en_estados_bloqueantes().filter(
            vehiculo=vehiculo,
            # La reserva existente empieza antes o en el fin de la nueva.
            fecha_inicio__lte=fecha_fin,
            # La reserva existente termina después o en el inicio de la nueva.
            fecha_fin__gte=fecha_inicio,
        )

class Reserva(models.Model):
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    fecha_reserva = models.DateTimeField(auto_now_add=True)

    #Relaciones
    estado_reserva = models.ForeignKey(EstadoReserva, on_delete=models.SET_NULL, null=True)
    cliente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.SET_NULL, null=True)


    # Asignamos el manager personalizado a nuestro modelo Reserva, lo que nos permitirá utilizar los métodos definidos en ReservaQuerySet para filtrar reservas según los criterios específicos de estados bloqueantes y solapamiento de fechas.
    objects = ReservaQuerySet.as_manager()

    def __str__(self):
        return f'Reserva #{self.id}'

class Pago(models.Model):
    fecha_pago = models.DateTimeField(auto_now_add=True)
    comprobante_transaccion = models.CharField(max_length=100)

    #Relaciones
    metodo_pago = models.ForeignKey(MetodoPago, on_delete=models.SET_NULL, null=True)
    reserva = models.OneToOneField(Reserva, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f'Pago #{self.id}'

