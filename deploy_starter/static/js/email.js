/**
 * 邮箱同步功能
 */

// 加载邮箱配置
async function loadEmailConfig() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/email/config`);
        const data = await response.json();
        if (data.configured) {
            document.getElementById('email').value = data.email_address || '';
            document.getElementById('savePassword').checked = data.save_password || false;
            // 如果开启了记住密码，自动填充密码
            if (data.save_password && data.password) {
                document.getElementById('password').value = data.password;
            }
            // 设置邮箱类型
            if (data.provider) {
                const select = document.getElementById('emailProvider');
                // 兼容老配置：保存的 provider 在下拉框里已不存在时，回退到自定义并显示原服务器
                const known = Array.from(select.options).some(o => o.value === data.provider);
                const provider = known ? data.provider : 'custom';
                select.value = provider;
                // 如果是自定义类型，显示服务器输入框
                const serverInput = document.getElementById('pop3Server');
                const portInput = document.getElementById('pop3PortInput');
                if (provider === 'custom') {
                    serverInput.style.display = 'inline-block';
                    portInput.style.display = 'inline-block';
                    serverInput.value = data.pop3_server || '';
                    portInput.value = data.pop3_port || 995;
                } else {
                    serverInput.style.display = 'none';
                    portInput.style.display = 'none';
                }
            }
        }
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

// 同步邮件
async function syncEmails(silent = false) {
    // 防止并发同步：如果正在同步，直接返回
    if (isSyncing) {
        console.log('[同步] 已有同步任务在进行中，跳过');
        return;
    }
    isSyncing = true;  // 立即加锁
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const provider = document.getElementById('emailProvider').value;
    let pop3Server = document.getElementById('pop3Server').value;
    let pop3Port = 995;  // 默认 SSL 端口
    
    // 获取服务器配置
    if (provider !== 'custom') {
        pop3Server = emailServers[provider].server;
        pop3Port = emailServers[provider].port;
    } else {
        // 自定义：从输入框获取端口
        pop3Port = parseInt(document.getElementById('pop3PortInput').value) || 995;
    }
    console.log('连接配置:', { provider, pop3Server, pop3Port });

    if (!email || !password) {
        isSyncing = false;  // 解锁
        if (!silent) {
            alert('请输入邮箱和密码/授权码');
        }
        return;
    }
    
    if (!pop3Server) {
        isSyncing = false;  // 解锁
        if (!silent) {
            alert('请选择邮箱服务商或输入POP3服务器地址');
        }
        return;
    }

    const syncBtn = document.getElementById('syncBtn');
    const statusDiv = document.getElementById('status');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    syncBtn.disabled = true;
    
    // 显示进度条
    if (!silent) {
        statusDiv.textContent = '';
        progressContainer.classList.add('active');
        progressText.style.display = 'block';
        progressText.textContent = '正在连接...';
        progressBar.style.width = '0%';
        progressBar.style.background = '';
    }

    // 使用 EventSource 接收 SSE 真实进度
    const savePassword = document.getElementById('savePassword').checked;
    // 从服务端同步设置读取"只同步7天内"选项
    const onlyRecent = syncSettings.only_recent_7days || false;
    const params = new URLSearchParams({
        email_address: email,
        password: password,
        pop3_server: pop3Server,
        pop3_port: pop3Port,
        save_password: savePassword,
        days_limit: onlyRecent ? 7 : 0,
        provider: provider
    });
    
    // 使用 URL 编码后的参数构建 SSE 连接
    const queryString = params.toString();
    const eventSource = new EventSource(`${API_BASE_URL}/api/emails/sync-stream?${queryString}`);
    currentEventSource = eventSource;  // 保存到全局变量
    document.getElementById('cancelSyncBtn').style.display = 'block';  // 显示取消按钮
    
    let finalResult = null;
    let hasError = false;
    let isCompleted = false;  // 标记是否已正常完成
    
    // 记录连接信息便于调试
    console.log('[SSE] 连接URL:', `${API_BASE_URL}/api/emails/sync-stream?${queryString}`);
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            // 更新真实进度
            if (!silent) {
                progressBar.style.width = data.progress + '%';
                progressText.textContent = data.message;
            }
            
            // 分析阶段：每处理完一封邮件刷新待办列表
            if (data.stage === 'analyzing') {
                loadTodos();
                loadCompletedTodos();
                if (currentTab === 'calendar') {
                    loadCalendar();
                }
                refreshForwardedBadge();
                if (currentTab === 'forwarded') {
                    loadForwardedEmails();
                }
            }
            
            // 处理错误
            if (data.error) {
                hasError = true;
                if (!silent) {
                    progressBar.style.background = '#dc3545';
                }
                statusDiv.textContent = '同步失败: ' + data.message;
                statusDiv.style.color = '#dc3545';
                eventSource.close();
                finishSync();
            }
            
            // 处理分析失败（LLM错误）
            if (data.stage === 'error') {
                hasError = true;
                finalResult = data.result || {};
                if (!silent) {
                    progressBar.style.width = '100%';
                    progressBar.style.background = '#dc3545';
                }
                const errorMsg = finalResult.error || data.message || '分析失败';
                statusDiv.textContent = `同步失败: ${errorMsg}`;
                statusDiv.style.color = '#dc3545';
                eventSource.close();
                finishSync();
                return;
            }
            
            // 处理完成
            if (data.stage === 'complete') {
                isCompleted = true;  // 标记为已完成
                finalResult = data.result || {};
                
                // 检查是否有部分失败
                if (finalResult && finalResult.partial_failure) {
                    if (!silent) {
                        progressBar.style.background = '#ffc107';  // 黄色表示部分成功
                    }
                    statusDiv.textContent = `部分成功：成功 ${finalResult.emails_processed || 0} 封，失败 ${finalResult.emails_failed || 0} 封，生成了 ${finalResult.todos_created || 0} 个待办`;
                    statusDiv.style.color = '#856404';
                } else if (finalResult.message === '没有新邮件') {
                    if (!silent) {
                        progressBar.style.background = '#28a745';
                    }
                    statusDiv.textContent = '没有新邮件需要处理';
                    statusDiv.style.color = '#28a745';
                } else {
                    if (!silent) {
                        progressBar.style.background = '#28a745';
                    }
                    statusDiv.textContent = `处理了 ${finalResult.emails_processed || 0} 封邮件，生成了 ${finalResult.todos_created || 0} 个待办事项`;
                    statusDiv.style.color = '#28a745';
                }
                
                loadTodos();
                if (currentTab === 'calendar') {
                    loadCalendar();
                }
                refreshForwardedBadge();
                if (currentTab === 'forwarded') {
                    loadForwardedEmails();
                }
                eventSource.close();
                finishSync();
            }
        } catch (e) {
            console.error('解析 SSE 数据失败:', e);
        }
    };
    
    eventSource.onerror = function(error) {
        // 延迟检查，等待 onmessage 处理完最后的消息
        setTimeout(() => {
            // 如果已经正常完成或已有错误，忽略此事件
            if (isCompleted || hasError) {
                return;
            }
            console.error('SSE 连接错误:', error);
            eventSource.close();
            hasError = true;
            if (!silent) {
                progressBar.style.width = '100%';
                progressBar.style.background = '#dc3545';
                progressText.textContent = '连接失败';
            }
            // 提供更详细的错误提示
            const providerName = document.getElementById('emailProvider').selectedOptions[0]?.text || '邮箱';
            statusDiv.innerHTML = `同步失败: 连接服务器出错<br>
                <small style="color:#888">请检查:<br>
                1. ${providerName}是否已开启POP3服务<br>
                2. 密码是否为授权码（不是登录密码）<br>
                3. 网络连接是否正常</small>`;
            statusDiv.style.color = '#dc3545';
            finishSync();
        }, 100);  // 延迟100ms，让 onmessage 有时间处理
    };
    
    function finishSync() {
        isSyncing = false;  // 解锁
        currentEventSource = null;  // 清除全局引用
        syncBtn.disabled = false;
        document.getElementById('cancelSyncBtn').style.display = 'none';  // 隐藏取消按钮
        // 进度条保持显示，不自动隐藏
        
        // 安排下一次自动同步（完成后1分钟）
        scheduleAutoSync();
    }
}

// 取消同步
function cancelSync() {
    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }
    
    isSyncing = false;
    document.getElementById('syncBtn').disabled = false;
    document.getElementById('cancelSyncBtn').style.display = 'none';
    document.getElementById('progressBar').style.background = '#6c757d';
    document.getElementById('progressText').textContent = '已取消';
    document.getElementById('status').textContent = '同步已取消';
    document.getElementById('status').style.color = '#6c757d';
    
    console.log('[同步] 用户取消了同步');
    scheduleAutoSync();
}

// 安排自动同步
function scheduleAutoSync() {
    // 清除之前的定时器
    if (autoSyncTimer) {
        clearTimeout(autoSyncTimer);
    }
    if (countdownTimer) {
        clearInterval(countdownTimer);
    }
    
    const intervalMs = autoSyncIntervalMinutes * 60 * 1000;
    nextSyncTime = Date.now() + intervalMs;
    console.log(`[自动同步] 将在 ${autoSyncIntervalMinutes} 分钟后同步`);
    
    // 启动倒计时显示（每秒更新）
    updateCountdownDisplay();
    countdownTimer = setInterval(updateCountdownDisplay, 1000);
    
    autoSyncTimer = setTimeout(() => {
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        if (email && password) {
            console.log('[自动同步] 触发自动同步...');
            syncEmails(false); // 显示进度条
        } else {
            // 没有配置邮箱，等待后再检查
            scheduleAutoSync();
        }
    }, intervalMs);
}

// 更新倒计时显示
function updateCountdownDisplay() {
    const countdown = document.getElementById('autoSyncCountdown');
    if (!countdown) return;
    
    // 如果正在同步，显示同步中
    if (isSyncing) {
        countdown.textContent = '同步中...';
        countdown.style.color = '#007bff';
        return;
    }
    
    // 如果没有设置下次同步时间，不显示
    if (!nextSyncTime) {
        countdown.textContent = '';
        return;
    }
    
    const remaining = Math.max(0, nextSyncTime - Date.now());
    const minutes = Math.ceil(remaining / 60000);  // 向上取整到分钟
    
    if (minutes > 1) {
        countdown.textContent = `${minutes}分钟后自动同步`;
    } else if (minutes === 1) {
        countdown.textContent = '1分钟内自动同步';
    } else {
        countdown.textContent = '即将同步';
    }
    countdown.style.color = '#888';
}

// 清空所有数据
async function clearAllData() {
    if (!confirm('确定要清空所有待办事项和同步记录吗？\n（邮箱配置将保留）')) {
        return;
    }
    
    const statusDiv = document.getElementById('status');
    try {
        const response = await fetch(`${API_BASE_URL}/api/data/clear`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.success) {
            statusDiv.textContent = '数据已清空';
            statusDiv.style.color = '#28a745';
            // 刷新所有视图
            loadTodos();
            loadCompletedTodos();
            loadCalendar();
            loadTrashTodos();
        } else {
            statusDiv.textContent = '清空失败: ' + (data.detail || '未知错误');
            statusDiv.style.color = '#dc3545';
        }
    } catch (error) {
        statusDiv.textContent = '清空失败: ' + error.message;
        statusDiv.style.color = '#dc3545';
    }
}

// 初始化邮箱服务商选择监听
function initEmailProviderListener() {
    document.getElementById('emailProvider').addEventListener('change', function() {
        const provider = this.value;
        const serverInput = document.getElementById('pop3Server');
        const portInput = document.getElementById('pop3PortInput');
        if (provider === 'custom') {
            serverInput.style.display = 'inline-block';
            portInput.style.display = 'inline-block';
            serverInput.value = '';
            portInput.value = '995';
        } else {
            serverInput.style.display = 'none';
            portInput.style.display = 'none';
            serverInput.value = emailServers[provider].server;
        }
    });
}
