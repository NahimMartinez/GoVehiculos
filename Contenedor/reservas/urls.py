from django.urls import path
from . import views

urlpatterns = [
    path('reserva/', views.reservar_view, name='reserva_vehiculo'),
]
