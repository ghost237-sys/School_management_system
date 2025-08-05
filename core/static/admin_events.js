// admin_events.js - Handles AJAX event creation for admin events page

document.addEventListener('DOMContentLoaded', function() {
    var eventModal = document.getElementById('eventModal');
    if (!eventModal) return;
    var form = eventModal.querySelector('form');
    if (!form) return;
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var formData = new FormData(form);
        fetch('/dashboard/events/create/', {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Hide the modal using Bootstrap 5
                var modalInstance = bootstrap.Modal.getOrCreateInstance(eventModal);
                modalInstance.hide();
                // Optionally, refresh the events table or reload part of the page here
                // window.location.reload();
            } else {
                let errorMsg = 'Error: ' + (data.error || 'Could not add event.');
                alert(errorMsg);
            }
        })
        .catch(err => {
            alert('Network error: Could not add event.');
        });
    });
});
