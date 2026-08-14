document.addEventListener('DOMContentLoaded', () => {
    loadPendingApprovals();
    loadTasks();

    // Refresh tasks frequently so running/completed status updates
    setInterval(loadPendingApprovals, 5000);
    setInterval(loadTasks, 2000);

    const taskForm = document.getElementById('task-form');

    taskForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const promptInput = document.getElementById('task-prompt');
        const prompt = promptInput.value.trim();

        if (!prompt) return;

        const submitButton = taskForm.querySelector('button');

        try {
            submitButton.disabled = true;
            submitButton.textContent = 'Running...';

            const res = await fetch('/api/v1/tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    prompt: prompt,
                    user_id: 'default',
                    require_approval: true
                })
            });

            if (res.ok) {
                const data = await res.json();

                showToast('Task submitted successfully', 'success');

                promptInput.value = '';

                // Immediately refresh the task list
                loadTasks();

            } else {
                showToast('Failed to submit task', 'error');
            }

        } catch (err) {
            console.error(err);
            showToast('Error submitting task', 'error');

        } finally {
            submitButton.disabled = false;
            submitButton.textContent = 'Submit Task';
        }
    });
});


async function loadPendingApprovals() {
    try {
        const res = await fetch('/api/v1/approvals/pending');

        if (!res.ok) return;

        const approvals = await res.json();

        renderApprovals(approvals);

    } catch (err) {
        console.error('Error loading approvals:', err);
    }
}


function renderApprovals(approvals) {

    const container = document.getElementById('approvals-container');

    if (!approvals || approvals.length === 0) {
        container.innerHTML =
            '<p class="empty-state">No pending approvals.</p>';
        return;
    }

    container.innerHTML = '';

    approvals.forEach(app => {

        const sevClass =
            app.severity <= 2
                ? 'badge-green'
                : app.severity === 3
                    ? 'badge-yellow'
                    : 'badge-red';

        const card = document.createElement('div');

        card.className = 'card';

        card.innerHTML = `
            <div class="card-header">
                <h3 style="font-size:1rem;">
                    Task: ${app.task_id.substring(0, 8)}
                </h3>

                <span class="badge ${sevClass}">
                    Sev ${app.severity}
                </span>
            </div>

            <div>
                <strong>Reason:</strong>
                ${app.reason}

                <strong style="margin-top:0.5rem;display:block;">
                    Proposed Action:
                </strong>

                <pre style="
                    background:var(--color-slate-100);
                    padding:0.5rem;
                    border-radius:4px;
                    font-size:0.875rem;
                    margin-top:0.25rem;
                ">${app.proposed_action}</pre>
            </div>

            <div class="card-actions">

                <button
                    class="btn btn-success"
                    onclick="submitDecision(
                        '${app.task_id}',
                        {approved:true, action:'proceed'}
                    )">
                    Approve
                </button>

                <button
                    class="btn btn-danger"
                    onclick="submitDecision(
                        '${app.task_id}',
                        {approved:false, action:'reject'}
                    )">
                    Reject
                </button>

                <button
                    class="btn btn-primary"
                    onclick="showTakeOver('${app.task_id}')">
                    Take Over
                </button>

            </div>

            <div
                class="takeover-panel"
                id="takeover-${app.task_id}">

                <textarea
                    id="feedback-${app.task_id}"
                    placeholder="Provide instructions or feedback..."
                ></textarea>

                <button
                    class="btn btn-primary"
                    onclick="submitTakeOver('${app.task_id}')">
                    Submit Feedback
                </button>

            </div>
        `;

        container.appendChild(card);
    });
}


function showTakeOver(taskId) {

    const panel =
        document.getElementById(`takeover-${taskId}`);

    panel.classList.toggle('active');
}


async function submitTakeOver(taskId) {

    const feedback =
        document.getElementById(`feedback-${taskId}`).value;

    await submitDecision(
        taskId,
        {
            approved: false,
            action: 'modify',
            feedback: feedback,
            human_response: feedback
        }
    );
}


async function submitDecision(taskId, decision) {

    try {

        const res = await fetch(
            `/api/v1/approvals/${taskId}/decide`,
            {
                method: 'POST',

                headers: {
                    'Content-Type': 'application/json'
                },

                body: JSON.stringify(decision)
            }
        );

        if (res.ok) {

            showToast(
                'Decision submitted',
                'success'
            );

            loadPendingApprovals();

        } else {

            showToast(
                'Failed to submit decision',
                'error'
            );
        }

    } catch (err) {

        console.error(err);

        showToast(
            'Error submitting decision',
            'error'
        );
    }
}


async function loadTasks() {

    try {

        const res =
            await fetch('/api/v1/tasks');

        if (!res.ok) return;

        const data = await res.json();

        /*
         * The API returns:
         *
         * {
         *     "tasks": [...],
         *     "total": ...
         * }
         *
         * So we need data.tasks
         */

        renderTasks(data.tasks || []);

    } catch (err) {

        console.error(
            'Error loading tasks:',
            err
        );
    }
}


function renderTasks(tasks) {

    const container =
        document.getElementById('tasks-container');

    if (!tasks || tasks.length === 0) {

        container.innerHTML =
            '<p class="empty-state">No recent tasks.</p>';

        return;
    }

    container.innerHTML = '';

    /*
     * Show newest tasks first
     */
    tasks
        .slice()
        .reverse()
        .slice(0, 10)
        .forEach(task => {

            let badgeClass = 'badge-gray';

            if (task.status === 'completed') {
                badgeClass = 'badge-green';
            }

            else if (task.status === 'running') {
                badgeClass = 'badge-blue';
            }

            else if (task.status === 'failed') {
                badgeClass = 'badge-red';
            }

            else if (task.status === 'queued') {
                badgeClass = 'badge-yellow';
            }

            /*
             * Create task card
             */

            const item =
                document.createElement('div');

            item.className = 'list-item';

            let resultHTML = '';

            if (task.status === 'completed' && task.final_output) {

                resultHTML = `
                    <div style="
                        margin-top: 15px;
                        padding: 15px;
                        background: var(--color-slate-100);
                        border-radius: 8px;
                        border-left: 4px solid var(--color-blue-500);
                    ">

                        <strong style="
                            display:block;
                            margin-bottom:8px;
                        ">
                            Agent Answer
                        </strong>

                        <div style="
                            line-height:1.6;
                            white-space:pre-wrap;
                        ">
                            ${escapeHtml(task.final_output)}
                        </div>

                    </div>
                `;
            }

            else if (task.status === 'running') {

                resultHTML = `
                    <div style="
                        margin-top:10px;
                        color:var(--color-slate-500);
                    ">
                        Agent is working...
                    </div>
                `;
            }

            else if (task.status === 'failed') {

                resultHTML = `
                    <div style="
                        margin-top:10px;
                        color:#dc2626;
                    ">
                        Error:
                        ${escapeHtml(task.error || 'Unknown error')}
                    </div>
                `;
            }

            item.innerHTML = `

                <div style="width:100%;">

                    <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                        gap:15px;
                    ">

                        <div>

                            <strong>
                                ${escapeHtml(
                                    task.request ||
                                    task.prompt ||
                                    'Unnamed task'
                                )}
                            </strong>

                            <div style="
                                font-size:0.75rem;
                                color:var(--color-slate-500);
                                margin-top:4px;
                            ">
                                ID:
                                ${task.task_id || ''}
                            </div>

                        </div>

                        <span class="badge ${badgeClass}">
                            ${task.status}
                        </span>

                    </div>

                    ${resultHTML}

                </div>
            `;

            container.appendChild(item);
        });
}


/*
 * Prevent HTML from being injected into the page
 */
function escapeHtml(value) {

    if (!value) return '';

    const div =
        document.createElement('div');

    div.textContent = value;

    return div.innerHTML;
}


function showToast(message, type = 'info') {

    const container =
        document.getElementById('toast-container');

    const toast =
        document.createElement('div');

    toast.className =
        `toast ${type}`;

    toast.textContent =
        message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}