(function ($) {
  $(document).ready(function () {
    const style = document.createElement("style");
    style.textContent = `
      .info-container {
        position: relative;
        display: inline-block;
        margin-left: 10px;
        align-content: center;
      }

      .info-icon {
        width: 20px;
        height: 20px;
        background-color: #3a3636;
        color: white;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        font-weight: bold;
        font-size: 14px;
      }

      .info-content {
        visibility: hidden;
        opacity: 0;
        position: absolute;
        top: -22px;
        left: 30px;
        background-color: #f9f9f9;
        min-width: 500px;
        box-shadow: 0px 8px 16px rgba(0,0,0,0.2);
        padding-left: 30px;
        padding-top: 20px;
        border-radius: 6px;
        z-index: 1000;
        transition: opacity 0.3s;
        
      }

      .info-container:hover .info-content {
        visibility: visible;
        opacity: 1;
      }

      .info-content ol {
        margin: 0;
        
      }
      form .aligned ol{
        margin-left :0 ;
        padding-left:0;
      }
      .info-content ol li {
        margin-bottom: 5px;
      }
      .form-row{
        overflow: visible;
      }
    `;
    document.head.appendChild(style);
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
        helpText.textContent =
          "The Device will run test cases directly on the Device.";
      } else if (testTypeField.value === "1") {
        helpText.textContent =
          "The test type Robot Framework defines the test cases that will run through Robot Framework.";
      } else {
        helpText.textContent = "Select the type of testshahshs.";
      }
    }
    const element = document.querySelector("#id_test_type");
    const toadd = `
      <div class="info-container">
        <span class="info-icon">i</span>
        <div class="info-content">
          <ol>
            <li>The test type Robot Framework defines the test cases that will run through Robot Framework.</li>
            <li>The Device will run test cases directly on the Device.</li>
           
          </ol>
        </div>
      </div>
    `;
    element.insertAdjacentHTML("afterend",toadd)
    // On page load
    updateHelpText();

    // On change
    testTypeField.addEventListener("change", updateHelpText);
  });
})(django.jQuery || jQuery || $); // Try multiple jQuery sources



