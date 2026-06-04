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

    def validar_datos(self):
        """
        Centraliza toda la validación de datos del formulario.
        Valida matrícula, precio, campos requeridos e imagen.
        """
        cleaned_data = self.cleaned_data
        
        # 1. Validar matrícula
        self._validar_matricula(cleaned_data)
        
        # 2. Validar precio
        self._validar_precio(cleaned_data)
        
        # 3. Validar campos requeridos
        self._validar_campos_requeridos(cleaned_data)
        
        # 4. Validar imagen
        self._validar_imagen(cleaned_data)
        
        return cleaned_data
    
    def _validar_matricula(self, cleaned_data):
        """Valida que la matrícula tenga formato correcto y sea única."""
        matricula = cleaned_data.get('matricula', '').strip().upper()
        
        # No vacío
        if not matricula:
            self.add_error('matricula', "La matrícula es obligatoria.")
            return
        
        # Formato: 2 letras, espacio, 3 números, espacio, 2 letras (ej: AE 456 RT)
        patron = r'^[A-Z]{2}\s\d{3}\s[A-Z]{2}$'
        if not RegexValidator(patron).regex.match(matricula):
            self.add_error('matricula', "Formato inválido. Debe ser: 2 letras, espacio, 3 números, espacio, 2 letras (ej: AE 456 RT)")
            return
        
        # Validar unicidad (excluir el objeto actual si es edición)
        exists = Vehiculo.objects.filter(matricula=matricula).exclude(pk=self.instance.pk)
        if exists.exists():
            self.add_error('matricula', "Ya existe un vehículo con esa matrícula.")
            return
        
        # Actualizar el valor normalizado
        cleaned_data['matricula'] = matricula.upper()
    
    def _validar_precio(self, cleaned_data):
        """Valida que el precio sea un valor válido."""
        precio = cleaned_data.get('precio_x_dia')
        
        if precio is None:
            self.add_error('precio_x_dia', "El precio es obligatorio.")
            return
        
        if precio < 0:
            self.add_error('precio_x_dia', "El precio no puede ser negativo.")
    
    def _validar_campos_requeridos(self, cleaned_data):
        """Valida que los campos requeridos estén presentes."""
        campos_requeridos = ['modelo', 'tipo_vehiculo', 'estado_vehiculo']
        for campo in campos_requeridos:
            if not cleaned_data.get(campo):
                self.add_error(campo, "Este campo es obligatorio.")
    
    def _validar_imagen(self, cleaned_data):
        """Valida que la imagen sea requerida en creación y opcional en edición."""
        # La imagen es obligatoria solo si es creación (no hay instancia)
        # En edición, la imagen es opcional (puede mantener la existente)
        if not self.instance.pk:  # Es creación si no hay pk
            if not cleaned_data.get('imagen'):
                self.add_error('imagen', "Este campo es obligatorio.")
    
    # Método clean que llama a validar_datos
    def clean(self):
        cleaned_data = super().clean()
        return self.validar_datos()