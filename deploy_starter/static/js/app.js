/**
 * 应用主入口和初始化
 */

// 切换标签页
function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById(tab + '-tab').classList.add('active');

    if (tab === 'calendar') {
        loadCalendar();
    } else if (tab === 'completed') {
        loadCompletedTodos();
    } else if (tab === 'trash') {
        loadTrashTodos();
    } else if (tab === 'forward') {
        loadForwardRules();
    } else if (tab === 'forwarded') {
        loadForwardedEmails();
    } else if (tab === 'chat') {
        // 聊天标签页：滚动到底部
        const chatContainer = document.getElementById('chatMessages');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    } else {
        loadTodos();
    }
}

// 页面加载初始化
window.onload = async function() {
    // 加载设置
    loadZoomSetting();
    loadSyncIntervalSetting();
    loadOnlyRecentSetting();
    
    // 加载邮箱配置
    await loadEmailConfig();
    
    // 加载数据
    loadTodos();
    loadCalendar();
    refreshForwardedBadge();
    
    // 初始化聊天助手
    initChat();
    
    // 初始化事件监听
    initEmailProviderListener();
    initDetailModalEvents();
    initAddManualModalEvents();
    initExportModalEvents();
    initReportModalEvents();
    initSettingsModalEvents();
    initHelpModalEvents();
    initRuleModalEvents();
    initZoomShortcuts();
    
    // 检查用户称呼是否设置，未设置则高亮帮助按钮
    checkUserNicknamesAndHighlight();
    
    // 启动时自动同步（带进度条）
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    if (email && password) {
        syncEmails(false); // 显示进度条，完成后会自动安排下一次同步
    }
};
