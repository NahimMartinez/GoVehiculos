from django.urls import path
from . import views

urlpatterns = [
    path('reserva/', views.reservar_view, name='reserva_vehiculo'),
    # Endpoint para crear una reserva, que se espera que reciba una solicitud POST con los datos necesarios para realizar la reserva de un vehículo. La vista asociada a este endpoint se encargará de validar los datos, verificar la disponibilidad del vehículo y crear la reserva si todo es correcto.
    path('reserva/crear/', views.crear_reserva_view, name='crear_reserva'),
    path('mis-reservas/', views.obtener_reservas_usuario_view, name='mis_reservas'),
    path('reserva/<int:reserva_id>/cancelar/', views.cancelar_reserva_view, name='cancelar_reserva'),
    # Checkout de pago
    path('checkout/<int:reserva_id>/', views.checkout_view, name='checkout'),
    path('checkout/<int:reserva_id>/pagar/', views.procesar_checkout_view, name='procesar_checkout'),
    path('checkout/<int:reserva_id>/cancelar/', views.cancelar_checkout_view, name='cancelar_checkout'),
    path('checkout/<int:reserva_id>/exitoso/', views.checkout_exitoso_view, name='checkout_exitoso'),
]
