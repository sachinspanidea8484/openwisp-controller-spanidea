(function ($) {
  $(document).ready(function () {

    // adding regex to test case id field
    document
      .getElementById("id_test_case_id")
      .addEventListener("input", function () {
        this.value = this.value.replace(/[^A-Za-z0-9_\-.:/]/g, "");
      });

    // Create a custom button for file upload
    var $jsonFileInput = $("#json-file-input");
    var $paramsField = $("#id_params");

    if ($jsonFileInput.length && $paramsField.length) {
      // Create custom upload button
      var $uploadBtn = $(
        '<button type="button" class="btn btn-secondary json-upload-btn">📁 Load JSON File</button>'
      );

      // Insert button after the params field
      $paramsField.after($uploadBtn);

      // Handle button click
      $uploadBtn.on("click", function (e) {
        e.preventDefault();
        $jsonFileInput.click();
      });

      // Handle file selection
      $jsonFileInput.on("change", function (e) {
        console.log("File input changed");
        var file = e.target.files[0];
        console.log("file", file);

        if (
          file &&
          (file.type === "application/json" || file.name.endsWith(".json"))
        ) {
          var reader = new FileReader();

          reader.onload = function (e) {
            try {
              var jsonContent = e.target.result;

              // Validate JSON
              // JSON.parse(jsonContent);
              console.log("jsonContent:", jsonContent);

              // Populate the params field
              $paramsField.val(jsonContent);

              // Show success message
            //   showMessage("JSON file loaded successfully!", "success");
            } catch (error) {
            //   showMessage("Invalid JSON file: " + error.message, "error");
            }
          };

          reader.readAsText(file);
        } else {
        //   showMessage("Please select a valid JSON file.", "error");
        }

        // Reset file input
        $(this).val("");
      });
    }

    // Function to show messages
    function showMessage(message, type) {
      var $messageDiv = $(".json-message");
      if ($messageDiv.length === 0) {
        $messageDiv = $('<div class="json-message"></div>');
        $(".json-upload-btn").after($messageDiv);
      }

      $messageDiv
        .removeClass("success error")
        .addClass(type)
        .text(message)
        .fadeIn();

      setTimeout(function () {
        $messageDiv.fadeOut();
      }, 3000);
    }
  });
  document.addEventListener("DOMContentLoaded", function () {
    const testTypeField = document.querySelector("#id_test_type");
    const helpText = testTypeField.closest(".form-row").querySelector(".help");
    function updateHelpText() {
      if (testTypeField.value === "2") {
        helpText.textContent = "Runs tests using Device Agent.";
      } else if (testTypeField.value === "1") {
        helpText.textContent = "Runs tests using Robot Framework.";
      } else {
        helpText.textContent = "Select the type of testshahshs.";
      }
    }

    // On page load
    updateHelpText();

    // On change
    testTypeField.addEventListener("change", updateHelpText);
  });
})(django.jQuery || jQuery || $); // Try multiple jQuery sources



