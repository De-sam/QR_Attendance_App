function toggleForm(form) {
    // Toggle active class on buttons
    const buttons = document.querySelectorAll('.btn-toggle');
    buttons.forEach(button => {
        if (button.getAttribute('data-form') === form) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    });

    // Toggle active class on forms
    const forms = document.querySelectorAll('.form-section');
    forms.forEach(section => {
        if (section.id === form + 'Form') {
            section.classList.add('active');
        } else {
            section.classList.remove('active');
        }
    });
}