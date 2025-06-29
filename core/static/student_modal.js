// student_modal.js
// Handles AJAX for Add Student modal in admin_students.html

document.addEventListener('DOMContentLoaded', function() {
    // Open modal and load form
    const addBtn = document.querySelector('[data-bs-target="#addStudentFormCollapse"]');
    if (addBtn) {
        addBtn.addEventListener('click', function() {
            fetch('/dashboard/students/add/', {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            })
            .then(res => res.json())
            .then(data => {
                if (data.form_html) {
                    document.getElementById('addStudentFormCollapse').innerHTML = data.form_html;
                    attachStudentFormHandler();
                }
            });
        });
    }
    // Attach handler if form already present
    attachStudentFormHandler();
});

function attachStudentFormHandler() {
    const container = document.getElementById('addStudentFormCollapse');
    if (!container) return;
    const form = container.querySelector('form');
    if (!form) return;
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(form);
        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast('Student added successfully!', 'success');
                // Close modal/collapse
                const collapse = bootstrap.Collapse.getOrCreateInstance(container);
                collapse.hide();
                // Refresh the student table
                reloadStudentTable();
            } else if (data.form_html) {
                container.innerHTML = data.form_html;
                attachStudentFormHandler();
                showToast('Please fix the errors in the form.', 'danger');
            } else if (data.error) {
                showToast(data.error, 'danger');
            }
        })
        .catch(() => showToast('An error occurred. Try again.', 'danger'));
    });
}

function reloadStudentTable() {
    fetch(window.location.href, {
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-Reload-Students': '1'}
    })
    .then(res => res.text())
    .then(html => {
        // Expect a partial with the table, or replace tbody
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newTable = doc.querySelector('.card.mb-4 .table');
        const curTable = document.querySelector('.card.mb-4 .table');
        if (newTable && curTable) {
            curTable.innerHTML = newTable.innerHTML;
        } else {
            window.location.reload();
        }
    });
}

function showToast(message, type) {
    // Bootstrap 5 toast or fallback alert
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.style.position = 'fixed';
        toastContainer.style.top = '1rem';
        toastContainer.style.right = '1rem';
        toastContainer.style.zIndex = 9999;
        document.body.appendChild(toastContainer);
    }
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0 show mb-2`;
    toast.role = 'alert';
    toast.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div><button type="button" class="btn-close btn-close-white ms-2 m-auto" data-bs-dismiss="toast"></button></div>`;
    toastContainer.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 4000);
}
