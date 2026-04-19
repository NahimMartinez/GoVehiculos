document.addEventListener("DOMContentLoaded", () => {
	const modalVehiculo = document.getElementById("modal-vehiculo");
	const formVehiculo = document.getElementById("form-vehiculo");
	const openVehiculoButtons = document.querySelectorAll("[data-open-modal-vehiculo]");
	const closeVehiculoButtons = document.querySelectorAll("[data-close-modal-vehiculo]");

	const openVehiculoModal = () => {
		if (modalVehiculo) {
			modalVehiculo.classList.remove("hidden");
		}
	};

	const closeVehiculoModal = () => {
		if (modalVehiculo) {
			modalVehiculo.classList.add("hidden");
		}
	};

	if (modalVehiculo && formVehiculo) {
		const isEditing = formVehiculo.dataset.esEdicion === "true";
		const hasErrors = formVehiculo.querySelectorAll(".text-red-500").length > 0;
		if (isEditing || hasErrors) {
			openVehiculoModal();
		}
	}

	openVehiculoButtons.forEach((button) => {
		button.addEventListener("click", openVehiculoModal);
	});

	closeVehiculoButtons.forEach((button) => {
		button.addEventListener("click", closeVehiculoModal);
	});

	if (modalVehiculo) {
		modalVehiculo.addEventListener("click", (event) => {
			if (event.target === modalVehiculo) {
				closeVehiculoModal();
			}
		});
	}

	const modalEliminar = document.getElementById("modal-eliminar-vehiculo");
	if (!modalEliminar) {
		return;
	}

	const inputVehiculoId = document.getElementById("input-vehiculo-id-eliminar");
	const textoVehiculo = document.getElementById("texto-vehiculo-eliminar");
	const cerrarModalEliminar = document.getElementById("cerrar-modal-eliminar");
	const cancelarEliminar = document.getElementById("cancelar-eliminar");
	const botonesEliminar = document.querySelectorAll(".btn-eliminar");

	if (!inputVehiculoId || !textoVehiculo || !cerrarModalEliminar || !cancelarEliminar) {
		return;
	}

	const closeEliminarModal = () => {
		modalEliminar.classList.add("hidden");
		inputVehiculoId.value = "";
		textoVehiculo.textContent = "";
	};

	botonesEliminar.forEach((button) => {
		button.addEventListener("click", () => {
			inputVehiculoId.value = button.dataset.vehiculoId || "";
			textoVehiculo.textContent = `${button.dataset.vehiculoNombre || ""} - ${button.dataset.vehiculoMatricula || ""}`;
			modalEliminar.classList.remove("hidden");
		});
	});

	cerrarModalEliminar.addEventListener("click", closeEliminarModal);
	cancelarEliminar.addEventListener("click", closeEliminarModal);

	modalEliminar.addEventListener("click", (event) => {
		if (event.target === modalEliminar) {
			closeEliminarModal();
		}
	});
});
