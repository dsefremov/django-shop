// Минимальный JS: выпадающие списки с data-autosubmit отправляют свою GET-форму сразу.
// Без JS всё работает через кнопку «Применить».
document.addEventListener('change', (event) => {
    const el = event.target;
    if (el instanceof HTMLSelectElement && el.dataset.autosubmit !== undefined && el.form) {
        el.form.requestSubmit();
    }
});
