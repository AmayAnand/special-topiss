$(document).ready(function() {
    // Function to validate end time
    function validateEndTime() {
        var startTime = $('#start_time').val();
        var endTime = $('#end_time').val();

        if (endTime <= startTime) {
            $('#end_time').addClass('is-invalid');
            $('#end_time_error').text('End time must be after start time.');
            return false;
        } else {
            $('#end_time').removeClass('is-invalid');
            $('#end_time_error').text('');
            return true;
        }
    }

    // Event listener for start time change
    $('#start_time').change(function() {
        validateEndTime();
    });

    // Event listener for end time change
    $('#end_time').change(function() {
        validateEndTime();
    });

    // Function to submit form
    $('#bookForm').submit(function(event) {
        if (!validateEndTime()) {
            event.preventDefault();
        }
    });
});

