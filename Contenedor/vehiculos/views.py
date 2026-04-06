from django.shortcuts import render
from vehiculos.models import Vehiculo
from django.db.models import Count

# Create your views here.
def index(request):
    # Traemos los 6 vehiculos mas reservados (vehiculos destacados)
    vehiculos = Vehiculo.objects.annotate(num_reservas=Count('reserva')).order_by('-num_reservas')[:6]

    contexto = {
        'vehiculos_destacados': vehiculos
    }

    return render(request, 'index.html', contexto)


def inicio_view(request):
    # Compatibilidad por si se usa esta vista en otra URL.
    return index(request)