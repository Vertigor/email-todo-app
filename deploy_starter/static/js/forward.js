/**
 * 邮件转发规则功能
 */

// 转发规则编辑状态
let editingRuleId = null;

// ========== 转发规则列表 ==========

// 加载转发规则列表
async function loadForwardRules() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/forward/rules`);
        const data = await response.json();
        renderForwardRules(data.rules || []);
    } catch (error) {
        document.getElementById('forward-rules-list').innerHTML = 
            '<div class="empty-state">加载失败: ' + error.message + '</div>';
    }
}

// 渲染转发规则列表
function renderForwardRules(rules) {
    const container = document.getElementById('forward-rules-list');
    
    if (rules.length === 0) {
        container.innerHTML = '<div class="empty-state">暂无转发规则<br><span style="font-size: 12px; color: #999;">点击右上角"添加规则"创建第一条转发规则</span></div>';
        return;
    }
    
    container.innerHTML = rules.map(rule => {
        const recipientsList = rule.recipients.map(r => 
            `<span style="display: inline-block; background: #e3f2fd; color: #0056b3; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin: 2px;">${escapeHtml(r)}</span>`
        ).join('');
        
        const statusBadge = rule.enabled 
            ? '<span style="color: #28a745; font-weight: 500;">● 启用</span>' 
            : '<span style="color: #999; font-weight: 500;">○ 禁用</span>';
        
        const matchInfo = rule.match_count > 0
            ? `<span style="margin-left: 10px; color: #888; font-size: 12px;">已匹配 ${rule.match_count} 次${rule.last_matched_at ? '，最近: ' + new Date(rule.last_matched_at).toLocaleString('zh-CN') : ''}</span>`
            : '';

        const modeBadge = rule.also_create_todo
            ? '<span style="margin-left: 10px; padding: 1px 8px; background: #fff3cd; color: #856404; border-radius: 10px; font-size: 11px;" title="转发后仍会让 AI 提取你需要跟进的事项加进待办">📌 转发+待办</span>'
            : '<span style="margin-left: 10px; padding: 1px 8px; background: #e3f2fd; color: #0056b3; border-radius: 10px; font-size: 11px;" title="命中即视为已委派/知会，不再加进你的待办">📨 仅知会</span>';
        
        return `
        <div class="forward-rule-item ${rule.enabled ? '' : 'disabled'}">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div style="flex: 1; min-width: 0;">
                    <div style="font-size: 15px; font-weight: 600; color: #333; margin-bottom: 5px;">
                        ${escapeHtml(rule.description)}
                    </div>
                    <div style="margin-bottom: 5px;">
                        ${statusBadge}
                        ${modeBadge}
                        ${matchInfo}
                    </div>
                </div>
                <div style="display: flex; gap: 6px; margin-left: 10px; flex-shrink: 0;">
                    <button onclick="toggleRuleEnabled('${rule.id}', ${!rule.enabled})" 
                        style="padding: 4px 10px; background: ${rule.enabled ? '#ffc107' : '#28a745'}; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;"
                        title="${rule.enabled ? '禁用' : '启用'}">
                        ${rule.enabled ? '禁用' : '启用'}
                    </button>
                    <button onclick="editRule('${rule.id}')" 
                        style="padding: 4px 10px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
                        编辑
                    </button>
                    <button onclick="deleteRule('${rule.id}')" 
                        style="padding: 4px 10px; background: #dc3545; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">
                        删除
                    </button>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 5px;">
                <span style="font-size: 12px; color: #888; white-space: nowrap;">转发给:</span>
                ${recipientsList}
            </div>
        </div>
        `;
    }).join('');
}

// 切换规则启用/禁用
async function toggleRuleEnabled(ruleId, enabled) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/forward/rules/${ruleId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ enabled: enabled })
        });
        const data = await response.json();
        if (data.success) {
            loadForwardRules();
        } else {
            alert('操作失败: ' + (data.detail || '未知错误'));
        }
    } catch (error) {
        alert('操作失败: ' + error.message);
    }
}

// 删除规则
async function deleteRule(ruleId) {
    if (!confirm('确定要删除此转发规则吗？')) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/forward/rules/${ruleId}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        if (data.success) {
            loadForwardRules();
        } else {
            alert('删除失败: ' + (data.detail || '未知错误'));
        }
    } catch (error) {
        alert('删除失败: ' + error.message);
    }
}

// ========== 添加/编辑规则弹窗 ==========

function showAddRuleModal() {
    editingRuleId = null;
    document.getElementById('ruleModalTitle').textContent = '📤 添加转发规则';
    document.getElementById('ruleDescription').value = '';
    document.getElementById('ruleRecipients').value = '';
    document.getElementById('ruleEnabled').checked = true;
    const alsoBox = document.getElementById('ruleAlsoCreateTodo');
    if (alsoBox) alsoBox.checked = false;
    document.querySelector('#ruleModal .modal').style.transform = `scale(${currentZoom})`;
    document.getElementById('ruleModal').classList.add('active');
}

async function editRule(ruleId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/forward/rules`);
        const data = await response.json();
        const rule = (data.rules || []).find(r => r.id === ruleId);
        if (!rule) {
            alert('规则不存在');
            return;
        }

        editingRuleId = ruleId;
        document.getElementById('ruleModalTitle').textContent = '📤 编辑转发规则';
        document.getElementById('ruleDescription').value = rule.description;
        document.getElementById('ruleRecipients').value = (rule.recipients || []).join('\n');
        document.getElementById('ruleEnabled').checked = rule.enabled;
        const alsoBox = document.getElementById('ruleAlsoCreateTodo');
        if (alsoBox) alsoBox.checked = !!rule.also_create_todo;
        document.querySelector('#ruleModal .modal').style.transform = `scale(${currentZoom})`;
        document.getElementById('ruleModal').classList.add('active');
    } catch (error) {
        alert('加载规则失败: ' + error.message);
    }
}

function closeRuleModal() {
    document.getElementById('ruleModal').classList.remove('active');
    editingRuleId = null;
}

async function saveRuleModal() {
    const description = document.getElementById('ruleDescription').value.trim();
    const recipientsText = document.getElementById('ruleRecipients').value.trim();
    const enabled = document.getElementById('ruleEnabled').checked;
    const alsoCreateTodo = !!(document.getElementById('ruleAlsoCreateTodo') && document.getElementById('ruleAlsoCreateTodo').checked);

    if (!description) {
        alert('请输入规则描述');
        return;
    }
    if (!recipientsText) {
        alert('请输入至少一个收件人邮箱');
        return;
    }

    const recipients = recipientsText.split('\n').map(r => r.trim()).filter(r => r);
    for (const r of recipients) {
        if (!r.includes('@')) {
            alert(`无效的邮箱地址: ${r}`);
            return;
        }
    }

    try {
        let response;
        const body = { description, recipients, enabled, also_create_todo: alsoCreateTodo };
        if (editingRuleId) {
            response = await fetch(`${API_BASE_URL}/api/forward/rules/${editingRuleId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
        } else {
            response = await fetch(`${API_BASE_URL}/api/forward/rules`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
        }

        const data = await response.json();
        if (data.success) {
            closeRuleModal();
            loadForwardRules();
        } else {
            alert('保存失败: ' + (data.detail || '未知错误'));
        }
    } catch (error) {
        alert('保存失败: ' + error.message);
    }
}

// 初始化规则弹窗事件
function initRuleModalEvents() {
    document.getElementById('ruleModal')?.addEventListener('mousedown', function(e) {
        if (e.target === this) {
            closeRuleModal();
        }
    });
}

// ========== 手动转发（从待办详情中） ==========

async function manualForwardEmail(todoId, ruleId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/forward/manual`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email_id: todoId, rule_id: ruleId })
        });
        const data = await response.json();
        if (data.success) {
            alert('转发成功: ' + data.message);
        } else {
            alert('转发失败: ' + (data.detail || data.error || '未知错误'));
        }
    } catch (error) {
        alert('转发失败: ' + error.message);
    }
}
