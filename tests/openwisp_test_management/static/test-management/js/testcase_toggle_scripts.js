(function ($) {
    const START_MARKER = "# START_DESCRIPTION";
    const END_MARKER = "# END_DESCRIPTION";

    // Store original file names on page load
    let originalPythonFile = null;
    let originalRobotFile = null;

    function extractBetweenMarkers(text) {
    const start = text.indexOf(START_MARKER);
    const end = text.indexOf(END_MARKER);
    
    if (start === -1 || end === -1 || end <= start) {
        return null;
    }
    
    // Extract text between markers
    let extracted = text.slice(start + START_MARKER.length, end).trim();
    
    // Clean up: Remove leading # and spaces from each line
    let lines = extracted.split('\n');
    let cleanedLines = lines.map(line => {
        // Remove leading # and spaces
        return line.replace(/^\s*#\s?/, '').trim();
    }).filter(line => line.length > 0); // Remove empty lines
    
    // Join back with newlines
    return cleanedLines.join('\n');
}

    function copyPythonToDescription() {
    const fileInput = $("#id_python_script");
    const description = $("#id_description");
    if (!fileInput.length || !description.length) return;

    fileInput.on("change", function () {
        const file = this.files[0];
        if (!file) return;

        if (!file.name.endsWith(".py")) {
            alert("Please select a valid .py file");
            this.value = "";
            return;
        }

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

            const currentDescription = description.val().trim();
            
            // **NEW: Check if extracted content is same as current description**
            if (currentDescription === extracted) {
                // Same content, no need to ask or update
                return;
            }

            // Only ask if description has content AND it's different
            if (currentDescription) {
                const ok = confirm(
                    "Description already contains content.\n" +
                    "Do you want to overwrite it with content from the python script?"
                );
                if (!ok) return;
            }
            
            description.val(extracted);
        };
        reader.readAsText(file);
    });
}

    // **NEW: Warning for file replacement**
    function checkFileReplacement() {
        const pythonInput = $("#id_python_script");
        const robotInput = $("#id_robot_script");
        const testCaseIdInput = $("#id_test_case_id");

        // Store original values on page load (edit mode)
        if (pythonInput.length) {
            const currentPythonLink = pythonInput.parent().find('a').text();
            if (currentPythonLink) {
                originalPythonFile = currentPythonLink;
            }
        }

        if (robotInput.length) {
            const currentRobotLink = robotInput.parent().find('a').text();
            if (currentRobotLink) {
                originalRobotFile = currentRobotLink;
            }
        }

        // **Python file change warning**
        pythonInput.on("change", function () {
            const file = this.files[0];
            if (!file) return;

            // Only warn in EDIT mode when original file exists
            if (originalPythonFile) {
                const confirmed = confirm(
                    "⚠️ WARNING: Replacing Python Script\n\n" +
                    `Current file: ${originalPythonFile}\n` +
                    `New file: ${file.name}\n\n` +
                    "This will OVERRIDE the existing script in the system.\n" +
                    "The old script will be permanently replaced.\n\n" +
                    "Do you want to continue?"
                );

                if (!confirmed) {
                    this.value = ""; // Clear the input
                    return false;
                }
            }
        });

        // **Robot file change warning**
        robotInput.on("change", function () {
            const file = this.files[0];
            if (!file) return;

            if (originalRobotFile) {
                const testCaseId = testCaseIdInput.val() || "the current ID";
                const confirmed = confirm(
                    "⚠️ WARNING: Replacing Robot Script\n\n" +
                    `Current file: ${originalRobotFile}\n` +
                    `New file: ${file.name}\n\n` +
                    "This will OVERRIDE the existing script in the system.\n" +
                    "The old script will be permanently replaced.\n\n" +
                    "Do you want to continue?"
                );

                if (!confirmed) {
                    this.value = "";
                    return false;
                }
            }
        });

        // **Test Case ID change warning (when robot file exists)**
        testCaseIdInput.on("blur", function () {
            const newId = $(this).val();
            const originalId = $(this).data("original-value");

            // Store original value on first load
            if (!originalId) {
                $(this).data("original-value", newId);
                return;
            }

            // Check if ID changed AND robot file exists
            if (newId !== originalId && originalRobotFile) {
                // const confirmed = confirm(
                //     "⚠️ WARNING: Test Case ID Changed\n\n" +
                //     `Old ID: ${originalId}\n` +
                //     `New ID: ${newId}\n\n` +
                //     "This will automatically update:\n" +
                //     `• The [Tags] line in ${originalRobotFile}\n` +
                //     "• All references in the system\n\n" +
                //     "Do you want to continue?"
                // );

                // if (!confirmed) {
                //     $(this).val(originalId); // Revert to original
                //     return false;
                // }
                
                // Update the original value
                $(this).data("original-value", newId);
            }
        });
    }

    function toggleScriptFields() {
        const testType = $("#id_test_type").val();
        const pythonRow = $(".field-python_script").closest(".form-row, .field");
        const robotRow = $(".field-robot_script").closest(".form-row, .field");

        if (testType === "1") { // ROBOT
            robotRow.show();
            pythonRow.show();
        } else if (testType === "2") { // DEVICE
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
        checkFileReplacement(); // **NEW**
        
        $("#id_test_type").on("change", toggleScriptFields);
    });

})(django.jQuery || jQuery || $);