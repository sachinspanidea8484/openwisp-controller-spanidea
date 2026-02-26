(function ($) {

    const START_MARKER = "# START_DESCRIPTION";
    const END_MARKER = "# END_DESCRIPTION";

    function extractBetweenMarkers(text) {
      const start = text.indexOf(START_MARKER);
      const end = text.indexOf(END_MARKER);

      if (start === -1 || end === -1 || end <= start) {
        return null;
      }

      return text.slice(start + START_MARKER.length, end).trim();
    }

    function copyPythonToDescription() {
      const fileInput = $("#id_python_script");
      const description = $("#id_description");

      if (!fileInput.length || !description.length) return;

      fileInput.on("change", function () {
        const file = this.files[0];
        if (!file) return;

        // Allow only python files
        if (!file.name.endsWith(".py")) {
          alert("Please select a valid .py file");
          this.value = "";
          return;
        }

        // size check (e.g. 200 KB)
        if (file.size > 200 * 1024) {
          alert("File too large to preview");
          return;
        }

        const reader = new FileReader();

        reader.onload = function (e) {
            const fullText = e.target.result;
            let extracted = extractBetweenMarkers(fullText);

            if (!extracted) {
              return;
            }

            // take confirmation before overwrite
            if (description.val().trim()) {
              const ok = confirm(
                "Description already contains content.\n" +
                  "Do you want to overwrite it with content from the script?"
              );
              if (!ok) return;
            }

            description.val(extracted);
        };

        reader.readAsText(file);
      });
    }
    function toggleScriptFields() {
        const testType = $("#id_test_type").val();

        const pythonRow = $(".field-python_script").closest(".form-row, .field");
        const robotRow = $(".field-robot_script").closest(".form-row, .field");

        if (testType === "1") {
        // ROBOT
        robotRow.show();
        pythonRow.show();
        } else if (testType === "2") {
        // DEVICE
        pythonRow.show();
        robotRow.hide();
        } else {
        pythonRow.hide();
        robotRow.hide();
        }
    }

  $(document).ready(function () {
    toggleScriptFields();
    copyPythonToDescription();
    $("#id_test_type").on("change", toggleScriptFields);
    
  });
})(django.jQuery || jQuery || $);
