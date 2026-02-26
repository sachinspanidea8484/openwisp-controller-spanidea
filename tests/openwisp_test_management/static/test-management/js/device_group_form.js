(function($) {
    'use strict';
    
    let selectedDeviceIds = new Set();
    let organizationDevices = [];
    $(document).ready(function () {
      if (window.recoveredDevicesForGroups && window.recoveredDevicesForGroups.length > 0) {
        window.recoveredDevicesForGroups.forEach((device) => {
            selectedDeviceIds.add(device.id);
        });
      }
    });
    function initializeDeviceSelection() {
        // Load existing selected devices
        const existingData = document.getElementById('existing-devices-data');
        if (existingData) {
            try {
                const devices = JSON.parse(existingData.textContent || '[]');
                devices.forEach(device => {
                    selectedDeviceIds.add(device.id);
                });
            } catch (e) {
                console.error('Error parsing existing devices:', e);
            }
        }
        
        // Set up event listeners
        setupEventListeners();
        
        // Watch for organization changes
        const orgField = document.getElementById('id_organization');
        if (orgField) {
            $(document).on(
              "change",
              "#id_organization",
              handleOrganizationChange
            );
            // Load devices if organization is already selected
            if (orgField.value) {
                loadOrganizationDevices(orgField.value);
            }
        }
        
        // Initialize search and filter
        setupSearchAndFilter();
    }
    
    function setupEventListeners() {
        // Add/Remove buttons
        $('#add-devices').on('click', addSelectedDevices);
        $('#add-all-devices').on('click', addAllDevices);
        $('#remove-devices').on('click', removeSelectedDevices);
        $('#remove-all-devices').on('click', removeAllDevices);
        
        // Double-click to add/remove
        $('#available-devices').on('dblclick', 'option', function() {
            $(this).prop('selected', true);
            addSelectedDevices();
        });
        
        $('#selected-devices').on('dblclick', 'option', function() {
            $(this).prop('selected', true);
            removeSelectedDevices();
        });
    }
    
    function handleOrganizationChange(event) {
        const orgId = event.target.value;
        if (orgId) {
            
            selectedDeviceIds.clear();
            updateHiddenField();
            loadOrganizationDevices(orgId);


        } else {
            // Clear devices if no organization selected
            organizationDevices = [];
            updateDeviceLists();
        }
    }
    

function loadOrganizationDevices(orgId) {
    $('#available-devices').html('<option disabled>Loading devices...</option>');
    
    const url = '/api/v1/test-management/get-organization-devices/';
    
    // Fetch devices from server
    $.ajax({
        url: url,
        type: 'GET',
        data: { organization_id: orgId },
        dataType: 'json',
        success: function(response) {
            organizationDevices = response.devices || [];
            updateDeviceLists();
            
            // Show device count in info
            if (response.count !== undefined) {
                $('#device-limit-info').show();
                $('#device-limit-text').text(`${response.count} devices available in this organization`);
            }
        },
        error: function(xhr, status, error) {
            console.error('Error loading devices:', error);
            let errorMsg = 'Error loading devices';
            
            try {
                const response = JSON.parse(xhr.responseText);
                if (response.error) {
                    errorMsg = response.error;
                }
            } catch (e) {
                // Ignore JSON parse errors
            }
            
            $('#available-devices').html(`<option disabled>${errorMsg}</option>`);
            organizationDevices = [];
        }
    });
}
    
    function updateDeviceLists() {
        const searchTerm = $('#device-search').val().toLowerCase();
        const statusFilter = $('#device-status-filter').val();
        
        // Filter available devices
        const availableDevices = organizationDevices.filter(device => {
            // Not already selected
            if (selectedDeviceIds.has(device.id)) {
                return false;
            }
            
            // Search filter
            if (searchTerm && !device.name.toLowerCase().includes(searchTerm) && 
                !device.mac_address.toLowerCase().includes(searchTerm)) {
                return false;
            }
            
            // Status filter
            if (statusFilter === 'active' && !device.is_active) {
                return false;
            }
            if (statusFilter === 'inactive' && device.is_active) {
                return false;
            }
            
            return true;
        });
        
        // Update available devices list
        const $availableSelect = $('#available-devices');
        $availableSelect.empty();
        
                availableDevices.forEach(device => {
            const statusIcon = device.is_active ? '🟢' : '🔴';
            const optionText = `${statusIcon} ${device.name} (${device.mac_address})`;
            $availableSelect.append(
                $('<option>').val(device.id).text(optionText).data('device', device)
            );
        });
        
        // Update selected devices list
        const $selectedSelect = $('#selected-devices');
        $selectedSelect.empty();
        
        const selectedDevices = organizationDevices.filter(device => 
            selectedDeviceIds.has(device.id)
        );
        
        selectedDevices.forEach(device => {
            const statusIcon = device.is_active ? '🟢' : '🔴';
            const optionText = `${statusIcon} ${device.name} (${device.mac_address})`;
            $selectedSelect.append(
                $('<option>').val(device.id).text(optionText).data('device', device)
            );
        });
        
        // Update counts
        $('#available-count').text(`(${availableDevices.length})`);
        $('#selected-count').text(`(${selectedDevices.length})`);
        
        // Update hidden field
        updateHiddenField();
    }
    
    function addSelectedDevices() {
        $('#available-devices option:selected').each(function() {
            selectedDeviceIds.add($(this).val());
        });
        updateDeviceLists();
    }
    
    function addAllDevices() {
        $('#available-devices option').each(function() {
            selectedDeviceIds.add($(this).val());
        });
        updateDeviceLists();
    }
    
    function removeSelectedDevices() {
        $('#selected-devices option:selected').each(function() {
            selectedDeviceIds.delete($(this).val());
        });
        updateDeviceLists();
    }
    
    function removeAllDevices() {
        selectedDeviceIds.clear();
        updateDeviceLists();
    }
    
    function setupSearchAndFilter() {
        // Search functionality
        $('#device-search').on('input', function() {
            updateDeviceLists();
        });
        
        // Status filter
        $('#device-status-filter').on('change', function() {
            updateDeviceLists();
        });
    }
    
    function updateHiddenField() {
        const selectedIds = Array.from(selectedDeviceIds);
        $('#selected_devices_data').val(JSON.stringify(selectedIds));
    }
    
    function checkDeviceLimit(orgId) {
        
        const selectedCount = selectedDeviceIds.size;
        if (selectedCount > 0) {
            $('#device-limit-info').show();
            $('#device-limit-text').text(`${selectedCount} devices selected`);
        } else {
            $('#device-limit-info').hide();
        }
    }
    
    // Initialize when DOM is ready
    $(document).ready(function() {
        initializeDeviceSelection();
    });
    
})(django.jQuery);