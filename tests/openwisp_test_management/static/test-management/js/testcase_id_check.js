let input; // shared reference

function getOrCreateErrorList() {
  let errorList = document.getElementById("id_test_case_id_error");
  const formRow = input.closest(".form-row");

  if (!errorList) {
    errorList = document.createElement("ul");
    errorList.className = "errorlist";
    errorList.id = "id_test_case_id_error";

    // Django places errorlist as FIRST child of form-row
    formRow.insertBefore(errorList, formRow.firstChild);
  }

  return errorList;
}

function showError(message) {
  const errorList = getOrCreateErrorList();
  errorList.innerHTML = `<li>${message}</li>`;

  input.setAttribute("aria-invalid", "true");

  const describedBy = new Set(
    (input.getAttribute("aria-describedby") || "").split(" ").filter(Boolean),
  );
  describedBy.add("id_test_case_id_error");
  input.setAttribute("aria-describedby", [...describedBy].join(" "));
}

function clearError() {
  const errorList = document.getElementById("id_test_case_id_error");
  if (errorList) errorList.remove();

  input.removeAttribute("aria-invalid");

  const describedBy = (input.getAttribute("aria-describedby") || "")
    .split(" ")
    .filter((id) => id && id !== "id_test_case_id_error");

  if (describedBy.length) {
    input.setAttribute("aria-describedby", describedBy.join(" "));
  } else {
    input.removeAttribute("aria-describedby");
  }
}

document.addEventListener("DOMContentLoaded", function () {
  input = document.getElementById("id_test_case_id");
  if (!input) return;

  let timer = null;

  input.addEventListener("input", function () {
    clearTimeout(timer);

    const value = input.value.trim();

    // Remove error if less than 3 chars
    if (value.length < 3) {
      clearError();
      return;
    }

    timer = setTimeout(() => {
      const objectId = document.body.dataset.objectId || "";

      fetch(
        `/api/v1/test-management/test-case/check-test-case-id/?test_case_id=${encodeURIComponent(
          value,
        )}&exclude_id=${objectId}`,
        {
          headers: { "X-Requested-With": "XMLHttpRequest" },
        },
      )
        .then((res) => res.json())
        .then((data) => {
          if (data.exists) {
            showError(
              `Test Case ID '${value}' already exists. Please use a unique ID.`,
            );
          } else {
            clearError();
          }
        })
        .catch(() => {
          // fail silently
        });
    }, 400);
  });
});
