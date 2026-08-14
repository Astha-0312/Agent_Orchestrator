document.addEventListener('DOMContentLoaded', () => {
    loadTraces();
    loadAnalytics();
    setInterval(loadTraces, 15000);
});

async function loadTraces() {
    try {
        const res = await fetch('/api/v1/traces');
        if (!res.ok) return;
        const traces = await res.json();
        renderTraceList(traces);
    } catch (err) {
        console.error('Error loading traces', err);
    }
}

function renderTraceList(traces) {
    const container = document.getElementById('trace-list');
    if (!traces || traces.length === 0) {
        container.innerHTML = '<p class="empty-state">No traces found.</p>';
        return;
    }
    
    container.innerHTML = '';
    traces.forEach(trace => {
        const item = document.createElement('div');
        item.className = 'trace-item';
        item.onclick = () => {
            document.querySelectorAll('.trace-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');
            loadTrace(trace.task_id);
        };
        
        item.innerHTML = `
            <div style="font-weight:500">${trace.task_id.substring(0, 8)}</div>
            <div class="trace-meta">
                <span>Cost: $${(trace.cost || 0).toFixed(4)}</span>
                <span>Lat: ${(trace.latency_ms || 0)}ms</span>
            </div>
        `;
        container.appendChild(item);
    });
}

async function loadTrace(taskId) {
    const container = document.getElementById('trace-tree-container');
    container.innerHTML = '<p class="empty-state">Loading trace details...</p>';
    
    try {
        const res = await fetch(`/api/v1/traces/${taskId}`);
        if (!res.ok) throw new Error('Failed to load');
        const trace = await res.json();
        
        container.innerHTML = `
            <div style="margin-bottom:1rem;display:flex;justify-content:space-between;align-items:center;">
                <h2>Trace: ${taskId.substring(0, 8)}</h2>
                <button class="badge-mini" style="cursor:pointer;padding:0.5rem" onclick="replayTrace('${taskId}')">Replay Trace</button>
            </div>
        `;
        
        // Render root spans (spans without parent_id)
        const rootSpans = trace.spans.filter(s => !s.parent_id);
        rootSpans.forEach(span => {
            container.appendChild(createTreeNode(span, trace.spans));
        });
        
    } catch (err) {
        container.innerHTML = '<p class="empty-state">Error loading trace.</p>';
    }
}

function createTreeNode(span, allSpans) {
    const node = document.createElement('div');
    node.className = 'tree-node';
    
    const children = allSpans.filter(s => s.parent_id === span.span_id);
    const hasChildren = children.length > 0;
    
    const statusClass = span.status === 'error' ? 'badge-error' : 'badge-success';
    
    node.innerHTML = `
        <div class="tree-node-content" onclick="loadSpanDetail('${span.task_id}', '${span.span_id}')">
            <strong>${span.name}</strong>
            <span class="badge-mini ${statusClass}">${span.status || 'ok'}</span>
            <span class="badge-mini">${span.latency_ms || 0}ms</span>
        </div>
        ${hasChildren ? `<div class="tree-children" id="children-${span.span_id}"></div>` : ''}
    `;
    
    if (hasChildren) {
        // Wait for next tick so DOM is populated
        setTimeout(() => {
            const childContainer = node.querySelector(`#children-${span.span_id}`);
            children.forEach(child => {
                childContainer.appendChild(createTreeNode(child, allSpans));
            });
        }, 0);
    }
    
    return node;
}

async function loadSpanDetail(taskId, spanId) {
    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('span-content');
    
    panel.classList.add('open');
    content.innerHTML = '<p class="empty-state">Loading span...</p>';
    
    try {
        const res = await fetch(`/api/v1/traces/${taskId}/spans/${spanId}`);
        if (!res.ok) throw new Error();
        const span = await res.json();
        
        content.innerHTML = `
            <div style="margin-bottom:1rem">
                <span class="badge-mini">Span ID: ${span.span_id.substring(0,8)}</span>
                <span class="badge-mini">${span.type || 'unknown'}</span>
            </div>
            
            ${span.inputs ? `
                <h4 style="font-size:0.875rem;margin-bottom:0.5rem">Inputs</h4>
                <pre>${JSON.stringify(span.inputs, null, 2)}</pre>
            ` : ''}
            
            ${span.outputs ? `
                <h4 style="font-size:0.875rem;margin-bottom:0.5rem">Outputs</h4>
                <pre>${JSON.stringify(span.outputs, null, 2)}</pre>
            ` : ''}
        `;
    } catch (err) {
        content.innerHTML = '<p class="empty-state">Failed to load span details.</p>';
    }
}

function closeDetailPanel() {
    document.getElementById('detail-panel').classList.remove('open');
}

async function loadAnalytics() {
    try {
        const res = await fetch('/api/v1/analytics/costs?days=30');
        if (!res.ok) return;
        const data = await res.json();
        
        const summary = document.getElementById('analytics-summary');
        summary.innerHTML = `
            <div style="padding:1rem;background:var(--color-slate-100);margin:1rem;border-radius:4px;">
                <div style="font-size:0.75rem;color:var(--color-slate-500)">Total Cost (30d)</div>
                <div style="font-size:1.5rem;font-weight:600">$${(data.total_cost || 0).toFixed(2)}</div>
            </div>
        `;
    } catch (err) {
        console.error('Error loading analytics', err);
    }
}

async function replayTrace(taskId) {
    if (!confirm('Replay this trace?')) return;
    try {
        const res = await fetch(`/api/v1/traces/${taskId}/replay`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ modifications: [] })
        });
        if (res.ok) {
            alert('Replay started');
            loadTraces();
        } else {
            alert('Failed to replay trace');
        }
    } catch (err) {
        console.error(err);
    }
}
