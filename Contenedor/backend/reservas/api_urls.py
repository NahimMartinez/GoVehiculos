from django.urls import include, path
from rest_framework import routers

from . import viewsets

# Configuración de rutas para la API REST de reservas utilizando un router de DRF. Esto permite definir automáticamente las rutas para las operaciones CRUD en el ViewSet asociado a las reservas, facilitando la gestión de las URLs y la organización del código.

router = routers.DefaultRouter()
router.register(r'reservas', viewsets.ReservaViewSet, basename='reservas')
router.register(r'estados-reserva', viewsets.EstadoReservaViewSet, basename='estados-reserva')
router.register(r'metodos-pago', viewsets.MetodoPagoViewSet, basename='metodos-pago')
router.register(r'pagos', viewsets.PagoViewSet, basename='pagos')
router.register(r'franquicias-tarjeta', viewsets.FranquiciaTarjetaViewSet, basename='franquicias-tarjeta')

urlpatterns = [
    path('v1/', include(router.urls)),
]
