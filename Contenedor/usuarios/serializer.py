# Este archivo define los serializers para la aplicación de usuarios, que se encargan de convertir los modelos de Django a formatos JSON y viceversa, facilitando la creación de la API REST.
from rest_framework import serializers
from .models import TipoUsuario, Usuario

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario # Tratamos el modelo Usuario para convertirlo a JSON
        fields = '__all__' # Incluimos todos los campos del modelo Usuario en el serializer