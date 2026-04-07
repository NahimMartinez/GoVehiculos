from django.shortcuts import render
from vehiculos.models import Vehiculo
from django.db.models import Count
from django.contrib.auth.decorators import login_required

# Create your views here.
def index(request):
    # Traemos los 6 vehiculos mas reservados (vehiculos destacados)
    vehiculos = Vehiculo.objects.annotate(num_reservas=Count('reserva')).order_by('-num_reservas')[:6]

    contexto = {
        'vehiculos_destacados': vehiculos
    }

    return render(request, 'index.html', contexto)

# si no estás logueado, te manda al login
@login_required 
def mis_vehiculos_view(request):
    # Filtra la tabla Vehiculo buscando que el dueño sea el usuario actual
    vehiculos_del_socio = Vehiculo.objects.filter(duenio=request.user)
    
    contexto = {
        'mis_vehiculos': vehiculos_del_socio
    }
    return render(request, 'vehiculos/mis_vehiculos.html', contexto)


def inicio_view(request):
    # Compatibilidad por si se usa esta vista en otra URL.
    return index(request)