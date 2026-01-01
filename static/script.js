let historyOpen = false;

document.addEventListener('DOMContentLoaded', () => {
    // History toggle
    document.getElementById('historyToggle').onclick = () => {
        historyOpen = !historyOpen;
        document.getElementById('historyPanel').classList.toggle('open', historyOpen);
    }
    
    // Main analysis form
    document.getElementById('analysisForm').onsubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const resultDiv = document.getElementById('analysisResult');
        const btn = e.target.querySelector('button');
        
        btn.innerHTML = 'Analyzing <span class="loading"></span>';
        btn.disabled = true;
        resultDiv.innerHTML = '';
        
        try {
            const response = await fetch('/analyze', { method: 'POST', body: formData });
            const data = await response.json();
            displayResults(data);
        } catch(e) {
            resultDiv.innerHTML = `<div style="color:red;padding:20px;">Error: ${e.message}</div>`;
        }
        
        btn.innerHTML = 'Analyze Jobs';
        btn.disabled = false;
    }
    
    // Cold email form
    document.getElementById('emailForm').onsubmit = async (e) => {
        e.preventDefault();
        if (!confirm('Send cold email with resume attached?')) return;
        
        const formData = new FormData(e.target);
        const previewDiv = document.getElementById('emailPreview');
        const btn = e.target.querySelector('button');
        
        btn.innerHTML = 'Sending <span class="loading"></span>';
        btn.disabled = true;
        
        try {
            const response = await fetch('/send-email', { method: 'POST', body: formData });
            const data = await response.json();
            previewDiv.innerHTML = `<div style="color:${data.success ? '#10b981' : '#ef4444'}">${data.message}</div>`;
        } catch(e) {
            previewDiv.innerHTML = `<div style="color:red;">Error: ${e.message}</div>`;
        }
        
        btn.innerHTML = 'Send Cold Email';
        btn.disabled = false;
    }
});

function displayResults(data) {
    const resultDiv = document.getElementById('analysisResult');
    let html = `
        <div class="jobs-grid">
    `;
    
    data.jobs.forEach(job => {
        html += `
            <div class="job-card">
                <div class="job-title">${job.title}</div>
                <div class="match-score">${job.match_score}% Match</div>
                ${job.improvements ? `<div class="improvements"><strong>📈 Improve:</strong> ${job.improvements}</div>` : ''}
                <a href="${job.apply_url}" target="_blank" class="job-link">🚀 Apply Now</a>
            </div>
        `;
    });
    
    html += `
        </div>
        <div style="text-align:center;margin-top:30px;color:#64748b;">
            Found ${data.jobs.length} matching jobs from ${data.company}
        </div>
    `;
    
    resultDiv.innerHTML = html;
}
