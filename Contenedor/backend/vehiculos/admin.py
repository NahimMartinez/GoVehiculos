from django.contrib import admin
from .models import EstadoVehiculo, TipoVehiculo, Marca, Modelo, Vehiculo
# Register your models here.

admin.site.register(EstadoVehiculo)
admin.site.register(TipoVehiculo)
admin.site.register(Marca)
admin.site.register(Modelo)


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
	# Agregué el campo "esta_aprobado" a list_display para que sea visible en la lista de vehículos en el panel de administración. Esto permite a los administradores ver rápidamente si un vehículo está aprobado o no sin tener que ingresar a cada registro individualmente.
	list_display = ('matricula', 'duenio', 'activo', 'esta_aprobado', 'precio_x_dia')
	list_filter = ('activo', 'esta_aprobado', 'tipo_vehiculo', 'estado_vehiculo')
	search_fields = ('matricula', 'duenio__email', 'duenio__username')