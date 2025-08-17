// teacher_calendar.js
// Calendar for teacher dashboard (read-only)

function initTeacherCalendar() {
    var calendarEl = document.getElementById('teacher-calendar');
    if (!calendarEl) {
        console.error('Teacher calendar container not found.');
        return;
    }
    // Ensure container has visible height if CSS fails to load
    if (!calendarEl.style.height) {
        calendarEl.style.minHeight = '500px';
    }
    // Fallback: static month grid renderer (with events overlaid)
    var staticCurrentDate = null;
    function renderStaticMonth(el, date) {
        try {
            var d = date || new Date();
            staticCurrentDate = new Date(d.getFullYear(), d.getMonth(), 1);
            var year = d.getFullYear();
            var month = d.getMonth(); // 0-11
            var first = new Date(year, month, 1);
            var last = new Date(year, month + 1, 0);
            var startWeekday = first.getDay(); // 0=Sun
            var daysInMonth = last.getDate();

            var dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

            var html = '';
            html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">';
            html +=   '<div style="font-weight:600;">' + d.toLocaleString(undefined,{month:'long'}) + ' ' + year + '</div>';
            html +=   '<div class="small text-muted">Static calendar</div>';
            html += '</div>';
            html += '<div class="tdb-static-grid" style="display:grid;grid-template-columns:repeat(7,1fr);gap:6px;">';
            // headers
            for (var i=0;i<7;i++) {
                html += '<div style="text-align:center;font-weight:600;padding:6px 4px;border:1px solid #e9ecef;border-radius:6px;background:#f8fafc;">'+dayNames[i]+'</div>';
            }
            // blanks before first day
            for (var b=0;b<startWeekday;b++) {
                html += '<div style="padding:16px;border:1px solid #e9ecef;border-radius:6px;background:#fff;min-height:64px;color:#94a3b8;">&nbsp;</div>';
            }
            // days
            for (var day=1; day<=daysInMonth; day++) {
                var isToday = (year === (new Date()).getFullYear() && month === (new Date()).getMonth() && day === (new Date()).getDate());
                var cellDate = new Date(year, month, day);
                var iso = cellDate.toISOString().slice(0,10);
                html += '<div class="tdb-day" data-date="'+iso+'" style="padding:8px;border:1px solid #e9ecef;border-radius:6px;background:#fff;min-height:64px;position:relative;">'
                      +   '<div class="tdb-daynum" style="position:absolute;top:6px;right:8px;' + (isToday ? 'background:#0d6efd;color:#fff;border-radius:10px;padding:0 6px;font-size:12px;' : 'color:#64748b;') + '">' + day + '</div>'
                      +   '<div class="tdb-events" style="margin-top:22px;display:flex;flex-direction:column;gap:4px;"></div>'
                      + '</div>';
            }
            html += '</div>';
            el.innerHTML = html;

            // Fetch events and overlay on static grid
            var startStr = first.toISOString().slice(0,10);
            var endExclusive = new Date(year, month + 1, 1); // first day of next month
            var endStr = endExclusive.toISOString().slice(0,10);
            var url = '/dashboard/events/json/?start=' + encodeURIComponent(startStr) + '&end=' + encodeURIComponent(endStr);
            fetch(url, { credentials: 'same-origin' })
              .then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
              .then(function(data){
                  if (!Array.isArray(data)) return;
                  var filters = getFilters();
                  var counts = {event:0, exam:0, responsibility:0, other:0};
                  data.forEach(function(evt){
                      try {
                          var cat = (evt.category || 'event').toString().toLowerCase();
                          if (cat === 'exam' && !filters.exam) return;
                          if (cat === 'responsibility' && !filters.responsibility) return;
                          if ((cat !== 'exam' && cat !== 'responsibility') && !filters.event) return;
                          if (counts.hasOwnProperty(cat)) counts[cat]++; else counts.other++;
                          var color = colorForCategory(cat);
                          // Place on each day the allDay spans cover; for timed events, place on start date
                          var s = new Date(evt.start);
                          var e = evt.end ? new Date(evt.end) : new Date(evt.start);
                          // If allDay, 'end' is exclusive per our API, so iterate until day before end
                          var dayCursor = new Date(s.getFullYear(), s.getMonth(), s.getDate());
                          var lastInclusive = new Date(e.getFullYear(), e.getMonth(), e.getDate());
                          if (evt.allDay) {
                              lastInclusive.setDate(lastInclusive.getDate() - 1);
                          }
                          var maxIter = 40; // safety
                          while (dayCursor <= lastInclusive && maxIter-- > 0) {
                              var key = dayCursor.toISOString().slice(0,10);
                              var cell = el.querySelector('.tdb-day[data-date="'+key+'"] .tdb-events');
                              if (cell) {
                                  var pill = document.createElement('div');
                                  pill.textContent = evt.title;
                                  pill.style.fontSize = '12px';
                                  pill.style.padding = '2px 6px';
                                  pill.style.borderRadius = '10px';
                                  pill.style.background = color;
                                  pill.style.color = '#fff';
                                  pill.title = (evt.title || '') + (evt.details ? ('\n' + evt.details) : '');
                                  cell.appendChild(pill);
                              }
                              dayCursor.setDate(dayCursor.getDate() + 1);
                          }
                      } catch(_e) {}
                  });
                  try { console.log('Static overlay events by category:', counts); } catch(_e) {}
              })
              .catch(function(err){ console.warn('Static calendar event overlay failed', err); });
        } catch (e) {
            console.warn('Static calendar fallback failed', e);
        }
    }
    function wireStaticNav(el){
        try {
            var btnPrev = document.getElementById('fc-nav-prev');
            var btnToday = document.getElementById('fc-nav-today');
            var btnNext = document.getElementById('fc-nav-next');
            if (btnPrev) btnPrev.onclick = function(){
                var base = staticCurrentDate || new Date();
                var nd = new Date(base.getFullYear(), base.getMonth()-1, 1);
                renderStaticMonth(el, nd);
            };
            if (btnToday) btnToday.onclick = function(){
                renderStaticMonth(el, new Date());
            };
            if (btnNext) btnNext.onclick = function(){
                var base = staticCurrentDate || new Date();
                var nd = new Date(base.getFullYear(), base.getMonth()+1, 1);
                renderStaticMonth(el, nd);
            };
        } catch(_e) {}
    }
    // If FullCalendar v6 API is missing, try legacy v3 via jQuery
    if (typeof FullCalendar === 'undefined' || typeof FullCalendar.Calendar === 'undefined') {
        if (window.jQuery && jQuery.fn && typeof jQuery.fn.fullCalendar === 'function') {
            try {
                // v3 init
                var $cal = jQuery(calendarEl);
                var cachedV3 = [];
                function getFilters() {
                    var ev = document.getElementById('fc-filter-event');
                    var ex = document.getElementById('fc-filter-exam');
                    var rs = document.getElementById('fc-filter-responsibility');
                    return { event: !ev || ev.checked, exam: !ex || ex.checked, responsibility: !rs || rs.checked };
                }
                function colorFor(cat){ if(cat==='exam') return '#dc3545'; if(cat==='responsibility') return '#198754'; return '#0d6efd'; }
                function applyFiltersV3() {
                    var f = getFilters();
                    var filtered = cachedV3.filter(function(e){
                        var c = (e.category||'event').toString().toLowerCase();
                        if (c==='exam') return f.exam; if (c==='responsibility') return f.responsibility; return f.event;
                    });
                    $cal.fullCalendar('removeEvents');
                    $cal.fullCalendar('addEventSource', filtered);
                }
                $cal.fullCalendar({
                    header: { left: 'prev,next today', center: 'title', right: 'month,agendaWeek,agendaDay' },
                    height: 500,
                    timezone: 'local',
                    editable: false,
                    eventLimit: true,
                    events: function(start, end, timezone, callback){
                        var url = '/dashboard/events/json/?start=' + encodeURIComponent(start.format()) + '&end=' + encodeURIComponent(end.format());
                        fetch(url, { credentials: 'same-origin' })
                          .then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
                          .then(function(data){
                              if (!Array.isArray(data)) { callback([]); return; }
                              cachedV3 = data.map(function(evt){
                                  var cat = (evt.category||'event').toString().toLowerCase();
                                  evt.color = colorFor(cat);
                                  return evt;
                              });
                              var f = getFilters();
                              var filtered = cachedV3.filter(function(e){
                                  var c=(e.category||'event').toString().toLowerCase();
                                  if (c==='exam') return f.exam; if (c==='responsibility') return f.responsibility; return f.event;
                              });
                              callback(filtered);
                          })
                          .catch(function(err){ console.warn('v3 events load failed', err); callback([]); });
                    },
                    eventRender: function(event, element){
                        var pieces = [event.title];
                        if (event.category) pieces.push('Category: '+event.category);
                        if (event.term) pieces.push('Term: '+event.term);
                        if (event.type) pieces.push('Type: '+event.type);
                        if (event.level) pieces.push('Level: '+event.level);
                        element.attr('title', pieces.join('\n'));
                    }
                });
                // filters
                var evCb = document.getElementById('fc-filter-event');
                var exCb = document.getElementById('fc-filter-exam');
                var rsCb = document.getElementById('fc-filter-responsibility');
                if (evCb) evCb.addEventListener('change', applyFiltersV3);
                if (exCb) exCb.addEventListener('change', applyFiltersV3);
                if (rsCb) rsCb.addEventListener('change', applyFiltersV3);
                // nav buttons
                var btnPrev = document.getElementById('fc-nav-prev');
                var btnToday = document.getElementById('fc-nav-today');
                var btnNext = document.getElementById('fc-nav-next');
                if (btnPrev) btnPrev.addEventListener('click', function(){ $cal.fullCalendar('prev'); });
                if (btnToday) btnToday.addEventListener('click', function(){ $cal.fullCalendar('today'); });
                if (btnNext) btnNext.addEventListener('click', function(){ $cal.fullCalendar('next'); });
                return; // done with v3
            } catch (e) {
                console.warn('FullCalendar v3 initialization failed, falling back to static grid', e);
            }
        }
        console.error('FullCalendar JS is not loaded or incompatible! Falling back to static month grid.');
        renderStaticMonth(calendarEl, new Date());
        wireStaticNav(calendarEl);
        return;
    }
    // Simple helpers
    function getFilters() {
        var ev = document.getElementById('fc-filter-event');
        var ex = document.getElementById('fc-filter-exam');
        var rs = document.getElementById('fc-filter-responsibility');
        return {
            event: !ev || ev.checked,
            exam: !ex || ex.checked,
            responsibility: !rs || rs.checked
        };
    }

    function colorForCategory(cat) {
        if (cat === 'exam') return '#dc3545'; // red
        if (cat === 'responsibility') return '#198754'; // green
        return '#0d6efd'; // blue for generic events
    }

    // Keep latest data for client-side filtering
    var cached = [];

    // Expose calendar within scope for nav controls
    var calendar;
    try {
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            contentHeight: 'auto',
            height: 500,
            initialDate: new Date(),
            timeZone: 'local',
            events: function(fetchInfo, successCb, failureCb) {
                var endpoint = '/dashboard/events/json/';
                var url = endpoint + '?start=' + encodeURIComponent(fetchInfo.startStr) + '&end=' + encodeURIComponent(fetchInfo.endStr);
                fetch(url, { credentials: 'same-origin' })
                  .then(function(resp){
                      if (!resp.ok) throw new Error('HTTP '+resp.status);
                      return resp.json();
                  })
                  .then(function(data){
                      if (!Array.isArray(data)) {
                          console.warn('Events feed did not return an array. Got:', data);
                      } else {
                          // cache and filter by current checkboxes
                          cached = data;
                          try {
                              var counts = {event:0, exam:0, responsibility:0, other:0};
                              cached.forEach(function(e){
                                  var c = (e.category||'event').toString().toLowerCase();
                                  if (counts.hasOwnProperty(c)) counts[c]++; else counts.other++;
                              });
                              console.log('Fetched events by category:', counts);
                          } catch(_e) {}
                          var f = getFilters();
                          var filtered = cached.filter(function(evt){
                              var cat = (evt.category || 'event').toString().toLowerCase();
                              if (cat === 'exam') return f.exam;
                              if (cat === 'responsibility') return (f.responsibility !== false); // show by default if no checkbox present
                              return f.event;
                          }).map(function(evt){
                              // apply colors
                              var cat = (evt.category || 'event').toString().toLowerCase();
                              evt.backgroundColor = colorForCategory(cat);
                              evt.borderColor = colorForCategory(cat);
                              return evt;
                          });
                          console.log('Loaded events:', filtered.length);
                          console.log('Responsibility presence after filter:', filtered.some(function(e){ return e.category === 'responsibility'; }));
                          successCb(filtered);
                          return;
                      }
                      successCb([]);
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
                var e = info.event;
                var cat = e.extendedProps && e.extendedProps.category ? e.extendedProps.category : 'event';
                var term = e.extendedProps && e.extendedProps.term ? ('\nTerm: ' + e.extendedProps.term) : '';
                var level = e.extendedProps && e.extendedProps.level ? ('\nLevel: ' + e.extendedProps.level) : '';
                var typ = e.extendedProps && e.extendedProps.type ? ('\nType: ' + e.extendedProps.type) : '';
                alert(e.title + '\n' + e.start.toLocaleDateString() + (e.allDay ? '' : (' ' + e.start.toLocaleTimeString())) + '\nCategory: ' + cat + term + level + typ);
            },
            eventDidMount: function(info) {
                var now = new Date();
                var startDate = new Date(info.event.start);
                if (startDate < now) {
                    info.el.style.opacity = '0.7';
                }
                // Add a tooltip via title attr
                var e = info.event;
                var pieces = [e.title];
                if (e.extendedProps && e.extendedProps.category) pieces.push('Category: ' + e.extendedProps.category);
                if (e.extendedProps && e.extendedProps.term) pieces.push('Term: ' + e.extendedProps.term);
                if (e.extendedProps && e.extendedProps.type) pieces.push('Type: ' + e.extendedProps.type);
                if (e.extendedProps && e.extendedProps.level) pieces.push('Level: ' + e.extendedProps.level);
                info.el.title = pieces.join('\n');
            }
        });
        calendar.render();

        // Wire up filters
        function reapplyFilters() {
            try {
                var f = getFilters();
                var filtered = cached.filter(function(evt){
                    var cat = (evt.category || 'event').toString().toLowerCase();
                    if (cat === 'exam') return f.exam;
                    if (cat === 'responsibility') return (f.responsibility !== false);
                    return f.event;
                }).map(function(evt){
                    var cat = (evt.category || 'event').toString().toLowerCase();
                    evt.backgroundColor = colorForCategory(cat);
                    evt.borderColor = colorForCategory(cat);
                    return evt;
                });
                try {
                    var cts = {event:0, exam:0, responsibility:0, other:0};
                    filtered.forEach(function(e){
                        var c = (e.category||'event').toString().toLowerCase();
                        if (cts.hasOwnProperty(c)) cts[c]++; else cts.other++;
                    });
                    console.log('Visible events by category after filter:', cts);
                } catch(_e) {}
                calendar.removeAllEvents();
                calendar.addEventSource(filtered);
            } catch(e) {
                console.warn('Failed to reapply filters', e);
            }
        }
        var evCb = document.getElementById('fc-filter-event');
        var exCb = document.getElementById('fc-filter-exam');
        var rsCb = document.getElementById('fc-filter-responsibility');
        if (evCb) evCb.addEventListener('change', reapplyFilters);
        if (exCb) exCb.addEventListener('change', reapplyFilters);
        if (rsCb) rsCb.addEventListener('change', reapplyFilters);

        // Wire up navigation buttons
        var btnPrev = document.getElementById('fc-nav-prev');
        var btnToday = document.getElementById('fc-nav-today');
        var btnNext = document.getElementById('fc-nav-next');
        if (btnPrev) btnPrev.addEventListener('click', function(){ calendar.prev(); });
        if (btnToday) btnToday.addEventListener('click', function(){ calendar.today(); });
        if (btnNext) btnNext.addEventListener('click', function(){ calendar.next(); });
    } catch (e) {
        console.error('Error initializing FullCalendar:', e);
        // Last-resort fallback
        try { renderStaticMonth(calendarEl, new Date()); } catch(_){}
    }
}

// Initialize when ready (handles late script load after DOMContentLoaded)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTeacherCalendar);
} else {
    // DOM is already parsed
    initTeacherCalendar();
}

