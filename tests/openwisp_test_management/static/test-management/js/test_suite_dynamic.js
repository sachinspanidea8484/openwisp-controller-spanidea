(function() {
    // Wait for Django jQuery
    if (typeof django === 'undefined' || typeof django.jQuery === 'undefined') {
        setTimeout(arguments.callee, 50);
        return;
    }
    
    const $ = django.jQuery;
    
    window.updateTestCases = function(categoryId) {
        const container = $('#test-cases-container');
        
        if (!categoryId) {
            container.html('Please select a category to see available test cases');
            return;
        }
        
        container.html('Loading test cases...');
        
        // Make AJAX request
        $.ajax({
            url: '/admin/test_management/testcase/',
            data: {
                'category__id__exact': categoryId,
                'is_active__exact': '1',
            },
            success: function(response) {
                // Parse response
                const tempDiv = $('<div>').html(response);
                const rows = tempDiv.find('#result_list tbody tr');
                
                if (rows.length === 0) {
                    container.html('No active test cases found for this category');
                    return;
                }
                
                let html = '<input type="hidden" name="selected_test_cases" id="selected_test_cases" value="">';
                html += '<table style="width:100%; border-collapse:collapse; margin-top:10px;">';
                html += '<thead><tr style="background:#417690; color:white;">';
                html += '<th style="padding:8px; text-align:left;">Select</th>';
                html += '<th style="padding:8px; text-align:left;">Test Case Name</th>';
                html += '<th style="padding:8px; text-align:left;">Test Case ID</th>';
                html += '<th style="padding:8px; text-align:left;">Test Type</th>';
                html += '</tr></thead><tbody>';
                
                rows.each(function() {
                    const $row = $(this);
                    const nameLink = $row.find('th.field-name a');
                    
                    if (nameLink.length) {
                        const href = nameLink.attr('href');
                        const idMatch = href.match(/\/(\d+)\/change\//);
                        
                        if (idMatch) {
                            const id = idMatch[1];
                            const name = nameLink.text();
                            const testCaseId = $row.find('td.field-test_case_id').text();
                            const testType = $row.find('td.field-test_type_display').text();
                            
                            html += '<tr style="border-bottom:1px solid #e0e0e0;">';
                            html += '<td style="padding:8px;"><input type="checkbox" class="test-case-checkbox" value="' + id + '"></td>';
                            html += '<td style="padding:8px;">' + name + '</td>';
                            html += '<td style="padding:8px;">' + testCaseId + '</td>';
                            html += '<td style="padding:8px;">' + testType + '</td>';
                            html += '</tr>';
                        }
                    }
                });
                
                html += '</tbody></table>';
                container.html(html);
                
                // Bind checkbox events
                $('.test-case-checkbox').on('change', function() {
                    const selected = [];
                    $('.test-case-checkbox:checked').each(function() {
                        selected.push($(this).val());
                    });
                    $('#selected_test_cases').val(selected.join(','));
                });
            },
            error: function() {
                container.html('Error loading test cases. Please try again.');
            }
        });
    };
    
    $(document).ready(function() {
        // Check if we have existing data (edit mode)
        if (window.testCasesData && window.categoryId) {
            const container = $('#test-cases-container');
            
            let html = '<input type="hidden" name="selected_test_cases" id="selected_test_cases" value="">';
            html += '<table style="width:100%; border-collapse:collapse; margin-top:10px;">';
            html += '<thead><tr style="background:#417690; color:white;">';
            html += '<th style="padding:8px; text-align:left;">Select</th>';
            html += '<th style="padding:8px; text-align:left;">Test Case Name</th>';
            html += '<th style="padding:8px; text-align:left;">Test Case ID</th>';
            html += '<th style="padding:8px; text-align:left;">Test Type</th>';
            html += '</tr></thead><tbody>';
            
            const selected = [];
            
            window.testCasesData.forEach(function(tc) {
                const checked = tc.selected ? 'checked' : '';
                if (tc.selected) selected.push(tc.id);
                
                html += '<tr style="border-bottom:1px solid #e0e0e0;">';
                html += '<td style="padding:8px;"><input type="checkbox" class="test-case-checkbox" value="' + tc.id + '" ' + checked + '></td>';
                html += '<td style="padding:8px;">' + tc.name + '</td>';
                html += '<td style="padding:8px;">' + tc.test_case_id + '</td>';
                html += '<td style="padding:8px;">' + tc.test_type + '</td>';
                html += '</tr>';
            });
            
            html += '</tbody></table>';
            container.html(html);
            $('#selected_test_cases').val(selected.join(','));
            
            // Bind checkbox events
            $('.test-case-checkbox').on('change', function() {
                const selected = [];
                $('.test-case-checkbox:checked').each(function() {
                    selected.push($(this).val());
                });
                $('#selected_test_cases').val(selected.join(','));
            });
        }
    });
})();