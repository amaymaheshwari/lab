// --- Chart instances ---
let spChart, unemploymentChart, treasuryChart, gdpChart;

// --- Utility: render a line chart ---
function renderLineChart(canvasId, labels, values, color) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                data: values,
                borderColor: color,
                borderWidth: 2,
                tension: 0.3,
                pointRadius: 0,
                fill: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    grid: { color: '#1f222a' },
                    ticks: { color: '#86868b', maxTicksLimit: 6, maxRotation: 0 }
                },
                y: {
                    grid: { color: '#1f222a' },
                    ticks: { color: '#86868b' }
                }
            },
            animation: false,
        }
    });
}

// --- Utility: update a KPI card ---
function updateKpi(id, value, status) {
    const card = document.getElementById('kpi-' + id);
    if (!card) return;
    const el = card.querySelector('.kpi-value');
    el.innerText = value;
    el.className = 'kpi-value ' + (status || '');
}

// --- Load macro data from FRED ---
async function loadMacro() {
    try {
        const res = await fetch('/api/macro');
        const data = await res.json();

        // CPI YoY
        if (data.cpi_yoy !== null && data.cpi_yoy !== undefined) {
            const yoy = data.cpi_yoy;
            const status = yoy > 4 ? 'red' : yoy < 2 ? 'green' : 'orange';
            updateKpi('cpi', yoy.toFixed(1) + '%', status);
        }

        // Unemployment
        if (data.unemployment?.length) {
            const val = data.unemployment.at(-1).value;
            updateKpi('unemployment', val.toFixed(1) + '%', val > 5.5 ? 'red' : 'green');
        }

        // 10yr Treasury
        if (data.treasury_10y?.length) {
            const val = data.treasury_10y.at(-1).value;
            updateKpi('treasury', val.toFixed(2) + '%', 'blue');
        }

        // Fed Funds
        if (data.fed_funds?.length) {
            const val = data.fed_funds.at(-1).value;
            updateKpi('fedfunds', val.toFixed(2) + '%', 'blue');
        }

        // S&P 500 chart
        if (data.sp500?.length) {
            const labels = data.sp500.map(d => d.date);
            const values = data.sp500.map(d => d.value);
            const first = values[0];
            const last = values.at(-1);
            const color = last >= first ? '#30d158' : '#ff3b30';
            spChart = renderLineChart('spChart', labels, values, color);
        }

        // Unemployment chart
        if (data.unemployment?.length) {
            const labels = data.unemployment.map(d => d.date);
            const values = data.unemployment.map(d => d.value);
            unemploymentChart = renderLineChart('unemploymentChart', labels, values, '#ff9f0a');
        }

        // 10yr Treasury chart
        if (data.treasury_10y?.length) {
            const labels = data.treasury_10y.map(d => d.date);
            const values = data.treasury_10y.map(d => d.value);
            treasuryChart = renderLineChart('treasuryChart', labels, values, '#2997ff');
        }

        // Timestamp
        document.getElementById('last-updated').innerText =
            'Updated ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    } catch (e) {
        console.error('Macro load failed:', e);
    }
}

// --- Load G7 GDP data from World Bank ---
async function loadGdp() {
    try {
        const res = await fetch('/api/gdp');
        const countries = await res.json();
        if (!countries.length) return;

        // Most recent year per country
        const labels = countries.map(c => c.name.replace('United ', 'U.'));
        const values = countries.map(c => c.data.length ? c.data.at(-1).value : 0);
        const year = countries[0]?.data.at(-1)?.year || '';

        document.getElementById('gdp-year').innerText = year ? `(${year})` : '';

        const ctx = document.getElementById('gdpChart').getContext('2d');
        gdpChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: values.map(v => v >= 0
                        ? 'rgba(48, 209, 88, 0.35)'
                        : 'rgba(255, 59, 48, 0.35)'),
                    borderColor: values.map(v => v >= 0 ? '#30d158' : '#ff3b30'),
                    borderWidth: 1,
                    borderRadius: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => ctx.parsed.y.toFixed(2) + '% GDP Growth'
                        }
                    }
                },
                scales: {
                    x: { grid: { color: '#1f222a' }, ticks: { color: '#86868b' } },
                    y: {
                        grid: { color: '#1f222a' },
                        ticks: { color: '#86868b', callback: v => v + '%' }
                    }
                }
            }
        });
    } catch (e) {
        console.error('GDP load failed:', e);
    }
}

// --- Gemini Historical Context ---
async function loadContext() {
    const btn = document.getElementById('context-btn');
    const result = document.getElementById('context-result');

    btn.disabled = true;
    btn.innerText = 'Analyzing...';
    result.innerHTML = '<div class="context-loading">Consulting the historical record...</div>';

    try {
        const res = await fetch('/api/context');
        if (!res.ok) {
            const err = await res.json();
            result.innerHTML = `<div class="context-error">${err.error}</div>`;
            return;
        }
        const data = await res.json();
        const confClass = { High: 'green', Medium: 'orange', Low: 'red' }[data.confidence] || '';
        result.innerHTML = `
            <div class="context-card">
                <div class="context-header">
                    <div class="context-era">${data.era}</div>
                    <div class="context-confidence ${confClass}">${data.confidence} Confidence</div>
                </div>
                <p class="context-reasoning">${data.reasoning}</p>
                <div class="context-risk">
                    <span class="risk-label">KEY RISK</span>
                    <span class="risk-text">${data.key_risk}</span>
                </div>
            </div>
        `;
    } catch (e) {
        result.innerHTML = '<div class="context-error">Analysis failed. Try again.</div>';
    } finally {
        btn.disabled = false;
        btn.innerText = 'Re-analyze';
    }
}

// --- Init ---
loadMacro();
loadGdp();
