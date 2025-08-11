/**
 * Test Management - Test Suite Form JavaScript
 * Handles test case selection with persistent global state management
 */

(function ($) {
  "use strict";

  // CSRF Token Utility
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  const csrftoken = getCookie("csrftoken");

  // GLOBAL STATE MANAGEMENT - This is the key change
  const globalState = {
    selectedTestCases: new Map(), // test_case_id -> { testCaseData, order }
    currentApiTestCases: [], // Current API response
    cachedTestCases: new Map(),

    // Add test case to global state
    addTestCase: function (testCase, order = null) {
      const testCaseId = String(testCase.id);
      if (order === null) {
        order =
          Math.max(
            0,
            ...Array.from(this.selectedTestCases.values()).map(
              (item) => item.order
            )
          ) + 1;
      }

      this.selectedTestCases.set(testCaseId, {
        testCaseData: {
          id: testCase.id,
          name: testCase.name,
          test_case_id: testCase.test_case_id,
          test_type: testCase.test_type || 1,
          test_type_display: testCase.test_type_display,
        },
        order: order,
        selected_at: Date.now(),
      });
      this.cachedTestCases.set(testCaseId, {
        testCaseData: {
          id: testCase.id,
          name: testCase.name,
          test_case_id: testCase.test_case_id,
          test_type: testCase.test_type || 1,
          test_type_display: testCase.test_type_display,
        },
        order: order,
        selected_at: Date.now(),
      });

      console.log(
        `Global State: Added test case ${testCase.name} (ID: ${testCaseId}) with order ${order}`
      );
      this.logState();
    },

    // Remove test case from global state (cleanup)
    removeTestCase: function (testCaseId) {
      testCaseId = String(testCaseId);
      if (this.selectedTestCases.has(testCaseId)) {
        const removed = this.selectedTestCases.get(testCaseId);
        this.selectedTestCases.delete(testCaseId);
        console.log(
          `Global State: Removed test case ID ${testCaseId} (${removed.testCaseData.name})`
        );
        this.reorderTestCases();
        this.logState();
      }
    },

    getFromCache(testCaseId) {
      return this.cachedTestCases.get(String(testCaseId))?.testCaseData || null;
    },

    // Check if test case is selected
    isSelected: function (testCaseId) {
      return this.selectedTestCases.has(String(testCaseId));
    },

    // Get ordered array of selected test case IDs
    getOrderedIds: function () {
      return Array.from(this.selectedTestCases.entries())
        .sort((a, b) => a[1].order - b[1].order)
        .map(([id, _]) => id);
    },

    // Get ordered array of selected test case data
    getOrderedTestCases: function () {
      return Array.from(this.selectedTestCases.entries())
        .sort((a, b) => a[1].order - b[1].order)
        .map(([id, item]) => ({
          ...item.testCaseData,
          order: item.order,
          isFromGlobalState: true,
        }));
    },

    // Reorder test cases after deletion
    reorderTestCases: function () {
      const sortedEntries = Array.from(this.selectedTestCases.entries()).sort(
        (a, b) => a[1].order - b[1].order
      );

      sortedEntries.forEach(([id, item], index) => {
        item.order = index + 1;
        this.selectedTestCases.set(id, item);
      });

      console.log("Global State: Reordered test cases");
    },

    // Get count of selected test cases
    getCount: function () {
      return this.selectedTestCases.size;
    },

    // Clear all selected test cases
    clear: function () {
      this.selectedTestCases.clear();
      console.log("Global State: Cleared all test cases");
    },

    // Set current API test cases
    setCurrentApiTestCases: function (testCases) {
      this.currentApiTestCases = testCases || [];
      console.log(
        `Global State: Set current API test cases (${this.currentApiTestCases.length})`
      );
    },

    // Merge API test cases with selected test cases for UI display
    getMergedTestCasesForDisplay: function () {
      console.log("Global State: Merging test cases for display");

      // Create a map of current API test cases for quick lookup
      const apiTestCasesMap = new Map();
      this.currentApiTestCases.forEach((tc) => {
        apiTestCasesMap.set(String(tc.id), tc);
      });

      // Start with current API test cases
      const mergedTestCases = [...this.currentApiTestCases];

      // Add selected test cases that are NOT in current API response
      this.selectedTestCases.forEach((item, testCaseId) => {
        if (!apiTestCasesMap.has(testCaseId)) {
          // This selected test case is not in current category/API response
          // but we want to show it so user can see their selection
          console.log(
            `Adding selected test case from global state: ${item.testCaseData.name}`
          );
          mergedTestCases.push({
            ...item.testCaseData,
            isFromGlobalState: true,
            order: item.order,
          });
        }
      });

      // Sort merged test cases: selected ones first (by order), then unselected ones
      mergedTestCases.sort((a, b) => {
        const aSelected = this.isSelected(a.id);
        const bSelected = this.isSelected(b.id);

        if (aSelected && bSelected) {
          // Both selected, sort by order
          const aOrder = this.selectedTestCases.get(String(a.id))?.order || 0;
          const bOrder = this.selectedTestCases.get(String(b.id))?.order || 0;
          return aOrder - bOrder;
        } else if (aSelected && !bSelected) {
          return -1; // Selected items first
        } else if (!aSelected && bSelected) {
          return 1; // Selected items first
        } else {
          // Both unselected, sort by name
          return a.name.localeCompare(b.name);
        }
      });

      console.log(
        `Global State: Merged ${mergedTestCases.length} test cases for display`
      );
      console.log(`- API test cases: ${this.currentApiTestCases.length}`);
      console.log(`- Selected test cases: ${this.selectedTestCases.size}`);

      return mergedTestCases;
    },

    // Debug logging
    logState: function () {
      console.log("=== GLOBAL STATE ===");
      console.log("Selected test cases:", this.selectedTestCases.size);
      this.selectedTestCases.forEach((item, id) => {
        console.log(
          `  ${id}: ${item.testCaseData.name} (order: ${item.order})`
        );
      });
      console.log("===================");
    },
  };

  // Legacy variables for compatibility
  let selectedTestCases = new Map(); // Will be kept in sync with globalState
  let allTestCases = []; // Will be kept in sync with globalState.currentApiTestCases

  // Sync functions to maintain compatibility with existing code
  function syncLegacyState() {
    selectedTestCases.clear();
    globalState.selectedTestCases.forEach((item, id) => {
      selectedTestCases.set(id, item.order);
    });
    allTestCases = globalState.currentApiTestCases;
  }

  // DOM Utility Functions
  function getElement(selector) {
    return $(selector);
  }

  // Initialization Functions
  function initializeSelectedTestCases() {
    try {
      const scriptElement = document.getElementById("existing-test-cases-data");
      if (scriptElement) {
        const existingTestCasesJson =
          scriptElement.textContent || scriptElement.innerText;
        console.log("Raw JSON string:", existingTestCasesJson);

        if (
          existingTestCasesJson &&
          existingTestCasesJson.trim() !== "" &&
          existingTestCasesJson.trim() !== "[]"
        ) {
          const existingTestCases = JSON.parse(existingTestCasesJson);
          if (
            Array.isArray(existingTestCases) &&
            existingTestCases.length > 0
          ) {
            existingTestCases.forEach(function (item) {
              if (item && item.id && item.order) {
                globalState.addTestCase(item, parseInt(item.order));
              }
            });

            console.log("Initialized global state with existing test cases");
            globalState.logState();

            syncLegacyState();
            displayTestCasesTable(existingTestCases);
            updateSelectionCount();
            updateHiddenInput();
          }
        } else {
          console.log("No existing test cases to initialize");
        }
      } else {
        console.log("No existing test cases data script element found");
      }
    } catch (e) {
      console.error("Error initializing existing test cases:", e);
    }
  }

  // UI Creation Functions
  function createTestCasesContainer() {
    const container = $('<div id="test-cases-container" class="hidden"></div>');
    const header = $('<div class="test-cases-header">Select Test Cases</div>');
    const errorMessage = $(`
      <div class="test-case-validation-error" id="test-case-error">
        <span class="error-icon">⚠</span>
        <span class="error-text">At least one test case must be selected for this test group.</span>
      </div>
    `);
    const successMessage = $(`
      <div class="test-case-validation-success" id="test-case-success">
        <span class="success-icon">✓</span>
        <span class="success-text"></span>
      </div>
    `);
    const tableContainer = $('<div class="table-container"></div>');
    const table = $(`
      <table class="test-cases-table">
        <thead>
          <tr>
            <th class="checkbox-col"><input type="checkbox" id="select-all-test-cases"></th>
            <th class="name-col">NAME</th>
            <th class="id-col">TEST CASE ID</th>
            <th class="type-col">TEST TYPE</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    `);

    tableContainer.append(table);
    container.append(header);
    container.append(errorMessage);
    container.append(successMessage);
    container.append(tableContainer);

    return container;
  }

  // UI Update Functions
  function displayTestCasesTable(testCases = null) {
    console.log("displayTestCasesTable called");

    const tbody = getElement(".test-cases-table tbody");
    if (tbody.length === 0) {
      console.error("No tbody element found!");
      return;
    }

    tbody.empty();

    // Use merged test cases if no specific test cases provided
    const testCasesToDisplay =
      testCases || globalState.getMergedTestCasesForDisplay();
    console.log(`Displaying ${testCasesToDisplay.length} test cases`);

    testCasesToDisplay.forEach(function (testCase) {
      const testCaseId = String(testCase.id);
      const isChecked = globalState.isSelected(testCaseId);
      const isFromGlobalState = testCase.isFromGlobalState || false;

      const row = $(`
        <tr class="${isChecked ? "selected" : ""} ${
        isFromGlobalState ? "from-global-state" : ""
      }" data-id="${testCase.id}">
          <td class="checkbox-col">
            <input type="checkbox" 
                   class="test-case-checkbox"
                   id="test_case_${testCase.id}" 
                   value="${testCase.id}"
                   ${isChecked ? "checked" : ""}>
          </td>
          <td class="name-col">
            <label for="test_case_${testCase.id}" class="test-case-name">
              ${testCase.name}
              ${
                isFromGlobalState
                  ? '<span class="global-state-indicator" title="Selected from another category">★</span>'
                  : ""
              }
            </label>
          </td>
          <td class="id-col">
            <span class="test-case-id">${testCase.test_case_id}</span>
          </td>
          <td class="type-col">
            <span class="test-type-badge">${testCase.test_type_display}</span>
          </td>
        </tr>
      `);
      tbody.append(row);
    });

    console.log("Table rows added:", tbody.find("tr").length);
    updateSelectAllCheckbox();
    updateSelectionCount();
    updateHiddenInput();
  }

  function updateSelectAllCheckbox() {
    const allCheckboxes = getElement(".test-case-checkbox");
    const checkedCheckboxes = getElement(".test-case-checkbox:checked");
    if (allCheckboxes.length > 0) {
      const selectAllCheckbox = getElement("#select-all-test-cases");
      if (allCheckboxes.length === checkedCheckboxes.length) {
        selectAllCheckbox.prop("checked", true).prop("indeterminate", false);
      } else if (checkedCheckboxes.length > 0) {
        selectAllCheckbox.prop("checked", false).prop("indeterminate", true);
      } else {
        selectAllCheckbox.prop("checked", false).prop("indeterminate", false);
      }
    }
  }

  function updateSelectionCount() {
    const selectedCount = globalState.getCount();
    const selectionDiv = getElement(".selection-count");
    const countSpan = selectionDiv.find(".count");
    const categoryField = getElement(".field-category");
    const errorDiv = getElement("#test-case-error");
    const successDiv = getElement("#test-case-success");

    countSpan.text(selectedCount);
    if (selectedCount === 0) {
      selectionDiv.find("span:not(.count)").remove();
      selectionDiv.append(" Test Case Selected");
    } else if (selectedCount === 1) {
      selectionDiv.find("span:not(.count)").remove();
      selectionDiv.append(" Test Case Selected");
    } else {
      selectionDiv.find("span:not(.count)").remove();
      selectionDiv.append(" Test Cases Selected");
    }

    if (getElement("#id_category").val() && selectedCount === 0) {
      errorDiv.show();
      successDiv.hide();
      selectionDiv.removeClass("success").addClass("error");
      categoryField.addClass("has-error");
    } else if (getElement("#id_category").val() && selectedCount > 0) {
      errorDiv.hide();
      successDiv
        .find(".success-text")
        .text(
          `${selectedCount} test case${selectedCount > 1 ? "s" : ""} selected`
        );
      successDiv.show();
      selectionDiv.removeClass("error").addClass("success");
      categoryField.removeClass("has-error");
    } else {
      errorDiv.hide();
      successDiv.hide();
      selectionDiv.removeClass("error success");
      categoryField.removeClass("has-error");
    }
  }

  function updateHiddenInput() {
    let input = getElement('input[name="selected_test_cases_data"]');
    if (!input.length) {
      input = $('<input type="hidden" name="selected_test_cases_data">');
      getElement("form").append(input);
    }

    const sortedIds = globalState.getOrderedIds();
    input.val(JSON.stringify(sortedIds));
    console.log("Updated hidden input:", JSON.stringify(sortedIds));

    // Sync legacy state
    syncLegacyState();
  }

  // Selection Management Functions
  function reorderTestCases() {
    globalState.reorderTestCases();
    syncLegacyState();
  }

  function findTestCaseInCurrentApi(testCaseId) {
    return globalState.currentApiTestCases.find(
      (tc) => String(tc.id) === String(testCaseId)
    );
  }

  // Event Handlers
  function handleTestCaseSelection() {
    $(document).on("change", ".test-case-checkbox", function () {
      const testCaseId = $(this).val();
      const row = $(this).closest("tr");

      if ($(this).is(":checked")) {
        // Find test case data
        let testCaseData = findTestCaseInCurrentApi(testCaseId);

        // If not in current API, get from global state
        if (
          !testCaseData &&
          globalState.cachedTestCases.has(String(testCaseId))
        ) {
          testCaseData = globalState.cachedTestCases.get(
            String(testCaseId)
          ).testCaseData;
        }

        if (testCaseData) {
          globalState.addTestCase(testCaseData);
          row.addClass("selected");
          console.log(`Selected test case: ${testCaseData.name}`);
        } else {
          console.error(`Test case data not found for ID: ${testCaseId}`);
          $(this).prop("checked", false); // Revert checkbox
          return;
        }
      } else {
        // Remove from global state (cleanup)
        const testCaseName =
          globalState.selectedTestCases.get(String(testCaseId))?.testCaseData
            ?.name || testCaseId;
        globalState.removeTestCase(testCaseId);
        row.removeClass("selected");
        console.log(`Unselected test case: ${testCaseName}`);
      }

      updateHiddenInput();
      updateSelectAllCheckbox();
      updateSelectionCount();
    });
  }

  function handleRowClick() {
    $(document).on("click", ".test-cases-table tbody tr", function (e) {
      if (
        !$(e.target).is('input[type="checkbox"]') &&
        !$(e.target).is("label")
      ) {
        const checkbox = $(this).find(".test-case-checkbox");
        checkbox.prop("checked", !checkbox.prop("checked")).trigger("change");
      }
    });
  }

  function handleSelectAll() {
    $(document).on("change", "#select-all-test-cases", function () {
      const isChecked = $(this).is(":checked");

      if (isChecked) {
        // Select all currently visible test cases
        getElement(".test-case-checkbox:not(:checked)").each(function () {
          $(this).prop("checked", true).trigger("change");
        });
      } else {
        // Deselect all currently visible test cases
        getElement(".test-case-checkbox:checked").each(function () {
          $(this).prop("checked", false).trigger("change");
        });
      }
    });
  }

  function handleCategoryChangeWarning() {
    let originalCategoryValue = getElement("#id_category").val();
    getElement("#id_category").on("change", function () {
      const newValue = $(this).val();
      if (globalState.getCount() > 0 && originalCategoryValue !== newValue) {
        const selectedCount = globalState.getCount();
        const confirmChange = confirm(
          `You have ${selectedCount} test case${
            selectedCount > 1 ? "s" : ""
          } selected. ` +
            "Changing the category will show test cases from the new category, " +
            "but your previously selected test cases will remain selected and visible. " +
            "Do you want to continue?"
        );
        if (!confirmChange) {
          $(this).val(originalCategoryValue);
          return false;
        }
      }
      originalCategoryValue = newValue;
    });
  }

  function handleFormSubmission() {
    getElement("form").on("submit", function (e) {
      updateHiddenInput();
      getElement(".field-category").removeClass("has-error");
      getElement("#test-case-error").hide();

      if (globalState.getCount() === 0 && getElement("#id_category").val()) {
        e.preventDefault();
        getElement("#test-case-error").show();
        getElement(".field-category").addClass("has-error");
        getElement(".selection-count").removeClass("success").addClass("error");

        $("html, body").animate(
          {
            scrollTop: getElement("#test-cases-container").offset().top - 100,
          },
          500
        );
        getElement("#id_category").focus();
        return false;
      }

      console.log(
        "Form submitted with test cases:",
        globalState.getOrderedIds()
      );
      console.log(
        "Global state at submission:",
        globalState.getOrderedTestCases()
      );
    });
  }

  function handleApplyCategoryFilter() {
    const categorySelect = document.getElementById("category-filter");
    const applyButton = document.getElementById("apply-category-filter");

    if (applyButton && categorySelect) {
      applyButton.addEventListener("click", function () {
        console.log("Apply button clicked");
        const categoryId = Array.from(categorySelect.selectedOptions)?.map(
          (option) => option.value
        );
        console.log("Selected category IDs:", categoryId);

        const container = getElement("#test-cases-container");
        const tbody = container.find(".test-cases-table tbody");
        const errorDiv = getElement("#test-case-error");
        const successDiv = getElement("#test-case-success");

        // if (categoryId.length === 0) {
        //   console.log("No categories selected, hiding container");
        //   container.addClass("hidden");
        //   errorDiv.hide();
        //   successDiv.hide();
        //   getElement(".field-category").removeClass("has-error");
        //   return;
        // }

        // Show loading
        tbody.html(
          '<tr><td colspan="4" class="no-test-cases"><div class="loading-spinner"></div> Loading test cases...</td></tr>'
        );
        container.removeClass("hidden");

        // Clear validation messages
        errorDiv.hide();
        successDiv.hide();
        getElement(".field-category").removeClass("has-error");

        // KEY CHANGE: Don't clear global state - this preserves selected test cases across category changes
        console.log("Preserving global state during category change");
        globalState.logState();

        // Construct API URL
        const queryString = categoryId.join(",");
        const apiUrl = `/api/v1/test-management/category/get-test-cases/?category_ids=${queryString}`;
        console.log("Calling API:", apiUrl);

        // Fetch test cases
        $.ajax({
          url: apiUrl,
          method: "GET",
          headers: {
            "X-CSRFToken": csrftoken,
            "X-Requested-With": "XMLHttpRequest",
          },
          success: function (data) {
            console.log("API Response:", data);

            if (data.test_cases && data.test_cases.length > 0) {
              console.log("Found test cases from API, updating global state");

              // Update global state with new API test cases
              globalState.setCurrentApiTestCases(data.test_cases);

              // Display merged test cases (API + selected from global state)
              displayTestCasesTable();

              container.removeClass("hidden");
              console.log(
                "Container visibility ensured:",
                !container.hasClass("hidden")
              );
            } else {
              console.log("No test cases found from API");

              // Even if no API test cases, we might have selected test cases to show
              globalState.setCurrentApiTestCases([]);

              if (globalState.getCount() > 0) {
                console.log(
                  "Showing only selected test cases from global state"
                );
                displayTestCasesTable();
              } else {
                tbody.html(
                  '<tr><td colspan="4" class="no-test-cases">No active test cases in this category</td></tr>'
                );
              }
            }

            updateSelectionCount();
            syncLegacyState();
          },
          error: function (xhr, status, error) {
            console.error("API Error:", status, error);
            console.error("Response:", xhr.responseText);

            let errorMessage = "Error loading test cases";
            if (xhr.status === 401 || xhr.status === 403) {
              errorMessage =
                "Authentication required. Please ensure you are logged in.";
            } else if (xhr.status === 404) {
              errorMessage =
                "API endpoint not found. Please check the URL configuration.";
            } else if (xhr.status === 500) {
              errorMessage = "Server error. Please try again later.";
            }

            // Even on error, show selected test cases from global state if any
            if (globalState.getCount() > 0) {
              console.log(
                "API failed, but showing selected test cases from global state"
              );
              globalState.setCurrentApiTestCases([]);
              displayTestCasesTable();

              // Show error message above the table
              const errorRow = `<tr><td colspan="4" class="api-error-message">${errorMessage}</td></tr>`;
              tbody.prepend(errorRow);
            } else {
              tbody.html(
                `<tr><td colspan="4" class="no-test-cases">${errorMessage}</td></tr>`
              );
            }
          },
        });
      });
    } else {
      console.error("Apply button or category select not found!");
    }
  }

  // Additional utility functions for global state management
  function debugGlobalState() {
    console.log("=== DEBUG GLOBAL STATE ===");
    console.log("Selected test cases count:", globalState.getCount());
    console.log(
      "Current API test cases count:",
      globalState.currentApiTestCases.length
    );
    console.log("Ordered IDs:", globalState.getOrderedIds());
    console.log(
      "Merged test cases for display:",
      globalState.getMergedTestCasesForDisplay().length
    );
    globalState.logState();
    console.log("========================");
  }

  // Add global functions for debugging (can be called from browser console)
  window.testSuiteDebug = {
    globalState: globalState,
    debugState: debugGlobalState,
    syncLegacy: syncLegacyState,
  };

  // Document Ready Initialization
  $(document).ready(function () {
    console.log("Initializing Test Suite form with Global State Management");

    // Create the test cases container
    const categoryField = getElement(".field-category");
    if (categoryField.length) {
      console.log("Creating test cases container on page load");
      const container = createTestCasesContainer();
      categoryField.after(container);
      console.log("Container created and inserted");
    } else {
      console.error("Category field not found on page load!");
    }

    // Initialize selected test cases from Django context (edit mode)
    initializeSelectedTestCases();

    // Check for edit mode
    const scriptElement = document.getElementById("existing-test-cases-data");
    let isEditMode = false;
    let existingTestCases = [];

    if (scriptElement) {
      const existingTestCasesJson =
        scriptElement.textContent || scriptElement.innerText;
      if (
        existingTestCasesJson &&
        existingTestCasesJson.trim() !== "" &&
        existingTestCasesJson.trim() !== "[]"
      ) {
        try {
          existingTestCases = JSON.parse(existingTestCasesJson);
          isEditMode =
            Array.isArray(existingTestCases) && existingTestCases.length > 0;
          console.log(
            "Edit mode detected with pre-selected test cases:",
            existingTestCases.length
          );
        } catch (e) {
          console.error("Error parsing existing test cases JSON:", e);
        }
      }
    }

    if (isEditMode) {
      const container = getElement("#test-cases-container");
      container.removeClass("hidden");
      console.log("Showing test cases container in edit mode");

      // Map existing test cases to expected format and set as current API test cases
      const testCasesForDisplay = existingTestCases.map((tc) => ({
        id: tc.id,
        name: tc.name,
        test_case_id: tc.test_case_id,
        test_type: tc.test_type || 1,
        test_type_display: tc.test_type_display || "Robot",
      }));

      // Set current API test cases and display
      globalState.setCurrentApiTestCases(testCasesForDisplay);
      displayTestCasesTable(testCasesForDisplay);

      console.log("Displayed pre-selected test cases in edit mode");
      debugGlobalState();
    }

    // Setup all event handlers
    handleTestCaseSelection();
    handleRowClick();
    handleSelectAll();
    handleCategoryChangeWarning();
    handleFormSubmission();
    handleApplyCategoryFilter();

    // Trigger change if category is pre-selected
    if (getElement("#id_category").val()) {
      getElement("#id_category").trigger("change");
    }

    console.log("Test Suite form initialized with Global State Management");
    console.log("Available debug functions: window.testSuiteDebug");

    // Initial state log
    debugGlobalState();
  });
})(django.jQuery);