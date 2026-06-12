/**
 * 工具函数
 */

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 获取待办状态
function getTodoStatus(todo) {
    // 已完成 - 绿色
    if (todo.completed) {
        return 'status-completed';
    }
    
    // 没有截止日期 - 蓝色（正常）
    if (!todo.due_date) {
        return 'status-normal';
    }
    
    const now = new Date();
    const dueDate = new Date(todo.due_date);
    
    // 获取今天的日期（只比较年月日）
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const dueDateOnly = new Date(dueDate.getFullYear(), dueDate.getMonth(), dueDate.getDate());
    
    // 已过期（截止日期在今天之前）- 红色
    if (dueDateOnly < today) {
        return 'status-overdue';
    }
    
    // 今天截止 - 橙色
    if (dueDateOnly.getTime() === today.getTime()) {
        return 'status-today';
    }
    
    // 其他（未来截止）- 蓝色
    return 'status-normal';
}

// 获取状态标签
function getStatusLabel(status) {
    const labels = {
        'status-completed': '✓ 已完成',
        'status-overdue': '⚠ 已过期',
        'status-today': '⏰ 今天截止',
        'status-normal': ''
    };
    return labels[status] || '';
}

// 获取状态图标
function getStatusIcon(status) {
    const icons = {
        'status-completed': '✓ ',
        'status-overdue': '⚠ ',
        'status-today': '⏰ ',
        'status-normal': ''
    };
    return icons[status] || '';
}

// 获取相对天数描述
function getRelativeDays(dueDateStr) {
    if (!dueDateStr) return '';
    
    const now = new Date();
    const dueDate = new Date(dueDateStr);
    
    // 只比较日期部分
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const dueDateOnly = new Date(dueDate.getFullYear(), dueDate.getMonth(), dueDate.getDate());
    
    const diffTime = dueDateOnly.getTime() - today.getTime();
    const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
        return '(今天)';
    } else if (diffDays === 1) {
        return '(明天)';
    } else if (diffDays === 2) {
        return '(后天)';
    } else if (diffDays === -1) {
        return '(昨天)';
    } else if (diffDays === -2) {
        return '(前天)';
    } else if (diffDays > 0) {
        return `(${diffDays}天后)`;
    } else {
        return `(${Math.abs(diffDays)}天前)`;
    }
}

// 刷新当前视图
function refreshCurrentView() {
    if (currentTab === 'completed') {
        loadCompletedTodos();
    } else if (currentTab === 'calendar') {
        loadCalendar();
    } else if (currentTab === 'trash') {
        loadTrashTodos();
    } else {
        loadTodos();
    }
}
