/**
 * 日历功能
 */

// 加载日历
async function loadCalendar() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/todos/calendar?year=${currentYear}&month=${currentMonth}`);
        const data = await response.json();
        renderCalendar(data.calendar, currentYear, currentMonth);
    } catch (error) {
        document.getElementById('calendar-view').innerHTML = '<div class="empty-state">加载失败: ' + error.message + '</div>';
    }
}

// 渲染日历
function renderCalendar(calendar, year, month) {
    const container = document.getElementById('calendar-view');
    const titleDiv = document.getElementById('calendar-title');
    titleDiv.textContent = `${year}年${month}月`;

    const daysInMonth = new Date(year, month, 0).getDate();
    const firstDay = new Date(year, month - 1, 1).getDay();
    const today = new Date();
    const isCurrentMonth = year === today.getFullYear() && month === today.getMonth() + 1;
    const todayDate = today.getDate();

    let html = '<div class="calendar">';
    const weekDays = ['日', '一', '二', '三', '四', '五', '六'];

    // 星期标题
    weekDays.forEach(day => {
        html += `<div style="text-align: center; font-weight: bold; padding: 10px;">${day}</div>`;
    });

    // 空白日期
    for (let i = 0; i < firstDay; i++) {
        html += '<div class="calendar-day other-month"></div>';
    }

    // 日期
    for (let day = 1; day <= daysInMonth; day++) {
        const dateKey = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const todos = calendar[dateKey] || [];
        const isToday = isCurrentMonth && day === todayDate;
        
        html += `
            <div class="calendar-day ${isToday ? 'today' : ''}">
                <div class="calendar-day-header">${day}</div>
                ${todos.map(todo => {
                    const status = getTodoStatus(todo);
                    const icon = getStatusIcon(status);
                    return `
                    <div class="calendar-todo ${status}" title="${escapeHtml(todo.title)}${todo.completed ? ' (已完成)' : ''}" onclick="openDetailModal('${todo.id}')">
                        ${icon}${escapeHtml(todo.title)}
                    </div>
                `}).join('')}
            </div>
        `;
    }

    html += '</div>';
    container.innerHTML = html;
}

// 上个月
function prevMonth() {
    currentMonth--;
    if (currentMonth < 1) {
        currentMonth = 12;
        currentYear--;
    }
    loadCalendar();
}

// 下个月
function nextMonth() {
    currentMonth++;
    if (currentMonth > 12) {
        currentMonth = 1;
        currentYear++;
    }
    loadCalendar();
}
