/**
 * 全局配置和常量
 */

// 当前标签页状态
let currentTab = 'list';
let currentSubTab = 'with-due';  // 'with-due' 或 'no-due'
let noDueSortAsc = true;  // 无截止时间排序方向：true=升序（早的在前），false=降序（晚的在前）
let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth() + 1;

// 邮箱服务商配置
const emailServers = {
    'firefox': { server: 'pop.fastmail.com', port: 995 },  // Firefox邮箱（Fastmail）
    '163': { server: 'pop.163.com', port: 995 },
    'qq': { server: 'pop.qq.com', port: 995 },
    'gmail': { server: 'pop.gmail.com', port: 995 },
    'outlook': { server: 'outlook.office365.com', port: 995 },
    'custom': { server: '', port: 995 }
};

// 缩放相关配置
let currentZoom = 1.0;
const ZOOM_STEP = 0.1;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 5.0;

// 同步相关状态
let autoSyncTimer = null;  // 自动同步定时器
let countdownTimer = null;  // 倒计时显示定时器
let nextSyncTime = null;    // 下次同步的时间戳
let isSyncing = false;     // 是否正在同步（防止并发）
let autoSyncIntervalMinutes = 1;  // 自动同步间隔（分钟）
let currentEventSource = null;  // 当前同步的 EventSource 对象

// 服务端同步设置
let syncSettings = { only_recent_7days: false, max_emails_per_sync: 100 };

// 详情弹窗状态
let currentDetailTodoId = null;
let currentDetailTodo = null;

// 聊天相关状态
let chatMessages = [];  // 聊天消息列表
let chatMemoryEnabled = false;  // 是否开启记忆
let isChatSending = false;  // 是否正在发送消息

// API 基础地址（留空使用同源，前后端端口一致）
const API_BASE_URL = '';
