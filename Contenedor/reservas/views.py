from .models import Reserva
from usuarios.models import Usuario
from django.shortcuts import get_object_or_404, redirect, render


def reservar_view(request): #(ACA PONER LA LOGICA PARA RESERVAR VEHICULO, LA IDEA ES QUE LOS DATOS DEL CLIENTE SE AUTOCOMPLETEN.)
    return render(request, 'reservas/reserva.html')
