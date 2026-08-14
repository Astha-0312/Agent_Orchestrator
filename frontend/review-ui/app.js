/*
 * Agent Orchestrator - Review UI
 *
 * Session behavior:
 * - Old tasks from previous sessions are NOT loaded.
 * - Tasks submitted during the current browser session are displayed.
 * - Task status and final answers are polled using the individual task API.
 * - Backend task history is preserved.
 */

const sessionTasks = new Map();


/* =========================================================
   INITIALIZATION
   ========================================================= */

document.addEventListener('DOMContentLoaded', () => {

    // Load pending human approvals.
    loadPendingApprovals();

    // Keep approval information updated.
    setInterval(loadPendingApprovals, 5000);

    // Update only tasks submitted during THIS session.
    setInterval(updateSessionTasks, 2000);


    /* ---------------------------------------------------------
       Task submission form
       --------------------------------------------------------- */

    const taskForm = document.getElementById('task-form');

    if (taskForm) {

        taskForm.addEventListener('submit', async (e) => {

            e.preventDefault();

            const promptInput =
                document.getElementById('task-prompt');

            const prompt =
                promptInput.value.trim();

            if (!prompt) {
                return;
            }


            const submitButton =
                taskForm.querySelector('button');


            try {

                // Prevent multiple clicks while submitting.
                if (submitButton) {
                    submitButton.disabled = true;
                    submitButton.textContent = 'Submitting...';
                }


                const res = await fetch(
                    '/api/v1/tasks',
                    {
                        method: 'POST',

                        headers: {
                            'Content-Type': 'application/json'
                        },

                        body: JSON.stringify({
                            prompt: prompt,
                            user_id: 'default',
                            require_approval: true
                        })
                    }
                );


                if (!res.ok) {

                    showToast(
                        'Failed to submit task',
                        'error'
                    );

                    return;
                }


                const data = await res.json();


                /*
                 * Backend returns:
                 *
                 * {
                 *     "task_id": "...",
                 *     "status": "queued"
                 * }
                 *
                 * Store this task locally in the current
                 * browser session.
                 */

                sessionTasks.set(
                    data.task_id,
                    {
                        task_id: data.task_id,
                        request: prompt,
                        status: data.status || 'queued',
                        final_output: null,
                        error: null
                    }
                );


                // Clear the input box.
                promptInput.value = '';


                // Immediately show the new task.
                renderSessionTasks();


                showToast(
                    'Task submitted successfully',
                    'success'
                );


            } catch (err) {

                console.error(
                    'Error submitting task:',
                    err
                );

                showToast(
                    'Error submitting task',
                    'error'
                );


            } finally {

                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = 'Submit Task';
                }

            }

        });

    }


    /*
     * Show the initial empty state.
     *
     * IMPORTANT:
     * We deliberately DO NOT call loadTasks().
     *
     * This prevents tasks from previous sessions appearing
     * when the website is opened.
     */

    renderSessionTasks();

});


/* =========================================================
   PENDING HUMAN APPROVALS
   ========================================================= */

async function loadPendingApprovals() {

    try {

        const res =
            await fetch('/api/v1/approvals/pending');


        if (!res.ok) {
            return;
        }


        const approvals =
            await res.json();


        renderApprovals(approvals);


    } catch (err) {

        console.error(
            'Error loading approvals:',
            err
        );

    }

}


/* =========================================================
   RENDER APPROVALS
   ========================================================= */

function renderApprovals(approvals) {

    const container =
        document.getElementById(
            'approvals-container'
        );


    if (!container) {
        return;
    }


    if (
        !approvals ||
        approvals.length === 0
    ) {

        container.innerHTML =
            '<p class="empty-state">No pending approvals.</p>';

        return;
    }


    container.innerHTML = '';


    approvals.forEach(app => {

        const severity =
            Number(app.severity || 1);


        const sevClass =
            severity <= 2
                ? 'badge-green'
                : severity === 3
                    ? 'badge-yellow'
                    : 'badge-red';


        const taskId =
            app.task_id || '';


        const card =
            document.createElement('div');


        card.className = 'card';


        card.innerHTML = `

            <div class="card-header">

                <h3 style="font-size:1rem;">
                    Task:
                    ${escapeHtml(
                        taskId.substring(0, 8)
                    )}
                </h3>

                <span class="badge ${sevClass}">
                    Sev ${severity}
                </span>

            </div>


            <div>

                <strong>
                    Reason:
                </strong>

                ${escapeHtml(
                    app.reason || ''
                )}


                <strong
                    style="
                        margin-top:0.5rem;
                        display:block;
                    "
                >
                    Proposed Action:
                </strong>


                <pre
                    style="
                        background:var(--color-slate-100);
                        padding:0.5rem;
                        border-radius:4px;
                        font-size:0.875rem;
                        margin-top:0.25rem;
                    "
                >${escapeHtml(
                    app.proposed_action || ''
                )}</pre>

            </div>


            <div class="card-actions">

                <button
                    class="btn btn-success"
                    onclick="submitDecision(
                        '${escapeJs(taskId)}',
                        {
                            approved: true,
                            action: 'proceed'
                        }
                    )"
                >
                    Approve
                </button>


                <button
                    class="btn btn-danger"
                    onclick="submitDecision(
                        '${escapeJs(taskId)}',
                        {
                            approved: false,
                            action: 'reject'
                        }
                    )"
                >
                    Reject
                </button>


                <button
                    class="btn btn-primary"
                    onclick="showTakeOver(
                        '${escapeJs(taskId)}'
                    )"
                >
                    Take Over
                </button>

            </div>


            <div
                class="takeover-panel"
                id="takeover-${escapeHtml(taskId)}"
            >

                <textarea
                    id="feedback-${escapeHtml(taskId)}"
                    placeholder="Provide instructions or feedback..."
                ></textarea>


                <button
                    class="btn btn-primary"
                    onclick="submitTakeOver(
                        '${escapeJs(taskId)}'
                    )"
                >
                    Submit Feedback
                </button>

            </div>

        `;


        container.appendChild(card);

    });

}


/* =========================================================
   TAKE OVER
   ========================================================= */

function showTakeOver(taskId) {

    const panel =
        document.getElementById(
            `takeover-${taskId}`
        );


    if (panel) {
        panel.classList.toggle('active');
    }

}


/* =========================================================
   SUBMIT TAKE OVER
   ========================================================= */

async function submitTakeOver(taskId) {

    const feedbackElement =
        document.getElementById(
            `feedback-${taskId}`
        );


    const feedback =
        feedbackElement
            ? feedbackElement.value
            : '';


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


/* =========================================================
   SUBMIT APPROVAL DECISION
   ========================================================= */

async function submitDecision(
    taskId,
    decision
) {

    try {

        const res =
            await fetch(
                `/api/v1/approvals/${encodeURIComponent(taskId)}/decide`,
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

        console.error(
            'Error submitting decision:',
            err
        );


        showToast(
            'Error submitting decision',
            'error'
        );

    }

}


/* =========================================================
   UPDATE CURRENT SESSION TASKS
   ========================================================= */

async function updateSessionTasks() {

    /*
     * No tasks submitted during this session.
     * Nothing to update.
     */

    if (sessionTasks.size === 0) {
        return;
    }


    /*
     * Copy the Map entries so that we can safely
     * update individual task objects.
     */

    for (
        const [taskId, task]
        of sessionTasks.entries()
    ) {

        try {

            const res =
                await fetch(
                    `/api/v1/tasks/${encodeURIComponent(taskId)}`
                );


            /*
             * If the task is temporarily unavailable,
             * keep the current UI state and try again
             * during the next polling cycle.
             */

            if (!res.ok) {
                continue;
            }


            const data =
                await res.json();


            /*
             * Update task status.
             */

            task.status =
                data.status || task.status;


            /*
             * The backend returns final_output
             * after the LangGraph workflow completes.
             */

            if (
                data.final_output !== undefined &&
                data.final_output !== null
            ) {

                task.final_output =
                    data.final_output;

            }


            /*
             * Store any backend error.
             */

            if (data.error) {

                task.error =
                    data.error;

            }


            /*
             * In case the backend has the original
             * request, use it.
             */

            if (data.request) {

                task.request =
                    data.request;

            }


        } catch (err) {

            console.error(
                `Error updating task ${taskId}:`,
                err
            );

        }

    }


    /*
     * Re-render only the tasks belonging to this
     * browser session.
     */

    renderSessionTasks();

}


/* =========================================================
   RENDER CURRENT SESSION TASKS
   ========================================================= */

function renderSessionTasks() {

    const container =
        document.getElementById(
            'tasks-container'
        );


    if (!container) {
        return;
    }


    /*
     * Empty session.
     */

    if (sessionTasks.size === 0) {

        container.innerHTML =
            '<p class="empty-state">No tasks submitted in this session.</p>';

        return;
    }


    container.innerHTML = '';


    /*
     * Convert Map to array.
     *
     * Newest tasks are displayed first.
     */

    const tasks =
        Array.from(
            sessionTasks.values()
        ).reverse();


    tasks.forEach(task => {

        let badgeClass =
            'badge-gray';


        if (
            task.status === 'completed'
        ) {

            badgeClass =
                'badge-green';

        } else if (
            task.status === 'running'
        ) {

            badgeClass =
                'badge-blue';

        } else if (
            task.status === 'queued'
        ) {

            badgeClass =
                'badge-yellow';

        } else if (
            task.status === 'failed'
        ) {

            badgeClass =
                'badge-red';

        } else if (
            task.status === 'paused'
        ) {

            badgeClass =
                'badge-yellow';

        }


        const item =
            document.createElement('div');


        item.className =
            'list-item';


        /*
         * Build the result section.
         */

        let resultHTML = '';


        if (
            task.status === 'completed' &&
            task.final_output
        ) {

            resultHTML = `

                <div
                    style="
                        margin-top:15px;
                        padding:15px;
                        background:var(--color-slate-100);
                        border-radius:8px;
                        border-left:4px solid var(--color-blue-500);
                    "
                >

                    <strong
                        style="
                            display:block;
                            margin-bottom:8px;
                        "
                    >
                        Agent Answer
                    </strong>


                    <div
                        style="
                            line-height:1.6;
                            white-space:pre-wrap;
                        "
                    >
                        ${escapeHtml(
                            task.final_output
                        )}
                    </div>

                </div>

            `;


        } else if (
            task.status === 'running' ||
            task.status === 'queued'
        ) {

            resultHTML = `

                <div
                    style="
                        margin-top:10px;
                        color:var(--color-slate-500);
                    "
                >
                    Agent is working...
                </div>

            `;


        } else if (
            task.status === 'failed'
        ) {

            resultHTML = `

                <div
                    style="
                        margin-top:10px;
                        color:#dc2626;
                    "
                >

                    <strong>
                        Task failed
                    </strong>

                    <br>

                    ${escapeHtml(
                        task.error ||
                        'Unknown error'
                    )}

                </div>

            `;

        }


        item.innerHTML = `

            <div style="width:100%;">

                <div
                    style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                        gap:15px;
                    "
                >

                    <div>

                        <strong>
                            ${escapeHtml(
                                task.request ||
                                'Unnamed task'
                            )}
                        </strong>


                        <div
                            style="
                                font-size:0.75rem;
                                color:var(--color-slate-500);
                                margin-top:4px;
                            "
                        >
                            ID:
                            ${escapeHtml(
                                task.task_id
                            )}
                        </div>

                    </div>


                    <span
                        class="badge ${badgeClass}"
                    >
                        ${escapeHtml(
                            task.status
                        )}
                    </span>

                </div>


                ${resultHTML}

            </div>

        `;


        container.appendChild(item);

    });

}


/* =========================================================
   HTML ESCAPING
   ========================================================= */

function escapeHtml(value) {

    if (
        value === null ||
        value === undefined
    ) {

        return '';

    }


    const div =
        document.createElement('div');


    div.textContent =
        String(value);


    return div.innerHTML;

}


/* =========================================================
   JAVASCRIPT STRING ESCAPING
   ========================================================= */

function escapeJs(value) {

    if (
        value === null ||
        value === undefined
    ) {

        return '';

    }


    return String(value)
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/"/g, '\\"')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r');

}


/* =========================================================
   TOAST NOTIFICATIONS
   ========================================================= */

function showToast(
    message,
    type = 'info'
) {

    const container =
        document.getElementById(
            'toast-container'
        );


    if (!container) {
        return;
    }


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