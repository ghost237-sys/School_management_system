(function(){
  const $ = (s) => document.querySelector(s);
  const panel = document.getElementById('asst-panel');
  const fab = document.getElementById('asst-fab');
  if (!fab) return; // widget not present on this page
  const body = document.getElementById('asst-body');
  const sug = document.getElementById('asst-suggestions');
  const input = document.getElementById('asst-text');
  const send = document.getElementById('asst-send');
  const btnClose = document.getElementById('asst-close');
  const btnMin = document.getElementById('asst-min');
  const btnClear = document.getElementById('asst-clear');

  const HISTORY_URL = panel?.dataset.historyUrl || '/assistant/history/';
  const MESSAGE_URL = panel?.dataset.messageUrl || '/assistant/message/';
  const CLEAR_URL = panel?.dataset.clearUrl || '/assistant/clear/';

  function append(role, text){
    const row = document.createElement('div');
    row.className = 'asst-msg ' + role;
    const b = document.createElement('div');
    b.className = 'asst-bubble ' + role;
    b.textContent = text;
    row.appendChild(b);
    body.appendChild(row);
    body.scrollTop = body.scrollHeight;
  }

  function renderSuggestions(list){
    if (!sug) return;
    sug.innerHTML = '';
    if (!list || !list.length) { sug.style.display = 'none'; return; }
    list.forEach(it => {
      const chip = document.createElement('span');
      chip.className = 'asst-chip';
      chip.textContent = it.text || '';
      chip.addEventListener('click', () => { input.value = it.text || ''; sendMsg(); });
      sug.appendChild(chip);
    });
    sug.style.display = 'flex';
  }

  function csrf(){
    // Prefer CSRF token rendered in hidden form to support HttpOnly cookies
    const form = document.getElementById('asst-csrf-form');
    if (form) {
      const input = form.querySelector('input[name="csrfmiddlewaretoken"]');
      if (input && input.value) return input.value;
    }
    // Fallback to cookie if available
    const name = 'csrftoken';
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : '';
  }

  async function loadHistory(){
    try {
      const res = await fetch(HISTORY_URL);
      if (!res.ok) return;
      const data = await res.json();
      body.innerHTML = '';
      (data.messages || []).forEach(m => append(m.role, m.text));
    } catch(e) { /* noop */ }
  }

  async function sendMsg(){
    const text = (input.value || '').trim();
    if (!text) return;
    append('user', text);
    input.value = '';
    try {
      const res = await fetch(MESSAGE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'X-CSRFToken': csrf()
        },
        body: new URLSearchParams({ text })
      });
      let data;
      try { data = await res.json(); } catch(_) { /* non-JSON error */ }
      if (!res.ok) {
        const msg = (data && (data.detail || data.message)) || `Server error (${res.status}). Please try again.`;
        append('bot', msg);
        return;
      }
      append('bot', (data && data.reply) || '');
      renderSuggestions(data && data.suggestions);
      if (data && data.action && data.action.type === 'navigate' && data.action.url) {
        setTimeout(() => { window.location.href = data.action.url; }, 400);
      }
    } catch(e) {
      append('bot', 'Network error. Please try again.');
    }
  }

  fab.addEventListener('click', () => {
    panel.style.display = panel.style.display === 'block' ? 'none' : 'block';
    if (panel.style.display === 'block') loadHistory();
  });
  btnClose && btnClose.addEventListener('click', () => panel.style.display = 'none');
  btnMin && btnMin.addEventListener('click', () => panel.classList.toggle('minimized'));
  btnClear && btnClear.addEventListener('click', async () => {
    try {
      const res = await fetch(CLEAR_URL, { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
      if (!res.ok) throw new Error('Failed');
      body.innerHTML = '';
      renderSuggestions([]);
      append('bot', 'History cleared.');
    } catch(e) {
      append('bot', 'Could not clear history.');
    }
  });
  send.addEventListener('click', sendMsg);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendMsg(); });
})();
