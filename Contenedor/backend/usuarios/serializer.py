# Este archivo define los serializers para la aplicación de usuarios, que se encargan de convertir los modelos de Django a formatos JSON y viceversa, facilitando la creación de la API REST.
from django.contrib.auth.models import Group
from rest_framework import serializers
from .models import Usuario

ROLE_CLIENTE = "cliente"
ROLE_SOCIO = "socio"

class UsuarioSerializer(serializers.ModelSerializer):
    # Cuando registramos un usuario, el cliente debe elegir su rol (cliente o socio) para que se le asignen los permisos correspondientes. Este campo es de solo escritura (write_only) porque no queremos que se muestre al obtener los datos del usuario, sino solo al crear o actualizar un usuario.
    rol = serializers.ChoiceField(
        choices=[(ROLE_CLIENTE, "Cliente"), (ROLE_SOCIO, "Socio")],
        write_only=True,
    )

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
            "rol",
        )
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        rol = validated_data.pop("rol")
        password = validated_data.pop("password", None)
        user = Usuario(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        self._assign_group(user, rol)
        return user

    def update(self, instance, validated_data):
        rol = validated_data.pop("rol", None)
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if rol:
            instance.groups.clear()
            self._assign_group(instance, rol)
        return instance

    # A partir del rol que eligió el usuario al registrarse o actualizar su perfil, asignamos el grupo correspondiente (Clientes o Socios) para que se le otorguen los permisos adecuados. Si el grupo no existe, se lanza una excepción de validación.
    def _assign_group(self, user, rol):
        group_name = "Clientes" if rol == ROLE_CLIENTE else "Socios"
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"rol": f"El grupo '{group_name}' no existe."}
            ) from exc
        user.groups.add(group)