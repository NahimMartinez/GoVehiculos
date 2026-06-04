document.addEventListener("DOMContentLoaded", () => {
	const filtersForm = document.querySelector("[data-users-filter-form]");
	const searchInput = document.querySelector("[data-users-search-input]");
	const groupSelect = document.querySelector("[data-users-group-select]");

	if (filtersForm && searchInput) {
		let submitTimer = null;

		const submitFilters = () => {
			filtersForm.submit();
		};

		searchInput.addEventListener("input", () => {
			if (submitTimer) {
				window.clearTimeout(submitTimer);
			}

			submitTimer = window.setTimeout(() => {
				submitFilters();
			}, 350);
		});

		searchInput.addEventListener("keydown", (event) => {
			if (event.key === "Enter") {
				event.preventDefault();
				if (submitTimer) {
					window.clearTimeout(submitTimer);
				}
				submitFilters();
			}
		});
	}

	if (filtersForm && groupSelect) {
		groupSelect.addEventListener("change", () => {
			filtersForm.submit();
		});
	}

	const modal = document.getElementById("user-action-modal");
	if (!modal) {
		return;
	}

	const modalTitle = document.getElementById("user-action-modal-title");
	const modalMessage = document.getElementById("user-action-modal-message");
	const modalForm = document.getElementById("user-action-modal-form");
	const modalCancel = document.getElementById("user-action-modal-cancel");
	const modalBackdrop = modal.querySelector("[data-modal-backdrop]");
	const triggers = document.querySelectorAll("[data-user-action-trigger]");

	if (!modalTitle || !modalMessage || !modalForm || !modalCancel || !modalBackdrop) {
		return;
	}

	const closeModal = () => {
		modal.classList.add("hidden");
		modal.classList.remove("flex");
	};

	const openModal = ({ url, title, message }) => {
		modalForm.action = url;
		modalTitle.textContent = title;
		modalMessage.textContent = message;
		modal.classList.remove("hidden");
		modal.classList.add("flex");
	};

	triggers.forEach((trigger) => {
		trigger.addEventListener("click", () => {
			openModal({
				url: trigger.dataset.actionUrl,
				title: trigger.dataset.actionTitle,
				message: trigger.dataset.actionMessage,
			});
		});
	});

	modalCancel.addEventListener("click", closeModal);
	modalBackdrop.addEventListener("click", closeModal);

	document.addEventListener("keydown", (event) => {
		if (event.key === "Escape" && !modal.classList.contains("hidden")) {
			closeModal();
		}
	});
});
