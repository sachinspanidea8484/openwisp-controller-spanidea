(function($) {
    $(document).ready(function() {
        // Handle category change to update test cases
        $('#id_category').change(function() {
            var categoryId = $(this).val();
            
            if (categoryId) {
                // Clear current selections
                $('#id_selected_test_cases input[type="checkbox"]').prop('checked', false);
                
                // You can add AJAX here to dynamically load test cases
                // For now, the form will handle it on page reload
            } else {
                // Clear test cases if no category selected
                $('#id_selected_test_cases input[type="checkbox"]').prop('checked', false);
            }
        });
    });
})(django.jQuery);