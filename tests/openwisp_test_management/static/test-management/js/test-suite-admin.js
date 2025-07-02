django.jQuery(function ($) {
    'use strict';

    // Handle category change
    $('#id_category').on('change', function () {
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
            success: function (response) {
                $testCasesList.empty();

                if (response.results && response.results.length > 0) {
                    $.each(response.results, function (index, testCase) {
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
            error: function () {
                $testCasesList.html('<li>Error loading test cases</li>');
            }
        });
    });

    // Trigger change on page load if category is selected
    if ($('#id_category').val()) {
        $('#id_category').trigger('change');
    }

    // Handle inline ordering
    $('.inline-group').on('change', '.field-order input', function () {
        // Auto-sort by order when changed
        var $tbody = $(this).closest('tbody');
        var $rows = $tbody.find('tr.form-row').get();

        $rows.sort(function (a, b) {
            var orderA = parseInt($(a).find('.field-order input').val()) || 999;
            var orderB = parseInt($(b).find('.field-order input').val()) || 999;
            return orderA - orderB;
        });

        $.each($rows, function (index, row) {
            $tbody.append(row);
        });
    });












    // Create modal HTML
    function createModal() {
        const modalHTML = `
            <div id="jsonModal" class="json-modal">
                <div class="json-modal-content">
                    <div class="json-modal-header">
                        <h2 class="json-modal-title">Execution Details</h2>
                        <button id="copyJsonBtn" class="json-copy-btn">Copy JSON</button>
                        <button class="json-modal-close" id="closeModal">&times;</button>
                    </div>
                    <div class="json-modal-body">
                        <div id="jsonContent" class="json-container">
                            <div class="json-loading">Loading...</div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add modal to body if it doesn't exist
        if (!document.getElementById('jsonModal')) {
            document.body.insertAdjacentHTML('beforeend', modalHTML);

            // Add event listeners
            document.getElementById('closeModal').addEventListener('click', closeModal);
            document.getElementById('copyJsonBtn').addEventListener('click', copyJsonToClipboard);

            // Close modal when clicking outside
            document.getElementById('jsonModal').addEventListener('click', function (e) {
                if (e.target === this) {
                    closeModal();
                }
            });

            // Close modal with Escape key
            document.addEventListener('keydown', function (e) {
                if (e.key === 'Escape') {
                    closeModal();
                }
            });
        }
    }

    // Show execution details
    window.showExecutionDetails = function (executionId) {
        createModal();

        const modal = document.getElementById('jsonModal');
        const content = document.getElementById('jsonContent');

        // Show modal
        modal.style.display = 'block';

        // Reset content
        content.innerHTML = '<div class="json-loading">Loading execution details...</div>';

        // Get current admin URL base
        const currentPath = window.location.pathname;
        const adminBase = currentPath.substring(0, currentPath.indexOf('/test_management/'));
        const jsonUrl = `${adminBase}/test_management/testsuitexecution/${executionId}/json-details/`;

        // Fetch data
        fetch(jsonUrl, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                // Store data for copying
                window.currentJsonData = data;

                // Display formatted JSON
                content.innerHTML = JSON.stringify(data, null, 2);
            })
            .catch(error => {
                console.error('Error fetching execution details:', error);
                content.innerHTML = `
                <div class="json-error">
                    <strong>Error loading execution details:</strong><br>
                    ${error.message}
                </div>
            `;
            });
    };

    // Close modal
    function closeModal() {
        const modal = document.getElementById('jsonModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    // Copy JSON to clipboard
    function copyJsonToClipboard() {
        if (window.currentJsonData) {
            const jsonString = JSON.stringify(window.currentJsonData, null, 2);

            // Create temporary textarea
            const textarea = document.createElement('textarea');
            textarea.value = jsonString;
            document.body.appendChild(textarea);
            textarea.select();

            try {
                document.execCommand('copy');

                // Visual feedback
                const copyBtn = document.getElementById('copyJsonBtn');
                const originalText = copyBtn.textContent;
                copyBtn.textContent = 'Copied!';
                copyBtn.style.backgroundColor = '#28a745';
                setTimeout(() => {
                    copyBtn.textContent = originalText;
                    copyBtn.style.backgroundColor = '#28a745';
                }, 2000);

            } catch (err) {
                console.error('Failed to copy JSON:', err);
                alert('Failed to copy JSON to clipboard');
            } finally {
                document.body.removeChild(textarea);
            }
        } else {
            alert('No JSON data to copy');
        }
    }

    // Initialize when DOM is loaded
    document.addEventListener('DOMContentLoaded', function () {
        console.log('Test Management Admin JS loaded');
    });






});