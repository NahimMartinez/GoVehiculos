from django import forms
from .models import Vehiculo
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

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

    # Validar matrícula específicamente
    def clean_matricula(self):
        matricula = self.cleaned_data.get('matricula', '').strip().upper()
        
        # No vacío
        if not matricula:
            raise ValidationError("La matrícula es obligatoria.")
        
        # Formato: 2 letras, espacio, 3 números, espacio, 2 letras (ej: AE 456 RT)
        patron = r'^[A-Z]{2}\s\d{3}\s[A-Z]{2}$'
        if not RegexValidator(patron).regex.match(matricula):
            raise ValidationError("Formato inválido. Debe ser: 2 letras, espacio, 3 números, espacio, 2 letras (ej: AE 456 RT)")
        
        # Validar unicidad (excluir el objeto actual si es edición)
        exists = Vehiculo.objects.filter(matricula=matricula).exclude(pk=self.instance.pk)
        if exists.exists():
            raise ValidationError("Ya existe un vehículo con esa matrícula.")
        
        return matricula.upper()

    # Validar precio
    def clean_precio_x_dia(self):
        precio = self.cleaned_data.get('precio_x_dia')
        
        if precio is None:
            raise ValidationError("El precio es obligatorio.")
        
        if precio < 0:
            raise ValidationError("El precio no puede ser negativo.")
        
        return precio

    # Validar campos generales
    def clean(self):
        cleaned_data = super().clean()
        
        # Validar campos requeridos
        campos_requeridos = ['modelo', 'tipo_vehiculo', 'estado_vehiculo']
        for campo in campos_requeridos:
            if not cleaned_data.get(campo):
                self.add_error(campo, f"Este campo es obligatorio.")
        
        # La imagen es obligatoria solo si es creación (no hay instancia)
        # En edición, la imagen es opcional (puede mantener la existente)
        if not self.instance.pk:  # Es creación si no hay pk
            if not cleaned_data.get('imagen'):
                self.add_error('imagen', "Este campo es obligatorio.")
        
        return cleaned_data