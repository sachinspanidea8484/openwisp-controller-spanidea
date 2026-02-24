(function ($) {
  "use strict";

  $(document).ready(function () {
    
    console.log("Test Execution Toggle JS Loaded");

    // Function to toggle test selection fields
    function toggleTestSelectionFields() {
      var selectedType = $('input[name="test_selection_type"]:checked').val();
      console.log("Test selection type changed to:", selectedType);

      // Get the form rows
      var testSuiteRow = $(".field-test_suite");
      var individualTestCasesRow = $(".field-individual_test_cases");
      const testCasesDisplay = $("#test-cases-display");

      if (selectedType === "0" && testCasesDisplay) {
        testCasesDisplay.hide();
      }
      
      if (selectedType === "1") {
        // Test Suite mode
        if(testCasesDisplay){
          testCasesDisplay.show();
        }
        testSuiteRow.show().addClass("required-field");
        individualTestCasesRow.hide().removeClass("required-field");

        // Update field requirements
        $("#id_test_suite").prop("required", true);

        // Clear individual test cases selection
        if ($("#id_individual_test_cases_from").length) {
          $("#id_individual_test_cases_from option:selected").each(function () {
            $(this).prop("selected", false);
          });
        }

        // Add visual indicator
        if (!testSuiteRow.find("label .required-indicator").length) {
          testSuiteRow
            .find("label")
            .append(
              '<span class="required-indicator" style="color: #ba2121; font-weight: bold;"> *</span>'
            );
        }
        individualTestCasesRow.find(".required-indicator").remove();
      } else if (selectedType === "0") {
        // Individual mode
        testSuiteRow.hide().removeClass("required-field");
        individualTestCasesRow.show().addClass("required-field");

        // Update field requirements
        $("#id_test_suite").prop("required", false);

        // Clear test suite selection
        $("#id_test_suite").val("");

        // Add visual indicator
        if (!individualTestCasesRow.find("label .required-indicator").length) {
          individualTestCasesRow
            .find("label")
            .first()
            .append(
              '<span class="required-indicator" style="color: #ba2121; font-weight: bold;"> *</span>'
            );
        }
        testSuiteRow.find(".required-indicator").remove();
      }
    }

  

    // Run on page load
    toggleTestSelectionFields();

    // Run when radio buttons change
    $('input[name="test_selection_type"]').on(
      "change",
      toggleTestSelectionFields
    );
    

    // Form validation before submit
    // $("form").on("submit", function (e) {
    //   var testSelectionType = $(
    //     'input[name="test_selection_type"]:checked'
    //   ).val();

    //   if (testSelectionType === "1") {
    //     // Test Suite mode - validate test_suite is selected
    //     if (!$("#id_test_suite").val()) {
    //       e.preventDefault();
    //       alert("Please select a test suite.");
    //       $("#id_test_suite").focus();
    //       return false;
    //     }
    //   } else if (testSelectionType === "0") {
    //     // Individual mode - validate at least one test case is selected
    //     if ($("#id_individual_test_cases_to option").length === 0) {
    //       e.preventDefault();
    //       alert("Please select at least one test case.");
    //       return false;
    //     }
    //   }

    //   // Device validation
    //   var deviceSelection = $('input[name="device_selection"]:checked').val();
    //   if (deviceSelection === "1") {
    //     if (!$("#id_device_group").val()) {
    //       e.preventDefault();
    //       alert("Please select a device group.");
    //       $("#id_device_group").focus();
    //       return false;
    //     }
    //   }
    // });
  
    const orderedIds = window.ORDERED_TESTCASE_IDS || [];
    if (!orderedIds.length) return;

    const observer = new MutationObserver(function () {
      const $selected = $('select[multiple][id$="_to"]');
  
      if (!$selected.length) return;

      const options = {};
      $selected.find("option").each(function () {
        options[this.value] = this;
      });

      $selected.empty();
      orderedIds.forEach((id) => options[id] && $selected.append(options[id]));

      observer.disconnect();
    });

    observer.observe(document.body, { childList: true, subtree: true });

  });
})(django.jQuery);
