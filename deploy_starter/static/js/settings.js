/**
 * 设置功能
 */

// ========== 缩放功能 ==========

// 加载缩放设置
async function loadZoomSetting() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/zoom`);
        const data = await response.json();
        if (data.zoom) {
            currentZoom = data.zoom;
            applyZoom();
        }
    } catch (error) {
        console.log('加载缩放设置失败，使用默认值');
    }
}

// 应用缩放
function applyZoom() {
    document.getElementById('mainContainer').style.transform = `scale(${currentZoom})`;
    document.getElementById('mainContainer').style.transformOrigin = 'top center';
    document.getElementById('zoomLevel').textContent = Math.round(currentZoom * 100) + '%';
}

// 保存缩放设置
function saveZoomSetting() {
    fetch(`${API_BASE_URL}/api/settings/zoom`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({zoom: currentZoom})
    }).catch(() => {});
}

// 放大
function zoomIn() {
    if (currentZoom < ZOOM_MAX) {
        currentZoom = Math.min(ZOOM_MAX, currentZoom + ZOOM_STEP);
        applyZoom();
        saveZoomSetting();
    }
}

// 缩小
function zoomOut() {
    if (currentZoom > ZOOM_MIN) {
        currentZoom = Math.max(ZOOM_MIN, currentZoom - ZOOM_STEP);
        applyZoom();
        saveZoomSetting();
    }
}

// 重置缩放
function zoomReset() {
    currentZoom = 1.0;
    applyZoom();
    saveZoomSetting();
}

// 初始化缩放快捷键
function initZoomShortcuts() {
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey) {
            if (e.key === '=' || e.key === '+') {
                e.preventDefault();
                zoomIn();
            } else if (e.key === '-') {
                e.preventDefault();
                zoomOut();
            } else if (e.key === '0') {
                e.preventDefault();
                zoomReset();
            }
        }
    });
}

// ========== 同步间隔设置 ==========

// 加载同步间隔设置
function loadSyncIntervalSetting() {
    const saved = localStorage.getItem('autoSyncIntervalMinutes');
    if (saved) {
        autoSyncIntervalMinutes = parseInt(saved) || 1;
    }
    console.log(`[设置] 自动同步间隔: ${autoSyncIntervalMinutes} 分钟`);
}

// 保存同步间隔设置
function saveSyncIntervalSetting() {
    const input = document.getElementById('autoSyncInterval');
    let value = parseInt(input.value) || 1;
    // 限制范围 1-1440
    value = Math.max(1, Math.min(1440, value));
    input.value = value;
    
    autoSyncIntervalMinutes = value;
    localStorage.setItem('autoSyncIntervalMinutes', value.toString());
    console.log(`[设置] 已保存自动同步间隔: ${value} 分钟`);
}

// ========== 服务端同步设置 ==========

// 加载服务端同步设置
async function loadServerSyncSettings() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/sync`);
        const data = await response.json();
        syncSettings = data;
    } catch (error) {
        console.error('加载同步设置失败:', error);
    }
}

// 兼容旧函数名（页面加载时调用）
async function loadOnlyRecentSetting() {
    await loadServerSyncSettings();
}

// 保存服务端同步设置
async function saveServerSyncSettings() {
    const onlyRecent = document.getElementById('onlyRecent').checked;
    const maxEmailsInput = document.getElementById('maxEmailsPerSync');
    let maxEmails = parseInt(maxEmailsInput.value) || 100;
    maxEmails = Math.max(10, Math.min(1000, maxEmails));
    maxEmailsInput.value = maxEmails;
    
    try {
        await fetch(`${API_BASE_URL}/api/settings/sync`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                only_recent_7days: onlyRecent,
                max_emails_per_sync: maxEmails 
            })
        });
        // 更新本地缓存
        syncSettings.only_recent_7days = onlyRecent;
        syncSettings.max_emails_per_sync = maxEmails;
        console.log(`[设置] 已保存同步设置: 只同步7天=${onlyRecent}, 最多邮件数=${maxEmails}`);
    } catch (error) {
        console.error('保存同步设置失败:', error);
    }
}

// ========== 用户信息设置 ==========

// 加载用户称呼设置
async function loadUserNicknames() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/user-info`);
        const data = await response.json();
        document.getElementById('userNicknames').value = data.nicknames || '';
    } catch (error) {
        console.error('加载用户称呼失败:', error);
    }
}

// 保存用户称呼设置
async function saveUserNicknames() {
    const nicknames = document.getElementById('userNicknames').value.trim();
    try {
        await fetch(`${API_BASE_URL}/api/settings/user-info`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nicknames: nicknames })
        });
        console.log(`[设置] 已保存用户称呼: ${nicknames}`);
    } catch (error) {
        console.error('保存用户称呼失败:', error);
    }
}

// ========== 设置模态框 ==========

// 打开设置
async function openSettings() {
    loadLLMSettings();
    loadSmtpSettings();
    loadDataDir();
    loadUserNicknames();
    // 填充同步间隔设置
    document.getElementById('autoSyncInterval').value = autoSyncIntervalMinutes;
    // 加载并填充服务端同步设置
    await loadServerSyncSettings();
    document.getElementById('maxEmailsPerSync').value = syncSettings.max_emails_per_sync || 100;
    document.getElementById('onlyRecent').checked = syncSettings.only_recent_7days || false;
    // 应用当前缩放比例到模态框
    document.querySelector('#settingsModal .modal').style.transform = `scale(${currentZoom})`;
    document.getElementById('settingsModal').classList.add('active');
}

// 关闭设置
function closeSettings() {
    document.getElementById('settingsModal').classList.remove('active');
}

// 加载数据目录
async function loadDataDir() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/data-dir`);
        const data = await response.json();
        document.getElementById('dataDirPath').textContent = data.data_dir || '未知';
    } catch (error) {
        document.getElementById('dataDirPath').textContent = '加载失败';
        console.error('加载数据目录失败:', error);
    }
}

// 打开数据目录
async function openDataDir() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/data-dir/open`, {
            method: 'POST'
        });
        const result = await response.json();
        if (!result.success) {
            alert('打开目录失败: ' + result.error);
        }
    } catch (error) {
        alert('打开目录失败: ' + error.message);
    }
}

// 加载 LLM 设置
async function loadLLMSettings() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/llm`);
        const data = await response.json();
        document.getElementById('llmModel').value = data.model || '';
        document.getElementById('llmBaseUrl').value = data.base_url || '';
        document.getElementById('llmApiKey').value = data.api_key || '';
        document.getElementById('llmTemperature').value = data.temperature !== null && data.temperature !== undefined ? data.temperature : '';
    } catch (error) {
        console.error('加载LLM设置失败:', error);
    }
}

// 保存 LLM 设置
async function saveLLMSettings() {
    // 先保存用户信息和同步相关设置
    await saveUserNicknames();
    saveSyncIntervalSetting();
    await saveServerSyncSettings();
    // 同时保存SMTP设置
    await saveSmtpSettings();
    
    const model = document.getElementById('llmModel').value.trim();
    const baseUrl = document.getElementById('llmBaseUrl').value.trim();
    const apiKey = document.getElementById('llmApiKey').value.trim();
    const temperatureStr = document.getElementById('llmTemperature').value.trim();

    if (!model) {
        alert('请输入模型名称');
        return;
    }

    if (!baseUrl) {
        alert('请输入API Base URL');
        return;
    }

    // Parse temperature: null if empty, otherwise float value
    let temperature = null;
    if (temperatureStr !== '') {
        temperature = parseFloat(temperatureStr);
        if (isNaN(temperature) || temperature < 0 || temperature > 2) {
            alert('Temperature 必须在 0 到 2 之间');
            return;
        }
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/llm`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                model: model,
                base_url: baseUrl,
                api_key: apiKey,
                temperature: temperature
            })
        });
        const data = await response.json();
        if (data.success) {
            alert('设置已保存');
            closeSettings();
            // 刷新帮助按钮高亮状态
            checkUserNicknamesAndHighlight();
        } else {
            alert('保存失败: ' + (data.message || '未知错误'));
        }
    } catch (error) {
        alert('保存失败: ' + error.message);
    }
}

// 初始化设置模态框事件
function initSettingsModalEvents() {
    // 点击模态框外部关闭（使用 mousedown 避免拖选文字时误关闭）
    document.getElementById('settingsModal').addEventListener('mousedown', function(e) {
        if (e.target === this) {
            closeSettings();
        }
    });

    // ESC键关闭模态框
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeSettings();
            closeHelp();
        }
    });
}

// ========== 帮助模态框 ==========

// 打开帮助
function openHelp() {
    document.querySelector('#helpModal .modal').style.transform = `scale(${currentZoom})`;
    document.getElementById('helpModal').classList.add('active');
}

// 关闭帮助
function closeHelp() {
    document.getElementById('helpModal').classList.remove('active');
}

// 初始化帮助模态框事件
function initHelpModalEvents() {
    // 点击模态框外部关闭
    document.getElementById('helpModal')?.addEventListener('mousedown', function(e) {
        if (e.target === this) {
            closeHelp();
        }
    });
}

// 检查用户称呼是否设置，未设置则高亮帮助按钮
async function checkUserNicknamesAndHighlight() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/user-info`);
        const data = await response.json();
        const helpBtn = document.getElementById('helpBtn');
        
        if (!data.nicknames || data.nicknames.trim() === '') {
            // 未设置称呼，高亮帮助按钮
            helpBtn?.classList.add('highlight');
        } else {
            // 已设置称呼，移除高亮
            helpBtn?.classList.remove('highlight');
        }
    } catch (error) {
        console.error('检查用户称呼失败:', error);
    }
}

// ========== SMTP 发送设置 ==========

// 加载SMTP设置
async function loadSmtpSettings() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/smtp`);
        const data = await response.json();
        document.getElementById('smtpServer').value = data.smtp_server || '';
        document.getElementById('smtpPort').value = data.smtp_port || 465;
        document.getElementById('smtpSsl').checked = data.smtp_ssl !== false;
        document.getElementById('smtpEmail').value = data.email_address || '';
        document.getElementById('smtpPassword').value = '';  // 不回显密码
        document.getElementById('smtpSenderName').value = data.sender_name || '邮箱待办助手';
    } catch (error) {
        console.error('加载SMTP设置失败:', error);
    }
}

// 保存SMTP设置
async function saveSmtpSettings() {
    const smtpServer = document.getElementById('smtpServer').value.trim();
    const smtpPort = parseInt(document.getElementById('smtpPort').value) || 465;
    const smtpSsl = document.getElementById('smtpSsl').checked;
    const email = document.getElementById('smtpEmail').value.trim();
    const password = document.getElementById('smtpPassword').value;
    const senderName = document.getElementById('smtpSenderName').value.trim() || '邮箱待办助手';
    
    // 只有填了服务器才保存
    if (!smtpServer) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/smtp`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                smtp_server: smtpServer,
                smtp_port: smtpPort,
                smtp_ssl: smtpSsl,
                email_address: email,
                password: password,
                sender_name: senderName
            })
        });
        const data = await response.json();
        if (!data.success) {
            console.error('保存SMTP设置失败:', data.detail);
        }
    } catch (error) {
        console.error('保存SMTP设置失败:', error);
    }
}

// 测试SMTP连接
async function testSmtpConnection() {
    const smtpServer = document.getElementById('smtpServer').value.trim();
    const smtpPort = parseInt(document.getElementById('smtpPort').value) || 465;
    const smtpSsl = document.getElementById('smtpSsl').checked;
    const email = document.getElementById('smtpEmail').value.trim();
    const password = document.getElementById('smtpPassword').value;
    const resultSpan = document.getElementById('smtpTestResult');
    
    if (!smtpServer || !email) {
        resultSpan.textContent = '请先填写服务器和邮箱';
        resultSpan.style.color = '#dc3545';
        return;
    }
    
    resultSpan.textContent = '测试中...';
    resultSpan.style.color = '#888';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/smtp/test`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                smtp_server: smtpServer,
                smtp_port: smtpPort,
                smtp_ssl: smtpSsl,
                email_address: email,
                password: password,
                sender_name: document.getElementById('smtpSenderName').value.trim() || '邮箱待办助手'
            })
        });
        const data = await response.json();
        if (data.success) {
            resultSpan.textContent = '连接成功';
            resultSpan.style.color = '#28a745';
        } else {
            resultSpan.textContent = '失败: ' + (data.error || '未知错误');
            resultSpan.style.color = '#dc3545';
        }
    } catch (error) {
        resultSpan.textContent = '测试失败: ' + error.message;
        resultSpan.style.color = '#dc3545';
    }
}
