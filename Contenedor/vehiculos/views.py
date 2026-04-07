from django.shortcuts import render, redirect
from vehiculos.models import Vehiculo
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from .forms import VehiculoForm

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
    # El usuario envió el formulario desde la modal?
    if request.method == 'POST':
        # request.FILES es obligatorio porque el modelo tiene un ImageField
        form = VehiculoForm(request.POST, request.FILES)
        if form.is_valid():
            # Guardamos el formulario en pausa (commit=False) para agregarle el dueño
            nuevo_vehiculo = form.save(commit=False)
            nuevo_vehiculo.duenio = request.user 
            nuevo_vehiculo.save() 
            
            return redirect('mis_vehiculos') # Recargamos la página para ver el auto nuevo
    
    # Si el usuario solo entró a ver la página:
    else:
        form = VehiculoForm()

    # Filtramos los vehículos del dueño actual
    vehiculos_del_socio = Vehiculo.objects.filter(duenio=request.user)
    
    contexto = {
        'mis_vehiculos': vehiculos_del_socio,
        'form': form, # Pasamos el formulario al HTML
    }
    return render(request, 'vehiculos/mis_vehiculos.html', contexto)

def inicio_view(request):
    # Compatibilidad por si se usa esta vista en otra URL.
    return index(request)