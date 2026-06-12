/**
 * 已转发邮件（知会流）
 * 这些条目不进入待办：邮件已委派/通知给他人，邮箱主人只需"知悉"。
 */

let forwardedSubTab = 'unread';

function switchForwardedSubTab(sub) {
    forwardedSubTab = sub;
    document.querySelectorAll('#forwarded-tab .sub-tab').forEach(btn => {
        btn.style.background = '#f8f9fa';
        btn.style.color = '#333';
    });
    const active = document.getElementById('fwd-sub-' + sub);
    if (active) {
        active.style.background = '#007bff';
        active.style.color = 'white';
    }
    loadForwardedEmails();
}

async function loadForwardedEmails() {
    const container = document.getElementById('forwarded-list');
    if (!container) return;
    container.innerHTML = '<div class="loading">加载中...</div>';
    try {
        const onlyUnread = forwardedSubTab === 'unread';
        const resp = await fetch(`${API_BASE_URL}/api/forwarded?only_unread=${onlyUnread ? 'true' : 'false'}&limit=300`);
        const data = await resp.json();
        renderForwardedEmails(data.items || []);
        updateForwardedBadge(data.unread_count || 0);
    } catch (e) {
        container.innerHTML = '<div class="empty-state">加载失败: ' + e.message + '</div>';
    }
}

function renderForwardedEmails(items) {
    const container = document.getElementById('forwarded-list');
    if (!items.length) {
        const msg = forwardedSubTab === 'unread'
            ? '暂无未读已转发邮件<br><span style="font-size:12px;color:#999;">命中转发规则的邮件会出现在这里</span>'
            : '暂无已转发邮件';
        container.innerHTML = `<div class="empty-state">${msg}</div>`;
        return;
    }

    container.innerHTML = items.map(item => {
        const dt = item.forwarded_at ? new Date(item.forwarded_at).toLocaleString('zh-CN') : '';
        const origDt = item.original_date ? new Date(item.original_date).toLocaleString('zh-CN') : '';
        const recipients = (item.recipients || []).map(r =>
            `<span style="display:inline-block; background:#e3f2fd; color:#0056b3; padding:2px 8px; border-radius:12px; font-size:12px; margin:2px;">${escapeHtml(r)}</span>`
        ).join('');
        const unreadDot = item.read
            ? ''
            : '<span style="display:inline-block; width:8px; height:8px; background:#dc3545; border-radius:50%; margin-right:8px; vertical-align:middle;" title="未读"></span>';
        const bg = item.read ? '#fafafa' : '#fff';
        const borderL = item.read ? '#cfd8dc' : '#2196f3';

        const preview = (item.body_preview || '').slice(0, 200);
        const previewHtml = preview
            ? `<div style="margin-top:6px; padding:8px 10px; background:#f8f9fa; border-radius:4px; font-size:12px; color:#666; white-space:pre-wrap; line-height:1.5; max-height:80px; overflow:hidden;">${escapeHtml(preview)}${item.body_preview && item.body_preview.length > 200 ? '...' : ''}</div>`
            : '';

        return `
        <div class="forwarded-item" style="background:${bg}; border:1px solid #e0e0e0; border-left:4px solid ${borderL}; border-radius:6px; padding:12px 14px; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px;">
                <div style="flex:1; min-width:0;">
                    <div style="font-size:15px; font-weight:600; color:#333; margin-bottom:4px;">
                        ${unreadDot}${escapeHtml(item.subject || '(无主题)')}
                    </div>
                    <div style="font-size:12px; color:#666; margin-bottom:6px;">
                        <span>发件人: ${escapeHtml(item.from_addr || '未知')}</span>
                        ${origDt ? `<span style="margin-left:12px;">邮件时间: ${origDt}</span>` : ''}
                    </div>
                    <div style="display:flex; align-items:center; flex-wrap:wrap; gap:4px; margin-bottom:4px;">
                        <span style="font-size:12px; color:#888;">已转发给:</span>
                        ${recipients}
                    </div>
                    <div style="font-size:12px; color:#888;">
                        <span>规则: ${escapeHtml(item.rule_description || '(已删除)')}</span>
                        ${item.reason ? `<span style="margin-left:10px;">理由: ${escapeHtml(item.reason)}</span>` : ''}
                        <span style="margin-left:10px;">转发于: ${dt}</span>
                    </div>
                    ${previewHtml}
                </div>
                <div style="flex-shrink:0;">
                    ${item.read
                        ? `<button onclick="setForwardedRead('${item.email_id}', '${item.rule_id}', false)" style="padding:4px 10px; background:#f8f9fa; color:#666; border:1px solid #ddd; border-radius:4px; cursor:pointer; font-size:12px;">标为未读</button>`
                        : `<button onclick="setForwardedRead('${item.email_id}', '${item.rule_id}', true)" style="padding:4px 10px; background:#28a745; color:white; border:none; border-radius:4px; cursor:pointer; font-size:12px;">已知悉</button>`
                    }
                </div>
            </div>
        </div>
        `;
    }).join('');
}

async function setForwardedRead(emailId, ruleId, read) {
    try {
        await fetch(`${API_BASE_URL}/api/forwarded/read`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email_id: emailId, rule_id: ruleId, read })
        });
        loadForwardedEmails();
    } catch (e) {
        alert('操作失败: ' + e.message);
    }
}

async function markAllForwardedRead() {
    try {
        const resp = await fetch(`${API_BASE_URL}/api/forwarded/read-all`, { method: 'PUT' });
        const data = await resp.json();
        if (data.success) loadForwardedEmails();
    } catch (e) {
        alert('操作失败: ' + e.message);
    }
}

function updateForwardedBadge(count) {
    const badge = document.getElementById('forwardedBadge');
    if (!badge) return;
    if (count > 0) {
        badge.textContent = count > 99 ? '99+' : count;
        badge.style.display = 'inline-block';
    } else {
        badge.style.display = 'none';
    }
}

async function refreshForwardedBadge() {
    try {
        const resp = await fetch(`${API_BASE_URL}/api/forwarded/unread-count`);
        const data = await resp.json();
        updateForwardedBadge(data.unread_count || 0);
    } catch (e) {
        // 静默失败：角标不可用不影响主流程
    }
}
