(function ($) {
  ("use strict");

  // Get CSRF token
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

  const csrftoken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
  // Store available devices and selected devices
  let availableDevices = [];
  let selectedDevices = new Map(); // Map of device_id -> device_data
  let configPushTestCases = [];
  let pendingGroupSelection = null;
  function applyDisabledState() {
    if (window.disabledViewMode) {
      $(".device-selector select, .device-selector button").prop(
        "disabled",
        true
      );
      $(".remove-device-btn, .remove-all-btn").prop("disabled", true);
    }
  }
  // Create test cases display section
  function createTestCasesDisplay() {
    const container = $(`
            <div id="test-cases-display">
                <div class="section-header">Test Cases in Selected Test Group</div>
                <div class="test-cases-container">
                    <table class="test-cases-readonly-table">
                        <thead>
                            <tr>
                                <th class="readonly-name-col">NAME</th>
                                <th class="readonly-id-col">TEST CASE ID</th>
                                
                                <th class="readonly-type-col">TEST TYPE</th>
                            </tr>
                        </thead>
                        <tbody>
                        </tbody>
                    </table>
                </div>
            </div>
        `);
    return container;
  }

  // Create device selection section
  function createDeviceSelection(mode = "single") {
    const isGroupMode = mode === "group";
    const container = $(`
        <div id="device-selection">
            <div class="section-header">Select ${
              isGroupMode ? "Device Group" : "Devices"
            }</div>
            <div class="device-selector-container">
                <div class="device-selector">
                    <select class="device-dropdown" id="device-dropdown">
                        <option value="">${
                          isGroupMode
                            ? "Loading groups..."
                            : "Loading devices..."
                        }</option>
                    </select>
                    <button type="button" 
                        class="${
                          isGroupMode ? "add-group-btn" : "add-device-btn"
                        }" 
                        id="${
                          isGroupMode ? "add-group-btn" : "add-device-btn"
                        }" 
                        disabled>
                        ${isGroupMode ? "Add Devices from Group" : "Add Device"}
                    </button>
                </div>
            </div>
            <div class="selected-devices-list" id="selected-devices-list">
                <div class="no-devices-selected">No devices selected</div>
            </div>
            <div class="device-count-info">
                <span class="count">0</span> device(s) selected
            </div>
        </div>
        <div id="schedule-execution-info"></div>
        <div class="push-config-div"></div>
    `);

    return container;
  }

  function uploadConfigOverDevice(device_id, file, fileInput) {
    let formData = new FormData();
    formData.append("device_id", device_id);
    formData.append("file", file);
    const apiUrl = `/api/v1/test-management/devices/configuration-push`;
    $.ajax({
      url: apiUrl,
      method: "POST",
      headers: {
        "X-CSRFToken": csrftoken,
      },
      data: formData,
      processData: false,
      contentType: false,
      success: function (data) {
        fileInput.value=""
        console.log("successs", data);
      },
      error: function (data) {
        console.log("error", data);
      },
    });
  }
  $(document).on("click", ".tc-action-btn", function(){
    const deviceId= $(this).data("device-id");

    const fileInput = $(this).closest(".tc-actions").find(".file-input")[0];
    const file = fileInput?.files?.[0];

    if (!file) {
      alert("Please select a file before clicking Run");
      return;
    }
    uploadConfigOverDevice(deviceId, file, fileInput);
  });
  function createPushConfigDiv() {
    const pushconfigcontainer = $(".push-config-div");
    pushconfigcontainer.empty();
    if(configPushTestCases.length >0){
      selectedDevices.forEach((device, deviceId) => {
        const testCasesHTML = configPushTestCases
          .map(
            (tc) => `
              <li class="testcase-row">
                <span class="tc-name">${tc.name}</span>

                <div class="tc-actions">
                  <input type="file" class="file-input" />
                  <button type="button" class="tc-action-btn" data-device-id="${device.id}" data-device-name="${device.name}" data-tc-name= "${tc.name}">Upload on Device</button>
                </div>
              </li>
            `
          )
          .join("");
        const device_cont = `
          <div class="config-device-box">
            <div class="device-header">${device.name}</div>

            <ul class="testcase-list">
              ${testCasesHTML}
            </ul>
          </div>
        `;
        pushconfigcontainer.append(device_cont);
      });
    }
  }

  // CHANGE: Updated handleGroupSelection to properly manage selectedDevices map
  function handleGroupSelection(groupId) {
    // Call API to fetch devices for the group
    const match = window.location.pathname.match(
      /testsuiteexecution\/([0-9a-fA-F-]+)\/change\/$/
    );
    const executionId = match ? match[1] : null;
    const api_url = executionId
      ? `/api/v1/test-management/device-groups/${groupId}/devices/${executionId}`
      : `/api/v1/test-management/device-groups/${groupId}/devices`;
    $.ajax({
      url: api_url,
      method: "GET",
      headers: {
        "X-CSRFToken": csrftoken,
        "X-Requested-With": "XMLHttpRequest",
      },
      success: function (data) {
        const devices = data?.devices || [];
        const list = $("#selected-devices-list");
        list.empty(); // clear old devices

        // CHANGE: Clear previous selections in the map
        selectedDevices.clear();

        if (devices.length === 0) {
          list.append(
            "<div class='no-devices-selected'>No devices in this group</div>"
          );
        } else {
          devices.forEach((device) => {
            const selectedProtocol = device._chosen_protocol;
            isssh = device.connection_protocol === 1 || (selectedProtocol && selectedProtocol==='1')  ? "checked" : "";
            ismqtt =
              device.connection_protocol === 0 ||
              isssh === "" ||
              (selectedProtocol && selectedProtocol === "0")
                ? "checked"
                : "";
            // CHANGE: Add devices to selectedDevices map
            selectedDevices.set(String(device.id), device);

            // CHANGE: Updated UI structure to match single device selection
            list.append(`
                <div class="selected-device-item" data-device-id="${device.id}">
                    <div class="device-info">
                        <div class="device-name">${device.name}</div>
                        <div class="device-details">
                          ${device.organization || ""} - ${
                            device.management_ip || ""
                          } - ${device.status || ""}
                        </div>
                    </div>

                    <div class="protocol-selection">
                      <label>
                        <input type="radio" name="protocol_${
                          device.id
                        }" value="0" 
                        ${ismqtt} ${window.disabledViewMode ? "disabled" : ""} 
                        style="cursor : ${
                          window.disabledViewMode ? "not-allowed" : "pointer"
                        }">
                        MQTT
                      </label>
                      <label>
                        <input type="radio" name="protocol_${device.id}" value="1" ${isssh} 
                        ${window.disabledViewMode ? "disabled" : ""} 
                        style="cursor : ${window.disabledViewMode ? "not-allowed" : "pointer"}">     
                        SSH
                      </label>
                    </div>
                  </div>  
                </div>
              `);
          });
          // Update device count
          // CHANGE: Use updateDeviceCount function for consistency
          updateDeviceCount();
          // CHANGE: Update hidden input to sync form data
          updateHiddenInput();
          createPushConfigDiv();
          $("#device-selection select").prop("disabled", true);
          // Swap "Add Devices from Group" with "Remove All"
          $("#add-group-btn").replaceWith(`
                    <button type="button" class="remove-all-btn" id="remove-all-btn" ${
                      window.disabledViewMode ? "disabled" : ""
                    }>Remove All Devices</button>
                `);

          // CHANGE: Removed the click handler from here - it's now delegated
        }
      },
      error: function () {
        alert("Failed to load devices for the group.");
      },
    });
  }

  // CHANGE: NEW FUNCTION - Load device groups for group mode
  function loadDeviceGroups() {
    const dropdown = $("#device-dropdown");
    dropdown.empty();
    dropdown.append('<option value="">Loading groups...</option>');
    $.ajax({
      url: "/api/v1/test-management/device-groups", // CHANGE: Adjust this endpoint to match your API
      method: "GET",
      headers: {
        "X-CSRFToken": csrftoken,
        "X-Requested-With": "XMLHttpRequest",
      },
      success: function (data) {
        dropdown.empty();
        dropdown.append('<option value="">Select a device group...</option>');
        if (data && data.length > 0) {
          data.forEach(function (group) {
            dropdown.append(
              `<option value="${group.id}">${group.name}</option>`
            );
          });
          if (pendingGroupSelection) {
            const groupId = String(pendingGroupSelection.id);
            const groupName = pendingGroupSelection.name;

            // Check if option exists
            if (dropdown.find(`option[value='${groupId}']`).length === 0) {
              // Add missing option
              dropdown.append(
                `<option value="${groupId}">${groupName}</option>`
              );
            }

            // Select the option
            dropdown.val(groupId).trigger("change");

            // Handle the group selection
            handleGroupSelection(groupId);

            // Clear the pending selection
            pendingGroupSelection = null;
          }
        } else {
          dropdown.append(
            '<option value="">No device groups available</option>'
          );
        }
        applyDisabledState();
      },
      error: function (xhr, status, error) {
        console.error("Error loading device groups:", error);
        dropdown.html('<option value="">Error loading groups</option>');
        applyDisabledState();
      },
    });
  }

  // CHANGE: Completely replaced the radio button change handler with improved version
  // Remove any existing radio button handlers first to avoid duplicates
  $(document).off("change", "#id_device_selection input[type=radio]");
  $(document).off("change", "#id_test_selection_type input[type=radio]");

  $(document).on("change", "#id_test_selection_type input[type=radio]", function(){
    configPushTestCases=[];
    createPushConfigDiv();
  });

  // Handle radio button changes
  $(document).on(
    "change",
    "#id_device_selection input[type=radio]",
    function () {
      const deviceSelectionField = $(".field-device_selection");
      const selection = $(this).val(); // "0" for single, "1" for group
      selectedDevices.clear();
      // Remove old container
      $("#device-selection").remove();
      $("#schedule-execution-info").remove();
      $(".push-config-div").remove();

      if (selection === "0") {
        // Single device mode
        deviceSelectionField.after(createDeviceSelection("single"));
        loadAvailableDevices(); // This populates the dropdown
      } else if (selection === "1") {
        // Group mode
        const cont = createDeviceSelection("group");
        deviceSelectionField.after(cont);

        loadDeviceGroups(); // CHANGE: Now calling the new loadDeviceGroups function
      }
      createPushConfigDiv();
    }
  );

  // CHANGE: NEW - Delegated handler for device dropdown changes
  $(document).on("change", "#device-dropdown", function () {
    const value = $(this).val();

    // Check which button exists to determine the mode
    if ($("#add-device-btn").length > 0) {
      // Single device mode
      $("#add-device-btn").prop("disabled", !value);
    } else if ($("#add-group-btn").length > 0) {
      // Group mode
      $("#add-group-btn").prop("disabled", !value);
    }
  });

  // CHANGE: NEW - Delegated handler for "Add Devices from Group" button
  $(document).on("click", "#add-group-btn", function () {
    const groupId = $("#device-dropdown").val();
    if (groupId) {
      handleGroupSelection(groupId);
    }
  });

  // CHANGE: NEW - Delegated handler for "Remove All Devices" button
  $(document).on("click", "#remove-all-btn", function () {
    const list = $("#selected-devices-list");
    list
      .empty()
      .append("<div class='no-devices-selected'>No devices selected</div>");
    $(".device-count-info .count").text(0);

    // Clear the selectedDevices map
    selectedDevices.clear();
    updateHiddenInput();
    $("#device-selection select").prop("disabled", false);
    // Replace with "Add Devices from Group" button
    $(this).replaceWith(`
            <button type="button" class="add-group-btn" id="add-group-btn" disabled>
                Add Devices from Group
            </button>
        `);

    // Reset dropdown
    $("#device-dropdown").val("");
  });

  const apiUrl = `/api/v1/test-management/devices`;
  // Load available devices on page load
  function loadAvailableDevices() {
    $.ajax({
      url: apiUrl,
      method: "GET",
      headers: {
        "X-CSRFToken": csrftoken,
        "X-Requested-With": "XMLHttpRequest",
      },
      success: function (data) {
        console.log("Available devices:", data);
        availableDevices = data.devices || [];
        updateDeviceDropdown();
        applyDisabledState();
      },
      error: function (xhr, status, error) {
        console.error("Error loading devices:", error);
        $("#device-dropdown").html(
          '<option value="">Error loading devices</option>'
        );
        applyDisabledState();
      },
    });
  }

  function initializeDeviceSelection() {
    const selectedValue = $('input[name="device_selection"]:checked').val();
    console.log("Initializing device selection, type:", selectedValue);

    // Remove any existing container
    $("#device-selection").remove();

    const deviceSelectionField = $(".field-device_selection");

    if (selectedValue === "1") {
      // Group mode
      const deviceSelection = createDeviceSelection("group");
      deviceSelectionField.after(deviceSelection);
      loadDeviceGroups();
    } else {
      // Single mode (default or when value is "0")
      const deviceSelection = createDeviceSelection("single");
      deviceSelectionField.after(deviceSelection);
      loadAvailableDevices();
    }
  }
  // Insert containers after test_suite field
  const testSuiteField = $(".field-test_suite");
  const deviceSelectionField = $(".field-device_selection");
  if (testSuiteField.length) {
    const testCasesDisplay = createTestCasesDisplay();

    testSuiteField.after(testCasesDisplay);
    initializeDeviceSelection();
  }



  // Update device dropdown

  // Update device dropdown
  function updateDeviceDropdown() {
    const dropdown = $("#device-dropdown");
    dropdown.empty();

    if (availableDevices.length === 0) {
      dropdown.append('<option value="">No devices available</option>');
      $("#add-device-btn").prop("disabled", true);
      return;
    }

    dropdown.append('<option value="">Select a device...</option>');

    availableDevices.forEach(function (device) {
      // Don't show already selected devices
      if (
        !selectedDevices.has(String(device.id)) &&
        device.status !== "Deactivated"
      ) {
        dropdown.append(`
                    <option value="${device.id}">
                        ${device.name} (${device.organization}) - ${device.status}
                    </option>
                `);
      }
    });

    if (!window.disabledViewMode) {
      $("#add-device-btn").prop("disabled", false);
    }
  }
  $(document).on("change", "input[name^='protocol_']", function () {
    const id = $(this).attr("name").replace("protocol_", "");
    const dev = selectedDevices.get(id);
    if (dev) {
      dev._chosen_protocol = $(this).val(); // Save selected protocol
    }
    updateHiddenInput();
  });

  // Handle test suite selection change
  $(document).on("change", "#id_test_suite", function () {
    const testSuiteId = $(this).val();
    const testCasesDisplay = $("#test-cases-display");
    const deviceSelection = $("#device-selection");
    const tbody = testCasesDisplay.find("tbody");
    if (!testSuiteId) {
      testCasesDisplay.hide();
      //   deviceSelection.hide();
      return;
    }

    // Show loading
    tbody.html(
      '<tr><td colspan="4" style="text-align: center; padding: 20px;"><div class="loading-spinner"></div> Loading test cases...</td></tr>'
    );
    testCasesDisplay.show();
    deviceSelection.show();

    const apiUrl = `/api/v1/test-management/test-suite/${testSuiteId}/details/`;

    // Fetch test suite details
    $.ajax({
      url: apiUrl,
      method: "GET",
      headers: {
        "X-CSRFToken": csrftoken,
        "X-Requested-With": "XMLHttpRequest",
      },
      success: function (data) {
        console.log("Test suite details:", data);
        displayTestCases(data.test_cases);
      },
      error: function (xhr, status, error) {
        console.error("Error loading test suite details:", error);
        tbody.html(
          '<tr><td colspan="4" style="text-align: center; padding: 20px; color: #dc3545;">Error loading test cases</td></tr>'
        );
      },
    });
  });

  // Display test cases (read-only)
  function displayTestCases(testCases) {
    const tbody = $("#test-cases-display tbody");
    tbody.empty();

    if (!testCases || testCases.length === 0) {
      tbody.html(
        '<tr><td colspan="4" style="text-align: center; padding: 20px; color: #999;">No test cases in this test group</td></tr>'
      );
      return;
    }

    testCases.forEach(function (testCase) {
      const typeClass =
        testCase.test_type === 1
          ? "readonly-test-type-robot"
          : "readonly-test-type-agent";
      const row = $(`
                <tr>
                    <td class="readonly-name-col">
                        <div class="readonly-test-case-name">${testCase.name}</div>
                    </td>
                    <td class="readonly-id-col">
                        <div class="readonly-test-case-id">${testCase.test_case_id}</div>
                    </td>
                   
                    <td class="readonly-type-col">
                        <span class="readonly-test-type-badge ">${testCase.test_type_display}</span>
                    </td>
                </tr>
            `);

      tbody.append(row);
      
    });
    configPushTestCases = testCases.filter(
      (t) => t.is_configuration_push_required
    );
    createPushConfigDiv();
  }
  $(document).ready(function () {
    if (window.recoveredDevices && window.recoveredDevices.length > 0) {
      window.recoveredDevices.forEach((device) => {
        if (device.status !== "Deactivated") {
          selectedDevices.set(String(device.id), device);
        }
      });

      // Sync UI after preload
      updateSelectedDevicesList();
      updateDeviceDropdown();
      updateDeviceCount();
      updateHiddenInput();
    }
    if (window.recoveredDeviceGroup?.id) {
      pendingGroupSelection = window.recoveredDeviceGroup;
    }
   
    if(window.scheduled_dt_time){
      const element = document.getElementById("schedule-execution-info");
      element.innerHTML = `<strong style={{}}>Scheduled Execution Time:</strong> ${(() => {
        const d = new Date(window.scheduled_dt_time);
        return `${String(d.getDate()).padStart(2, "0")}-${String(
          d.getMonth() + 1
        ).padStart(2, "0")}-${d.getFullYear()} ${String(d.getHours()).padStart(
          2,
          "0"
        )}:${String(d.getMinutes()).padStart(2, "0")}`;
      })()}`;
    }


    const target = document.querySelector(".field-individual_test_cases");

    if (!target) {
      console.log("M2M field not found");
      return;
    }

    const observer1 = new MutationObserver(() => {
      const chosenBox = document.getElementById("id_individual_test_cases_to");

      if (chosenBox) {
        // attachM2MListeners();
        const observer2 = new MutationObserver(() => {
          logValues();
        });

        observer2.observe(chosenBox, {
          childList: true, // options added/removed
          subtree: true,
        });
        observer1.disconnect(); // Stop observing once initialized
      }
    });

    observer1.observe(target, { childList: true, subtree: true });
   

    // Mutation observer to detect any change to options
    const el= document.querySelector("#testcase-config-json");
    const casetoconfigmapping= JSON.parse(el.textContent);
    function logValues() {
      
      configPushTestCases=[]
      configPushTestCases = Array.from(
        document.querySelectorAll("#id_individual_test_cases_to option")
      )
        .map((opt) => ({
          value: opt.value,
          title: opt.title,
          name: opt.title.split("-configRequired")[0],
        }))
        .filter((tc) => casetoconfigmapping[tc.value] === true);

      createPushConfigDiv();
    }
  });
  
 

  // CHANGE: Converted to delegated event handler for add device button
  $(document).off("click", "#add-device-btn"); // Remove any existing direct handlers
  $(document).on("click", "#add-device-btn", function () {
    const deviceId = $("#device-dropdown").val();

    if (!deviceId) {
      // You might want to uncomment this for better UX
      // alert('Please select a device first');
      return;
    }

    // Find device in available devices
    const device = availableDevices.find(
      (d) => String(d.id) === String(deviceId)
    );
    if (!device) {
      alert("Device not found");
      return;
    }

    // Add to selected devices
    selectedDevices.set(String(deviceId), device);

    // Update displays
    updateSelectedDevicesList();
    updateDeviceDropdown();
    updateDeviceCount();
    updateHiddenInput();
    createPushConfigDiv();

    // Reset dropdown
    $("#device-dropdown").val("");
  });
  // Update selected devices list
  function updateSelectedDevicesList() {
    const container = $("#selected-devices-list");
    container.empty();

    if (selectedDevices.size === 0) {
      container.html(
        '<div class="no-devices-selected">No devices selected</div>'
      );
      return;
    }

    selectedDevices.forEach(function (device, deviceId) {

       const selectedProtocol = device._chosen_protocol;
      
       issshChecked =
         device.connection_protocol === 1 ||
         (selectedProtocol && selectedProtocol === "1")
           ? "checked"
           : "";
       ismqttChecked =
         device.connection_protocol === 0 ||
         issshChecked === "" ||
         (selectedProtocol && selectedProtocol === "0")
           ? "checked"
           : "";
      const deviceItem = $(`
                <div class="selected-device-item" data-device-id="${deviceId}">
                    <div class="device-info">
                        <div class="device-name">${device.name}</div>
                        <div class="device-details">${device.organization} - ${
                          device.management_ip
                        } - ${device.status}</div>
                    </div>

                    <div class="protocol-selection">
                      <label>
                        <input type="radio" name="protocol_${device.id}" value="0" ${ismqttChecked}>
                        MQTT
                      </label>
                      <label>
                        <input type="radio" name="protocol_${device.id}" value="1" ${issshChecked}>
                        SSH
                      </label>
                    </div>
                    <button type="button" class="remove-device-btn" data-device-id="${deviceId}" ${
                      window.disabledViewMode ? "disabled" : ""
                    }>Remove</button>
                </div>
            `);
      if (device?.status !== "Deactivated") {
        container.append(deviceItem);
      }
    });
  }

  // Handle device removal
  $(document).on("click", ".remove-device-btn", function () {
    const deviceId = $(this).data("device-id");

    // Remove from selected devices
    selectedDevices.delete(String(deviceId));

    // Update displays
    updateSelectedDevicesList();
    updateDeviceDropdown();
    updateDeviceCount();
    updateHiddenInput();
    createPushConfigDiv();
  });

  // Update device count
  function updateDeviceCount() {
    const count = selectedDevices.size;
    const countInfo = $(".device-count-info .count");
    countInfo.text(count);

    // Update text
    const textSpan = $(".device-count-info");
    if (count === 1) {
      textSpan.html(`<span class="count">${count}</span> device selected`);
    } else {
      textSpan.html(`<span class="count">${count}</span> devices selected`);
    }
  }

  // Update hidden input with selected devices
  function updateHiddenInput() {
    let input = $('input[name="selected_devices_data"]');

    if (!input.length) {
      input = $('<input type="hidden" name="selected_devices_data">');
      $("form").append(input);
    }

    // Get device IDs
    const deviceIds = Array.from(selectedDevices.keys()).map((id)=> {
      const selectedProtocol = $(`input[name="protocol_${id}"]:checked`).val() || 0;
      return {id, protocol : selectedProtocol};
    });
    input.val(JSON.stringify(deviceIds));
    console.log("Updated selected devices:", deviceIds);

    // Handle device group
    let groupInput = $('input[name="device_group"]');
    if (!groupInput.length) {
      groupInput = $(
        '<input type="hidden" name="device_group" id="id_device_group">'
      );
      $("form").append(groupInput);
    }

    // If "Device Group Selection" is chosen, set the group id
    const selectedType = $('input[name="device_selection"]:checked').val();
    if (selectedType === "1") {
      const groupId = $("#device-dropdown").val(); // or however you let user pick group
      groupInput.val(groupId);
      console.log("Updated device_group:", groupId);
    } else {
      groupInput.val(""); // not needed in single mode
    }
  }

  // Form submission validation
  $("form").on("submit", function (e) {
    updateHiddenInput();

    // Validate test suite selection
    // if (!$('#id_test_suite').val()) {
    //     alert('Please select a test group');
    //     e.preventDefault();
    //     return false;
    // }

    // Validate device selection
    // if (selectedDevices.size === 0) {
    //     alert('Please select at least one device');
    //     e.preventDefault();
    //     return false;
    // }

    console.log(
      "Form submitted with devices:",
      Array.from(selectedDevices.keys())
    );
  });

  // Initialize on page load
  // loadAvailableDevices();

  // If editing existing execution, trigger test suite change to load test cases
  if ($("#id_test_suite").val()) {
    $("#id_test_suite").trigger("change");
  }

  console.log("TestSuiteExecution form initialized");
})(django.jQuery);
