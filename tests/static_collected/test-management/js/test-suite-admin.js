// JSON View Modal functionality
(function () {
    'use strict';

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

})();