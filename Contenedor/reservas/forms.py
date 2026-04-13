from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from vehiculos.models import Vehiculo


class ReservarVehiculoForm(forms.Form):
	vehiculo_id = forms.IntegerField(min_value=1)
	fecha_inicio = forms.DateField()
	fecha_fin = forms.DateField()

	MAX_DIAS_RESERVA = 30 # Limite máximo de días para una reserva, lo que ayuda a controlar la duración de las reservas y evitar bloqueos prolongados de vehículos.

    # El método clean_vehiculo_id se encarga de validar que el ID del vehículo proporcionado corresponde a un vehículo activo y aprobado. Si el vehículo no existe o no cumple con estas condiciones, se lanza una ValidationError, lo que garantiza que solo se puedan reservar vehículos disponibles para los clientes.
	def clean_vehiculo_id(self):
		vehiculo_id = self.cleaned_data['vehiculo_id']

		try:
			vehiculo = Vehiculo.objects.get(id=vehiculo_id, activo=True, esta_aprobado=True)
		except Vehiculo.DoesNotExist as exc:
			raise ValidationError('El vehiculo no esta disponible para reservar.') from exc

		self.cleaned_data['vehiculo'] = vehiculo
		return vehiculo_id

    # El método clean se encarga de validar las fechas de inicio y fin de la reserva. Verifica que la fecha de inicio no esté en el pasado, que la fecha de fin sea posterior a la fecha de inicio, y que la duración total de la reserva no supere el límite máximo definido por MAX_DIAS_RESERVA. Si alguna de estas condiciones no se cumple, se añaden errores específicos a los campos correspondientes, lo que ayuda a garantizar que las reservas sean válidas y razonables.
	def clean(self):
		cleaned_data = super().clean()
		fecha_inicio = cleaned_data.get('fecha_inicio')
		fecha_fin = cleaned_data.get('fecha_fin')

		if not fecha_inicio or not fecha_fin:
			return cleaned_data

		hoy = timezone.localdate() # Obtenemos la fecha actual sin la parte de tiempo, lo que es útil para comparar solo las fechas sin considerar las horas, minutos o segundos. Esto permite validar que la fecha de inicio de la reserva no esté en el pasado en relación con la fecha actual.
		if fecha_inicio < hoy:
			self.add_error('fecha_inicio', 'La fecha de inicio no puede estar en el pasado.')

		if fecha_fin <= fecha_inicio:
			self.add_error('fecha_fin', 'La fecha de fin debe ser mayor a la fecha de inicio.')
			return cleaned_data

		dias_reserva = (fecha_fin - fecha_inicio).days
		if dias_reserva > self.MAX_DIAS_RESERVA:
			self.add_error(
				'fecha_fin',
				f'La reserva no puede superar los {self.MAX_DIAS_RESERVA} dias.'
			)

		return cleaned_data

