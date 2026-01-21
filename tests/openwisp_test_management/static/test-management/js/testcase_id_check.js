document.addEventListener("DOMContentLoaded", function () {
    const input = document.getElementById("id_test_case_id");
    if (!input) return;

    /* ===============================
       Inject CSS dynamically
    =============================== */
    if (!document.getElementById("test-case-id-style")) {
        const style = document.createElement("style");
        style.id = "test-case-id-style";
        style.innerHTML = `
            .field-error {
                color: #dc3545;
                font-size: 13px;
                margin-top: 8px;
                margin-left: 10px;
            }
            .tc-invalid {
                border-color: #dc3545 !important;
            }
        `;
        document.head.appendChild(style);
    }

    let timer = null;

    input.addEventListener("input", function () {
        clearTimeout(timer);

        const value = input.value.trim();
        let error = document.getElementById("test-case-id-error");

        // Remove error if less than 3 chars
        if (value.length < 3) {
            if (error) error.remove();
            input.classList.remove("tc-invalid");
            return;
        }

        timer = setTimeout(() => {
            const objectId = document.body.dataset.objectId || "";

            fetch(
                `/api/v1/test-management/test-case/check-test-case-id/?test_case_id=${encodeURIComponent(value)}&exclude_id=${objectId}`,
                {
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                    }
                }
            )
            .then(res => res.json())
            .then(data => {
                let error = document.getElementById("test-case-id-error");

                if (!error) {
                    error = document.createElement("div");
                    error.id = "test-case-id-error";
                    error.className = "field-error";
                    input.insertAdjacentElement("afterend", error);
                }

                if (data.exists) {
                    error.textContent = `Test Case ID "${value}" already exists. Please use a unique ID.`;

                    input.classList.add("tc-invalid");
                } else {
                    error.remove();
                    input.classList.remove("tc-invalid");
                }
            })
            .catch(() => {
                // fail silently
            });
        }, 400);
    });
});
