// Handles subject average charts for class cards on admin_classes.html
// Requires Chart.js to be loaded in the template

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.class-subject-chart').forEach(function (canvas) {
        const data = JSON.parse(canvas.dataset.chart);
        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.scores,
                    backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    borderRadius: 3,
                    maxBarThickness: 12,
                }]
            },
            options: {
                responsive: false,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: false }
                },
                scales: {
                    x: {
                        display: false,
                        grid: { display: false, drawBorder: false }
                    },
                    y: {
                        display: false,
                        grid: { display: false, drawBorder: false },
                        beginAtZero: true,
                        max: 100
                    }
                },
                layout: {
                    padding: { left: 0, right: 0, top: 0, bottom: 0 }
                }
            }
        });
    });
});
