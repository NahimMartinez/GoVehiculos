from django.contrib import admin
from .models import EstadoVehiculo, TipoVehiculo, Marca, Modelo, Vehiculo
# Register your models here.

admin.site.register(EstadoVehiculo)
admin.site.register(TipoVehiculo)
admin.site.register(Marca)
admin.site.register(Modelo)
admin.site.register(Vehiculo)