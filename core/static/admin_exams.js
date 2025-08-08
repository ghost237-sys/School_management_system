document.addEventListener('DOMContentLoaded', function() {
    try {
        const calendarEl = document.getElementById('exam-calendar');
        if (calendarEl) {
            // Show loading indicator
            calendarEl.innerHTML = '<div class="text-center p-4"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Loading exam calendar...</p></div>';
            
            const calendar = new FullCalendar.Calendar(calendarEl, {
                initialView: 'dayGridMonth',
                height: 600,
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek,listWeek'
                },
                events: {
                    url: '/api/exams/',
                    failure: function(error) {
                        console.error('Error loading exam events:', error);
                        calendarEl.innerHTML = '<div class="alert alert-danger"><i class="bi bi-exclamation-triangle me-2"></i>Error loading exam calendar. Please refresh the page.</div>';
                    }
                },
                loading: function(isLoading) {
                    if (!isLoading) {
                        // Calendar has finished loading
                        console.log('Exam calendar loaded successfully');
                    }
                },
                eventDidMount: function(info) {
                    // Add tooltip with exam details
                    info.el.setAttribute('title', info.event.extendedProps.description || info.event.title);
                    info.el.classList.add('fc-event-exam');
                },
                eventClick: function(info) {
                    // Populate the modal with event details
                    document.getElementById('modalExamName').textContent = info.event.title;
                    
                    // Format dates properly
                    const startDate = info.event.start ? info.event.start.toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                    }) : 'N/A';
                    
                    const endDate = info.event.end ? info.event.end.toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                    }) : 'N/A';
                    
                    document.getElementById('modalExamStart').textContent = startDate;
                    document.getElementById('modalExamEnd').textContent = endDate;
                    document.getElementById('modalExamTerm').textContent = info.event.extendedProps.term || 'No Term';

                    // Show the modal
                    var examModal = new bootstrap.Modal(document.getElementById('examDetailModal'));
                    examModal.show();
                },
                // Add some nice styling options
                dayMaxEvents: 3, // Show max 3 events per day, then show "more" link
                moreLinkClick: 'popover', // Show popover when clicking "more"
                eventDisplay: 'block'
            });
            
            calendar.render();
        } else {
            console.error('Exam calendar element not found.');
        }
    } catch (e) {
        console.error('Error initializing exam calendar:', e);
        const calendarEl = document.getElementById('exam-calendar');
        if (calendarEl) {
            calendarEl.innerHTML = '<div class="alert alert-danger"><i class="bi bi-exclamation-triangle me-2"></i>Error initializing exam calendar: ' + e.message + '</div>';
        }
    }
});
