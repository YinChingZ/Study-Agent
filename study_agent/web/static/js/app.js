class StudyAgentWS {
    constructor() {
        this.ws = null;
        this.handlers = [];
        this.connect();
    }

    connect() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${location.host}/ws`);
        this.ws.onopen = () => {
            const statusTag = document.getElementById('global-status');
            if (statusTag) statusTag.textContent = '状态：已连接';
        };
        this.ws.onmessage = (msg) => {
            const event = JSON.parse(msg.data);
            this.handlers.forEach(handler => handler(event));
        };
        this.ws.onclose = () => {
            const statusTag = document.getElementById('global-status');
            if (statusTag) statusTag.textContent = '状态：重连中';
            setTimeout(() => this.connect(), 2000);
        };
    }

    onEvent(handler) {
        this.handlers.push(handler);
    }
}

window.agentWS = new StudyAgentWS();

const DASHBOARD_STATE_KEY = 'studyagent.dashboard.state.v1';

window.dashboard = function () {
    return {
        status: 'idle',
        progress: { current: 0, total: 0 },
        logs: [],
        screenshot: null,
        elapsed: 0,
        url: '',
        task: '',
        timer: null,
        startedAt: null,

        init() {
            this.loadPersistedState();
            window.agentWS.onEvent((event) => this.handleWSMessage(event));
            this.syncStatus();
            window.addEventListener('beforeunload', () => this.persistState());
            this.$watch('url', () => this.persistState());
            this.$watch('task', () => this.persistState());
        },

        compactLogsForStorage() {
            return this.logs.slice(-120).map((item) => ({
                id: item.id,
                time: item.time,
                color: item.color,
                text: String(item.text || '').slice(0, 400),
            }));
        },

        loadPersistedState() {
            try {
                const raw = localStorage.getItem(DASHBOARD_STATE_KEY);
                if (!raw) return;
                const saved = JSON.parse(raw);
                this.status = saved.status || this.status;
                this.progress = saved.progress || this.progress;
                this.logs = Array.isArray(saved.logs) ? saved.logs.slice(-200) : this.logs;
                this.screenshot = saved.screenshot || null;
                this.url = saved.url || '';
                this.task = saved.task || '';
                this.startedAt = saved.startedAt || null;
                if (typeof saved.elapsed === 'number') {
                    this.elapsed = Math.max(0, Math.floor(saved.elapsed));
                }
                if (this.status === 'running') {
                    this.startTimer();
                }
            } catch {
                return;
            }
        },

        persistState() {
            const safeScreenshot = this.screenshot && this.screenshot.length < 800000
                ? this.screenshot
                : null;
            const payload = {
                status: this.status,
                progress: this.progress,
                logs: this.compactLogsForStorage(),
                screenshot: safeScreenshot,
                elapsed: this.elapsed,
                url: this.url,
                task: this.task,
                startedAt: this.startedAt,
            };
            try {
                localStorage.setItem(DASHBOARD_STATE_KEY, JSON.stringify(payload));
            } catch {
                return;
            }
        },

        startTimer() {
            if (!this.startedAt) {
                this.startedAt = Date.now();
            }
            if (this.timer) return;
            this.timer = setInterval(() => {
                this.elapsed = Math.max(0, Math.floor((Date.now() - this.startedAt) / 1000));
                this.persistState();
            }, 1000);
        },

        stopTimer() {
            if (this.timer) {
                clearInterval(this.timer);
            }
            this.timer = null;
        },

        async syncStatus() {
            const res = await fetch('/api/task/status');
            const data = await res.json();
            this.status = data.status || 'idle';
            if (data.waiting_login) {
                this.addLog('已打开任务页面，请先登录后点击“恢复”', 'text-yellow-400');
            }
            if (this.status === 'running') {
                this.startTimer();
            }
            this.persistState();
        },

        get progressPercent() {
            if (!this.progress.total) return 0;
            return Math.min(100, Math.round(this.progress.current * 100 / this.progress.total));
        },

        get statusText() {
            const map = {
                idle: '空闲',
                running: '运行中',
                paused: '已暂停',
                stopped: '已停止',
                finished: '已完成',
                error: '错误',
            };
            return `当前状态：${map[this.status] || this.status}`;
        },

        get elapsedText() {
            const sec = this.elapsed % 60;
            const min = Math.floor(this.elapsed / 60);
            return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
        },

        addLog(text, color = 'text-gray-200') {
            this.logs.push({
                id: Date.now() + Math.random(),
                time: new Date().toLocaleTimeString(),
                text: String(text || '').slice(0, 800),
                color,
            });
            if (this.logs.length > 200) {
                this.logs = this.logs.slice(-200);
            }
            this.persistState();
            this.$nextTick(() => {
                const el = document.getElementById('log-scroll');
                if (el) el.scrollTop = el.scrollHeight;
            });
        },

        async startTask() {
            const res = await fetch('/api/task/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: this.url || null, task_description: this.task || null }),
            });
            const data = await res.json();
            if (data.status === 'started') {
                this.status = 'running';
                this.elapsed = 0;
                this.startedAt = Date.now();
                this.stopTimer();
                this.startTimer();
                this.addLog('任务已启动', 'text-blue-400');
            } else if (data.status === 'paused' && data.waiting_login) {
                this.status = 'paused';
                this.addLog(data.message || '等待登录中，请点击“恢复”', 'text-yellow-400');
            } else {
                this.addLog(data.message || '启动失败', 'text-red-400');
            }
            this.persistState();
        },

        async pauseTask() {
            const res = await fetch('/api/task/pause', { method: 'POST' });
            const data = await res.json();
            this.status = data.status || 'paused';
            this.addLog('任务已暂停', 'text-yellow-400');
            this.persistState();
        },

        async resumeTask() {
            const res = await fetch('/api/task/resume', { method: 'POST' });
            const data = await res.json();
            this.status = data.status || 'running';
            if (this.status === 'running') {
                this.startTimer();
                this.addLog(data.message || '任务已恢复', 'text-emerald-400');
            } else {
                this.addLog(data.message || '恢复失败', 'text-red-400');
            }
            this.persistState();
        },

        async stopTask() {
            const res = await fetch('/api/task/stop', { method: 'POST' });
            const data = await res.json();
            this.status = data.status || 'stopped';
            this.stopTimer();
            this.addLog('任务已停止', 'text-red-400');
            this.persistState();
        },

        handleWSMessage(event) {
            const type = event.type;
            const data = event.data || {};

            if (type === 'task_started') {
                this.status = 'running';
                if (!this.startedAt) {
                    this.startedAt = Date.now();
                }
                this.startTimer();
                this.addLog('任务开始执行', 'text-blue-400');
            } else if (type === 'task_paused') {
                this.status = 'paused';
                this.addLog('任务已暂停，等待你登录后点击“恢复”', 'text-yellow-400');
            } else if (type === 'task_resumed') {
                this.status = 'running';
                this.startTimer();
                this.addLog('任务恢复执行', 'text-emerald-400');
            } else if (type === 'task_finished') {
                this.status = 'finished';
                this.stopTimer();
                this.addLog('任务完成', 'text-green-400');
            } else if (type === 'task_error') {
                this.status = 'error';
                this.stopTimer();
                this.addLog(`任务错误：${data.error || ''}`, 'text-red-400');
            } else if (type === 'question_found') {
                this.addLog(`发现题目：${data.question || ''}`, 'text-blue-300');
            } else if (type === 'solver_calling') {
                this.addLog('Solver 推理中...', 'text-yellow-300');
            } else if (type === 'solver_answered') {
                this.addLog(`Solver 答案：${data.answer || ''}`, 'text-green-300');
            } else if (type === 'screenshot') {
                this.screenshot = data.image || null;
                this.persistState();
            } else if (type === 'progress') {
                this.progress.current = data.current || 0;
                this.progress.total = data.total || 0;
                this.persistState();
            } else if (type === 'log') {
                this.addLog(data.message || '', 'text-gray-200');
            }
        }
    };
};

window.settingsPage = function () {
    return {
        sameAsBrowser: false,
        form: {
            api_keys: {
                OPENAI_API_KEY: '',
                ANTHROPIC_API_KEY: '',
                GOOGLE_API_KEY: '',
            },
            browser_llm: { provider: 'openai', model: '', base_url: '' },
            solver_llm: { provider: 'openai', model: '', base_url: '' },
            browser: { cdp_url: 'http://localhost:9222', auto_launch_chrome: true, cdp_port: 9222 },
            agent: { use_vision: true, use_thinking: true, max_steps: 200, max_actions_per_step: 3, max_failures: 5, enable_planning: true, use_judge: true, demo_mode: true },
            task_description: '',
        },
        validateResult: '',
        chromeStatus: '检测中...',

        async loadConfig() {
            const res = await fetch('/api/config');
            this.form = await res.json();
            if (!this.form.solver_llm || !Object.keys(this.form.solver_llm).length) {
                this.form.solver_llm = { ...this.form.browser_llm };
            }
            this.sameAsBrowser = (
                (this.form.browser_llm.provider || '') === (this.form.solver_llm.provider || '')
                && (this.form.browser_llm.model || '') === (this.form.solver_llm.model || '')
                && (this.form.browser_llm.base_url || '') === (this.form.solver_llm.base_url || '')
            );
        },

        async checkChrome() {
            const res = await fetch('/api/config/chrome');
            const data = await res.json();
            if (data.installed) {
                this.chromeStatus = `✅ 已检测到 Chrome${data.running ? '（调试端口已就绪）' : ''}`;
            } else {
                this.chromeStatus = '❌ 未找到 Chrome';
            }
        },

        async validateKey(target = 'browser') {
            const llmConfig = target === 'solver' ? this.form.solver_llm : this.form.browser_llm;
            const provider = (llmConfig.provider || 'openai').toLowerCase();
            const keyMap = {
                openai: this.form.api_keys.OPENAI_API_KEY,
                anthropic: this.form.api_keys.ANTHROPIC_API_KEY,
                google: this.form.api_keys.GOOGLE_API_KEY,
            };
            const providerKey = keyMap[provider] || '';
            if (!providerKey) {
                this.validateResult = '❌ 请先填写该 Provider 对应的 API Key';
                return;
            }

            const payload = {
                provider,
                model: llmConfig.model,
                base_url: llmConfig.base_url,
                api_key: providerKey,
            };
            const res = await fetch('/api/config/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            const prefix = target === 'solver' ? 'Solver' : 'Browser';
            this.validateResult = data.ok ? `✅ ${prefix}: ${data.message}` : `❌ ${prefix}: ${data.message}`;
        },

        async saveConfig() {
            const payload = JSON.parse(JSON.stringify(this.form));
            if (this.sameAsBrowser) {
                payload.solver_llm = { ...payload.browser_llm };
            }

            const res = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            alert(data.message || '配置已保存');
        },
    };
};

window.reviewPage = function () {
    return {
        sessions: [],
        details: {},
        openSessionId: null,

        async loadSessions() {
            const res = await fetch('/api/history');
            const data = await res.json();
            this.sessions = data.items || [];
        },

        async toggleSession(sessionId) {
            if (this.openSessionId === sessionId) {
                this.openSessionId = null;
                return;
            }
            if (!this.details[sessionId]) {
                const res = await fetch(`/api/history/${sessionId}`);
                this.details[sessionId] = await res.json();
            }
            this.openSessionId = sessionId;
        },
    };
};
