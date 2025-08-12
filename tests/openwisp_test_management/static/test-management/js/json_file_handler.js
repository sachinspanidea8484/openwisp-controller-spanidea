(function ($) {
  $(document).ready(function () {
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
})(django.jQuery || jQuery || $); // Try multiple jQuery sources
