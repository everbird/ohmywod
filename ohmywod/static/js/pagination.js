/* Small progressive enhancement; navigation stays native GET/links. */
(function () {
    'use strict';
    document.querySelectorAll('.pager-jump').forEach(function (form) {
        var input = form.querySelector('.pager-page');
        var submit = form.querySelector('.pager-submit');
        var feedback = document.getElementById(input.getAttribute('aria-describedby'));
        var current = Number(form.dataset.currentPage);
        var total = Number(form.dataset.totalPages);

        function update() {
            var value = Number(input.value);
            var valid = /^[0-9]+$/.test(input.value) && Number.isSafeInteger(value)
                && value >= 1 && value <= total;
            var message = valid ? '' : '请输入 1～' + total + ' 之间的整数页码。';
            input.setCustomValidity(message);
            input.setAttribute('aria-invalid', String(!valid));
            feedback.textContent = message;
            feedback.hidden = valid;
            submit.disabled = !valid || value === current;
            return valid;
        }

        input.addEventListener('focus', function () {
            input.select();
        });
        input.addEventListener('input', update);
        form.addEventListener('submit', function (event) {
            if (!update() || Number(input.value) === current) {
                event.preventDefault();
                input.reportValidity();
            }
        });
        window.addEventListener('pageshow', update);
        update();
    });
}());
