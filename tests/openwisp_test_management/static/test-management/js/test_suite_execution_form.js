
(function($) {
    'use strict';
    
    // Get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    const csrftoken = getCookie('csrftoken');
    
    // Store available devices and selected devices
    let availableDevices = [];
    let selectedDevices = new Map(); // Map of device_id -> device_data
    
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
                                <th class="readonly-category-col">CATEGORY</th>
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
    function createDeviceSelection() {
        const container = $(`
            <div id="device-selection">
                <div class="section-header">Select Devices</div>
                <div class="device-selector-container">
                    <div class="device-selector">
                        <select class="device-dropdown" id="device-dropdown">
                            <option value="">Loading devices...</option>
                        </select>
                        <button type="button" class="add-device-btn" id="add-device-btn" disabled>Add Device</button>
                    </div>
                </div>
                <div class="selected-devices-list" id="selected-devices-list">
                    <div class="no-devices-selected">No devices selected</div>
                </div>
                <div class="device-count-info">
                    <span class="count">0</span> device(s) selected
                </div>
            </div>
        `);
        return container;
    }
    
    // Insert containers after test_suite field
    const testSuiteField = $('.field-test_suite');
    if (testSuiteField.length) {
        const testCasesDisplay = createTestCasesDisplay();
        const deviceSelection = createDeviceSelection();
        testSuiteField.after(testCasesDisplay);
        testCasesDisplay.after(deviceSelection);
    }
    
    const apiUrl = `/api/v1/test-management/devices`;
    // Load available devices on page load
    function loadAvailableDevices() {
        $.ajax({
            url: apiUrl,
            method: 'GET',
            headers: {
                'X-CSRFToken': csrftoken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function(data) {
                console.log('Available devices:', data);
                availableDevices = data.devices || [];
                updateDeviceDropdown();
            },
            error: function(xhr, status, error) {
                console.error('Error loading devices:', error);
                $('#device-dropdown').html('<option value="">Error loading devices</option>');
            }
        });
    }
    
    // Update device dropdown
    function updateDeviceDropdown() {
        const dropdown = $('#device-dropdown');
        dropdown.empty();
        
        if (availableDevices.length === 0) {
            dropdown.append('<option value="">No devices available</option>');
            $('#add-device-btn').prop('disabled', true);
            return;
        }
        
        dropdown.append('<option value="">Select a device...</option>');
        
        availableDevices.forEach(function(device) {
            // Don't show already selected devices
            if (!selectedDevices.has(String(device.id))) {
                dropdown.append(`
                    <option value="${device.id}">
                        ${device.name} (${device.organization}) - ${device.status}
                    </option>
                `);
            }
        });
        
        $('#add-device-btn').prop('disabled', false);
    }
    
    // Handle test suite selection change
    $('#id_test_suite').on('change', function() {
        const testSuiteId = $(this).val();
        const testCasesDisplay = $('#test-cases-display');
        const deviceSelection = $('#device-selection');
        const tbody = testCasesDisplay.find('tbody');
        
        if (!testSuiteId) {
            testCasesDisplay.hide();
            deviceSelection.hide();
            return;
        }
        
        // Show loading
        tbody.html('<tr><td colspan="4" style="text-align: center; padding: 20px;"><div class="loading-spinner"></div> Loading test cases...</td></tr>');
        testCasesDisplay.show();
        deviceSelection.show();
        
        const apiUrl = `/api/v1/test-management/test-suite/${testSuiteId}/details/`;

        

        // Fetch test suite details
        $.ajax({
            url: apiUrl,
            method: 'GET',
            headers: {
                'X-CSRFToken': csrftoken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function(data) {
                console.log('Test suite details:', data);
                displayTestCases(data.test_cases);
            },
            error: function(xhr, status, error) {
                console.error('Error loading test suite details:', error);
                tbody.html('<tr><td colspan="4" style="text-align: center; padding: 20px; color: #dc3545;">Error loading test cases</td></tr>');
            }
        });
    });
    
    // Display test cases (read-only)
    function displayTestCases(testCases) {
        const tbody = $('#test-cases-display tbody');
        tbody.empty();
        
        if (!testCases || testCases.length === 0) {
            tbody.html('<tr><td colspan="4" style="text-align: center; padding: 20px; color: #999;">No test cases in this test group</td></tr>');
            return;
        }
        
        testCases.forEach(function(testCase) {
            const typeClass = testCase.test_type === 1 ? 'readonly-test-type-robot' : 'readonly-test-type-agent';
            
            const row = $(`
                <tr>
                    <td class="readonly-name-col">
                        <div class="readonly-test-case-name">${testCase.name}</div>
                    </td>
                    <td class="readonly-id-col">
                        <div class="readonly-test-case-id">${testCase.test_case_id}</div>
                    </td>
                    <td class="readonly-category-col">${testCase.category}</td>
                    <td class="readonly-type-col">
                        <span class="readonly-test-type-badge ">${testCase.test_type_display}</span>
                    </td>
                </tr>
            `);
            
            tbody.append(row);
        });
    }
    
    // Handle add device button click
    $('#add-device-btn').on('click', function() {
        const deviceId = $('#device-dropdown').val();
        
        if (!deviceId) {
            alert('Please select a device first');
            return;
        }
        
        // Find device in available devices
        const device = availableDevices.find(d => String(d.id) === String(deviceId));
        if (!device) {
            alert('Device not found');
            return;
        }
        
        // Add to selected devices
        selectedDevices.set(String(deviceId), device);
        
        // Update displays
        updateSelectedDevicesList();
        updateDeviceDropdown();
        updateDeviceCount();
        updateHiddenInput();
        
        // Reset dropdown
        $('#device-dropdown').val('');
    });
    
    // Update selected devices list
    function updateSelectedDevicesList() {
        const container = $('#selected-devices-list');
        container.empty();
        
        if (selectedDevices.size === 0) {
            container.html('<div class="no-devices-selected">No devices selected</div>');
            return;
        }
        
        selectedDevices.forEach(function(device, deviceId) {
            const deviceItem = $(`
                <div class="selected-device-item" data-device-id="${deviceId}">
                    <div class="device-info">
                        <div class="device-name">${device.name}</div>
                        <div class="device-details">${device.organization} - ${device.last_ip} - ${device.status}</div>
                    </div>
                    <button type="button" class="remove-device-btn" data-device-id="${deviceId}">Remove</button>
                </div>
            `);
            
            container.append(deviceItem);
        });
    }
    
    // Handle device removal
    $(document).on('click', '.remove-device-btn', function() {
        const deviceId = $(this).data('device-id');
        
        // Remove from selected devices
        selectedDevices.delete(String(deviceId));
        
        // Update displays
        updateSelectedDevicesList();
        updateDeviceDropdown();
        updateDeviceCount();
        updateHiddenInput();
    });
    
    // Update device count
    function updateDeviceCount() {
        const count = selectedDevices.size;
        const countInfo = $('.device-count-info .count');
        countInfo.text(count);
        
        // Update text
        const textSpan = $('.device-count-info');
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
            $('form').append(input);
        }
        
        // Get device IDs
        const deviceIds = Array.from(selectedDevices.keys());
        input.val(JSON.stringify(deviceIds));
        console.log('Updated selected devices:', deviceIds);
    }
    
    // Form submission validation
    $('form').on('submit', function(e) {
        updateHiddenInput();
        
        // Validate test suite selection
        if (!$('#id_test_suite').val()) {
            alert('Please select a test group');
            e.preventDefault();
            return false;
        }
        
        // Validate device selection
        if (selectedDevices.size === 0) {
            alert('Please select at least one device');
            e.preventDefault();
            return false;
        }
        
        console.log('Form submitted with devices:', Array.from(selectedDevices.keys()));
    });
    
    // Initialize on page load
    loadAvailableDevices();
    
    // If editing existing execution, trigger test suite change to load test cases
    if ($('#id_test_suite').val()) {
        $('#id_test_suite').trigger('change');
    }
    
    console.log('TestSuiteExecution form initialized');
    
})(django.jQuery);
