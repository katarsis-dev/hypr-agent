/**
 * hypr-agent — Frontend logic
 * Handles WebSocket chat, streaming agent steps, settings, conversation history.
 */

(function () {
    'use strict';

    // DOM Elements
    const chatArea = document.getElementById('chat-area');
    const messages = document.getElementById('messages');
    const welcome = document.getElementById('welcome');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsPanel = document.getElementById('settings-panel');
    const closeSettingsBtn = document.getElementById('close-settings');
    const saveSettingsBtn = document.getElementById('save-settings');
    const modelSelect = document.getElementById('model-select');
    const tempSlider = document.getElementById('temperature');
    const tempValue = document.getElementById('temp-value');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebarOpen = document.getElementById('sidebar-open');
    const newChatBtn = document.getElementById('new-chat-btn');
    const conversationList = document.getElementById('conversation-list');
    const attachBtn = document.getElementById('attach-btn');
    const fileInput = document.getElementById('file-input');
    const attachmentPreview = document.getElementById('attachment-preview');

    // State
    let ws = null;
    let conversationId = null;
    let isProcessing = false;
    let currentAgentBlock = null;
    let streamingThinkingEl = null;   // element receiving streaming tokens
    let streamingRawText = '';        // accumulated raw text from thinking_delta
    let taskStartTime = null;
    let activeStreamConvId = null;    // conversation ID of in-flight WS stream
    let pendingAttachments = [];       // files uploaded and ready to send

    // --- WebSocket Connection ---

    function connectWS() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/api/ws/chat`;

        ws = new WebSocket(url);

        ws.onopen = () => {
            setStatus('connected', 'ready');
        };

        ws.onclose = (event) => {
            // Code 1000 = normal close (e.g., conversation switch) — don't auto-reconnect
            if (event.code === 1000) return;
            setStatus('error', 'disconnected');
            setTimeout(connectWS, 3000);
        };

        ws.onerror = () => {
            setStatus('error', 'connection error');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleWSMessage(data);
        };
    }

    function handleWSMessage(data) {
        // Ignore stale events from a previous conversation
        if (activeStreamConvId && data.type !== 'meta' && data.type !== 'done'
            && conversationId !== activeStreamConvId) {
            return;
        }

        switch (data.type) {
            case 'meta':
                activeStreamConvId = data.conversation_id;
                conversationId = data.conversation_id;
                loadConversations();
                break;

            case 'status':
                updateAgentStatus(data.content, data.step, data.max_steps);
                break;

            case 'thinking_delta':
                appendThinkingToken(data.content);
                break;

            case 'thought':
                finalizeThinking(data.content, data.duration);
                break;

            case 'action_start':
                addActionStart(data.action, data.action_input);
                break;

            case 'observation':
                addObservation(data.content, data.action, data.duration);
                break;

            case 'final_answer':
                addFinalAnswer(data.content, data.duration, data.total_duration);
                setProcessing(false);
                break;

            case 'error':
                addError(data.content, data.duration);
                setProcessing(false);
                break;

            case 'done':
                setProcessing(false);
                removeStatusBar();
                loadConversations();
                break;
        }
        scrollToBottom();
    }

    // --- Streaming Progress Rendering ---

    function ensureAgentBlock() {
        if (!currentAgentBlock) {
            const block = document.createElement('div');
            block.className = 'agent-block';
            messages.appendChild(block);
            currentAgentBlock = block;
        }
        return currentAgentBlock;
    }

    function updateAgentStatus(content, step, maxSteps) {
        removeLoading();
        const block = ensureAgentBlock();

        let bar = block.querySelector('.agent-status-bar');
        if (!bar) {
            bar = document.createElement('div');
            bar.className = 'agent-status-bar';
            block.appendChild(bar);
        }

        const elapsed = taskStartTime ? ((Date.now() - taskStartTime) / 1000).toFixed(1) : '0.0';
        const stepInfo = step && maxSteps ? `step ${step}/${maxSteps}` : '';

        bar.innerHTML = `
            <span class="status-spinner"></span>
            <span class="status-msg">${escapeHtml(content)}</span>
            <span class="status-meta">${stepInfo} &middot; ${elapsed}s</span>
        `;
        scrollToBottom();
    }

    function removeStatusBar() {
        if (currentAgentBlock) {
            const bar = currentAgentBlock.querySelector('.agent-status-bar');
            if (bar) bar.remove();
        }
    }

    function appendThinkingToken(token) {
        removeLoading();
        const block = ensureAgentBlock();

        if (!streamingThinkingEl) {
            // Create a new streaming thinking step
            const step = document.createElement('div');
            step.className = 'step step-streaming';

            step.innerHTML = `
                <div class="step-header">
                    <span class="step-label thinking">generating</span>
                    <span class="step-duration" data-start="${Date.now()}"></span>
                </div>
                <div class="step-content thinking-stream"></div>
            `;

            // Insert before status bar if present
            const statusBar = block.querySelector('.agent-status-bar');
            if (statusBar) {
                block.insertBefore(step, statusBar);
            } else {
                block.appendChild(step);
            }

            streamingThinkingEl = step.querySelector('.thinking-stream');
            streamingRawText = '';
        }

        streamingRawText += token;
        streamingThinkingEl.textContent = streamingRawText;

        // Update live timer
        const stepEl = streamingThinkingEl.closest('.step');
        const durEl = stepEl ? stepEl.querySelector('.step-duration') : null;
        if (durEl) {
            const startMs = parseInt(durEl.dataset.start, 10);
            durEl.textContent = ((Date.now() - startMs) / 1000).toFixed(1) + 's';
        }

        scrollToBottom();
    }

    function finalizeThinking(content, duration) {
        // Replace streaming block with final parsed thought
        if (streamingThinkingEl) {
            const stepEl = streamingThinkingEl.closest('.step');
            if (stepEl) {
                stepEl.classList.remove('step-streaming');
                const label = stepEl.querySelector('.step-label');
                if (label) {
                    label.textContent = 'thought';
                    label.className = 'step-label thought';
                }
                const durEl = stepEl.querySelector('.step-duration');
                if (durEl) {
                    durEl.textContent = duration ? duration.toFixed(1) + 's' : '';
                    delete durEl.dataset.start;
                }
                streamingThinkingEl.textContent = content;
            }
            streamingThinkingEl = null;
            streamingRawText = '';
        } else {
            // No streaming happened (fallback)
            addStep('thought', content, duration);
        }
        // Remove the status bar since we're moving to the next phase
        removeStatusBar();
    }

    function addActionStart(action, actionInput) {
        removeStatusBar();
        const block = ensureAgentBlock();

        const step = document.createElement('div');
        step.className = 'step step-running';
        step.dataset.action = action;

        const inputStr = formatInput(actionInput);
        const inputPreview = inputStr.length > 120 ? inputStr.slice(0, 120) + '...' : inputStr;

        step.innerHTML = `
            <div class="step-header">
                <span class="step-label action">
                    <span class="status-spinner small"></span>
                    ${escapeHtml(action)}
                </span>
                <span class="step-duration" data-start="${Date.now()}">running...</span>
            </div>
            <div class="step-content action-input">${escapeHtml(inputPreview)}</div>
        `;

        block.appendChild(step);
        scrollToBottom();
    }

    function addObservation(content, action, duration) {
        const block = ensureAgentBlock();

        // Find the running action step and finalize it
        const runningStep = block.querySelector('.step-running');
        if (runningStep) {
            runningStep.classList.remove('step-running');
            const durEl = runningStep.querySelector('.step-duration');
            if (durEl) {
                durEl.textContent = duration ? duration.toFixed(1) + 's' : '';
                delete durEl.dataset.start;
            }
            const label = runningStep.querySelector('.step-label');
            if (label) {
                label.innerHTML = escapeHtml(action || 'action');
            }
        }

        // Add observation below it
        const step = document.createElement('div');
        step.className = 'step';

        const truncated = content.length > 800 ? content.slice(0, 800) + '\n...[truncated]' : content;

        step.innerHTML = `
            <div class="step-header">
                <span class="step-label observation">result</span>
                <span class="step-duration">${duration ? duration.toFixed(1) + 's' : ''}</span>
            </div>
            <div class="step-content observation-content">${escapeHtml(truncated)}</div>
        `;

        block.appendChild(step);
        scrollToBottom();
    }

    function addFinalAnswer(content, duration, totalDuration) {
        removeStatusBar();
        const block = ensureAgentBlock();

        // Remove any lingering streaming block
        if (streamingThinkingEl) {
            const stepEl = streamingThinkingEl.closest('.step');
            if (stepEl) stepEl.remove();
            streamingThinkingEl = null;
            streamingRawText = '';
        }

        const step = document.createElement('div');
        step.className = 'step step-final';

        const totalStr = totalDuration ? ` &middot; total ${totalDuration.toFixed(1)}s` : '';

        step.innerHTML = `
            <div class="step-header">
                <span class="step-label final">answer</span>
                <span class="step-duration">${duration ? duration.toFixed(1) + 's' : ''}${totalStr}</span>
            </div>
            <div class="step-content markdown-body">${renderMarkdown(content)}</div>
        `;

        block.appendChild(step);
        scrollToBottom();
    }

    function addError(content, duration) {
        removeStatusBar();
        const block = ensureAgentBlock();

        if (streamingThinkingEl) {
            const stepEl = streamingThinkingEl.closest('.step');
            if (stepEl) stepEl.remove();
            streamingThinkingEl = null;
            streamingRawText = '';
        }

        const step = document.createElement('div');
        step.className = 'step';
        step.innerHTML = `
            <div class="step-header">
                <span class="step-label error">error</span>
                <span class="step-duration">${duration ? duration.toFixed(1) + 's' : ''}</span>
            </div>
            <div class="step-content">${escapeHtml(content)}</div>
        `;

        block.appendChild(step);
        scrollToBottom();
    }

    // Legacy addStep for loading conversations from history
    function addStep(type, content, duration) {
        removeLoading();
        const block = ensureAgentBlock();

        const step = document.createElement('div');
        step.className = 'step';

        const labelClass = type === 'final' ? 'final' : type;
        const labelText = type === 'final' ? 'answer' : type;
        const durationStr = duration ? `${duration.toFixed(1)}s` : '';

        let contentHtml;
        if (type === 'observation') {
            contentHtml = `<div class="step-content observation-content">${escapeHtml(content)}</div>`;
        } else if (type === 'final') {
            contentHtml = `<div class="step-content markdown-body">${renderMarkdown(content)}</div>`;
        } else {
            contentHtml = `<div class="step-content">${escapeHtml(content)}</div>`;
        }

        step.innerHTML = `
            <div class="step-header">
                <span class="step-label ${labelClass}">${labelText}</span>
                <span class="step-duration">${durationStr}</span>
            </div>
            ${contentHtml}
        `;

        block.appendChild(step);
        scrollToBottom();
    }

    // --- UI Helpers ---

    function addUserMessage(text, attachments) {
        if (welcome) welcome.style.display = 'none';
        const div = document.createElement('div');
        div.className = 'message message-user';

        let attachHtml = '';
        if (attachments && attachments.length > 0) {
            const chips = attachments.map(att => {
                const sizeStr = formatFileSize(att.size);
                return `<span class="msg-attachment">${getFileIcon(att.filename)} ${escapeHtml(att.filename)} <span class="attachment-size">${sizeStr}</span></span>`;
            }).join('');
            attachHtml = `<div class="msg-attachments">${chips}</div>`;
        }

        div.innerHTML = `<div class="bubble">${escapeHtml(text)}${attachHtml}</div>`;
        messages.appendChild(div);
        scrollToBottom();
    }

    function addLoading() {
        const block = ensureAgentBlock();
        const loading = document.createElement('div');
        loading.className = 'loading';
        loading.id = 'loading-indicator';
        loading.innerHTML = '<span></span><span></span><span></span>';
        block.appendChild(loading);
        scrollToBottom();
    }

    function removeLoading() {
        const el = document.getElementById('loading-indicator');
        if (el) el.remove();
    }

    function setStatus(state, text) {
        statusDot.className = `status-indicator ${state}`;
        statusText.textContent = text;
    }

    function setProcessing(processing) {
        isProcessing = processing;
        sendBtn.disabled = processing;
        if (processing) {
            setStatus('processing', 'processing');
        } else {
            setStatus('connected', 'ready');
            currentAgentBlock = null;
            streamingThinkingEl = null;
            streamingRawText = '';
            taskStartTime = null;
        }
    }

    function scrollToBottom() {
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function renderMarkdown(text) {
        if (typeof marked !== 'undefined') {
            try {
                return marked.parse(text, { breaks: true });
            } catch {
                return escapeHtml(text);
            }
        }
        return escapeHtml(text);
    }

    function formatInput(input) {
        if (input === null || input === undefined) return '';
        if (typeof input === 'object') {
            return JSON.stringify(input);
        }
        return String(input);
    }

    // --- Send Message ---

    function sendMessage() {
        const text = userInput.value.trim();
        if (!text || isProcessing) return;
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            setStatus('error', 'not connected');
            return;
        }

        addUserMessage(text, pendingAttachments);
        userInput.value = '';
        autoResize();

        setProcessing(true);
        taskStartTime = Date.now();
        currentAgentBlock = null;
        ensureAgentBlock();
        addLoading();

        const payload = {
            message: text,
            conversation_id: conversationId,
        };
        if (pendingAttachments.length > 0) {
            payload.attachments = pendingAttachments;
        }

        ws.send(JSON.stringify(payload));
        clearAttachments();
    }

    // --- File Attachments ---

    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const resp = await fetch('/api/upload', { method: 'POST', body: formData });
            if (!resp.ok) throw new Error('Upload failed');
            return await resp.json();
        } catch (e) {
            console.error('Upload error:', e);
            return null;
        }
    }

    async function handleFileSelect(files) {
        for (const file of files) {
            const result = await uploadFile(file);
            if (result) {
                pendingAttachments.push(result);
            }
        }
        renderAttachmentPreview();
    }

    function renderAttachmentPreview() {
        if (pendingAttachments.length === 0) {
            attachmentPreview.classList.add('hidden');
            attachmentPreview.innerHTML = '';
            return;
        }

        attachmentPreview.classList.remove('hidden');
        attachmentPreview.innerHTML = pendingAttachments.map((att, i) => {
            const sizeStr = formatFileSize(att.size);
            return `<div class="attachment-chip">
                <span class="attachment-icon">${getFileIcon(att.filename)}</span>
                <span class="attachment-name">${escapeHtml(att.filename)}</span>
                <span class="attachment-size">${sizeStr}</span>
                <button class="attachment-remove" data-index="${i}" title="Remove">&times;</button>
            </div>`;
        }).join('');

        // Bind remove buttons
        attachmentPreview.querySelectorAll('.attachment-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.target.dataset.index, 10);
                pendingAttachments.splice(idx, 1);
                renderAttachmentPreview();
            });
        });
    }

    function clearAttachments() {
        pendingAttachments = [];
        renderAttachmentPreview();
        fileInput.value = '';
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function getFileIcon(filename) {
        const ext = (filename || '').split('.').pop().toLowerCase();
        const icons = {
            pdf: '\uD83D\uDCC4', doc: '\uD83D\uDCC4', docx: '\uD83D\uDCC4',
            txt: '\uD83D\uDCDD', md: '\uD83D\uDCDD', log: '\uD83D\uDCDD',
            py: '\uD83D\uDC0D', js: '\uD83D\uDCDC', ts: '\uD83D\uDCDC',
            json: '\u007B\u007D', yaml: '\u2699', yml: '\u2699',
            png: '\uD83D\uDDBC', jpg: '\uD83D\uDDBC', jpeg: '\uD83D\uDDBC',
            gif: '\uD83D\uDDBC', svg: '\uD83D\uDDBC',
            zip: '\uD83D\uDCE6', tar: '\uD83D\uDCE6', gz: '\uD83D\uDCE6',
            csv: '\uD83D\uDCCA', xls: '\uD83D\uDCCA', xlsx: '\uD83D\uDCCA',
        };
        return icons[ext] || '\uD83D\uDCCE';
    }

    // --- Conversation History ---

    async function loadConversations() {
        try {
            const resp = await fetch('/api/conversations');
            const data = await resp.json();
            renderConversationList(data.conversations);
        } catch (e) {
            console.error('Failed to load conversations:', e);
        }
    }

    function renderConversationList(conversations) {
        conversationList.innerHTML = '';
        if (!conversations || conversations.length === 0) {
            conversationList.innerHTML = '<div class="conv-empty">No conversations yet</div>';
            return;
        }

        conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = 'conv-item' + (conv.id === conversationId ? ' active' : '');

            const title = conv.first_message || 'New conversation';
            const date = conv.updated_at ? formatDate(conv.updated_at) : '';

            item.innerHTML = `
                <div class="conv-item-title">${escapeHtml(title)}</div>
                <div class="conv-item-date">${date}</div>
            `;

            item.addEventListener('click', () => {
                loadConversation(conv.id);
            });

            conversationList.appendChild(item);
        });
    }

    async function loadConversation(convId) {
        // If processing, abort by reconnecting WebSocket
        if (isProcessing) {
            setProcessing(false);
            if (ws) {
                ws.close();
            }
            connectWS();
        }

        try {
            const resp = await fetch(`/api/conversations/${convId}`);
            const data = await resp.json();

            conversationId = convId;
            activeStreamConvId = null;
            messages.innerHTML = '';
            currentAgentBlock = null;
            if (welcome) welcome.style.display = 'none';

            // Render conversation messages
            if (data.messages) {
                data.messages.forEach(msg => {
                    if (msg.role === 'user') {
                        addUserMessage(msg.content);
                    } else if (msg.role === 'agent') {
                        currentAgentBlock = null;
                        ensureAgentBlock();
                        renderSavedAgentMessage(msg);
                    }
                });
                currentAgentBlock = null;
            }

            // Update active state in sidebar
            document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
            loadConversations();
            scrollToBottom();
        } catch (e) {
            console.error('Failed to load conversation:', e);
        }
    }

    function renderSavedAgentMessage(msg) {
        // Agent messages from memory have: thought, action, action_input, observation, final_answer
        if (msg.thought) {
            addStep('thought', msg.thought, 0);
        }
        if (msg.action) {
            const inputStr = msg.action_input || '';
            addStep('action', `${msg.action}(${inputStr})`, 0);
        }
        if (msg.observation) {
            addStep('observation', msg.observation, 0);
        }
        if (msg.final_answer) {
            addStep('final', msg.final_answer, 0);
        }
        // Fallback: if none of the above, show raw content if present
        if (!msg.thought && !msg.action && !msg.final_answer && msg.content) {
            addStep('final', msg.content, 0);
        }
    }

    function startNewChat() {
        // Abort in-flight request if any
        if (isProcessing) {
            setProcessing(false);
            if (ws) {
                ws.close();
            }
            connectWS();
        }

        conversationId = null;
        activeStreamConvId = null;
        messages.innerHTML = '';
        if (welcome) welcome.style.display = 'block';
        currentAgentBlock = null;
        document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
    }

    // --- Export Conversation ---

    async function exportConversation() {
        if (!conversationId) {
            alert('No conversation to export.');
            return;
        }

        try {
            const resp = await fetch(`/api/conversations/${conversationId}`);
            const data = await resp.json();

            let md = `# Conversation\n\n`;
            if (data.messages) {
                data.messages.forEach(msg => {
                    if (msg.role === 'user') {
                        md += `## User\n\n${msg.content}\n\n`;
                    } else if (msg.role === 'agent') {
                        md += `## Agent\n\n`;
                        if (msg.thought) md += `**Thought:** ${msg.thought}\n\n`;
                        if (msg.action) md += `**Action:** \`${msg.action}(${msg.action_input || ''})\`\n\n`;
                        if (msg.observation) md += `**Result:**\n\`\`\`\n${msg.observation}\n\`\`\`\n\n`;
                        if (msg.final_answer) md += `${msg.final_answer}\n\n`;
                        if (!msg.thought && !msg.action && !msg.final_answer && msg.content) {
                            md += `${msg.content}\n\n`;
                        }
                        md += `---\n\n`;
                    }
                });
            }

            const blob = new Blob([md], { type: 'text/markdown' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `hypr-agent-${conversationId.slice(0, 8)}.md`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error('Export failed:', e);
            alert('Failed to export conversation.');
        }
    }

    function formatDate(isoStr) {
        try {
            const d = new Date(isoStr);
            const now = new Date();
            const diffMs = now - d;
            const diffMins = Math.floor(diffMs / 60000);

            if (diffMins < 1) return 'just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            const diffHrs = Math.floor(diffMins / 60);
            if (diffHrs < 24) return `${diffHrs}h ago`;
            const diffDays = Math.floor(diffHrs / 24);
            if (diffDays < 7) return `${diffDays}d ago`;
            return d.toLocaleDateString();
        } catch {
            return '';
        }
    }

    // --- Sidebar Toggle ---

    function toggleSidebar() {
        sidebar.classList.toggle('collapsed');
    }

    // --- Settings Tabs ---

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
            if (btn.dataset.tab === 'profile') loadProfile();
        });
    });

    // --- Profile ---

    async function loadProfile() {
        try {
            const resp = await fetch('/api/profile');
            const data = await resp.json();
            document.getElementById('profile-editor').value = data.content || '';
            document.getElementById('profile-path-display').textContent = data.path || '';
            document.getElementById('profile-status').textContent = '';
        } catch (e) {
            console.error('Failed to load profile:', e);
        }
    }

    async function saveProfile() {
        const content = document.getElementById('profile-editor').value;
        try {
            const resp = await fetch('/api/profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content }),
            });
            const data = await resp.json();
            document.getElementById('profile-status').textContent = 'Saved!';
            setTimeout(() => {
                document.getElementById('profile-status').textContent = '';
            }, 3000);
        } catch (e) {
            document.getElementById('profile-status').textContent = 'Error saving';
            console.error('Failed to save profile:', e);
        }
    }

    document.getElementById('save-profile').addEventListener('click', saveProfile);

    // --- Settings ---

    async function loadModels() {
        try {
            const resp = await fetch('/api/models');
            const data = await resp.json();
            modelSelect.innerHTML = '';
            data.models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.filename;
                opt.textContent = `${m.filename} (${m.size_mb} MB)`;
                if (m.filename === data.current_model) opt.selected = true;
                modelSelect.appendChild(opt);
            });
        } catch (e) {
            console.error('Failed to load models:', e);
        }
    }

    async function saveSettings() {
        const payload = {
            model: modelSelect.value || null,
            temperature: parseFloat(tempSlider.value),
            ctx_size: parseInt(document.getElementById('ctx-size').value),
            threads: parseInt(document.getElementById('threads').value),
        };

        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            settingsPanel.classList.add('hidden');
        } catch (e) {
            console.error('Failed to save settings:', e);
        }
    }

    // --- Auto-resize textarea ---

    function autoResize() {
        userInput.style.height = 'auto';
        userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
    }

    // --- Event Listeners ---

    sendBtn.addEventListener('click', sendMessage);

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    userInput.addEventListener('input', autoResize);

    settingsBtn.addEventListener('click', () => {
        settingsPanel.classList.toggle('hidden');
        if (!settingsPanel.classList.contains('hidden')) {
            loadModels();
        }
    });

    closeSettingsBtn.addEventListener('click', () => {
        settingsPanel.classList.add('hidden');
    });

    saveSettingsBtn.addEventListener('click', saveSettings);

    tempSlider.addEventListener('input', () => {
        tempValue.textContent = tempSlider.value;
    });

    sidebarToggle.addEventListener('click', toggleSidebar);
    sidebarOpen.addEventListener('click', () => {
        sidebar.classList.remove('collapsed');
        sidebar.classList.toggle('open');
    });
    newChatBtn.addEventListener('click', startNewChat);
    document.getElementById('export-btn').addEventListener('click', exportConversation);

    // Attach file button
    attachBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileSelect(fileInput.files);
        }
    });

    // Drag and drop on input area
    const inputArea = document.getElementById('input-area');
    inputArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        inputArea.classList.add('drag-over');
    });
    inputArea.addEventListener('dragleave', () => {
        inputArea.classList.remove('drag-over');
    });
    inputArea.addEventListener('drop', (e) => {
        e.preventDefault();
        inputArea.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files);
        }
    });

    // --- Health Check ---

    async function checkHealth() {
        try {
            const resp = await fetch('/api/health');
            const data = await resp.json();
            if (!isProcessing) {
                if (data.llm_connected) {
                    setStatus('connected', 'ready');
                } else {
                    setStatus('error', 'llm offline');
                }
            }
        } catch {
            if (!isProcessing) {
                setStatus('error', 'backend offline');
            }
        }
    }

    // --- Init ---

    connectWS();
    checkHealth();
    loadConversations();
    setInterval(checkHealth, 10000);

})();
