// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.getElementById('hamburger');
    const navMenu = document.getElementById('navMenu');
    
    if (hamburger) {
        hamburger.addEventListener('click', function() {
            navMenu.classList.toggle('active');
            
            // Animate hamburger
            const spans = this.querySelectorAll('span');
            spans.forEach(span => span.classList.toggle('active'));
        });
    }
    
    // Auto-hide flash messages
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(message => {
        setTimeout(() => {
            message.style.opacity = '0';
            setTimeout(() => {
                message.remove();
            }, 300);
        }, 3000);
    });
    
    // Check model status
    checkModelStatus();
});

function checkModelStatus() {
    fetch('/api/health')
        .then(response => response.json())
        .then(data => {
            const statusElement = document.getElementById('modelStatus');
            if (statusElement) {
                if (data.model_available) {
                    statusElement.innerHTML = '<span class="status-dot active"></span> Model Ready';
                } else {
                    statusElement.innerHTML = '<span class="status-dot"></span> Model Loading...';
                }
            }
        })
        .catch(error => {
            console.error('Error checking model status:', error);
        });
}