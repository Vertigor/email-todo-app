/**
 * 待办列表功能
 */

// 加载待办列表
async function loadTodos() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/todos?completed=false`);
        const data = await response.json();
        
        // 根据子标签过滤
        let filteredTodos = data.todos;
        if (currentSubTab === 'with-due') {
            filteredTodos = data.todos.filter(todo => todo.due_date);
        } else if (currentSubTab === 'no-due') {
            filteredTodos = data.todos.filter(todo => !todo.due_date);
            // 无截止时间的按发件时间排序
            filteredTodos.sort((a, b) => {
                const dateA = a.source_email_date ? new Date(a.source_email_date) : new Date(0);
                const dateB = b.source_email_date ? new Date(b.source_email_date) : new Date(0);
                return noDueSortAsc ? (dateA - dateB) : (dateB - dateA);
            });
        }
        
        renderTodos(filteredTodos, 'todos-list', false);
    } catch (error) {
        document.getElementById('todos-list').innerHTML = '<div class="empty-state">加载失败: ' + error.message + '</div>';
    }
}

// 切换子标签
function switchSubTab(subTab) {
    currentSubTab = subTab;
    // 更新子标签样式
    document.querySelectorAll('.sub-tab').forEach(btn => {
        btn.style.background = '#f8f9fa';
        btn.style.color = '#333';
    });
    const activeBtn = document.getElementById('sub-tab-' + subTab);
    if (activeBtn) {
        activeBtn.style.background = '#007bff';
        activeBtn.style.color = 'white';
    }
    // 显示/隐藏排序按钮
    const sortBtn = document.getElementById('noDueSortBtn');
    if (sortBtn) {
        sortBtn.style.display = (subTab === 'no-due') ? 'inline-block' : 'none';
    }
    // 重新加载待办列表
    loadTodos();
}

// 切换无截止时间排序方向
function toggleNoDueSort() {
    noDueSortAsc = !noDueSortAsc;
    const sortBtn = document.getElementById('noDueSortBtn');
    if (sortBtn) {
        sortBtn.textContent = noDueSortAsc ? '📧 发件时间 ↑' : '📧 发件时间 ↓';
        sortBtn.title = noDueSortAsc ? '当前：早的在前，点击切换' : '当前：晚的在前，点击切换';
    }
    loadTodos();
}

// 加载已完成列表
async function loadCompletedTodos() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/todos?completed=true`);
        const data = await response.json();
        renderTodos(data.todos, 'completed-list', true);
    } catch (error) {
        document.getElementById('completed-list').innerHTML = '<div class="empty-state">加载失败: ' + error.message + '</div>';
    }
}

// 加载回收站
async function loadTrashTodos() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/todos/deleted`);
        const data = await response.json();
        renderTodos(data.todos, 'trash-list', false, true);
    } catch (error) {
        document.getElementById('trash-list').innerHTML = '<div class="empty-state">加载失败: ' + error.message + '</div>';
    }
}

// 渲染待办列表
function renderTodos(todos, containerId, isCompletedView, isTrashView = false) {
    const container = document.getElementById(containerId);
    
    if (todos.length === 0) {
        let emptyMsg = '暂无待办事项';
        if (isCompletedView) emptyMsg = '暂无已完成事项';
        if (isTrashView) emptyMsg = '回收站为空';
        container.innerHTML = `<div class="empty-state">${emptyMsg}</div>`;
        return;
    }

    container.innerHTML = todos.map(todo => {
        const status = isTrashView ? 'status-deleted' : getTodoStatus(todo);
        const statusLabel = isTrashView ? '🗑️ 已删除' : getStatusLabel(status);
        
        // 根据视图类型生成不同的按钮
        let actionButton = '';
        if (isTrashView) {
            actionButton = `
                <button class="complete-btn" style="background: #28a745; white-space: nowrap; flex-shrink: 0; min-width: 60px;" onclick="restoreTodo('${todo.id}')">恢复</button>
            `;
        } else {
            actionButton = `
                <button class="complete-btn" style="background: #dc3545; white-space: nowrap; flex-shrink: 0; min-width: 60px; margin-right: 8px;" onclick="deleteTodo('${todo.id}')">删除</button>
                <button class="complete-btn" style="background: ${todo.completed ? '#6c757d' : '#28a745'}; white-space: nowrap; flex-shrink: 0; min-width: 60px;" onclick="toggleComplete('${todo.id}', ${!todo.completed})">
                    ${todo.completed ? '取消' : '完成'}
                </button>
            `;
        }
        
        return `
        <div class="todo-item ${status}" onclick="openDetailModal('${todo.id}')" style="cursor: pointer;">
            <div class="todo-title">
                ${escapeHtml(todo.title)}
                ${statusLabel ? `<span style="font-size: 12px; margin-left: 10px;">${statusLabel}</span>` : ''}
            </div>
            <div class="todo-description">${escapeHtml(todo.description)}</div>
            <div class="todo-meta">
                <div style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; text-align: left;">
                    <div style="text-align: left;">
                        <span>截止: ${todo.due_date ? new Date(todo.due_date).toLocaleString('zh-CN') + ' ' + getRelativeDays(todo.due_date) : '无'}</span>
                        <span style="margin-left: 15px;">发信人: ${escapeHtml(todo.source_email_from || '未知')}</span>
                        ${todo.completed && todo.completed_at ? `<span style="margin-left: 15px;">完成于: ${new Date(todo.completed_at).toLocaleString('zh-CN')}</span>` : ''}
                        ${isTrashView && todo.deleted_at ? `<span style="margin-left: 15px;">删除于: ${new Date(todo.deleted_at).toLocaleString('zh-CN')}</span>` : ''}
                    </div>
                    <div style="margin-top: 3px; text-align: left;" class="todo-source">${todo.is_manual ? '来源: 手动录入' : '邮件标题: ' + escapeHtml(todo.source_email_subject)}</div>
                </div>
                <div onclick="event.stopPropagation();" style="margin-left: 15px; flex-shrink: 0;">
                    ${actionButton}
                </div>
            </div>
        </div>
    `}).join('');
}

// 切换完成状态
async function toggleComplete(todoId, completed) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/todos/${todoId}/complete`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({completed: completed})
        });
        if (response.ok) {
            refreshCurrentView();
        }
    } catch (error) {
        alert('操作失败: ' + error.message);
    }
}

// 恢复待办
async function restoreTodo(todoId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/todos/${todoId}/restore`, {
            method: 'PUT'
        });
        if (response.ok) {
            loadTrashTodos();
            // 同时刷新其他视图
            loadTodos();
            loadCompletedTodos();
        }
    } catch (error) {
        alert('恢复失败: ' + error.message);
    }
}

// 删除待办
async function deleteTodo(todoId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/todos/${todoId}/delete`, {
            method: 'PUT'
        });
        if (response.ok) {
            refreshCurrentView();
        }
    } catch (error) {
        alert('删除失败: ' + error.message);
    }
}

// ========== 详情弹窗功能 ==========

// 打开详情弹窗
async function openDetailModal(todoId) {
    currentDetailTodoId = todoId;
    try {
        const response = await fetch(`${API_BASE_URL}/api/todos/${todoId}`);
        const data = await response.json();
        currentDetailTodo = data.todo;
        
        // 填充表单
        document.getElementById('detailTitle').value = currentDetailTodo.title || '';
        document.getElementById('detailDescription').value = currentDetailTodo.description || '';
        document.getElementById('detailCompleted').checked = currentDetailTodo.completed || false;
        document.getElementById('detailCreatedAt').textContent = currentDetailTodo.created_at ? 
            new Date(currentDetailTodo.created_at).toLocaleString('zh-CN') : '未知';
        
        // 填充原邮件信息
        document.getElementById('detailSource').textContent = currentDetailTodo.source_email_subject || '无';
        document.getElementById('detailFrom').textContent = currentDetailTodo.source_email_from || '未知';
        document.getElementById('detailTo').textContent = currentDetailTodo.source_email_to || '未知';
        // 抄送：有内容时显示，无内容时隐藏整行
        const ccRow = document.getElementById('detailCcRow');
        const ccValue = currentDetailTodo.source_email_cc;
        if (ccValue && ccValue.trim()) {
            document.getElementById('detailCc').textContent = ccValue;
            ccRow.style.display = 'block';
        } else {
            ccRow.style.display = 'none';
        }
        document.getElementById('detailEmailDate').textContent = currentDetailTodo.source_email_date ? 
            new Date(currentDetailTodo.source_email_date).toLocaleString('zh-CN') : '未知';
        document.getElementById('detailEmailBody').textContent = currentDetailTodo.source_email_body || '(无正文)';
        // 手动创建的待办隐藏原邮件信息
        const emailInfo = document.getElementById('detailEmailInfo');
        if (emailInfo) {
            emailInfo.style.display = currentDetailTodo.is_manual ? 'none' : 'block';
        }
        
        // 处理截止日期
        if (currentDetailTodo.due_date) {
            const dueDate = new Date(currentDetailTodo.due_date);
            // 转换为 datetime-local 格式
            const localDateStr = dueDate.getFullYear() + '-' + 
                String(dueDate.getMonth() + 1).padStart(2, '0') + '-' +
                String(dueDate.getDate()).padStart(2, '0') + 'T' +
                String(dueDate.getHours()).padStart(2, '0') + ':' +
                String(dueDate.getMinutes()).padStart(2, '0');
            document.getElementById('detailDueDate').value = localDateStr;
        } else {
            document.getElementById('detailDueDate').value = '';
        }
        
        // 根据是否已删除显示不同的按钮
        const deleteBtn = document.getElementById('detailDeleteBtn');
        if (currentDetailTodo.deleted) {
            deleteBtn.textContent = '恢复';
            deleteBtn.style.background = '#28a745';
        } else {
            deleteBtn.textContent = '删除';
            deleteBtn.style.background = '#dc3545';
        }
        
        // 显示弹窗
        document.querySelector('#detailModal .modal').style.transform = `scale(${currentZoom})`;
        document.getElementById('detailModal').classList.add('active');
    } catch (error) {
        alert('加载详情失败: ' + error.message);
    }
}

// 清除截止日期
function clearDueDate() {
    document.getElementById('detailDueDate').value = '';
}

// 关闭详情弹窗
function closeDetailModal() {
    document.getElementById('detailModal').classList.remove('active');
    currentDetailTodoId = null;
    currentDetailTodo = null;
}

// 保存待办详情
async function saveTodoDetail() {
    if (!currentDetailTodoId) return;
    
    const title = document.getElementById('detailTitle').value.trim();
    const description = document.getElementById('detailDescription').value.trim();
    const completed = document.getElementById('detailCompleted').checked;
    const dueDateValue = document.getElementById('detailDueDate').value;
    
    if (!title) {
        alert('标题不能为空');
        return;
    }
    
    try {
        const body = {
            title: title,
            description: description,
            completed: completed
        };
        
        // 处理截止日期：有值则设置，空则清除
        if (dueDateValue) {
            body.due_date = new Date(dueDateValue).toISOString();
        } else {
            // 明确发送空字符串表示清除截止日期
            body.due_date = "";
        }
        
        const response = await fetch(`${API_BASE_URL}/api/todos/${currentDetailTodoId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        
        if (response.ok) {
            closeDetailModal();
            refreshCurrentView();
        } else {
            const data = await response.json();
            alert('保存失败: ' + (data.detail || '未知错误'));
        }
    } catch (error) {
        alert('保存失败: ' + error.message);
    }
}

// 从详情弹窗删除待办
async function deleteTodoFromDetail() {
    if (!currentDetailTodoId || !currentDetailTodo) return;
    
    if (currentDetailTodo.deleted) {
        // 恢复
        await restoreTodo(currentDetailTodoId);
    } else {
        // 删除（可在回收站恢复，无需确认）
        await deleteTodo(currentDetailTodoId);
    }
    closeDetailModal();
}

// ========== 手动新增待办弹窗 ==========

// 打开新增待办弹窗
function showAddManualModal() {
    document.getElementById('manualTitle').value = '';
    document.getElementById('manualDescription').value = '';
    document.getElementById('manualDueDate').value = '';
    document.querySelector('#addManualModal .modal').style.transform = `scale(${currentZoom})`;
    document.getElementById('addManualModal').classList.add('active');
    document.getElementById('manualTitle').focus();
}

// 关闭新增待办弹窗
function closeAddManualModal() {
    document.getElementById('addManualModal').classList.remove('active');
}

// 保存手动新增的待办
async function saveManualTodo() {
    const title = document.getElementById('manualTitle').value.trim();
    const description = document.getElementById('manualDescription').value.trim();
    const dueDateValue = document.getElementById('manualDueDate').value;

    if (!title) {
        alert('标题不能为空');
        return;
    }

    const body = {
        title: title,
        description: description || null
    };
    if (dueDateValue) {
        body.due_date = new Date(dueDateValue).toISOString();
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/todos`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        if (response.ok) {
            closeAddManualModal();
            refreshCurrentView();
        } else {
            const data = await response.json();
            alert('创建失败: ' + (data.detail || '未知错误'));
        }
    } catch (error) {
        alert('创建失败: ' + error.message);
    }
}

// 初始化新增待办弹窗事件
function initAddManualModalEvents() {
    document.getElementById('addManualModal').addEventListener('mousedown', function(e) {
        if (e.target === this) {
            closeAddManualModal();
        }
    });
}

// ========== 导出待办弹窗 ==========

// 计算 YYYY-MM-DD 字符串（本地时区）
function _toDateStr(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

// 打开导出弹窗（默认最近 7 天）
function showExportModal() {
    const today = new Date();
    const endStr = _toDateStr(today);
    const start = new Date(today);
    start.setDate(today.getDate() - 6);
    const startStr = _toDateStr(start);
    document.getElementById('exportStartDate').value = startStr;
    document.getElementById('exportEndDate').value = endStr;
    document.getElementById('exportFormat').value = 'csv';
    document.getElementById('exportOnlyPending').checked = false;
    document.querySelector('#exportModal .modal').style.transform = `scale(${currentZoom})`;
    document.getElementById('exportModal').classList.add('active');
    refreshExportCount();
}

// 关闭导出弹窗
function closeExportModal() {
    document.getElementById('exportModal').classList.remove('active');
}

// 刷新「本时间段共 N 条」预览
async function refreshExportCount() {
    const tip = document.getElementById('exportCountTip');
    const start = document.getElementById('exportStartDate').value;
    const end = document.getElementById('exportEndDate').value;
    if (!start || !end) {
        tip.textContent = '请选择开始和结束日期';
        return;
    }
    if (start > end) {
        tip.textContent = '⚠️ 开始日期不能晚于结束日期';
        return;
    }
    const onlyPending = document.getElementById('exportOnlyPending').checked;
    const params = new URLSearchParams({
        start_date: start,
        end_date: end,
        count_only: 'true'
    });
    if (onlyPending) params.set('completed', 'false');
    try {
        const resp = await fetch(`${API_BASE_URL}/api/todos/export?${params.toString()}`);
        if (!resp.ok) {
            tip.textContent = '查询数量失败';
            return;
        }
        const data = await resp.json();
        tip.textContent = `本时间段共 ${data.count} 条待办`;
    } catch (e) {
        tip.textContent = '查询数量失败: ' + e.message;
    }
}

// 执行导出（触发浏览器下载）
async function exportTodos() {
    const start = document.getElementById('exportStartDate').value;
    const end = document.getElementById('exportEndDate').value;
    const fmt = document.getElementById('exportFormat').value;
    const onlyPending = document.getElementById('exportOnlyPending').checked;

    if (!start || !end) {
        alert('请选择开始和结束日期');
        return;
    }
    if (start > end) {
        alert('开始日期不能晚于结束日期');
        return;
    }

    const params = new URLSearchParams({
        start_date: start,
        end_date: end,
        format: fmt
    });
    if (onlyPending) params.set('completed', 'false');

    const url = `${API_BASE_URL}/api/todos/export?${params.toString()}`;
    try {
        const resp = await fetch(url);
        if (!resp.ok) {
            let msg = '导出失败';
            try { msg = '导出失败: ' + (await resp.text()); } catch (e) {}
            alert(msg);
            return;
        }
        const blob = await resp.blob();
        // 从 Content-Disposition 取文件名，兼容带引号 / 不带引号
        const cd = resp.headers.get('Content-Disposition') || '';
        let filename = `todos_${start}_${end}.${fmt}`;
        const fm = cd.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)/i);
        if (fm) filename = fm[1].replace(/^["']|["']$/g, '');

        const a = document.createElement('a');
        const objectUrl = URL.createObjectURL(blob);
        a.href = objectUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(objectUrl);

        closeExportModal();
    } catch (e) {
        alert('导出失败: ' + e.message);
    }
}

// 初始化导出弹窗事件
function initExportModalEvents() {
    document.getElementById('exportModal').addEventListener('mousedown', function(e) {
        if (e.target === this) {
            closeExportModal();
        }
    });
}

// 打开报告弹窗（默认周报，自动算日期范围）
function showReportModal(period) {
    const p = period || 'weekly';
    const radios = document.querySelectorAll('input[name="reportPeriod"]');
    radios.forEach(r => { r.checked = (r.value === p); });
    _applyReportPeriod(p);
    document.querySelector('#reportModal .modal').style.transform = `scale(${currentZoom})`;
    document.getElementById('reportModal').classList.add('active');
}

// 关闭报告弹窗
function closeReportModal() {
    document.getElementById('reportModal').classList.remove('active');
}

// 根据周期类型计算默认日期范围（本周一~今天 / 今天 / 本月1号~今天）
function _applyReportPeriod(period) {
    const today = new Date();
    const endStr = _toDateStr(today);
    let start;
    if (period === 'daily') {
        start = today;
    } else if (period === 'monthly') {
        start = new Date(today.getFullYear(), today.getMonth(), 1);
    } else { // weekly：本周一 ~ 今天
        start = new Date(today);
        const dow = (today.getDay() + 6) % 7; // 周一=0
        start.setDate(today.getDate() - dow);
    }
    document.getElementById('reportStartDate').value = _toDateStr(start);
    document.getElementById('reportEndDate').value = endStr;
}

// 生成并下载 Word 报告
async function generateReport() {
    const start = document.getElementById('reportStartDate').value;
    const end = document.getElementById('reportEndDate').value;
    const periodEl = document.querySelector('input[name="reportPeriod"]:checked');
    const period = periodEl ? periodEl.value : 'weekly';

    if (!start || !end) {
        alert('请选择开始和结束日期');
        return;
    }
    if (start > end) {
        alert('开始日期不能晚于结束日期');
        return;
    }

    const params = new URLSearchParams({ start_date: start, end_date: end, period });
    const url = `${API_BASE_URL}/api/todos/report?${params.toString()}`;
    try {
        const resp = await fetch(url);
        if (!resp.ok) {
            let msg = '生成失败';
            try { msg = '生成失败: ' + (await resp.text()); } catch (e) {}
            alert(msg);
            return;
        }
        const blob = await resp.blob();
        const cd = resp.headers.get('Content-Disposition') || '';
        let filename = `工作报告_${start}_${end}.docx`;
        const fmStar = cd.match(/filename\*=UTF-8''([^;]+)/i);
        const fmPlain = cd.match(/filename="?([^";]+)"?/i);
        if (fmStar) {
            try { filename = decodeURIComponent(fmStar[1]); } catch (e) { filename = fmStar[1]; }
        } else if (fmPlain) {
            filename = fmPlain[1];
        }

        const a = document.createElement('a');
        const objectUrl = URL.createObjectURL(blob);
        a.href = objectUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(objectUrl);

        closeReportModal();
    } catch (e) {
        alert('生成失败: ' + e.message);
    }
}

// 初始化报告弹窗事件
function initReportModalEvents() {
    document.getElementById('reportModal').addEventListener('mousedown', function(e) {
        if (e.target === this) {
            closeReportModal();
        }
    });
}

// 初始化详情弹窗事件
function initDetailModalEvents() {
    // 点击弹窗外部关闭（使用 mousedown 避免拖选文字时误关闭）
    document.getElementById('detailModal').addEventListener('mousedown', function(e) {
        if (e.target === this) {
            closeDetailModal();
        }
    });
}
