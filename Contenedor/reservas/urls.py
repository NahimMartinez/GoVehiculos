from django.urls import path
from . import views

urlpatterns = [
    path('reserva/', views.reservar_view, name='reserva_vehiculo'),
    # Endpoint para crear una reserva, que se espera que reciba una solicitud POST con los datos necesarios para realizar la reserva de un vehículo. La vista asociada a este endpoint se encargará de validar los datos, verificar la disponibilidad del vehículo y crear la reserva si todo es correcto.
    path('reserva/crear/', views.crear_reserva_view, name='crear_reserva'),
]
