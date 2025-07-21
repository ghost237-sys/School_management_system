// deadline_countdown.js
// Adds countdown timers to elements with class 'deadline-countdown' and data-deadline attribute

document.addEventListener('DOMContentLoaded', function() {
    function updateCountdowns() {
        var countdowns = document.querySelectorAll('.deadline-countdown');
        countdowns.forEach(function(el) {
            var deadline = el.getAttribute('data-deadline');
            if (!deadline) return;
            var deadlineDate = new Date(deadline);
            var now = new Date();
            var diff = deadlineDate - now;
            if (diff <= 0) {
                el.textContent = 'Deadline passed';
                el.classList.add('text-danger');
            } else {
                var days = Math.floor(diff / (1000 * 60 * 60 * 24));
                var hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
                var minutes = Math.floor((diff / (1000 * 60)) % 60);
                var seconds = Math.floor((diff / 1000) % 60);
                el.textContent = days + 'd ' + hours + 'h ' + minutes + 'm ' + seconds + 's';
                // Remove all possible bg classes
                el.classList.remove('bg-primary', 'bg-warning', 'bg-danger', 'text-danger');
                // Color logic: >3d = blue, <3d = orange, <24h = red
                if (diff < 24 * 60 * 60 * 1000) {
                    el.classList.add('bg-danger');
                } else if (diff < 3 * 24 * 60 * 60 * 1000) {
                    el.classList.add('bg-warning');
                } else {
                    el.classList.add('bg-primary');
                }
            }
        });
    }
    updateCountdowns();
    setInterval(updateCountdowns, 1000);
});
