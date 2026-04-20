document.addEventListener("DOMContentLoaded", () => {
	const searchInput = document.querySelector("[data-users-search]");
	const groupFilter = document.querySelector("[data-users-group-filter]");
	const resultCount = document.querySelector("[data-users-result-count]");
	const emptyState = document.querySelector("[data-users-empty-state]");
	const userRows = Array.from(document.querySelectorAll("[data-user-row]"));

	const normalizeText = (value) => (value || "").toString().trim().toLowerCase();

	const getRowGroups = (row) => {
		const groupsFromDataset = normalizeText(row.dataset.userGroups);
		if (groupsFromDataset) {
			return groupsFromDataset
				.split("|")
				.map((group) => group.trim())
				.filter(Boolean);
		}

		const groupsFromBadges = Array.from(row.querySelectorAll("[data-user-group-item]"))
			.map((groupBadge) => normalizeText(groupBadge.textContent))
			.filter(Boolean);

		if (groupsFromBadges.length) {
			return groupsFromBadges;
		}

		return ["sin grupo"];
	};

	const getRowSearchableText = (row) => {
		const searchableFromDataset = normalizeText(row.dataset.searchText);
		if (searchableFromDataset) {
			return searchableFromDataset;
		}

		return normalizeText(row.textContent);
	};

	const updateResultCount = (visibleRowsCount) => {
		if (!resultCount) {
			return;
		}

		const label = visibleRowsCount === 1 ? "usuario visible" : "usuarios visibles";
		resultCount.textContent = `${visibleRowsCount} ${label}`;
	};

	const applyUsersFilters = () => {
		if (!userRows.length) {
			updateResultCount(0);
			return;
		}

		const query = normalizeText(searchInput ? searchInput.value : "");
		const selectedGroup = normalizeText(groupFilter ? groupFilter.value : "todos");
		let visibleRowsCount = 0;

		userRows.forEach((row) => {
			const searchableText = getRowSearchableText(row);
			const rowGroups = getRowGroups(row);

			const matchesQuery = !query || searchableText.includes(query);
			const matchesGroup = selectedGroup === "todos" || rowGroups.includes(selectedGroup);
			const isVisible = matchesQuery && matchesGroup;

			row.classList.toggle("hidden", !isVisible);
			if (isVisible) {
				visibleRowsCount += 1;
			}
		});

		if (emptyState) {
			emptyState.classList.toggle("hidden", visibleRowsCount !== 0);
		}

		updateResultCount(visibleRowsCount);
	};

	const setupGroupFilterOptions = () => {
		if (!groupFilter || !userRows.length) {
			return;
		}

		const uniqueGroups = new Set();
		userRows.forEach((row) => {
			getRowGroups(row).forEach((group) => uniqueGroups.add(group));
		});

		Array.from(uniqueGroups)
			.sort((first, second) => first.localeCompare(second))
			.forEach((group) => {
				const option = document.createElement("option");
				option.value = group;
				option.textContent = group.charAt(0).toUpperCase() + group.slice(1);
				groupFilter.appendChild(option);
			});
	};

	setupGroupFilterOptions();
	if (searchInput) {
		searchInput.addEventListener("input", applyUsersFilters);
	}
	if (groupFilter) {
		groupFilter.addEventListener("change", applyUsersFilters);
	}
	applyUsersFilters();

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
