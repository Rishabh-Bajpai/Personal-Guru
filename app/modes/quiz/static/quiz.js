document.addEventListener('DOMContentLoaded', function () {
    const options = document.querySelectorAll('.option');

    options.forEach(option => {
        option.addEventListener('click', function (e) {
            // Find the radio button inside this option
            const radio = this.querySelector('input[type="radio"]');

            // If the click wasn't on the radio itself (since clicking label/radio propagates),
            // we manualy select it. However, since the label covers the whole area,
            // click on label triggers radio change. We just need to update visual classes.

            // Remove selected class from all options in the same question group
            const questionContainer = this.closest('.options');
            const siblingOptions = questionContainer.querySelectorAll('.option');
            siblingOptions.forEach(sibling => sibling.classList.remove('selected'));

            // Add selected class to this option
            this.classList.add('selected');

            // Ensure radio is checked (redundant if label click, but safe)
            radio.checked = true;
        });

        // Handle pre-selected inputs (browser back button etc)
        const radio = option.querySelector('input[type="radio"]');
        if (radio.checked) {
            option.classList.add('selected');
        }
    });
});
