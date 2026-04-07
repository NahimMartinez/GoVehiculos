from django.conf import settings
from django.db import models
from PIL import Image
from django.core.validators import MaxLengthValidator, MinValueValidator, MaxValueValidator, MinLengthValidator
# Create your models here.
class EstadoVehiculo(models.Model):
    nombre = models.CharField(max_length=30)

    def __str__(self):
        return self.nombre

class TipoVehiculo(models.Model):
    nombre = models.CharField(max_length=30)

    def __str__(self):
        return self.nombre

class Marca(models.Model):
    nombre = models.CharField(max_length=50)

    def __str__(self):
        return self.nombre
    

class Modelo(models.Model):
    nombre = models.CharField(max_length=50)

    # Relaciones
    marca = models.ForeignKey(Marca, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.marca.nombre + " - " + self.nombre

class Vehiculo(models.Model):
    matricula = models.CharField(max_length=25, unique=True, validators=[MinLengthValidator(3), MaxLengthValidator(25)])
    precio_x_dia = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    imagen = models.ImageField(upload_to='vehiculos/', null=True, blank=True)
    activo = models.BooleanField(default=True)

    # Relaciones
    duenio = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    tipo_vehiculo = models.ForeignKey(TipoVehiculo, on_delete=models.SET_NULL, null=True)
    estado_vehiculo = models.ForeignKey(EstadoVehiculo, on_delete=models.SET_NULL, null=True)
    modelo = models.ForeignKey(Modelo, on_delete=models.SET_NULL, null=True)

    # Sobrescribimos el método save para redimensionar las fotos (que todas tengan igual tamaño)
    def save(self, *args, **kwargs):
        # 1. Guardamos el modelo normalmente
        super().save(*args, **kwargs)

        # 2. Verificamos si el vehículo realmente tiene una imagen cargada
        if self.imagen:
            # 3. Abrimos la imagen desde su ruta física
            img = Image.open(self.imagen.path)

            # 4. Verificamos si la imagen es muy grande
            if img.height > 600 or img.width > 800:
                tamaño_maximo = (800, 600)
                
                # thumbnail achica la imagen sin deformarla
                img.thumbnail(tamaño_maximo)
                
                # 5. Guardamos la imagen achicada, pisando el archivo original
                img.save(self.imagen.path)

# Definimos permisos personalizados para el modelo Vehiculo, en este caso un permiso para que los dueños de vehículos puedan ver solo su propia flota de vehículos.
    class Meta:
        permissions = [
            ("view_own_fleet", "Puede ver su propia flota"),
        ]