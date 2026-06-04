// Scripts globales
document.addEventListener('click', (event) => {
	const dismissButton = event.target.closest('[data-dismiss-message]');

	if (!dismissButton) {
		return;
	}

	const messageBanner = dismissButton.closest('[data-message-banner]');
	if (messageBanner) {
		messageBanner.remove();
	}
});

document.addEventListener('DOMContentLoaded', () => {
	const reservaForm = document.querySelector('[data-reserva-form]');
	if (!reservaForm) {
		return;
	}

	const metodoSelect = reservaForm.querySelector('[data-metodo-select]');
	const vehicleSelect = reservaForm.querySelector('[data-vehicle-select]');
	const selectedVehicleCard = reservaForm.querySelector('[data-selected-vehicle-card]');
	const resumenMetodo = reservaForm.querySelector('[data-resumen-metodo]');
	const resumenDias = reservaForm.querySelector('[data-resumen-dias]');
	const resumenTotal = reservaForm.querySelector('[data-resumen-total]');
	const resumenAyuda = reservaForm.querySelector('[data-resumen-ayuda]');
	const fechaInicioInput = reservaForm.querySelector('#fecha_inicio');
	const fechaFinInput = reservaForm.querySelector('#fecha_fin');
	const fechaReservaInputs = [fechaInicioInput, fechaFinInput].filter(Boolean);

	const parseNumber = (value) => {
		const parsed = Number.parseFloat(value);
		return Number.isFinite(parsed) ? parsed : 0;
	};

	const getSelectedVehicleInfo = () => {
		if (selectedVehicleCard) {
			return {
				name: selectedVehicleCard.getAttribute('data-vehicle-name') || 'Vehículo seleccionado',
				price: parseNumber(selectedVehicleCard.getAttribute('data-vehicle-price')),
			};
		}

		if (!vehicleSelect) {
			return { name: '', price: 0 };
		}

		const selectedOption = vehicleSelect.options[vehicleSelect.selectedIndex];
		if (!selectedOption || !selectedOption.value) {
			return { name: '', price: 0 };
		}

		return {
			name: selectedOption.getAttribute('data-vehiculo-nombre') || selectedOption.textContent.trim(),
			price: parseNumber(selectedOption.getAttribute('data-precio')),
		};
	};

	const calculateDays = () => {
		if (!fechaInicioInput || !fechaFinInput || !fechaInicioInput.value || !fechaFinInput.value) {
			return 0;
		}

		const startDate = new Date(`${fechaInicioInput.value}T00:00:00`);
		const endDate = new Date(`${fechaFinInput.value}T00:00:00`);
		const diffMs = endDate.getTime() - startDate.getTime();

		if (!Number.isFinite(diffMs) || diffMs <= 0) {
			return 0;
		}

		return Math.round(diffMs / 86400000);
	};

	const updateSummary = () => {
		if (!resumenMetodo || !resumenDias || !resumenTotal || !resumenAyuda) {
			return;
		}

		const { name: vehicleName, price: pricePerDay } = getSelectedVehicleInfo();
		const selectedMethod = metodoSelect && metodoSelect.value ? metodoSelect.options[metodoSelect.selectedIndex] : null;
		const methodName = selectedMethod && selectedMethod.value ? selectedMethod.textContent.trim() : 'Seleccionar';
		const days = calculateDays();
		const total = days > 0 && pricePerDay > 0 ? days * pricePerDay : 0;

		resumenMetodo.textContent = methodName;
		resumenDias.textContent = String(days);
		resumenTotal.textContent = new Intl.NumberFormat('es-AR', {
			style: 'currency',
			currency: 'ARS',
			maximumFractionDigits: 2,
		}).format(total);

		if (methodName !== 'Seleccionar' && vehicleName && days > 0) {
			resumenAyuda.textContent = `Método elegido: ${methodName}. ${vehicleName} se calcula a $${pricePerDay.toFixed(2)} por día.`;
			return;
		}

		if (methodName === 'Seleccionar') {
			resumenAyuda.textContent = 'Elegí un método de pago para completar la reserva.';
			return;
		}

		resumenAyuda.textContent = 'Elegí un vehículo, las fechas y un método de pago para ver el cálculo.';
	};

	[metodoSelect, vehicleSelect, ...fechaReservaInputs].forEach((element) => {
		if (element) {
			element.addEventListener('change', updateSummary);
			element.addEventListener('input', updateSummary);
		}
	});

	updateSummary();
});