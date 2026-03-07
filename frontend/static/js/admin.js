// Admin Panel JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Close flash messages
    document.querySelectorAll('.close-flash').forEach(btn => {
        btn.addEventListener('click', function() {
            this.parentElement.remove();
        });
    });
    
    // Auto-hide flash messages after 5 seconds
    setTimeout(() => {
        document.querySelectorAll('.admin-flash-message').forEach(msg => {
            msg.style.opacity = '0';
            setTimeout(() => msg.remove(), 300);
        });
    }, 5000);
    
    // Initialize search functionality
    const searchInput = document.getElementById('adminSearch');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(handleGlobalSearch, 500));
    }
    
    // Load real-time stats
    loadRealTimeStats();
    setInterval(loadRealTimeStats, 30000); // Update every 30 seconds
});

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function handleGlobalSearch(e) {
    const query = e.target.value;
    if (query.length > 2) {
        // Implement global search
        console.log('Searching for:', query);
    }
}

function loadRealTimeStats() {
    fetch('/admin/api/stats')
        .then(response => response.json())
        .then(data => {
            updateStatsCards(data);
            updateNotificationBadge(data);
        })
        .catch(error => console.error('Error loading stats:', error));
}

function updateStatsCards(data) {
    // Update stats in real-time if they exist on the page
    const elements = {
        totalUsers: document.querySelector('[data-stat="total-users"]'),
        activeToday: document.querySelector('[data-stat="active-today"]'),
        conversations: document.querySelector('[data-stat="conversations"]'),
        avgResponse: document.querySelector('[data-stat="avg-response"]')
    };
    
    if (elements.totalUsers) {
        elements.totalUsers.textContent = data.users.total;
    }
    
    if (elements.activeToday) {
        elements.activeToday.textContent = data.users.active_today;
    }
    
    if (elements.conversations) {
        elements.conversations.textContent = data.conversations.total;
    }
    
    if (elements.avgResponse) {
        elements.avgResponse.textContent = data.system.avg_response_time.toFixed(0) + 'ms';
    }
}

function updateNotificationBadge(data) {
    const badge = document.querySelector('.notification-badge .badge');
    if (badge) {
        const alertCount = (data.system.errors_last_hour || 0) + 
                          (data.users.locked_accounts || 0);
        badge.textContent = alertCount;
        badge.style.display = alertCount > 0 ? 'block' : 'none';
    }
}

function refreshData() {
    location.reload();
}

// Modal functions
function openModal(modalId) {
    document.getElementById(modalId).style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
};

// Confirmation dialogs
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Export functions
function exportData(type, format) {
    fetch(`/admin/api/export/${type}?format=${format}`)
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${type}_export_${new Date().toISOString().slice(0,10)}.${format}`;
            a.click();
        });
}

// Chart utilities
function createChart(canvasId, type, data, options = {}) {
    const ctx = document.getElementById(canvasId)?.getContext('2d');
    if (!ctx) return null;
    
    return new Chart(ctx, {
        type: type,
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            ...options
        }
    });
}

// Format helpers
function formatDate(date) {
    return new Date(date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function formatDuration(ms) {
    if (ms < 1000) return ms + 'ms';
    return (ms / 1000).toFixed(2) + 's';
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    });
}

// Toast notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}