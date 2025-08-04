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
                window.location.reload(); // Reload to show new event
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
