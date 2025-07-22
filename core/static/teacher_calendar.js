// teacher_calendar.js
// Calendar for teacher dashboard (read-only)

document.addEventListener('DOMContentLoaded', function() {
    var calendarEl = document.getElementById('teacher-calendar');
    if (!calendarEl) {
        console.error('Teacher calendar container not found.');
        return;
    }
    if (typeof FullCalendar === 'undefined') {
        console.error('FullCalendar JS is not loaded!');
        return;
    }
    try {
        var calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            height: 500,
            events: {
                url: '/dashboard/events/json/',
                failure: function() {
                    console.error('Failed to load events from /dashboard/events/json/.');
                }
            },
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },
            eventClick: function(info) {
                alert(info.event.title + '\n' + info.event.start.toLocaleString());
            },
            eventDidMount: function(info) {
                var now = new Date();
                var startDate = new Date(info.event.start);
                if (startDate < now) {
                    info.el.style.opacity = '0.7';
                }
            }
        });
        calendar.render();
    } catch (e) {
        console.error('Error initializing FullCalendar:', e);
    }
});

