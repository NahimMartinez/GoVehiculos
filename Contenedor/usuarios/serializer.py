# Este archivo define los serializers para la aplicación de usuarios, que se encargan de convertir los modelos de Django a formatos JSON y viceversa, facilitando la creación de la API REST.
from rest_framework import serializers
from .models import Usuario

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario # Tratamos el modelo Usuario para convertirlo a JSON
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "dni",
            "password",
        )
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = Usuario(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance