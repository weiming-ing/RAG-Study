const API_BASE = '/api';

const state = {
    authToken: localStorage.getItem('auth_token') || '',
    currentUser: null,
    loginMode: 'login',
    currentSessionId: null,
    sessions: [],
    isGenerating: false,
    currentAssistantMsg: null,
    kbPanelOpen: false,
    autoRefreshInterval: null,
    abortController: null,
    agentMode: false,
};

const els = {
    loginOverlay: document.getElementById('login-overlay'),
    loginTitle: document.getElementById('login-title'),
    loginForm: document.getElementById('login-form'),
    loginUsername: document.getElementById('login-username'),
    loginPassword: document.getElementById('login-password'),
    registerFields: document.getElementById('register-fields'),
    registerDisplayName: document.getElementById('register-display-name'),
    loginError: document.getElementById('login-error'),
    btnLoginSubmit: document.getElementById('btn-login-submit'),
    btnToggleMode: document.getElementById('btn-toggle-mode'),
    btnGuestMode: document.getElementById('btn-guest-mode'),
    loginToggleText: document.getElementById('login-toggle-text'),
    appContainer: document.getElementById('app-container'),
    userInfo: document.getElementById('user-info'),
    btnLogout: document.getElementById('btn-logout'),
    btnGuestLogin: document.getElementById('btn-guest-login'),
    sessionList: document.getElementById('session-list'),
    chatMessages: document.getElementById('chat-messages'),
    chatInput: document.getElementById('chat-input'),
    btnSend: document.getElementById('btn-send'),
    btnStop: document.getElementById('btn-stop'),
    btnNewSession: document.getElementById('btn-new-session'),
    btnToggleSidebar: document.getElementById('btn-toggle-sidebar'),
    btnToggleKb: document.getElementById('btn-toggle-kb'),
    btnCloseKb: document.getElementById('btn-close-kb'),
    kbPanel: document.getElementById('kb-panel'),
    kbModules: document.getElementById('kb-modules'),
    statusIndicator: document.getElementById('status-indicator'),
    sidebar: document.getElementById('sidebar'),
    inputHint: document.querySelector('.input-hint'),
    kbSearchInput: document.getElementById('kb-search-input'),
    btnKbSearch: document.getElementById('btn-kb-search'),
    btnAgentToggle: document.getElementById('btn-agent-toggle'),
    agentBadge: document.getElementById('agent-badge'),
    chunkModal: document.getElementById('chunk-modal'),
    chunkModalTitle: document.getElementById('chunk-modal-title'),
    chunkModalBody: document.getElementById('chunk-modal-body'),
    btnCloseChunkModal: document.getElementById('btn-close-chunk-modal'),
    statDocs: document.getElementById('stat-docs'),
    statChunks: document.getElementById('stat-chunks'),
    statSize: document.getElementById('stat-size'),
    kbAutoRefresh: document.getElementById('kb-auto-refresh'),
    toastContainer: document.getElementById('toast-container'),
};

async function apiFetch(url, options = {}) {
    const headers = options.headers || {};
    if (state.authToken) {
        headers['Authorization'] = 'Bearer ' + state.authToken;
    }
    return fetch(url, { ...options, headers });
}

async function init() {
    if (state.authToken) {
        await verifyAndEnter();
    }
    bindLoginEvents();
    bindAppEvents();
}

function bindLoginEvents() {
    els.btnLoginSubmit.addEventListener('click', handleLoginSubmit);
    els.btnToggleMode.addEventListener('click', toggleLoginMode);
    els.btnGuestMode.addEventListener('click', showGuestMode);
    els.btnGuestLogin.addEventListener('click', () => {
        els.loginOverlay.style.display = 'flex';
    });
    els.loginPassword.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') handleLoginSubmit();
    });
    els.loginUsername.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') els.loginPassword.focus();
    });
    els.btnLogout.addEventListener('click', handleLogout);
}

function toggleLoginMode() {
    if (state.loginMode === 'login') {
        state.loginMode = 'register';
        els.loginTitle.textContent = '创建账号';
        els.btnLoginSubmit.querySelector('.btn-login-text').textContent = '注 册';
        els.loginToggleText.textContent = '已有账号？';
        els.btnToggleMode.textContent = '立即登录';
        els.registerFields.style.display = 'block';
    } else {
        state.loginMode = 'login';
        els.loginTitle.textContent = '账号密码登录';
        els.btnLoginSubmit.querySelector('.btn-login-text').textContent = '登 录';
        els.loginToggleText.textContent = '还没有账号？';
        els.btnToggleMode.textContent = '立即注册';
        els.registerFields.style.display = 'none';
    }
    els.loginError.style.display = 'none';
}

async function handleLoginSubmit() {
    const username = els.loginUsername.value.trim();
    const password = els.loginPassword.value.trim();
    if (!username || !password) {
        showLoginError('请输入用户名和密码');
        return;
    }

    els.btnLoginSubmit.disabled = true;
    els.btnLoginSubmit.querySelector('.btn-login-text').style.display = 'none';
    els.btnLoginSubmit.querySelector('.btn-login-loader').style.display = 'inline';
    els.loginError.style.display = 'none';

    try {
        let url, body;
        if (state.loginMode === 'register') {
            url = `${API_BASE}/auth/register`;
            body = JSON.stringify({ username, password, display_name: els.registerDisplayName.value.trim() || username });
        } else {
            url = `${API_BASE}/auth/login`;
            body = JSON.stringify({ username, password });
        }

        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body,
        });
        const data = await resp.json();

        if (data.success) {
            if (state.loginMode === 'register') {
                toast('注册成功，请登录', 'success');
                toggleLoginMode();
                els.loginUsername.value = username;
                els.loginPassword.value = '';
                els.loginPassword.focus();
            } else {
                state.authToken = data.data.access_token;
                state.currentUser = { username: data.data.username, display_name: data.data.display_name };
                localStorage.setItem('auth_token', state.authToken);
                toast('登录成功', 'success');
                showApp();
                await loadSessions();
                await checkHealth();
            }
        } else {
            showLoginError(data.error || '操作失败');
        }
    } catch (e) {
        showLoginError('网络错误: ' + e.message);
    } finally {
        els.btnLoginSubmit.disabled = false;
        els.btnLoginSubmit.querySelector('.btn-login-text').style.display = '';
        els.btnLoginSubmit.querySelector('.btn-login-loader').style.display = 'none';
    }
}

async function verifyAndEnter() {
    try {
        const resp = await apiFetch(`${API_BASE}/auth/me`);
        const data = await resp.json();
        if (data.success) {
            state.currentUser = { username: data.data.username, display_name: data.data.display_name };
            showApp();
            await loadSessions();
            await checkHealth();
            return;
        }
    } catch (e) {}
    state.authToken = '';
    localStorage.removeItem('auth_token');
}

function showApp() {
    els.loginOverlay.style.display = 'none';
    els.appContainer.style.display = 'flex';
    els.sidebar.style.display = '';
    els.chatInput.disabled = true;
    els.btnSend.disabled = true;
    els.btnSend.style.display = 'none';
    els.btnStop.style.display = 'none';
    els.btnGuestLogin.style.display = 'none';
    els.inputHint.textContent = '正在初始化会话...';
    if (state.currentUser) {
        els.userInfo.textContent = state.currentUser.display_name || state.currentUser.username;
        els.userInfo.style.display = '';
        els.btnLogout.style.display = '';
    }
}

function showWelcomeMessage(html) {
    const div = document.createElement('div');
    div.className = 'welcome-message';
    div.id = 'welcome-message';
    div.innerHTML = html;
    els.chatMessages.appendChild(div);
}

function showGuestMode() {
    els.loginOverlay.style.display = 'none';
    els.appContainer.style.display = 'flex';
    els.sidebar.style.display = 'none';
    els.userInfo.style.display = 'none';
    els.btnLogout.style.display = 'none';
    els.chatInput.disabled = false;
    els.btnSend.disabled = false;
    els.btnSend.style.display = '';
    els.btnStop.style.display = 'none';
    els.btnGuestLogin.style.display = '';
    showWelcomeMessage('未登录状态下仅支持闲聊，会话内容不会保存。<br><a href="javascript:void(0)" onclick="document.getElementById(\'login-overlay\').style.display=\'flex\'">登录后</a>解锁完整功能');
}

function showLoginError(msg) {
    els.loginError.textContent = msg;
    els.loginError.style.display = 'block';
}

function handleLogout() {
    state.authToken = '';
    state.currentUser = null;
    localStorage.removeItem('auth_token');
    els.chatMessages.innerHTML = '';
    els.appContainer.style.display = 'none';
    els.loginOverlay.style.display = 'flex';
    els.loginUsername.value = '';
    els.loginPassword.value = '';
    els.loginError.style.display = 'none';
    state.currentSessionId = null;
    state.sessions = [];
    state.loginMode = 'login';
    els.loginTitle.textContent = '账号密码登录';
    els.btnLoginSubmit.querySelector('.btn-login-text').textContent = '登 录';
    els.loginToggleText.textContent = '还没有账号？';
    els.btnToggleMode.textContent = '立即注册';
    els.registerFields.style.display = 'none';
}

function bindAppEvents() {
    els.btnNewSession.addEventListener('click', createSession);
    els.btnSend.addEventListener('click', sendMessage);
    els.btnStop.addEventListener('click', stopGeneration);
    els.btnAgentToggle.addEventListener('click', toggleAgentMode);
    els.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    els.chatInput.addEventListener('input', autoResizeInput);
    els.btnToggleSidebar.addEventListener('click', () => els.sidebar.classList.toggle('open'));
    els.btnToggleKb.addEventListener('click', toggleKbPanel);
    els.btnCloseKb.addEventListener('click', toggleKbPanel);
    els.btnKbSearch.addEventListener('click', searchKnowledgeBase);
    els.kbSearchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            searchKnowledgeBase();
        }
    });
    els.btnCloseChunkModal.addEventListener('click', closeChunkModal);
    els.chunkModal.addEventListener('click', function (e) {
        if (e.target === els.chunkModal) closeChunkModal();
    });
    els.chunkModalBody.addEventListener('click', function (e) {
        var closeBtn = e.target.closest('.modal-close-btn');
        if (closeBtn) closeChunkModal();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            if (els.chunkModal.style.display === 'flex') {
                closeChunkModal();
            }
        }
    });

    els.kbModules.addEventListener('click', (e) => {
        if (e.target.closest('.kb-search-back')) {
            renderBrowse(state.kbModulesData || []);
            return;
        }
        const folder = e.target.closest('.kb-tree-folder');
        if (folder) {
            const node = folder.closest('.kb-tree-node');
            const children = node.querySelector('.kb-tree-children');
            const caret = folder.querySelector('.kb-tree-caret');
            const collapsed = children.style.display === 'none';
            children.style.display = collapsed ? '' : 'none';
            caret.textContent = collapsed ? '▾' : '▸';
            return;
        }
        const item = e.target.closest('.kb-tree-doc');
        if (!item) return;
        if (e.target.closest('.doc-preview-btn')) {
            previewDocument(item.dataset.kbId, item.dataset.docId, item.dataset.docFilename);
        }
    });
}

async function toggleKbPanel() {
    state.kbPanelOpen = !state.kbPanelOpen;
    els.kbPanel.style.display = state.kbPanelOpen ? 'flex' : 'none';
    if (state.kbPanelOpen) {
        await loadBrowse();
        startAutoRefresh();
    } else {
        stopAutoRefresh();
    }
}

async function loadBrowse() {
    try {
        const resp = await apiFetch(`${API_BASE}/kb/browse`);
        if (!resp.ok) {
            const errText = await resp.text().catch(() => '');
            console.error('加载知识库失败: HTTP', resp.status, errText);
            els.kbModules.innerHTML = '<p class="empty-hint">加载失败: 服务异常 (HTTP ' + resp.status + ')</p>';
            toast('加载知识库失败: 服务异常', 'error');
            return;
        }
        const data = await resp.json();
        const modules = data.data || [];

        // 统计：可见知识库数 / 文档总数 / 分块总数（均基于有权限的范围）
        const kbCount = modules.length;
        const docCount = modules.reduce((s, m) => s + (m.docs || []).length, 0);
        const chunkCount = modules.reduce((s, m) => s + (m.docs || []).reduce((x, d) => x + (d.chunkCount || d.chunks || 0), 0), 0);
        els.statDocs.textContent = kbCount;
        els.statChunks.textContent = docCount;
        els.statSize.textContent = chunkCount;

        state.kbModulesData = modules;
        renderBrowse(modules);
    } catch (e) {
        console.error('加载知识库失败:', e);
        els.kbModules.innerHTML = '<p class="empty-hint">加载失败，请检查网络连接</p>';
        toast('加载知识库失败: ' + (e.message || '网络错误'), 'error');
    }
}

function renderBrowse(modules) {
    if (modules.length === 0) {
        els.kbModules.innerHTML = '<p class="empty-hint">暂无可访问的知识库</p>';
        return;
    }
    // 目录树样式：知识库为文件夹节点（可折叠），文档为其子条目
    els.kbModules.innerHTML = modules.map((m, idx) => {
        const docs = m.docs || [];
        const visTag = m.visibility
            ? `<span class="kb-vis-tag kb-vis-${(m.visibility || '').toLowerCase()}">${escapeHtml(m.visibilityText || m.visibility)}</span>`
            : '';
        const docsHtml = docs.map(d => `
            <div class="kb-tree-doc" data-kb-id="${m.id}" data-doc-id="${d.id}" data-doc-filename="${escapeHtml(d.filename || d.name || '')}">
                <span class="kb-tree-indent"></span>
                <span class="doc-icon">${getFileIcon(d.filename || d.name || '')}</span>
                <span class="kb-tree-doc-name" title="${escapeHtml(d.filename || d.name || '')}">${escapeHtml(d.filename || d.name || '')}</span>
                <span class="kb-tree-doc-meta">${d.chunkCount || d.chunks || 0} 块 · ${formatFileSize(d.fileSize || d.size || 0)}</span>
                <button class="doc-action doc-preview-btn">预览</button>
            </div>
        `).join('');
        return `
            <div class="kb-tree-node" data-kb-name="${escapeHtml((m.name || '') + ' ' + (m.description || ''))}">
                <div class="kb-tree-folder" data-node-idx="${idx}">
                    <span class="kb-tree-caret">▾</span>
                    <span class="kb-tree-folder-icon">📁</span>
                    <span class="kb-tree-folder-name">${escapeHtml(m.name || ('知识库 #' + m.id))}</span>
                    ${visTag}
                    <span class="kb-tree-count">${docs.length} 篇</span>
                </div>
                ${m.description ? `<div class="kb-tree-desc">${escapeHtml(m.description)}</div>` : ''}
                <div class="kb-tree-children">${docsHtml}</div>
            </div>
        `;
    }).join('');
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = { pdf: '📕', txt: '📄', md: '📝', docx: '📘' };
    return icons[ext] || '📄';
}

async function previewDocument(kbId, docId, filename) {
    els.chunkModalTitle.textContent = `文档分块 - ${filename}`;
    els.chunkModalBody.innerHTML = '<div class="loading-spinner">加载中...</div>';
    els.chunkModal.classList.remove('modal-hidden');
    els.chunkModal.style.display = 'flex';
    try {
        const resp = await apiFetch(`${API_BASE}/kb/browse/${kbId}/documents/${docId}/chunks`);
        const data = await resp.json();
        if (data.success && data.data.length > 0) {
            var chunks = data.data;

            var sortedChunks = chunks.slice().sort(function(a, b) { return (a.chunk_index || 0) - (b.chunk_index || 0); });
            var mergedParts = [];
            for (var ci = 0; ci < sortedChunks.length; ci++) {
                var text = (sortedChunks[ci].content || '').trim();
                if (!text) continue;
                if (ci > 0) {
                    text = removeOverlap(mergedParts[mergedParts.length - 1], text);
                }
                mergedParts.push(text);
            }
            var mergedMd = mergedParts.join('\n\n');
            var mergedHtml = '<div class="chunk-merged-preview">' +
                '<div class="chunk-merged-header">' +
                    '<span class="chunk-merged-title">文档合并预览</span>' +
                    '<span class="chunk-merged-count">共 ' + chunks.length + ' 个分块</span>' +
                '</div>' +
                '<div class="chunk-merged-body">' + renderMarkdown(mergedMd) + '</div>' +
            '</div>';

            var chunkItems = sortedChunks.map(function(chunk, i) {
                var isLong = chunk.is_truncated;
                var preview = escapeHtml(chunk.content_preview || chunk.content);
                var full = renderMarkdown(chunk.content);
                var chunkId = docId + '_' + chunk.chunk_index;
                return (
                '<div class="chunk-item" data-chunk-id="' + chunkId + '">' +
                    '<div class="chunk-header">' +
                        '<span class="chunk-badge">分块 ' + (chunk.chunk_index + 1) + '</span>' +
                        (chunk.page > 0 ? '<span class="chunk-page">第 ' + chunk.page + ' 页</span>' : '') +
                    '</div>' +
                    '<div class="chunk-content' + (isLong ? ' chunk-content-collapsed' : '') + '" id="chunk-content-' + chunkId + '">' +
                        '<span class="chunk-text-preview">' + preview + '</span>' +
                        (isLong ? '<span class="chunk-text-full" style="display:none;">' + full + '</span>' : '') +
                    '</div>' +
                    (isLong ? '<button class="chunk-expand-btn" data-chunk-id="' + chunkId + '" onclick="toggleChunkExpand(\'' + chunkId + '\')">展开全部 ▼</button>' : '') +
                '</div>'
            )}).join('');

            els.chunkModalBody.innerHTML = mergedHtml +
                '<div class="chunk-divider"><span>分块明细</span></div>' +
                chunkItems +
                '<div class="modal-actions"><button class="btn btn-outline modal-close-btn">关闭</button></div>';
        } else {
            els.chunkModalBody.innerHTML = '<p class="empty-hint">暂无分块数据</p><div class="modal-actions"><button class="btn btn-outline modal-close-btn">关闭</button></div>';
        }
    } catch (e) {
        els.chunkModalBody.innerHTML = '<p class="empty-hint">加载失败</p><div class="modal-actions"><button class="btn btn-outline modal-close-btn">关闭</button></div>';
    }
}

function toggleChunkExpand(chunkId) {
    const contentEl = document.getElementById('chunk-content-' + chunkId);
    const btn = document.querySelector(`.chunk-expand-btn[data-chunk-id="${chunkId}"]`);
    if (!contentEl || !btn) return;
    const previewEl = contentEl.querySelector('.chunk-text-preview');
    const fullEl = contentEl.querySelector('.chunk-text-full');
    const isCollapsed = contentEl.classList.contains('chunk-content-collapsed');
    if (isCollapsed) {
        contentEl.classList.remove('chunk-content-collapsed');
        if (previewEl) previewEl.style.display = 'none';
        if (fullEl) fullEl.style.display = '';
        btn.textContent = '收起 ▲';
    } else {
        contentEl.classList.add('chunk-content-collapsed');
        if (previewEl) previewEl.style.display = '';
        if (fullEl) fullEl.style.display = 'none';
        btn.textContent = '展开全部 ▼';
    }
}

function closeChunkModal() {
    els.chunkModal.style.display = 'none';
    els.chunkModal.classList.add('modal-hidden');
}

async function searchKnowledgeBase() {
    const query = els.kbSearchInput.value.trim();
    if (!query) return;

    els.kbSearchInput.placeholder = '搜索中...';
    els.kbSearchInput.disabled = true;

    try {
        // 权限过滤：仅检索当前用户可访问的知识库（服务端强制）
        const resp = await apiFetch(`${API_BASE}/kb/browse/search?q=${encodeURIComponent(query)}`);
        const data = await resp.json();
        if (data.success && data.data.length > 0) {
            const grouped = {};
            data.data.forEach(item => {
                if (!grouped[item.doc_id]) {
                    grouped[item.doc_id] = { filename: item.filename, results: [] };
                }
                grouped[item.doc_id].results.push(item);
            });

            const resultsHtml = Object.values(grouped).map(g => `
                <div class="kb-search-group">
                    <div class="kb-search-doc">${getFileIcon(g.filename)} ${escapeHtml(g.filename)}</div>
                    ${g.results.map(r => `
                        <div class="kb-search-item">
                            <div class="kb-search-score">相关度 ${(r.score || 0).toFixed(3)}</div>
                            <div class="kb-search-text">${escapeHtml((r.content || '').substring(0, 200))}${(r.content || '').length > 200 ? '...' : ''}</div>
                        </div>
                    `).join('')}
                </div>
            `).join('');
            els.kbModules.innerHTML = `<div class="kb-section-title">搜索结果（${data.data.length} 条，仅限你有权限的知识库）<button class="doc-action kb-search-back">返回知识库</button></div>` + resultsHtml;
        } else {
            els.kbModules.innerHTML = '<p class="empty-hint">未找到相关内容（仅检索你有权限的知识库）</p>';
        }
    } catch (e) {
        console.error('搜索失败:', e);
        toast('搜索失败: ' + (e.message || '网络错误'), 'error');
    } finally {
        els.kbSearchInput.placeholder = '搜索知识库或文档...';
        els.kbSearchInput.disabled = false;
    }
}

function toast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    els.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('removing');
        toast.addEventListener('animationend', () => toast.remove());
    }, 3000);
}

async function loadSessions() {
    try {
        const resp = await apiFetch(`${API_BASE}/sessions`);
        const data = await resp.json();
        state.sessions = data.data || [];
        renderSessions();
        if (state.sessions.length > 0 && !state.currentSessionId) {
            selectSession(state.sessions[0].id);
        } else if (state.sessions.length === 0 && !state.currentSessionId) {
            await autoCreateSession();
        }
    } catch (e) {
        console.error('加载会话失败:', e);
        renderSessions();
        if (!state.currentSessionId) {
            await autoCreateSession();
        }
    }
}

async function autoCreateSession() {
    try {
        const resp = await apiFetch(`${API_BASE}/sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: '默认对话' }),
        });
        const data = await resp.json();
        if (data.success) {
            await loadSessions();
            selectSession(data.data.id);
        } else {
            enableInputFallback();
        }
    } catch (e) {
        console.error('自动创建会话失败:', e);
        enableInputFallback();
    }
}

function enableInputFallback() {
    els.chatInput.disabled = false;
    els.btnSend.disabled = false;
    els.btnSend.style.display = '';
    els.btnStop.style.display = 'none';
    els.inputHint.textContent = '后端服务未连接，部分功能不可用';
    els.statusIndicator.textContent = '● 服务未连接';
    els.statusIndicator.className = 'status error';
}

function renderSessions() {
    els.sessionList.innerHTML = state.sessions.length === 0
        ? '<p class="empty-hint">暂无会话</p>'
        : state.sessions.map(s => `
            <div class="session-item ${s.id === state.currentSessionId ? 'active' : ''}"
                 data-id="${s.id}" onclick="selectSession('${s.id}')" ondblclick="startRenameSession('${s.id}', event)">
                <span class="title">${escapeHtml(s.title)}</span>
                <button class="delete-btn" onclick="event.stopPropagation(); deleteSession('${s.id}')">×</button>
            </div>
        `).join('');
}

async function createSession() {
    try {
        const resp = await apiFetch(`${API_BASE}/sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: '新对话' }),
        });
        const data = await resp.json();
        if (data.success) {
            await loadSessions();
            selectSession(data.data.id);
        }
    } catch (e) {
        console.error('创建会话失败:', e);
    }
}

async function selectSession(sessionId) {
    state.currentSessionId = sessionId;
    els.chatInput.disabled = false;
    els.btnSend.disabled = false;
    els.btnSend.style.display = '';
    els.btnStop.style.display = 'none';
    els.inputHint.textContent = '按 Enter 发送，Shift+Enter 换行';
    renderSessions();
    await loadHistory(sessionId);
}

async function deleteSession(sessionId) {
    if (!confirm('确定删除此会话？')) return;
    try {
        await apiFetch(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE' });
        if (state.currentSessionId === sessionId) {
            state.currentSessionId = null;
            els.chatMessages.innerHTML = `
                <div class="welcome-message">
                    <div class="welcome-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" width="48" height="48">
                            <path d="M4 19.5A2.5 2.5 0 016.5 17H20"/>
                            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>
                        </svg>
                    </div>
                    <h2>欢迎使用企业知识库助手</h2>
                    <p>上传企业文档后，即可向我提问任何关于文档内容的问题</p>
                </div>`;
            els.chatInput.disabled = true;
            els.btnSend.disabled = true;
            els.btnSend.style.display = 'none';
            els.btnStop.style.display = 'none';
            els.inputHint.textContent = '请先创建或选择一个会话开始对话';
        }
        await loadSessions();
    } catch (e) {
        console.error('删除会话失败:', e);
    }
}

function startRenameSession(sessionId, event) {
    event.stopPropagation();
    const item = document.querySelector(`.session-item[data-id="${sessionId}"]`);
    if (!item) return;
    const titleSpan = item.querySelector('.title');
    const oldTitle = titleSpan.textContent;

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'session-rename-input';
    input.value = oldTitle;
    input.maxLength = 50;
    titleSpan.replaceWith(input);
    input.focus();
    input.select();

    const finishRename = async () => {
        const newTitle = input.value.trim() || oldTitle;
        input.replaceWith(titleSpan);
        titleSpan.textContent = newTitle;
        if (newTitle !== oldTitle) {
            await renameSession(sessionId, newTitle);
        }
    };

    input.addEventListener('blur', finishRename);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { input.blur(); }
        if (e.key === 'Escape') {
            input.value = oldTitle;
            input.blur();
        }
    });
}

async function renameSession(sessionId, title) {
    try {
        await apiFetch(`${API_BASE}/sessions/${sessionId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title }),
        });
    } catch (e) {
        console.error('重命名失败:', e);
    }
}

async function loadHistory(sessionId) {
    try {
        const resp = await apiFetch(`${API_BASE}/sessions/${sessionId}/history`);
        const data = await resp.json();
        els.chatMessages.innerHTML = '';
        if (data.data && data.data.length > 0) {
            data.data.forEach(msg => addMessageToUI(msg.role, msg.content, msg.sources));
        } else {
            els.chatMessages.innerHTML = `
                <div class="welcome-message">
                    <div class="welcome-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" width="48" height="48">
                            <path d="M4 19.5A2.5 2.5 0 016.5 17H20"/>
                            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>
                        </svg>
                    </div>
                    <h2>开始对话</h2>
                    <p>在下方输入您的问题</p>
                </div>`;
        }
        scrollToBottom();
    } catch (e) {
        console.error('加载历史失败:', e);
    }
}

async function streamSSEResponse(reader, contentEl, assistantMsg) {
    const decoder = new TextDecoder();
    let fullText = '';
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const data = JSON.parse(line);
                if (data.token) {
                    fullText += data.token;
                    contentEl.innerHTML = renderMarkdown(fullText);
                    scrollToBottom();
                }
                if (data.done) {
                    if (data.sources) {
                        renderSources(assistantMsg, data.sources);
                    }
                    // 显示用户反馈按钮（仅登录用户有 conversation_id）
                    if (data.conversation_id) {
                        addFeedbackUI(assistantMsg, data.conversation_id);
                    }
                }
            } catch (e) {}
        }
    }
    return fullText;
}

function startMessageFlow() {
    els.chatInput.value = '';
    els.chatInput.style.height = 'auto';
    els.btnSend.disabled = true;
    els.btnSend.style.display = 'none';
    els.btnStop.style.display = '';
    state.isGenerating = true;
    state.abortController = new AbortController();
    removeWelcomeMessage();
}

function endMessageFlow(onSuccess) {
    state.isGenerating = false;
    state.currentAssistantMsg = null;
    state.abortController = null;
    els.btnSend.disabled = false;
    els.btnSend.style.display = '';
    els.btnStop.style.display = 'none';
    els.chatInput.focus();
    if (onSuccess) onSuccess();
}

async function sendGuestMessage(query) {
    startMessageFlow();
    addMessageToUI('user', query, null);
    const assistantMsg = addMessageToUI('assistant', '', null);
    state.currentAssistantMsg = assistantMsg;
    const contentEl = assistantMsg.querySelector('.message-content');

    try {
        const resp = await fetch(`${API_BASE}/chat/guest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: query }),
            signal: state.abortController.signal,
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        await streamSSEResponse(resp.body.getReader(), contentEl, assistantMsg);
    } catch (e) {
        if (e.name !== 'AbortError') {
            contentEl.textContent = `请求失败: ${e.message}`;
        }
    } finally {
        endMessageFlow();
    }
}

async function sendMessage() {
    if (state.isGenerating) return;
    const query = els.chatInput.value.trim();
    if (!query) return;

    if (!state.authToken) {
        await sendGuestMessage(query);
        return;
    }

    if (!state.currentSessionId) {
        toast('请先创建或选择一个会话', 'warning');
        return;
    }

    if (state.agentMode) {
        await sendAgentMessage(query);
        return;
    }

    startMessageFlow();
    addMessageToUI('user', query, null);
    const assistantMsg = addMessageToUI('assistant', '', null);
    state.currentAssistantMsg = assistantMsg;
    const contentEl = assistantMsg.querySelector('.message-content');

    try {
        const resp = await apiFetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.currentSessionId, message: query }),
            signal: state.abortController.signal,
        });

        await streamSSEResponse(resp.body.getReader(), contentEl, assistantMsg);
    } catch (e) {
        if (e.name !== 'AbortError') {
            contentEl.textContent = `请求失败: ${e.message}`;
        }
    } finally {
        endMessageFlow(() => loadSessions());
    }
}

function toggleAgentMode() {
    state.agentMode = !state.agentMode;
    if (state.agentMode) {
        els.btnAgentToggle.classList.add('active');
        els.btnAgentToggle.textContent = 'Agent模式';
        if (els.agentBadge) els.agentBadge.style.display = '';
        toast('已切换到 Agent 模式（闲聊 + 工具调用）', 'info');
    } else {
        els.btnAgentToggle.classList.remove('active');
        els.btnAgentToggle.textContent = 'RAG检索';
        if (els.agentBadge) els.agentBadge.style.display = 'none';
        toast('已切换到 RAG 检索模式（知识库文档问答）', 'info');
    }
}

async function sendAgentMessage(query) {
    startMessageFlow();
    addMessageToUI('user', query, null);
    const assistantMsg = addMessageToUI('assistant', '', null);
    state.currentAssistantMsg = assistantMsg;
    const contentEl = assistantMsg.querySelector('.message-content');

    const thinkingContainer = document.createElement('div');
    thinkingContainer.className = 'agent-thinking';
    const wrapper = assistantMsg.querySelector('.message-content-wrapper');
    wrapper.insertBefore(thinkingContainer, contentEl);

    try {
        const resp = await apiFetch(`${API_BASE}/agent/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: state.currentSessionId, message: query }),
            signal: state.abortController.signal,
        });

        await streamAgentResponse(resp.body.getReader(), contentEl, thinkingContainer, assistantMsg);
    } catch (e) {
        if (e.name !== 'AbortError') {
            contentEl.textContent = `请求失败: ${e.message}`;
        }
    } finally {
        endMessageFlow(() => loadSessions());
    }
}

async function streamAgentResponse(reader, contentEl, thinkingContainer, assistantMsg) {
    const decoder = new TextDecoder();
    let fullText = '';
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const event = JSON.parse(line);
                const eventType = event.type;

                if (eventType === 'thinking') {
                    addThinkingStep(thinkingContainer, 'thinking', event.content);
                } else if (eventType === 'tool_call') {
                    addThinkingStep(
                        thinkingContainer,
                        'tool_call',
                        `调用工具: ${event.tool_name}(${JSON.stringify(event.arguments)})`
                    );
                } else if (eventType === 'tool_result') {
                    addThinkingStep(
                        thinkingContainer,
                        'tool_result',
                        `结果: ${event.result.substring(0, 200)}${event.result.length > 200 ? '...' : ''}`
                    );
                } else if (eventType === 'token') {
                    fullText += event.content;
                    contentEl.innerHTML = renderMarkdown(fullText);
                    scrollToBottom();
                } else if (eventType === 'done') {
                    fullText = event.content || fullText;
                    contentEl.innerHTML = renderMarkdown(fullText);
                    if (event.sources && event.sources.length > 0) {
                        renderSources(assistantMsg, event.sources);
                    }
                    if (event.conversation_id) {
                        addFeedbackUI(assistantMsg, event.conversation_id);
                    }
                } else if (eventType === 'error') {
                    contentEl.textContent = `Agent 错误: ${event.content}`;
                } else if (eventType === 'finished') {
                    if (event.conversation_id) {
                        addFeedbackUI(assistantMsg, event.conversation_id);
                    }
                    scrollToBottom();
                }
            } catch (e) {}
        }
    }
    return fullText;
}

function addThinkingStep(container, type, content) {
    const step = document.createElement('div');
    step.className = `agent-step agent-step-${type}`;
    const iconMap = {
        thinking: '💭',
        tool_call: '🔧',
        tool_result: '📋',
    };
    step.innerHTML = `<span class="agent-step-icon">${iconMap[type] || '•'}</span><span class="agent-step-text">${escapeHtml(content)}</span>`;
    container.appendChild(step);
    scrollToBottom();
}

function addMessageToUI(role, content, sourcesJson) {
    removeWelcomeMessage();
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    const avatar = role === 'user' ? '👤' : '🤖';
    msgDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content-wrapper">
            <div class="message-content">${renderMarkdown(content)}</div>
        </div>`;
    els.chatMessages.appendChild(msgDiv);

    if (sourcesJson && role === 'assistant') {
        let sources = sourcesJson;
        if (typeof sources === 'string') {
            try { sources = JSON.parse(sources); } catch (e) { sources = []; }
        }
        if (sources && sources.length > 0) {
            renderSources(msgDiv, sources);
        }
    }

    scrollToBottom();
    return msgDiv;
}

function renderSources(msgDiv, sources) {
    const existing = msgDiv.querySelector('.message-sources');
    if (existing) existing.remove();
    const sourcesDiv = document.createElement('div');
    sourcesDiv.className = 'message-sources';
    sourcesDiv.innerHTML = `
        <div class="message-sources-header">参考来源</div>
        ${sources.map((s, i) => `
            <div class="source-item" data-doc-id="${escapeHtml(s.doc_id || '')}" data-chunk-index="${s.chunk_index || i}" style="cursor:pointer;">
                <span class="source-index">${i + 1}</span>
                <div class="source-info">
                    <div class="source-filename">${escapeHtml(s.filename)}</div>
                    <div class="source-meta">
                        ${s.page ? `<span>第${s.page}页</span>` : ''}
                        <span>${escapeHtml(s.type || '')}</span>
                    </div>
                </div>
                <div class="source-score">
                    <span class="source-score-text">${(s.score * 100).toFixed(0)}%</span>
                    <div class="source-score-bar">
                        <div class="source-score-fill" style="width:${(s.score * 100).toFixed(0)}%"></div>
                    </div>
                </div>
            </div>
        `).join('')}`;

    const contentWrapper = msgDiv.querySelector('.message-content-wrapper');
    contentWrapper.insertBefore(sourcesDiv, contentWrapper.firstChild);

    sourcesDiv.querySelectorAll('.source-item').forEach(item => {
        item.addEventListener('click', () => {
            const docId = item.dataset.docId;
            const chunkIndex = item.dataset.chunkIndex;
            viewSourceChunk(docId, chunkIndex);
        });
    });
}

/**
 * 在助手消息底部添加用户反馈按钮（👍 有帮助 / 👎 需要改进）
 */
function addFeedbackUI(msgDiv, conversationId) {
    if (!conversationId) return;
    const existing = msgDiv.querySelector('.message-feedback');
    if (existing) existing.remove();

    const feedbackDiv = document.createElement('div');
    feedbackDiv.className = 'message-feedback';
    feedbackDiv.innerHTML = `
        <div class="feedback-divider"></div>
        <div class="feedback-body">
            <span class="feedback-label">这个回答对您有帮助吗？</span>
            <div class="feedback-actions">
                <button class="feedback-btn feedback-like" data-value="1" onclick="sendFeedback('${conversationId}', 1, this)">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
                    </svg>
                    有帮助
                </button>
                <button class="feedback-btn feedback-dislike" data-value="-1" onclick="sendFeedback('${conversationId}', -1, this)">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10zM17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
                    </svg>
                    需要改进
                </button>
            </div>
        </div>
    `;
    msgDiv.querySelector('.message-content-wrapper').appendChild(feedbackDiv);
}

/**
 * 提交用户反馈到后端
 */
async function sendFeedback(conversationId, value, btn) {
    if (!conversationId || !state.authToken) return;

    const feedbackDiv = btn.closest('.message-feedback');
    const allBtns = feedbackDiv.querySelectorAll('.feedback-btn');
    const isAlreadyActive = btn.classList.contains('active');

    // 如果已选中，则取消选中（toggle 效果）
    if (isAlreadyActive) {
        btn.classList.remove('active');
        value = 0;
    } else {
        allBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }

    try {
        const resp = await apiFetch(`${API_BASE}/conversations/${conversationId}/feedback`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feedback: value }),
        });
        const data = await resp.json();
        if (data.success) {
            if (value === 1) {
                toast('感谢您的反馈 👍', 'success');
            } else if (value === -1) {
                toast('感谢您的反馈，我们会持续改进', 'info');
            }
        } else {
            btn.classList.remove('active');
            if (isAlreadyActive && value === 0) {
                // 取消选中不需要报错
            } else {
                toast('反馈提交失败', 'error');
            }
        }
    } catch (e) {
        btn.classList.remove('active');
        if (!(isAlreadyActive && value === 0)) {
            toast('反馈提交失败: ' + e.message, 'error');
        }
    }
}

async function viewSourceChunk(docId, chunkIndex) {
    try {
        const resp = await apiFetch(`${API_BASE}/kb/browse/${kbId}/documents/${docId}/chunks`);
        const data = await resp.json();
        if (!data.success || !data.data) {
            toast('无法加载来源内容', 'error');
            return;
        }
        const chunks = data.data;
        const targetIndex = parseInt(chunkIndex) || 0;
        const idx = chunks.findIndex(c => c.chunk_index === targetIndex);
        if (idx === -1) {
            toast('来源分块不存在', 'error');
            return;
        }
        const chunk = chunks[idx];
        const isLong = chunk.content && chunk.content.length > 300;
        const preview = escapeHtml(chunk.content_preview || chunk.content);
        const full = renderMarkdown(chunk.content);
        const chunkId = `source_${docId}_${idx}`;
        els.chunkModalTitle.textContent = `来源查看 - ${escapeHtml(chunk.filename || docId)}`;
        els.chunkModalBody.innerHTML = `
            <div class="chunk-item">
                <div class="chunk-badge">分块 ${idx + 1} / ${chunks.length}</div>
                <div class="chunk-content${isLong ? ' chunk-content-collapsed' : ''}" id="chunk-content-${chunkId}">
                    <span class="chunk-text-preview">${preview}</span>
                    ${isLong ? `<span class="chunk-text-full" style="display:none;">${full}</span>` : ''}
                </div>
                ${isLong ? `<button class="chunk-expand-btn" data-chunk-id="${chunkId}" onclick="toggleChunkExpand('${chunkId}')">展开全部 ▼</button>` : ''}
            </div>`;
        els.chunkModal.style.display = 'flex';
    } catch (e) {
        toast(`加载来源失败: ${e.message}`, 'error');
    }
}

function stopGeneration() {
    if (state.abortController) {
        state.abortController.abort();
        state.abortController = null;
    }
    state.isGenerating = false;
    els.btnSend.disabled = false;
    els.btnSend.style.display = '';
    els.btnStop.style.display = 'none';
}

function removeWelcomeMessage() {
    const welcome = els.chatMessages.querySelector('.welcome-message');
    if (welcome) welcome.remove();
}

async function checkHealth() {
    try {
        const resp = await apiFetch(`${API_BASE}/chat/health`);
        const data = await resp.json();
        if (data.llm || data.deepseek || data.ollama) {
            els.statusIndicator.textContent = '● 就绪';
            els.statusIndicator.className = 'status';
        } else {
            els.statusIndicator.textContent = '● DeepSeek API 未连接';
            els.statusIndicator.className = 'status error';
        }
    } catch (e) {
        els.statusIndicator.textContent = '● 服务未连接';
        els.statusIndicator.className = 'status error';
    }
}

function autoResizeInput() {
    els.chatInput.style.height = 'auto';
    els.chatInput.style.height = Math.min(els.chatInput.scrollHeight, 120) + 'px';
}

function scrollToBottom() {
    els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
}

function renderMarkdown(text) {
    if (!text) return '';
    try {
        if (typeof marked !== 'undefined' && marked.parse) {
            var normalized = normalizeLineBreaks(text);
            return marked.parse(normalized, { breaks: false, gfm: true });
        }
    } catch (e) {}
    // fallback: 简单转义换行
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function normalizeLineBreaks(text) {
    // 按双换行（段落分隔）拆分
    var blocks = text.split(/\n\s*\n/);
    return blocks.map(function(block) {
        var lines = block.split('\n');
        if (lines.length <= 1) return block;
        // 保留 Markdown 语法块：标题、列表、引用、代码围栏、表格
        for (var i = 0; i < lines.length; i++) {
            var t = lines[i].trim();
            if (/^(#{1,6}\s|[\*\-\+]\s|\d+\.\s|[>\|]|```|~~~)/.test(t)) {
                return block;
            }
        }
        // 普通段落：把 PDF 硬换行合并为连续文字
        return lines.map(function(l) { return l.trim(); }).filter(Boolean).join(' ');
    }).join('\n\n');
}

function removeOverlap(prev, current) {
    var maxOverlap = Math.min(prev.length, current.length, 200);
    for (var len = maxOverlap; len >= 10; len--) {
        var suffix = prev.slice(-len);
        var prefix = current.slice(0, len);
        if (suffix === prefix) {
            return current.slice(len);
        }
    }
    return current;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
        bytes /= 1024;
        i++;
    }
    return `${bytes.toFixed(1)} ${units[i]}`;
}

document.addEventListener('DOMContentLoaded', init);