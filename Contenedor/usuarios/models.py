from django.db import models

# Create your models here.

class TipoUsuario(models.Model):
    nombre = models.CharField(max_length=25)


class Usuario(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True)
    dni = models.CharField(max_length=100, unique=True)
    tipo_usuario = models.ForeignKey(TipoUsuario, on_delete=models.SET_NULL, null=True)
