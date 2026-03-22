document.addEventListener('DOMContentLoaded', () => {
    const darkModeToggle = document.getElementById('darkModeToggle');
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', () => {
            document.documentElement.classList.toggle('dark');
            localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
            darkModeToggle.textContent = document.documentElement.classList.contains('dark') ? 'Light Mode' : 'Dark Mode';
        });

        if (localStorage.getItem('theme') === 'dark') {
            document.documentElement.classList.add('dark');
            darkModeToggle.textContent = 'Light Mode';
        }
    }

    // Debug: Log the detail strings and their styling conditions
    document.querySelectorAll('li[data-detail]').forEach((li) => {
        const detail = li.getAttribute('data-detail');
        const hasCorrect = detail.includes('Correct');
        const hasIncorrect = detail.includes('Incorrect');
        console.log(`Detail: "${detail}" | Correct: ${hasCorrect} | Incorrect: ${hasIncorrect} | Classes: ${li.className}`);
    });
});