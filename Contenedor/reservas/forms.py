from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from vehiculos.models import Vehiculo


class ReservarVehiculoForm(forms.Form):
	vehiculo_id = forms.IntegerField(min_value=1)
	fecha_inicio = forms.DateField()
	fecha_fin = forms.DateField()

	MAX_DIAS_RESERVA = 30

	def clean_vehiculo_id(self):
		vehiculo_id = self.cleaned_data['vehiculo_id']

		try:
			vehiculo = Vehiculo.objects.get(id=vehiculo_id, activo=True, esta_aprobado=True)
		except Vehiculo.DoesNotExist as exc:
			raise ValidationError('El vehiculo no esta disponible para reservar.') from exc

		self.cleaned_data['vehiculo'] = vehiculo
		return vehiculo_id

	def clean(self):
		cleaned_data = super().clean()
		fecha_inicio = cleaned_data.get('fecha_inicio')
		fecha_fin = cleaned_data.get('fecha_fin')

		if not fecha_inicio or not fecha_fin:
			return cleaned_data

		hoy = timezone.localdate()
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

