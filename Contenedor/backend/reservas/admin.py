from django.contrib import admin
from .models import EstadoReserva, FranquiciaTarjeta, MetodoPago, Reserva, Pago
# Register your models here.

admin.site.register(EstadoReserva)
admin.site.register(MetodoPago)
admin.site.register(Reserva)
admin.site.register(Pago)
admin.site.register(FranquiciaTarjeta)
