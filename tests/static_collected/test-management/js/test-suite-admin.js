django.jQuery(function($) {
    'use strict';
    
    // Handle category change
    $('#id_category').on('change', function() {
        var categoryId = $(this).val();
        var $testCasesField = $('.field-test_cases');
        
        if (!categoryId) {
            // Hide test cases if no category selected
            $testCasesField.hide();
            return;
        }
        
        // Show loading message
        $testCasesField.show();
        var $testCasesList = $('#id_test_cases');
        $testCasesList.html('<option>Loading test cases...</option>');
        
        // Fetch test cases for the selected category
        $.ajax({
            url: '/api/v1/test-management/test-case/',
            data: {
                category: categoryId,
                is_active: true,
                page_size: 100
            },
            success: function(response) {
                $testCasesList.empty();
                
                if (response.results && response.results.length > 0) {
                    $.each(response.results, function(index, testCase) {
                        var $option = $('<input type="checkbox" />')
                            .attr('name', 'test_cases')
                            .attr('value', testCase.id)
                            .attr('id', 'id_test_cases_' + index);
                        
                        var $label = $('<label />')
                            .attr('for', 'id_test_cases_' + index)
                            .text(' ' + testCase.name);
                        
                        var $li = $('<li />').append($option).append($label);
                        $testCasesList.append($li);
                    });
                } else {
                    $testCasesList.html('<li>No test cases available for this category</li>');
                }
            },
            error: function() {
                $testCasesList.html('<li>Error loading test cases</li>');
            }
        });
    });
    
    // Trigger change on page load if category is selected
    if ($('#id_category').val()) {
        $('#id_category').trigger('change');
    }
    
        // Handle inline ordering
    $('.inline-group').on('change', '.field-order input', function() {
        // Auto-sort by order when changed
        var $tbody = $(this).closest('tbody');
        var $rows = $tbody.find('tr.form-row').get();
        
        $rows.sort(function(a, b) {
            var orderA = parseInt($(a).find('.field-order input').val()) || 999;
            var orderB = parseInt($(b).find('.field-order input').val()) || 999;
            return orderA - orderB;
        });
        
        $.each($rows, function(index, row) {
            $tbody.append(row);
        });
    });
});