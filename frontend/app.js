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
    activeKbTab: 'documents',
    editingChunkId: null,
    editingManualId: null,
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
    kbDocList: document.getElementById('kb-doc-list'),
    kbManualList: document.getElementById('kb-manual-list'),
    btnAddManual: document.getElementById('btn-add-manual'),
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
    editModal: document.getElementById('edit-modal'),
    editModalTitle: document.getElementById('edit-modal-title'),
    editMeta: document.getElementById('edit-meta'),
    editContent: document.getElementById('edit-content'),
    btnSaveEdit: document.getElementById('btn-save-edit'),
    btnCancelEdit: document.getElementById('btn-cancel-edit'),
    btnCloseEditModal: document.getElementById('btn-close-edit-modal'),
    manualModal: document.getElementById('manual-modal'),
    manualModalTitle: document.getElementById('manual-modal-title'),
    manualTitle: document.getElementById('manual-title'),
    manualContent: document.getElementById('manual-content'),
    manualTags: document.getElementById('manual-tags'),
    btnSaveManual: document.getElementById('btn-save-manual'),
    btnCancelManual: document.getElementById('btn-cancel-manual'),
    btnCloseManualModal: document.getElementById('btn-close-manual-modal'),
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
    els.btnAddManual.addEventListener('click', openManualModal);
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
        var btn = e.target.closest('.chunk-edit-btn');
        if (btn) {
            var chunkItem = btn.closest('.chunk-item');
            if (!chunkItem) return;
            var chunkId = chunkItem.dataset.chunkId;
            var content = chunkItem.querySelector('.chunk-content').textContent;
            var filename = els.chunkModalTitle.textContent.replace('文档分块 - ', '');
            var chunkBadge = chunkItem.querySelector('.chunk-badge');
            var chunkIndex = chunkBadge ? chunkBadge.textContent.replace('分块 ', '') : '1';
            var pageEl = chunkItem.querySelector('.chunk-page');
            var page = pageEl ? parseInt(pageEl.textContent.replace('第 ', '').replace(' 页', '')) : 0;
            openChunkEdit(chunkId, content, filename, chunkIndex, page);
        }
        var closeBtn = e.target.closest('.modal-close-btn');
        if (closeBtn) closeChunkModal();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            if (els.editModal.style.display === 'flex') {
                closeEditModal();
            } else if (els.manualModal.style.display === 'flex') {
                closeManualModal();
            } else if (els.chunkModal.style.display === 'flex') {
                closeChunkModal();
            }
        }
    });
    els.btnCloseEditModal.addEventListener('click', closeEditModal);
    els.btnCancelEdit.addEventListener('click', closeEditModal);
    els.editModal.addEventListener('click', (e) => {
        if (e.target === els.editModal) closeEditModal();
    });
    els.btnSaveEdit.addEventListener('click', saveChunkEdit);
    els.btnCloseManualModal.addEventListener('click', closeManualModal);
    els.btnCancelManual.addEventListener('click', closeManualModal);
    els.manualModal.addEventListener('click', (e) => {
        if (e.target === els.manualModal) closeManualModal();
    });
    els.btnSaveManual.addEventListener('click', saveManualEntry);

    document.querySelectorAll('.kb-tab').forEach(tab => {
        tab.addEventListener('click', () => switchKbTab(tab.dataset.tab));
    });

    els.kbDocList.addEventListener('click', (e) => {
        const item = e.target.closest('.kb-doc-item');
        if (!item) return;
        const docId = item.dataset.docId;
        const filename = item.dataset.docFilename;
        if (e.target.closest('.doc-preview-btn')) {
            previewDocument(docId, filename);
        }
    });

    els.kbManualList.addEventListener('click', (e) => {
        const item = e.target.closest('.kb-manual-item');
        if (!item) return;
        const entryId = item.dataset.entryId;
        if (e.target.closest('.manual-edit-btn')) {
            editManualEntry(entryId);
        } else if (e.target.closest('.doc-delete-btn')) {
            deleteManualEntry(entryId);
        }
    });
}

function switchKbTab(tab) {
    state.activeKbTab = tab;
    document.querySelectorAll('.kb-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    document.querySelectorAll('.kb-tab-content').forEach(c => c.classList.toggle('active', c.id === `tab-${tab}`));
    if (tab === 'manual') loadManualEntries();
    else loadDocuments();
}

async function toggleKbPanel() {
    state.kbPanelOpen = !state.kbPanelOpen;
    els.kbPanel.style.display = state.kbPanelOpen ? 'flex' : 'none';
    if (state.kbPanelOpen) {
        await loadStatistics();
        if (state.activeKbTab === 'manual') loadManualEntries();
        else loadDocuments();
        startAutoRefresh();
    } else {
        stopAutoRefresh();
    }
}

async function loadStatistics() {
    try {
        const resp = await apiFetch(`${API_BASE}/knowledge/statistics`);
        const data = await resp.json();
        if (data.success) {
            els.statDocs.textContent = data.data.total_documents;
            els.statChunks.textContent = data.data.total_chunks;
            els.statSize.textContent = formatFileSize(data.data.total_size);
        }
    } catch (e) {
        console.error('加载统计失败:', e);
        els.statDocs.textContent = '--';
        els.statChunks.textContent = '--';
        els.statSize.textContent = '--';
    }
}

function startAutoRefresh() {
    stopAutoRefresh();
    if (els.kbAutoRefresh) {
        els.kbAutoRefresh.classList.remove('paused');
    }
    state.autoRefreshInterval = setInterval(async () => {
        await loadStatistics();
        if (state.activeKbTab === 'manual') {
            await loadManualEntries();
        } else {
            await loadDocuments();
        }
    }, 600000);
}

function stopAutoRefresh() {
    if (state.autoRefreshInterval) {
        clearInterval(state.autoRefreshInterval);
        state.autoRefreshInterval = null;
    }
    if (els.kbAutoRefresh) {
        els.kbAutoRefresh.classList.add('paused');
    }
}

async function loadDocuments() {
    try {
        const resp = await apiFetch(`${API_BASE}/knowledge/documents`);
        if (!resp.ok) {
            const errText = await resp.text().catch(() => '');
            console.error('加载文档列表失败: HTTP', resp.status, errText);
            els.kbDocList.innerHTML = '<p class="empty-hint">加载失败: 服务异常 (HTTP ' + resp.status + ')</p>';
            toast('加载文档列表失败: 服务异常', 'error');
            return;
        }
        const data = await resp.json();
        const pageData = data.data || {};
        const docs = pageData.records || (Array.isArray(data.data) ? data.data : []);
        els.kbDocList.innerHTML = docs.length === 0
            ? '<p class="empty-hint">暂无文档，请通过管理平台上传</p>'
            : docs.map(d => `
                <div class="kb-doc-item" data-doc-id="${d.id}" data-doc-filename="${escapeHtml(d.filename)}">
                    <div class="doc-name">
                        <span class="doc-icon">${getFileIcon(d.filename)}</span>
                        ${escapeHtml(d.filename)}
                    </div>
                    <div class="doc-meta">
                        <span>${formatFileSize(d.size)} · ${d.chunks || 0} 个分块</span>
                        <span class="doc-actions">
                            <button class="doc-action doc-preview-btn">预览</button>
                        </span>
                    </div>
                </div>
            `).join('');
    } catch (e) {
        console.error('加载文档列表失败:', e);
        els.kbDocList.innerHTML = '<p class="empty-hint">加载失败，请检查网络连接</p>';
        toast('加载文档列表失败: ' + (e.message || '网络错误'), 'error');
    }
}

async function loadManualEntries() {
    try {
        const resp = await apiFetch(`${API_BASE}/knowledge/manual`);
        const data = await resp.json();
        const entries = data.data || [];
        els.kbManualList.innerHTML = entries.length === 0
            ? '<p class="empty-hint">暂无手动条目</p>'
            : entries.map(e => `
                <div class="kb-manual-item" data-entry-id="${e.id}">
                    <div class="manual-title">${escapeHtml(e.title)}</div>
                    <div class="manual-preview">${escapeHtml(e.content.substring(0, 120))}${e.content.length > 120 ? '...' : ''}</div>
                    ${e.tags && e.tags.length > 0 ? `
                        <div class="manual-tags">${e.tags.map(t => `<span class="manual-tag">${escapeHtml(t)}</span>`).join('')}</div>
                    ` : ''}
                    <div class="manual-meta">
                        <span>${e.updated_at ? new Date(e.updated_at).toLocaleDateString() : ''}</span>
                        <span class="doc-actions">
                            <button class="doc-action manual-edit-btn">编辑</button>
                            <button class="doc-action doc-delete-btn">删除</button>
                        </span>
                    </div>
                </div>
            `).join('');
    } catch (e) {
        console.error('加载手动条目失败:', e);
    }
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = { pdf: '📕', txt: '📄', md: '📝', docx: '📘' };
    return icons[ext] || '📄';
}

async function previewDocument(docId, filename) {
    els.chunkModalTitle.textContent = `文档分块 - ${filename}`;
    els.chunkModalBody.innerHTML = '<div class="loading-spinner">加载中...</div>';
    els.chunkModal.classList.remove('modal-hidden');
    els.chunkModal.style.display = 'flex';
    try {
        const resp = await apiFetch(`${API_BASE}/knowledge/documents/${docId}/chunks`);
        const data = await resp.json();
        if (data.success && data.data.length > 0) {
            els.chunkModalBody.innerHTML = data.data.map((chunk, i) => {
                const isLong = chunk.is_truncated;
                const preview = escapeHtml(chunk.content_preview || chunk.content);
                const full = escapeHtml(chunk.content);
                const chunkId = `${docId}_${chunk.chunk_index}`;
                return `
                <div class="chunk-item" data-chunk-id="${chunkId}">
                    <div class="chunk-header">
                        <span class="chunk-badge">分块 ${chunk.chunk_index + 1}</span>
                        ${chunk.page > 0 ? `<span class="chunk-page">第 ${chunk.page} 页</span>` : ''}
                        <button class="chunk-edit-btn">回写编辑</button>
                    </div>
                    <div class="chunk-content${isLong ? ' chunk-content-collapsed' : ''}" id="chunk-content-${chunkId}">
                        <span class="chunk-text-preview">${preview}</span>
                        ${isLong ? `<span class="chunk-text-full" style="display:none;">${full}</span>` : ''}
                    </div>
                    ${isLong ? `<button class="chunk-expand-btn" data-chunk-id="${chunkId}" onclick="toggleChunkExpand('${chunkId}')">展开全部 ▼</button>` : ''}
                </div>
            `}).join('') + '<div class="modal-actions"><button class="btn btn-outline modal-close-btn">关闭</button></div>';
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

function openChunkEdit(chunkId, content, filename, chunkIndex, page) {
    state.editingChunkId = chunkId;
    state.editingManualId = null;
    els.editModalTitle.textContent = '回写编辑分块';
    els.editMeta.innerHTML = `
        <strong>${escapeHtml(filename)}</strong> · 分块 ${chunkIndex}${page > 0 ? ` · 第 ${page} 页` : ''}
    `;
    els.editContent.value = content;
    els.editModal.style.display = 'flex';
    els.editContent.focus();
}

function closeEditModal() {
    els.editModal.style.display = 'none';
    state.editingChunkId = null;
    state.editingManualId = null;
}

async function saveChunkEdit() {
    const content = els.editContent.value.trim();
    if (!content) {
        toast('内容不能为空', 'warning');
        return;
    }

    const chunkId = state.editingChunkId;
    if (!chunkId) return;

    els.btnSaveEdit.disabled = true;
    els.btnSaveEdit.textContent = '保存中...';

    try {
        const resp = await apiFetch(`${API_BASE}/knowledge/chunks/${chunkId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content }),
        });
        const data = await resp.json().catch(() => null);
        if (data && data.success) {
            toast('回写成功，向量已更新', 'success');
            closeEditModal();
            closeChunkModal();
        } else {
            const errMsg = data ? (data.error || data.detail || '回写失败') : '服务器异常';
            toast(errMsg, 'error');
        }
    } catch (e) {
        toast(`回写失败: ${e.message}`, 'error');
    } finally {
        els.btnSaveEdit.disabled = false;
        els.btnSaveEdit.textContent = '保存回写';
    }
}

function openManualModal(entryId = null) {
    state.editingManualId = entryId;
    state.editingChunkId = null;

    if (entryId) {
        els.manualModalTitle.textContent = '编辑手动条目';
        els.btnSaveManual.textContent = '更新';
        apiFetch(`${API_BASE}/knowledge/manual`)
            .then(r => r.json())
            .then(data => {
                const entry = (data.data || []).find(e => e.id === entryId);
                if (entry) {
                    els.manualTitle.value = entry.title || '';
                    els.manualContent.value = entry.content || '';
                    els.manualTags.value = (entry.tags || []).join(', ');
                }
            })
            .catch(() => {});
    } else {
        els.manualModalTitle.textContent = '添加手动条目';
        els.btnSaveManual.textContent = '保存';
        els.manualTitle.value = '';
        els.manualContent.value = '';
        els.manualTags.value = '';
    }
    els.manualModal.style.display = 'flex';
    els.manualTitle.focus();
}

function closeManualModal() {
    els.manualModal.style.display = 'none';
    state.editingManualId = null;
}

async function saveManualEntry() {
    const title = els.manualTitle.value.trim();
    const content = els.manualContent.value.trim();
    const tagsStr = els.manualTags.value.trim();

    if (!title || !content) {
        toast('标题和内容不能为空', 'warning');
        return;
    }

    const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : [];
    els.btnSaveManual.disabled = true;
    els.btnSaveManual.textContent = '保存中...';

    try {
        let resp;
        if (state.editingManualId) {
            resp = await apiFetch(`${API_BASE}/knowledge/manual/${state.editingManualId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, content, tags }),
            });
        } else {
            resp = await apiFetch(`${API_BASE}/knowledge/manual`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, content, tags }),
            });
        }

        const data = await resp.json().catch(() => null);
        if (data && data.success) {
            toast(state.editingManualId ? '手动条目已更新' : '手动条目已添加', 'success');
            closeManualModal();
            await loadManualEntries();
            await loadStatistics();
        } else {
            const errMsg = data ? (data.error || data.detail || '操作失败') : '服务器异常';
            toast(errMsg, 'error');
        }
    } catch (e) {
        toast(`操作失败: ${e.message}`, 'error');
    } finally {
        els.btnSaveManual.disabled = false;
        els.btnSaveManual.textContent = state.editingManualId ? '更新' : '保存';
    }
}

async function editManualEntry(entryId) {
    openManualModal(entryId);
}

async function deleteManualEntry(entryId) {
    if (!confirm('确定删除此手动条目？')) return;
    try {
        const resp = await apiFetch(`${API_BASE}/knowledge/manual/${entryId}`, { method: 'DELETE' });
        const data = await resp.json().catch(() => null);
        if (data && data.success) {
            toast('手动条目已删除', 'success');
        }
        await loadManualEntries();
        await loadStatistics();
    } catch (e) {
        toast(`删除失败: ${e.message}`, 'error');
    }
}

async function searchKnowledgeBase() {
    const query = els.kbSearchInput.value.trim();
    if (!query) return;

    els.kbSearchInput.placeholder = '搜索中...';
    els.kbSearchInput.disabled = true;

    try {
        const resp = await apiFetch(`${API_BASE}/knowledge/search?q=${encodeURIComponent(query)}`);
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
                <div class="search-result-group">
                    <div class="search-result-filename">📄 ${escapeHtml(g.filename)} (${g.results.length} 条)</div>
                    ${g.results.map(r => `
                        <div class="search-result-item">
                            <div class="search-result-meta">
                                <span>分块 ${r.chunk_index + 1}</span>
                                ${r.page > 0 ? `<span>第 ${r.page} 页</span>` : ''}
                                <span class="search-score">相似度: ${(r.score * 100).toFixed(1)}%</span>
                            </div>
                            <div class="search-result-content">${escapeHtml(r.content.substring(0, 200))}${r.content.length > 200 ? '...' : ''}</div>
                        </div>
                    `).join('')}
                </div>
            `).join('');

            els.chunkModalTitle.textContent = `搜索结果: "${query}"`;
            els.chunkModalBody.innerHTML = resultsHtml + '<div class="modal-actions"><button class="btn btn-outline modal-close-btn">关闭</button></div>';
            els.chunkModal.classList.remove('modal-hidden');
            els.chunkModal.style.display = 'flex';
        } else {
            toast('未找到匹配内容', 'info');
        }
    } catch (e) {
        toast(`搜索失败: ${e.message}`, 'error');
    } finally {
        els.kbSearchInput.placeholder = '搜索知识库...';
        els.kbSearchInput.disabled = false;
        els.kbSearchInput.value = '';
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
                    contentEl.textContent = fullText;
                    scrollToBottom();
                }
                if (data.done && data.sources) {
                    renderSources(assistantMsg, data.sources);
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
                    contentEl.textContent = fullText;
                    scrollToBottom();
                } else if (eventType === 'done') {
                    fullText = event.content || fullText;
                    contentEl.textContent = fullText;
                    if (event.sources && event.sources.length > 0) {
                        renderSources(assistantMsg, event.sources);
                    }
                } else if (eventType === 'error') {
                    contentEl.textContent = `Agent 错误: ${event.content}`;
                } else if (eventType === 'finished') {
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
            <div class="message-content">${escapeHtml(content)}</div>
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
                <div class="source-score-bar">
                    <div class="source-score-fill" style="width:${(s.score * 100).toFixed(0)}%"></div>
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

async function viewSourceChunk(docId, chunkIndex) {
    try {
        const resp = await apiFetch(`${API_BASE}/knowledge/documents/${docId}/chunks`);
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
        const full = escapeHtml(chunk.content);
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
        if (data.deepseek || data.ollama) {
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