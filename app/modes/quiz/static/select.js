let quizConfig = {};

function initQuizSelect(config) {
    quizConfig = config;
}

function generateQuiz(count) {
    if (!quizConfig.topicName || !quizConfig.baseUrl) {
        console.error("Quiz configuration missing");
        return;
    }

    const topicName = quizConfig.topicName;
    const baseUrl = quizConfig.baseUrl; // e.g. "/quiz/generate"

    // Construct URL: /quiz/generate/<topic_name>/<count>
    // Note: Flask routes are /quiz/generate/<topic_name>/<count>
    let url = `${baseUrl}/${topicName}/${count}`;
    window.location.href = url;
}

function generateCustomQuiz() {
    const input = document.getElementById('custom-quiz-count');
    const count = input.value;

    if (!count || count < 1) {
        alert("Please enter a valid number of questions (min 1).");
        return;
    }

    generateQuiz(count);
}
