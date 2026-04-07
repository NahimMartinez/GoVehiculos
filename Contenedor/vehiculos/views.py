from django.shortcuts import render, redirect, get_object_or_404
from vehiculos.models import Vehiculo
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from reservas.models import Reserva
from .forms import VehiculoForm

# Create your views here.
def index(request):
    # Traemos los 6 vehiculos mas reservados (vehiculos destacados)
    vehiculos = Vehiculo.objects.filter(activo=True).annotate(num_reservas=Count('reserva')).order_by('-num_reservas')[:6]

    contexto = {
        'vehiculos_destacados': vehiculos
    }

    return render(request, 'index.html', contexto)

# si no estás logueado, te manda al login
@login_required
def mis_vehiculos_view(request):
    # Verificar si es edición
    vehiculo_id = request.GET.get('edit')
    vehiculo_a_editar = None
    
    if vehiculo_id:
        # Obtener el vehículo y verificar que pertenece al usuario actual
        vehiculo_a_editar = get_object_or_404(Vehiculo, id=vehiculo_id, duenio=request.user, activo=True)
    
    # El usuario envió el formulario desde la modal
    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'eliminar':
            vehiculo_id = request.POST.get('vehiculo_id')
            vehiculo_a_eliminar = get_object_or_404(Vehiculo, id=vehiculo_id, duenio=request.user, activo=True)

            hay_reservas_futuras = Reserva.objects.filter(
                vehiculo=vehiculo_a_eliminar,
                fecha_fin__gte=timezone.now().date()
            ).exists()

            if hay_reservas_futuras:
                messages.error(request, 'No se puede eliminar el vehículo porque tiene reservas vigentes o futuras.')
                return redirect('mis_vehiculos')

            vehiculo_a_eliminar.activo = False
            vehiculo_a_eliminar.save(update_fields=['activo'])
            messages.success(request, 'Vehículo eliminado correctamente.')
            return redirect('mis_vehiculos')

        # Si viene ID oculto, estamos editando
        vehiculo_id = request.POST.get('vehiculo_id')
        if vehiculo_id:
            vehiculo_a_editar = get_object_or_404(Vehiculo, id=vehiculo_id, duenio=request.user, activo=True)
            form = VehiculoForm(request.POST, request.FILES, instance=vehiculo_a_editar)
        else:
            # Es creación: nuevo vehículo
            form = VehiculoForm(request.POST, request.FILES)
        
        
        if form.is_valid():
            nuevo_vehiculo = form.save(commit=False)
            if not vehiculo_a_editar:
                # Solo asignar dueño si es creación
                nuevo_vehiculo.duenio = request.user 
            nuevo_vehiculo.save() 
            
            return redirect('mis_vehiculos') # Recargamos la página
    
    # Si el usuario solo entró a ver la página:
    else:
        if vehiculo_a_editar:
            # Cargar formulario con los datos del vehículo
            form = VehiculoForm(instance=vehiculo_a_editar)
        else:
            # Formulario vacío para crear
            form = VehiculoForm()

    # Filtramos los vehículos del dueño actual
    vehiculos_del_socio = Vehiculo.objects.filter(duenio=request.user, activo=True)
    
    contexto = {
        'mis_vehiculos': vehiculos_del_socio,
        'form': form, # Pasamos el formulario al HTML
        'vehiculo_a_editar': vehiculo_a_editar, # Indicar si estamos editando
    }
    return render(request, 'vehiculos/mis_vehiculos.html', contexto)

def inicio_view(request):
    # Compatibilidad por si se usa esta vista en otra URL.
    return index(request)