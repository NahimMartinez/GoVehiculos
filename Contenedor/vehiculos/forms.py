from django import forms
from .models import Vehiculo

class VehiculoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        # Excluimos al dueño porque se lo vamos a asignar automáticamente al usuario logueado
        fields = ['matricula', 'precio_x_dia', 'imagen', 'tipo_vehiculo', 'estado_vehiculo', 'modelo']
        
        # Le agregamos las clases de Tailwind CSS para que los inputs tengan el mismo estilo que el resto de la aplicación
        widgets = {
            'matricula': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-primary focus:border-primary'}),
            'precio_x_dia': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-primary focus:border-primary'}),
            'imagen': forms.ClearableFileInput(attrs={'class': 'w-full px-4 py-2 border border-slate-300 rounded-lg bg-white'}),
            'tipo_vehiculo': forms.Select(attrs={'class': 'w-full px-4 py-2 border border-slate-300 rounded-lg bg-white'}),
            'estado_vehiculo': forms.Select(attrs={'class': 'w-full px-4 py-2 border border-slate-300 rounded-lg bg-white'}),
            'modelo': forms.Select(attrs={'class': 'w-full px-4 py-2 border border-slate-300 rounded-lg bg-white'}),
        }