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

    // State
    let ws = null;
    let conversationId = null;
    let isProcessing = false;
    let currentAgentBlock = null;

    // --- WebSocket Connection ---

    function connectWS() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/api/ws/chat`;

        ws = new WebSocket(url);

        ws.onopen = () => {
            setStatus('connected', 'ready');
        };

        ws.onclose = () => {
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
        switch (data.type) {
            case 'meta':
                conversationId = data.conversation_id;
                loadConversations();
                break;
            case 'thought':
                addStep('thought', data.content, data.duration);
                break;
            case 'action':
                addStep('action', `${data.action}(${formatInput(data.action_input)})`, data.duration);
                break;
            case 'observation':
                addStep('observation', data.content, data.duration);
                break;
            case 'final_answer':
                addStep('final', data.content, data.duration);
                setProcessing(false);
                break;
            case 'error':
                addStep('error', data.content, data.duration);
                setProcessing(false);
                break;
            case 'done':
                setProcessing(false);
                removeLoading();
                loadConversations();
                break;
        }
        scrollToBottom();
    }

    // --- UI Rendering ---

    function addUserMessage(text) {
        if (welcome) welcome.style.display = 'none';
        const div = document.createElement('div');
        div.className = 'message message-user';
        div.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
        messages.appendChild(div);
        scrollToBottom();
    }

    function createAgentBlock() {
        const block = document.createElement('div');
        block.className = 'agent-block';
        messages.appendChild(block);
        currentAgentBlock = block;
        return block;
    }

    function addStep(type, content, duration) {
        removeLoading();

        if (!currentAgentBlock) {
            createAgentBlock();
        }

        const step = document.createElement('div');
        step.className = 'step';

        const labelClass = type === 'final' ? 'final' : type;
        const labelText = type === 'final' ? 'answer' : type;
        const durationStr = duration ? `${duration.toFixed(1)}s` : '';

        let contentHtml;
        if (type === 'observation') {
            contentHtml = `<div class="step-content observation-content">${escapeHtml(content)}</div>`;
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

        currentAgentBlock.appendChild(step);
        scrollToBottom();
    }

    function addLoading() {
        if (!currentAgentBlock) createAgentBlock();
        const loading = document.createElement('div');
        loading.className = 'loading';
        loading.id = 'loading-indicator';
        loading.innerHTML = '<span></span><span></span><span></span>';
        currentAgentBlock.appendChild(loading);
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
        if (!processing) {
            currentAgentBlock = null;
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

        addUserMessage(text);
        userInput.value = '';
        autoResize();

        setProcessing(true);
        createAgentBlock();
        addLoading();

        ws.send(JSON.stringify({
            message: text,
            conversation_id: conversationId,
        }));
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
        try {
            const resp = await fetch(`/api/conversations/${convId}`);
            const data = await resp.json();

            conversationId = convId;
            messages.innerHTML = '';
            if (welcome) welcome.style.display = 'none';

            // Render conversation messages
            if (data.messages) {
                data.messages.forEach(msg => {
                    if (msg.role === 'user') {
                        addUserMessage(msg.content);
                    } else if (msg.role === 'agent') {
                        currentAgentBlock = null;
                        createAgentBlock();
                        if (msg.steps) {
                            msg.steps.forEach(step => {
                                addStep(step.type, step.content, step.duration || 0);
                            });
                        } else {
                            addStep('final', msg.content, 0);
                        }
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

    function startNewChat() {
        conversationId = null;
        messages.innerHTML = '';
        if (welcome) welcome.style.display = 'block';
        currentAgentBlock = null;
        document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
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

    // --- Health Check ---

    async function checkHealth() {
        try {
            const resp = await fetch('/api/health');
            const data = await resp.json();
            if (data.llm_connected) {
                setStatus('connected', 'ready');
            } else {
                setStatus('error', 'llm offline');
            }
        } catch {
            setStatus('error', 'backend offline');
        }
    }

    // --- Init ---

    connectWS();
    checkHealth();
    loadConversations();
    setInterval(checkHealth, 10000);

})();
