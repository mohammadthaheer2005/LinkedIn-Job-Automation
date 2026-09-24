let statusInterval = null;

document.getElementById('botForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const form = e.target;
    const formData = new FormData(form);
    const startBtn = document.getElementById('startBtn');
    const statusBox = document.getElementById('statusBox');
    const resultsBox = document.getElementById('resultsBox');

    // UI Updates
    startBtn.disabled = true;
    startBtn.textContent = 'Bot Running...';
    statusBox.classList.remove('hidden');
    resultsBox.classList.add('hidden');
    form.style.opacity = '0.5';

    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (response.ok) {
            pollStatus();
        } else {
            alert(data.error || 'Failed to start bot.');
            resetUI();
        }
    } catch (error) {
        console.error(error);
        alert('An error occurred.');
        resetUI();
    }
});

// Stop button event listener
document.getElementById('stopBtn').addEventListener('click', async () => {
    const stopBtn = document.getElementById('stopBtn');
    stopBtn.disabled = true;
    stopBtn.textContent = 'Stopping...';

    try {
        await fetch('/api/stop', { method: 'POST' });
    } catch (e) {
        console.error('Error stopping bot:', e);
    }
});

// Start new search button listener
document.getElementById('newRunBtn').addEventListener('click', () => {
    document.getElementById('resultsBox').classList.add('hidden');
    resetUI();
});

async function pollStatus() {
    const statusMessage = document.getElementById('statusMessage');
    const liveAppCount = document.getElementById('liveAppCount');
    
    statusInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();

            statusMessage.textContent = data.message;
            if (liveAppCount && data.applications !== undefined) {
                liveAppCount.textContent = data.applications;
            }

            if (!data.is_running && data.message !== 'Waiting to start...') {
                clearInterval(statusInterval);
                showResults(data);
            }
        } catch (e) {
            console.error('Error fetching status:', e);
        }
    }, 1500);
}

function showResults(data) {
    const statusBox = document.getElementById('statusBox');
    const resultsBox = document.getElementById('resultsBox');
    const resultsBadge = document.getElementById('resultsBadge');
    const resultsSummary = document.getElementById('resultsSummary');
    const appliedList = document.getElementById('appliedList');
    const stopBtn = document.getElementById('stopBtn');

    statusBox.classList.add('hidden');
    resultsBox.classList.remove('hidden');

    stopBtn.disabled = false;
    stopBtn.textContent = '🛑 Stop Automation';

    const count = data.applications || 0;
    resultsBadge.textContent = `${count} Applied`;
    resultsSummary.textContent = data.message || 'Execution finished.';

    appliedList.innerHTML = '';
    const companies = data.applied_companies || [];

    if (companies.length === 0) {
        appliedList.innerHTML = `<li class="empty-msg">No company names captured (or bot stopped early).</li>`;
    } else {
        companies.forEach(company => {
            const li = document.createElement('li');
            li.className = 'company-item';
            li.innerHTML = `
                <span class="icon">🏢</span>
                <span class="name">${escapeHtml(company)}</span>
                <span class="status-tag">Submitted</span>
            `;
            appliedList.appendChild(li);
        });
    }
    
    resetUI();
}

function resetUI() {
    const startBtn = document.getElementById('startBtn');
    const form = document.getElementById('botForm');

    startBtn.disabled = false;
    startBtn.textContent = 'Start Automation';
    form.style.opacity = '1';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
