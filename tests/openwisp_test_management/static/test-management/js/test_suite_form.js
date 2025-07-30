/**
 * Test Management - Test Suite Form JavaScript
 * Handles test case selection, validation, and form submission
 */

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
    
    // Store selected test cases with their order
    let selectedTestCases = new Map(); // Map of test_case_id -> order
    let allTestCases = []; // Store all available test cases
    
    // Initialize selected test cases from Django context for edit mode
    function initializeSelectedTestCases() {
        try {
            const scriptElement = document.getElementById('existing-test-cases-data');
            if (scriptElement) {
                const existingTestCasesJson = scriptElement.textContent || scriptElement.innerText;
                console.log('Raw JSON string:', existingTestCasesJson);
                
                if (existingTestCasesJson && existingTestCasesJson.trim() !== '' && existingTestCasesJson.trim() !== '[]') {
                    const existingTestCases = JSON.parse(existingTestCasesJson);
                    console.log('Parsed existing test cases:', existingTestCases);
                    
                    if (Array.isArray(existingTestCases) && existingTestCases.length > 0) {
                        existingTestCases.forEach(function(item) {
                            if (item && item.id && item.order) {
                                selectedTestCases.set(String(item.id), parseInt(item.order));
                                console.log(`Added test case ${item.id} with order ${item.order}`);
                            }
                        });
                        
                        console.log('Final selectedTestCases:', Array.from(selectedTestCases.entries()));
                        updateSelectionCount();
                        updateHiddenInput();
                    }
                } else {
                    console.log('No existing test cases to initialize');
                }
            } else {
                console.log('No existing test cases data script element found');
            }
        } catch (e) {
            console.error('Error initializing existing test cases:', e);
        }
    }
    
    // Create test cases container with table
    function createTestCasesContainer() {
        const container = $('<div id="test-cases-container" class="hidden"></div>');
        const header = $('<div class="test-cases-header">Select Test Cases</div>');
        
        // Add validation error message container
        const errorMessage = $(`
            <div class="test-case-validation-error" id="test-case-error">
                <span class="error-icon">⚠</span>
                <span class="error-text">At least one test case must be selected for this test group.</span>
            </div>
        `);
        
        // Add success message container
        const successMessage = $(`
            <div class="test-case-validation-success" id="test-case-success">
                <span class="success-icon">✓</span>
                <span class="success-text"></span>
            </div>
        `);
        
        const selectAllContainer = $('<div class="select-all-container"><label><input type="checkbox" id="select-all-test-cases"> Select All</label></div>');
        
        const tableContainer = $('<div class="table-container"></div>');
        const table = $(`
            <table class="test-cases-table">
                <thead>
                    <tr>
                        <th class="checkbox-col"><input type="checkbox" id="select-all-test-cases"> </th>
                        <th class="name-col">NAME</th>
                        <th class="id-col">TEST CASE ID</th>
                        <th class="type-col">TEST TYPE</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        `);
        
        const selectionCount = $('<div class="selection-count"><span class="count">0</span> Test Case Selected</div>');
        
        tableContainer.append(table);
        container.append(header);
        container.append(errorMessage);
        container.append(successMessage);
        container.append(tableContainer);
        
        return container;
    }
    
    // Insert container after category field
    const categoryField = $('.field-category');
    if (categoryField.length) {
        const container = createTestCasesContainer();
        categoryField.after(container);
    }
    
    // Handle category change
    $('#id_category').on('change', function() {
        const categoryId = $(this).val();
        const container = $('#test-cases-container');
        const tbody = container.find('.test-cases-table tbody');
        const errorDiv = $('#test-case-error');
        const successDiv = $('#test-case-success');
        
        if (!categoryId) {
            container.addClass('hidden');
            errorDiv.hide();
            successDiv.hide();
            $('.field-category').removeClass('has-error');
            return;
        }
        
        // Show loading
        tbody.html('<tr><td colspan="4" class="no-test-cases"><div class="loading-spinner"></div> Loading test cases...</td></tr>');
        container.removeClass('hidden');
        
        // Clear validation messages
        errorDiv.hide();
        successDiv.hide();
        $('.field-category').removeClass('has-error');
        
        // Don't clear selections when category changes in edit mode if it's the initial load
        const isInitialLoad = allTestCases.length === 0;
        if (!isInitialLoad) {
            // Only clear selections if it's not the initial load
            selectedTestCases.clear();
            updateSelectionCount();
        }
        
        // Construct the API URL
        const apiUrl = `/api/v1/test-management/category/${categoryId}/test-cases/`;
        console.log('Calling API:', apiUrl);
        
        // Fetch test cases
        $.ajax({
            url: apiUrl,
            method: 'GET',
            headers: {
                'X-CSRFToken': csrftoken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function(data) {
                console.log('API Response:', data);
                
                if (data.test_cases && data.test_cases.length > 0) {
                    allTestCases = data.test_cases;
                    displayTestCasesTable(data.test_cases);
                } else {
                    tbody.html('<tr><td colspan="4" class="no-test-cases">No active test cases in this category</td></tr>');
                }
                updateSelectionCount();
            },
            error: function(xhr, status, error) {
                console.error('API Error:', status, error);
                console.error('Response:', xhr.responseText);
                
                let errorMessage = 'Error loading test cases';
                
                if (xhr.status === 401 || xhr.status === 403) {
                    errorMessage = 'Authentication required. Please ensure you are logged in.';
                } else if (xhr.status === 404) {
                    errorMessage = 'API endpoint not found. Please check the URL configuration.';
                } else if (xhr.status === 500) {
                    errorMessage = 'Server error. Please try again later.';
                }
                
                tbody.html(`<tr><td colspan="4" class="no-test-cases">${errorMessage}</td></tr>`);
            }
        });
    });
    
    // Display test cases in table format
    function displayTestCasesTable(testCases) {
        const tbody = $('.test-cases-table tbody');
        tbody.empty();
        
        console.log('Displaying test cases. Current selections:', Array.from(selectedTestCases.entries()));
        
        testCases.forEach(function(testCase) {
            const testCaseId = String(testCase.id);
            const isChecked = selectedTestCases.has(testCaseId);
            const typeClass = testCase.test_type === 1 ? 'test-type-robot' : 'test-type-agent';
            
            console.log(`Test case ${testCase.name} (ID: ${testCaseId}): isChecked = ${isChecked}`);
            
            const row = $(`
                <tr class="${isChecked ? 'selected' : ''}" data-id="${testCase.id}">
                    <td class="checkbox-col">
                        <input type="checkbox" 
                               class="test-case-checkbox"
                               id="test_case_${testCase.id}" 
                               value="${testCase.id}"
                               ${isChecked ? 'checked' : ''}>
                    </td>
                    <td class="name-col">
                        <label for="test_case_${testCase.id}" class="test-case-name">
                            ${testCase.name}
                        </label>
                    </td>
                    <td class="id-col">
                        <span class="test-case-id">${testCase.test_case_id}</span>
                    </td>
                    <td class="type-col">
                        <span class="test-type-badge ">${testCase.test_type_display}</span>
                    </td>
                </tr>
            `);
            
            tbody.append(row);
        });
        
        updateSelectAllCheckbox();
        updateSelectionCount();
        updateHiddenInput();
    }
    
    // Handle test case selection
    $(document).on('change', '.test-case-checkbox', function() {
        const testCaseId = $(this).val();
        const row = $(this).closest('tr');
        
        if ($(this).is(':checked')) {
            // Add to selected with next order number
            const maxOrder = Math.max(0, ...Array.from(selectedTestCases.values()));
            selectedTestCases.set(testCaseId, maxOrder + 1);
            row.addClass('selected');
        } else {
            // Remove from selected and reorder remaining
            selectedTestCases.delete(testCaseId);
            row.removeClass('selected');
            reorderTestCases();
        }
        
        updateHiddenInput();
        updateSelectAllCheckbox();
        updateSelectionCount();
    });
    
    // Handle row click (except checkbox)
    $(document).on('click', '.test-cases-table tbody tr', function(e) {
        if (!$(e.target).is('input[type="checkbox"]') && !$(e.target).is('label')) {
            const checkbox = $(this).find('.test-case-checkbox');
            checkbox.prop('checked', !checkbox.prop('checked')).trigger('change');
        }
    });
    
    // Reorder test cases after deletion
    function reorderTestCases() {
        const sortedEntries = Array.from(selectedTestCases.entries())
            .sort((a, b) => a[1] - b[1]);
        
        selectedTestCases.clear();
        sortedEntries.forEach(([id, _], index) => {
            selectedTestCases.set(id, index + 1);
        });
    }
    
    // Handle select all
    $(document).on('change', '#select-all-test-cases', function() {
        const isChecked = $(this).is(':checked');
        
        if (isChecked) {
            // Select all and assign orders
            let order = 1;
            $('.test-case-checkbox').each(function() {
                const testCaseId = $(this).val();
                
                if (!$(this).is(':checked')) {
                    $(this).prop('checked', true);
                    selectedTestCases.set(testCaseId, order++);
                    $(this).closest('tr').addClass('selected');
                }
            });
        } else {
            // Deselect all
            selectedTestCases.clear();
            $('.test-case-checkbox').each(function() {
                $(this).prop('checked', false);
                $(this).closest('tr').removeClass('selected');
            });
        }
        
        updateHiddenInput();
        updateSelectionCount();
    });
    
    // Update select all checkbox state
    function updateSelectAllCheckbox() {
        const allCheckboxes = $('.test-case-checkbox');
        const checkedCheckboxes = $('.test-case-checkbox:checked');
        
        if (allCheckboxes.length > 0) {
            const selectAllCheckbox = $('#select-all-test-cases');
            if (allCheckboxes.length === checkedCheckboxes.length) {
                selectAllCheckbox.prop('checked', true);
                selectAllCheckbox.prop('indeterminate', false);
            } else if (checkedCheckboxes.length > 0) {
                selectAllCheckbox.prop('checked', false);
                selectAllCheckbox.prop('indeterminate', true);
            } else {
                selectAllCheckbox.prop('checked', false);
                selectAllCheckbox.prop('indeterminate', false);
            }
        }
    }
    
    // Update selection count with validation
    function updateSelectionCount() {
        const selectedCount = selectedTestCases.size;
        const selectionDiv = $('.selection-count');
        const countSpan = selectionDiv.find('.count');
        const categoryField = $('.field-category');
        const errorDiv = $('#test-case-error');
        const successDiv = $('#test-case-success');
        
        countSpan.text(selectedCount);
        
        // Update text
        if (selectedCount === 0) {
            selectionDiv.find('span:not(.count)').remove();
            selectionDiv.append(' Test Case Selected');
        } else if (selectedCount === 1) {
            selectionDiv.find('span:not(.count)').remove();
            selectionDiv.append(' Test Case Selected');
        } else {
            selectionDiv.find('span:not(.count)').remove();
            selectionDiv.append(' Test Cases Selected');
        }
        
        // Show/hide validation messages
        if ($('#id_category').val() && selectedCount === 0) {
            // Show error
            errorDiv.show();
            successDiv.hide();
            selectionDiv.removeClass('success').addClass('error');
            categoryField.addClass('has-error');
        } else if ($('#id_category').val() && selectedCount > 0) {
            // Show success
            errorDiv.hide();
            successDiv.find('.success-text').text(`${selectedCount} test case${selectedCount > 1 ? 's' : ''} selected`);
            successDiv.show();
            selectionDiv.removeClass('error').addClass('success');
            categoryField.removeClass('has-error');
        } else {
            // Hide both
            errorDiv.hide();
            successDiv.hide();
            selectionDiv.removeClass('error success');
            categoryField.removeClass('has-error');
        }
    }
    
    // Update hidden input with selected test cases in order
    function updateHiddenInput() {
        let input = $('input[name="selected_test_cases_data"]');
        
        if (!input.length) {
            input = $('<input type="hidden" name="selected_test_cases_data">');
            $('form').append(input);
        }
        
        // Sort by order and get IDs
        const sortedIds = Array.from(selectedTestCases.entries())
            .sort((a, b) => a[1] - b[1])
            .map(([id, _]) => id);
        
        input.val(JSON.stringify(sortedIds));
        console.log('Updated hidden input:', JSON.stringify(sortedIds));
    }
    
    // Handle category change warning when test cases are selected
    let originalCategoryValue = $('#id_category').val();
    $('#id_category').on('change', function() {
        const newValue = $(this).val();
        
        if (selectedTestCases.size > 0 && originalCategoryValue !== newValue) {
            const confirmChange = confirm(
                'Changing the category will clear your current test case selection. ' +
                'Do you want to continue?'
            );
            
            if (!confirmChange) {
                $(this).val(originalCategoryValue);
                return false;
            }
        }
        
        originalCategoryValue = newValue;
    });
    
    // Enhanced form submission with UI validation
    $('form').on('submit', function(e) {
        updateHiddenInput();
        
        // Remove any previous error highlighting
        $('.field-category').removeClass('has-error');
        $('#test-case-error').hide();
        
        // Validate that at least one test case is selected
        if (selectedTestCases.size === 0 && $('#id_category').val()) {
            e.preventDefault();
            
            // Show error in UI
            $('#test-case-error').show();
            $('.field-category').addClass('has-error');
            $('.selection-count').removeClass('success').addClass('error');
            
            // Scroll to the error
            $('html, body').animate({
                scrollTop: $('#test-cases-container').offset().top - 100
            }, 500);
            
            // Focus on category field
            $('#id_category').focus();
            
            return false;
        }
        
        console.log('Form submitted with test cases:', Array.from(selectedTestCases.entries()));
    });
    
    // Initialize everything when document is ready
    $(document).ready(function() {
        initializeSelectedTestCases();
        
        if ($('#id_category').val()) {
            $('#id_category').trigger('change');
        }
        
        console.log('Test Suite form initialized with table view');
    });
    
})(django.jQuery); 