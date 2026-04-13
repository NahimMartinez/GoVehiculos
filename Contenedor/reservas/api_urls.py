from django.urls import include, path
from rest_framework import routers

from . import views

# Configuración de rutas para la API REST de reservas utilizando un router de DRF. Esto permite definir automáticamente las rutas para las operaciones CRUD en el ViewSet asociado a las reservas, facilitando la gestión de las URLs y la organización del código.

router = routers.DefaultRouter()
router.register(r'reservas', views.ReservaViewSet, basename='reservas')
router.register(r'estados-reserva', views.EstadoReservaViewSet, basename='estados-reserva')
router.register(r'metodos-pago', views.MetodoPagoViewSet, basename='metodos-pago')
router.register(r'pagos', views.PagoViewSet, basename='pagos')

urlpatterns = [
    path('v1/', include(router.urls)),
]
