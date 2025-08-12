// Stepper Logic for Add Teacher & Add Student
// Supports any form with .modern-stepper-card and .stepper-step/.stepper-next/.stepper-prev

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.modern-stepper-card').forEach(function(form) {
    const steps = form.querySelectorAll('.step-card');
    const navLinks = form.querySelectorAll('.stepper-step');
    const nextBtns = form.querySelectorAll('.stepper-next');
    const prevBtns = form.querySelectorAll('.stepper-prev');
    let currentStep = 0;

    function showStep(step) {
      steps.forEach((el, i) => {
        el.classList.toggle('d-none', i !== step);
      });
      navLinks.forEach((nav, i) => {
        nav.classList.toggle('active', i === step);
      });
      currentStep = step;
    }

    navLinks.forEach((nav, i) => {
      nav.addEventListener('click', () => {
        if (i <= currentStep) showStep(i);
      });
    });
    nextBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        if (currentStep < steps.length - 1) showStep(currentStep + 1);
      });
    });
    prevBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        if (currentStep > 0) showStep(currentStep - 1);
      });
    });
    showStep(0);
  });
});
