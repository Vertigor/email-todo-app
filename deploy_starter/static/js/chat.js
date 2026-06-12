/**
 * 聊天助手功能
 */

// 初始化聊天
async function initChat() {
    // 加载记忆设置
    const savedMemory = localStorage.getItem('chatMemoryEnabled');
    chatMemoryEnabled = savedMemory === 'true';
    document.getElementById('chatMemoryToggle').checked = chatMemoryEnabled;
    updateMemoryHint();
    
    // 如果开启了记忆，加载聊天记录
    if (chatMemoryEnabled) {
        await loadChatHistory();
    }
}

// 切换记忆开关
function toggleChatMemory() {
    chatMemoryEnabled = document.getElementById('chatMemoryToggle').checked;
    localStorage.setItem('chatMemoryEnabled', chatMemoryEnabled.toString());
    updateMemoryHint();
    
    if (chatMemoryEnabled && chatMessages.length > 0) {
        // 开启记忆时保存当前聊天
        saveChatHistoryToServer();
    }
}

// 更新记忆提示文字
function updateMemoryHint() {
    const hint = document.getElementById('memoryHint');
    if (chatMemoryEnabled) {
        hint.textContent = '（开启时聊天记录会保存）';
        hint.style.color = '#28a745';
    } else {
        hint.textContent = '（关闭时不保存聊天记录）';
        hint.style.color = '#888';
    }
}

// 从服务器加载聊天记录
async function loadChatHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/chat/history`);
        const data = await response.json();
        if (data.messages && data.messages.length > 0) {
            chatMessages = data.messages;
            renderChatMessages();
        }
    } catch (error) {
        console.error('加载聊天记录失败:', error);
    }
}

// 保存聊天记录到服务器
async function saveChatHistoryToServer() {
    if (!chatMemoryEnabled) return;
    
    try {
        await fetch(`${API_BASE_URL}/api/chat/history`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ messages: chatMessages })
        });
    } catch (error) {
        console.error('保存聊天记录失败:', error);
    }
}

// 清除聊天记录
async function clearChatHistory() {
    if (!confirm('确定要清除所有聊天记录吗？')) return;
    
    try {
        await fetch(`${API_BASE_URL}/api/chat/history`, { method: 'DELETE' });
        chatMessages = [];
        renderChatMessages();
    } catch (error) {
        console.error('清除聊天记录失败:', error);
    }
}

// 渲染聊天消息
function renderChatMessages() {
    const container = document.getElementById('chatMessages');
    
    if (chatMessages.length === 0) {
        container.innerHTML = `
            <div class="chat-welcome">
                <p>👋 你好！我是待办助手，可以帮你查询和了解待办事项。</p>
                <p>试试问我：</p>
                <ul>
                    <li onclick="askQuestion('我有多少个待办？')">我有多少个待办？</li>
                    <li onclick="askQuestion('今天有哪些事情要做？')">今天有哪些事情要做？</li>
                    <li onclick="askQuestion('哪些待办快到期了？')">哪些待办快到期了？</li>
                </ul>
            </div>
        `;
        return;
    }
    
    container.innerHTML = chatMessages.map(msg => `
        <div class="chat-message ${msg.role}${msg.isThinking ? ' thinking' : ''}">
            ${msg.isThinking ? '<span class="thinking-dots">正在思考</span>' : escapeHtml(msg.content).replace(/\n/g, '<br>')}
        </div>
    `).join('');
    
    // 滚动到底部
    container.scrollTop = container.scrollHeight;
}

// 点击示例问题
function askQuestion(question) {
    document.getElementById('chatInput').value = question;
    sendChatMessage();
}

// 处理键盘事件（Enter发送）
function handleChatKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
}

// 发送聊天消息
async function sendChatMessage() {
    if (isChatSending) return;
    
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;
    
    console.log('[聊天] 发送消息:', message);
    
    isChatSending = true;
    const sendBtn = document.getElementById('chatSendBtn');
    sendBtn.disabled = true;
    sendBtn.textContent = '发送中...';
    
    // 添加用户消息
    chatMessages.push({ role: 'user', content: message });
    input.value = '';
    renderChatMessages();
    
    // 添加助手消息占位符 - 显示"正在思考..."
    const assistantMsgIndex = chatMessages.length;
    chatMessages.push({ role: 'assistant', content: '正在思考...', isThinking: true });
    renderChatMessages();
    
    try {
        console.log('[聊天] 发送请求到服务器...');
        const response = await fetch(`${API_BASE_URL}/api/chat/todo-assistant`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ messages: chatMessages.slice(0, -1) })  // 不包括占位消息
        });
        
        console.log('[聊天] 收到响应，开始读取流...');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantContent = '';
        let hasReceivedContent = false;
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const text = decoder.decode(value);
            const lines = text.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.content) {
                            if (!hasReceivedContent) {
                                // 第一次收到内容，清除"正在思考..."
                                hasReceivedContent = true;
                                assistantContent = '';
                            }
                            assistantContent += data.content;
                            chatMessages[assistantMsgIndex].content = assistantContent;
                            chatMessages[assistantMsgIndex].isThinking = false;
                            renderChatMessages();
                        }
                        if (data.error) {
                            console.error('[聊天] 收到错误:', data.error);
                            assistantContent = '抱歉，发生了错误：' + data.error;
                            chatMessages[assistantMsgIndex].content = assistantContent;
                            chatMessages[assistantMsgIndex].isThinking = false;
                            renderChatMessages();
                        }
                        if (data.done) {
                            console.log('[聊天] 响应完成');
                        }
                    } catch (e) {
                        // 解析失败，忽略
                    }
                }
            }
        }
        
        // 如果没有收到任何内容
        if (!hasReceivedContent) {
            chatMessages[assistantMsgIndex].content = '抱歉，没有收到回复。';
            chatMessages[assistantMsgIndex].isThinking = false;
            renderChatMessages();
        }
        
        // 保存聊天记录
        saveChatHistoryToServer();
        
    } catch (error) {
        console.error('[聊天] 请求失败:', error);
        chatMessages[assistantMsgIndex].content = '抱歉，网络请求失败：' + error.message;
        chatMessages[assistantMsgIndex].isThinking = false;
        renderChatMessages();
    } finally {
        isChatSending = false;
        sendBtn.disabled = false;
        sendBtn.textContent = '发送';
    }
}
