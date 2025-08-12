// teacher_calendar.js
// Calendar for teacher dashboard (read-only)

document.addEventListener('DOMContentLoaded', function() {
    var calendarEl = document.getElementById('teacher-calendar');
    if (!calendarEl) {
        console.error('Teacher calendar container not found.');
        return;
    }
    // Ensure container has visible height if CSS fails to load
    if (!calendarEl.style.height) {
        calendarEl.style.minHeight = '500px';
    }
    if (typeof FullCalendar === 'undefined') {
        console.error('FullCalendar JS is not loaded!');
        return;
    }
    try {
        var calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            contentHeight: 'auto',
            height: 500,
            initialDate: new Date(),
            timeZone: 'local',
            events: function(fetchInfo, successCb, failureCb) {
                var endpoint = '/dashboard/events/json/';
                fetch(endpoint, { credentials: 'same-origin' })
                  .then(function(resp){
                      if (!resp.ok) throw new Error('HTTP '+resp.status);
                      return resp.json();
                  })
                  .then(function(data){
                      if (!Array.isArray(data)) {
                          console.warn('Events feed did not return an array. Got:', data);
                      } else {
                          console.log('Loaded events:', data.length, data.slice(0,5));
                      }
                      successCb(Array.isArray(data) ? data : []);
                  })
                  .catch(function(err){
                      console.error('Failed to load events from '+endpoint, err);
                      failureCb(err);
                  });
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

