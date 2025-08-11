// admin_events_modal_trigger.js
// Ensures the modal is shown via Bootstrap JS API if editing or form errors exist

document.addEventListener('DOMContentLoaded', function() {
    if (window.eventModalShouldShow) {
        var eventModal = document.getElementById('eventModal');
        if (eventModal) {
            var modal = new bootstrap.Modal(eventModal);
            modal.show();
        }
    }
});
