// 流水线任务中心：一键训练任务的列表、详情（阶段/闸门/视频漏斗/类别统计/帧浏览/复核）、API Key 管理
// 定位问题的路径：任务列表 → 详情里看哪个阶段失败、哪项闸门超阈值 → 点"查看帧"只看问题帧 → 逐帧通过/丢弃或在标注页修改
class PipelineCenter {
    constructor() {
        this.refreshTimer = null;
        this.currentRunId = null;
        this.frameFilter = {};
        this.frameSkip = 0;
        this.frameLimit = 48;
        this.lastFrames = [];
        this.layers = { vlm: false, sam: false, final: true };
        this.statusText = {
            queued: '排队中', running: '运行中', needs_review: '待复核', succeeded: '已完成',
            failed: '失败', cancelling: '取消中', cancelled: '已取消',
        };
        this.statusBadge = {
            queued: 'bg-secondary', running: 'bg-primary', needs_review: 'bg-warning text-dark', succeeded: 'bg-success',
            failed: 'bg-danger', cancelling: 'bg-secondary', cancelled: 'bg-secondary',
        };
        this.stageStatusBadge = {
            completed: 'bg-success', skipped: 'bg-light text-dark border', running: 'bg-primary', paused: 'bg-warning text-dark',
            failed: 'bg-danger', cancelled: 'bg-secondary', pending: 'bg-light text-muted border',
        };
        this.reviewText = { auto_accepted: '自动通过', to_review: '待复核', accepted: '人工通过', modified: '已修改', discarded: '已丢弃' };
        this.reasonText = {
            vlm_failed: '模型调用失败', no_box: '未检出', multi_box: '多框', sam_fallback: 'SAM 回退', temporal_outlier: '框跳变',
            label_mismatch: '类别名不一致', edge_truncated: '贴边/截断', tiny_box: '框过小',
        };
    }

    // ---------------------------------------------------------------- 工具
    esc(v) {
        return String(v === null || v === undefined ? '' : v)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    fmtTime(iso) {
        return iso ? new Date(iso).toLocaleString() : '-';
    }

    pct(v) {
        return (v === null || v === undefined) ? '-' : `${(v * 100).toFixed(1)}%`;
    }

    async api(path, options = {}) {
        const opts = { ...options };
        if (opts.json !== undefined) {
            opts.method = opts.method || 'POST';
            opts.headers = { ...(opts.headers || {}), 'Content-Type': 'application/json' };
            opts.body = JSON.stringify(opts.json);
            delete opts.json;
        }
        const res = await authenticatedFetch(`${API_URL}/pipeline${path}`, opts);
        let data = null;
        try { data = await res.json(); } catch (e) { /* 非 JSON 响应 */ }
        if (!res.ok) {
            throw new Error((data && (data.detail || (data.error && data.error.message))) || `请求失败（HTTP ${res.status}）`);
        }
        return data;
    }

    // ---------------------------------------------------------------- 生命周期
    init() {
        this.currentRunId = null;
        const root = document.getElementById('pipeline-root');
        if (!root) return;
        document.getElementById('pipeline-search-btn').addEventListener('click', () => this.loadRuns());
        document.getElementById('pipeline-search').addEventListener('keydown', (e) => { if (e.key === 'Enter') this.loadRuns(); });
        document.getElementById('pipeline-status-filter').addEventListener('change', () => this.loadRuns());
        document.getElementById('pipeline-back-btn').addEventListener('click', () => this.showList());
        document.getElementById('pipeline-create-btn').addEventListener('click', () => this.openCreateModal());
        document.getElementById('pipeline-apikeys-btn').addEventListener('click', () => this.openApiKeys());
        if (currentUser && currentUser.role && currentUser.role.toLowerCase() === 'admin') {
            document.getElementById('pipeline-apikeys-btn').style.display = 'inline-block';
        }
        this.showList();
        this.refreshTimer = window.memoryManager.setInterval(() => this.autoRefresh(), 5000);
    }

    stop() {
        if (this.refreshTimer) {
            window.memoryManager.clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    autoRefresh() {
        if (!document.getElementById('pipeline-root')) { this.stop(); return; }
        if (document.hidden) return;
        if (this.currentRunId) {
            this.loadDetail(this.currentRunId, true);
        } else {
            this.loadRuns(true);
        }
    }

    showList() {
        this.currentRunId = null;
        document.getElementById('pipeline-list-view').style.display = 'block';
        document.getElementById('pipeline-detail-view').style.display = 'none';
        this.loadRuns();
    }

    // ---------------------------------------------------------------- 列表
    async loadRuns(silent = false) {
        const q = document.getElementById('pipeline-search').value.trim();
        const status = document.getElementById('pipeline-status-filter').value;
        const params = new URLSearchParams({ limit: '100' });
        if (q) params.set('q', q);
        if (status) params.set('status', status);
        const tbody = document.getElementById('pipeline-runs-body');
        try {
            const data = await this.api(`/runs?${params}`);
            if (!data.items.length) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">暂无任务。可通过对外接口 /api/v1/pipeline/jobs 或右上角“新建任务”创建</td></tr>';
                return;
            }
            tbody.innerHTML = data.items.map(r => {
                const overall = r.progress ? r.progress.overall : 0;
                const source = r.source === 'api' ? `接口${r.api_key_name ? `（${this.esc(r.api_key_name)}）` : ''}` : '控制台';
                const error = r.error ? `<div class="small text-danger text-truncate" style="max-width:320px" title="${this.esc(r.error.message)}">${this.esc(r.error.code)}：${this.esc(r.error.message)}</div>` : '';
                return `<tr class="pipeline-run-row" data-id="${r.job_id}" style="cursor:pointer">
                    <td><div class="fw-semibold">${this.esc(r.name)}</div><div class="small text-muted">${r.job_id.slice(0, 8)}${r.external_ref ? ' · ' + this.esc(r.external_ref) : ''}</div>${error}</td>
                    <td><span class="badge ${this.statusBadge[r.status] || 'bg-secondary'}">${this.statusText[r.status] || this.esc(r.status)}</span></td>
                    <td>${this.esc(r.stage || '-')}</td>
                    <td style="min-width:140px"><div class="progress" style="height:8px"><div class="progress-bar" style="width:${(overall * 100).toFixed(0)}%"></div></div><div class="small text-muted">${(overall * 100).toFixed(0)}%</div></td>
                    <td>${r.video_count}</td>
                    <td>${source}</td>
                    <td>${r.llm_cost_usd ? '$' + r.llm_cost_usd.toFixed(3) : '-'}</td>
                    <td class="small">${this.fmtTime(r.created_at)}</td>
                </tr>`;
            }).join('');
            tbody.querySelectorAll('.pipeline-run-row').forEach(tr => tr.addEventListener('click', () => this.openDetail(tr.dataset.id)));
        } catch (e) {
            if (!silent) tbody.innerHTML = `<tr><td colspan="8" class="text-danger">加载失败：${this.esc(e.message)}</td></tr>`;
        }
    }

    // ---------------------------------------------------------------- 详情
    openDetail(runId) {
        this.currentRunId = runId;
        this.frameFilter = {};
        this.frameSkip = 0;
        document.getElementById('pipeline-list-view').style.display = 'none';
        document.getElementById('pipeline-detail-view').style.display = 'block';
        document.getElementById('pipeline-detail').innerHTML = '<div class="text-muted p-3">加载中...</div>';
        this.loadDetail(runId);
    }

    async loadDetail(runId, silent = false) {
        try {
            const run = await this.api(`/runs/${runId}`);
            if (this.currentRunId !== runId) return;
            this.run = run;
            this.renderDetail(run);
            if (!silent || !this.framesLoadedOnce) {
                this.framesLoadedOnce = true;
                this.loadFrames();
            }
            this.loadEvents();
        } catch (e) {
            if (!silent) document.getElementById('pipeline-detail').innerHTML = `<div class="alert alert-danger">加载失败：${this.esc(e.message)}</div>`;
        }
    }

    renderDetail(run) {
        const el = document.getElementById('pipeline-detail');
        const keepFrames = document.getElementById('pipeline-frames-section');
        const keepEvents = document.getElementById('pipeline-events-section');
        const overall = run.progress ? run.progress.overall : 0;
        const actions = [];
        if (['queued', 'running', 'needs_review'].includes(run.status)) actions.push(`<button class="btn btn-outline-danger btn-sm" data-act="cancel">取消任务</button>`);
        if (['failed', 'cancelled'].includes(run.status)) actions.push(`<button class="btn btn-outline-primary btn-sm" data-act="resume">从失败阶段继续</button>`);
        if (run.status === 'needs_review') {
            actions.push(`<button class="btn btn-success btn-sm" data-act="approve">放行继续</button>`);
            actions.push(`<button class="btn btn-outline-danger btn-sm" data-act="reject">驳回</button>`);
        }
        const trainingTaskId = run.artifacts && run.artifacts.training_task_id;
        if (trainingTaskId) actions.push(`<button class="btn btn-outline-secondary btn-sm" data-act="trainlog">训练日志与曲线</button>`);
        if (run.artifacts && run.artifacts.annotation_project_id) actions.push(`<a class="btn btn-outline-secondary btn-sm" target="_blank" href="/static/annotation.html?project_id=${run.artifacts.annotation_project_id}&mode=view">只读查看标注</a>`);

        const errorBox = run.error ? `<div class="alert alert-danger mb-3"><strong>${this.esc(run.error.code)}</strong>：${this.esc(run.error.message)}${this.renderErrorDetails(run)}</div>` : '';
        const review = run.review || {};
        const reviewBox = run.status === 'needs_review' ? `<div class="alert alert-warning mb-3">
                <div><strong>任务已暂停，等待人工处理</strong>（${review.reason === 'full_review' ? '全量复核模式' : review.reason === 'budget' ? '视觉模型费用达到预算' : '质量闸门触发'}）。</div>
                <div class="small mt-1">建议顺序：先看下方“质量闸门”中超阈值的项 → 视频类别选错的直接改类别（会自动重标该视频）、拍废的视频排除 →
                点“查看帧”逐帧通过/丢弃 → 点“放行继续”。待复核 ${run.review_counts.to_review} 帧。</div></div>` : '';

        el.innerHTML = `
            <div class="d-flex justify-content-between align-items-start mb-3">
                <div>
                    <h4 class="mb-1">${this.esc(run.name)} <span class="badge ${this.statusBadge[run.status] || 'bg-secondary'}">${this.statusText[run.status] || this.esc(run.status)}</span></h4>
                    <div class="small text-muted">ID ${run.job_id}${run.external_ref ? ' · 业务单号 ' + this.esc(run.external_ref) : ''} · 复核模式 ${this.esc(run.review_mode)}
                        · 来源 ${run.source === 'api' ? '对外接口' + (run.api_key ? `（${this.esc(run.api_key.name)}）` : '') : '控制台'} · 创建于 ${this.fmtTime(run.created_at)}</div>
                </div>
                <div class="d-flex gap-2 flex-wrap justify-content-end" id="pipeline-actions">${actions.join('')}</div>
            </div>
            <div class="progress mb-3" style="height:10px"><div class="progress-bar" style="width:${(overall * 100).toFixed(1)}%"></div></div>
            ${errorBox}${reviewBox}
            <div class="row g-3 mb-3">
                <div class="col-lg-5">${this.renderStages(run)}</div>
                <div class="col-lg-7">${this.renderGates(run)}</div>
            </div>
            <div class="row g-3 mb-3">
                <div class="col-lg-8">${this.renderVideos(run)}</div>
                <div class="col-lg-4">${this.renderClasses(run)}${this.renderResults(run)}</div>
            </div>`;
        el.appendChild(keepFrames || this.buildFramesSection());
        el.appendChild(keepEvents || this.buildEventsSection());
        this.bindDetailEvents(run);
    }

    renderErrorDetails(run) {
        const stage = (run.stages || []).find(s => s.status === 'failed');
        const details = stage && stage.error && stage.error.details;
        if (!details) return '';
        const text = details.log_tail || details.traceback || JSON.stringify(details, null, 2);
        return `<details class="mt-2"><summary class="small">详细信息</summary><pre class="small mb-0" style="max-height:240px;overflow:auto;white-space:pre-wrap">${this.esc(text)}</pre></details>`;
    }

    renderStages(run) {
        const rows = (run.stages || []).map(s => {
            const label = (run.stage_labels && run.stage_labels[s.name]) || s.name;
            const prog = s.status === 'running' && s.progress !== null && s.progress !== undefined ? ` ${(s.progress * 100).toFixed(0)}%` : '';
            const detail = s.status === 'running' && run.progress && run.progress.detail ? this.describeDetail(run.progress.detail) : '';
            const err = s.error ? `<div class="small text-danger">${this.esc(s.error.message || '')}</div>` : '';
            return `<li class="list-group-item d-flex justify-content-between align-items-start py-2">
                <div><div>${this.esc(label)}</div>${detail ? `<div class="small text-muted">${detail}</div>` : ''}${err}</div>
                <span class="badge ${this.stageStatusBadge[s.status] || 'bg-light text-dark'}">${this.esc(s.status)}${prog}</span></li>`;
        }).join('');
        return `<div class="card h-100"><div class="card-header">阶段</div><ul class="list-group list-group-flush">${rows}</ul></div>`;
    }

    describeDetail(d) {
        if (d.waiting_gpu) return `等待 GPU 空闲（已等 ${d.waited_seconds}s）`;
        if (d.epoch !== undefined) return `epoch ${d.epoch}/${d.epochs}${d.map50_95 ? `，mAP50-95 ${Number(d.map50_95).toFixed(3)}` : ''}`;
        if (d.annotated !== undefined) return `已标注 ${d.annotated}/${d.total}${d.cost_usd ? `，费用 $${Number(d.cost_usd).toFixed(3)}` : ''}`;
        if (d.video) return `视频 ${this.esc(d.video)}${d.frames ? `，${d.frames} 帧` : ''}`;
        if (d.step) return this.esc(d.step);
        return '';
    }

    renderGates(run) {
        const gates = run.gate_results || [];
        if (!gates.length) return `<div class="card h-100"><div class="card-header">质量闸门</div><div class="card-body text-muted small">自动标注完成后显示</div></div>`;
        const order = { fail: 0, pause: 1, warn: 2, ok: 3, skipped: 4 };
        const shown = gates.filter(g => g.status !== 'skipped').sort((a, b) => order[a.status] - order[b.status]);
        const badge = { fail: 'bg-danger', pause: 'bg-warning text-dark', warn: 'bg-info text-dark', ok: 'bg-success' };
        const reasonFor = { zero_box_rate: 'no_box', multi_box_rate: 'multi_box', vlm_fail_rate: 'vlm_failed', sam_fallback_rate: 'sam_fallback', temporal_jump_rate: 'temporal_outlier' };
        const rows = shown.map(g => {
            const isRate = g.metric.endsWith('rate') || g.metric.endsWith('agreement') || g.metric.endsWith('ratio') || g.metric === 'class_balance';
            const fmt = v => (v === null || v === undefined) ? '-' : (isRate ? this.pct(v) : v);
            const threshold = g.direction === 'max' ? `≤ ${fmt(g.warn)} / 暂停 > ${fmt(g.pause)}` : `≥ ${fmt(g.warn)}${g.pause !== null && g.pause !== undefined ? ` / 暂停 < ${fmt(g.pause)}` : ''}`;
            const link = g.scope === 'video' ? `<a href="#" class="small pipeline-gate-frames" data-video="${this.esc(g.key)}" data-reason="${reasonFor[g.metric] || ''}">查看帧</a>` : '';
            return `<tr><td>${this.esc(g.label)}${g.overridden ? ' <span class="badge bg-light text-dark border">已覆盖</span>' : ''}</td>
                <td>${this.esc(g.key || '整体')}</td><td>${fmt(g.value)}</td><td class="small text-muted">${threshold}</td>
                <td><span class="badge ${badge[g.status] || 'bg-secondary'}">${g.status}</span></td><td>${link}</td></tr>`;
        }).join('');
        return `<div class="card h-100"><div class="card-header">质量闸门</div><div class="card-body p-0" style="max-height:420px;overflow:auto">
            <table class="table table-sm mb-0"><thead><tr><th>指标</th><th>范围</th><th>值</th><th>阈值</th><th>结果</th><th></th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
    }

    renderVideos(run) {
        const canEdit = run.status === 'needs_review';
        const vstats = (run.metrics && run.metrics.gate && run.metrics.gate.video_stats) || {};
        const rows = (run.videos || []).map(v => {
            const st = v.stats || {};
            const clean = st.clean || {};
            const g = vstats[v.key] || {};
            const dropped = clean.dropped ? Object.entries(clean.dropped).map(([k, n]) => `${({ blur: '模糊', exposure: '曝光', duplicate: '重复', cap: '超上限' })[k] || k} ${n}`).join('，') : '';
            const cc = st.class_check;
            const ccText = cc && cc.agreement !== null && cc.agreement !== undefined
                ? `<div class="small ${cc.agreement < 0.6 ? 'text-danger' : 'text-muted'}">类别校验一致率 ${this.pct(cc.agreement)}（认出物品 ${cc.detected ?? cc.answered ?? '-'} 帧，最多：${this.esc(cc.top)}${cc.top_undeclared ? '，未声明类别中最多：' + this.esc(cc.top_undeclared) : ''}）</div>` : '';
            const statusBadge = v.status === 'ok' ? '' : `<span class="badge ${v.status === 'excluded' ? 'bg-secondary' : 'bg-danger'}">${v.status === 'excluded' ? '已排除' : '失败'}</span>`;
            const ops = canEdit ? `<div class="d-flex gap-1">
                    <button class="btn btn-sm btn-outline-secondary pipeline-reassign" data-key="${this.esc(v.key)}">改类别</button>
                    ${v.status === 'excluded' ? `<button class="btn btn-sm btn-outline-secondary pipeline-video-act" data-key="${this.esc(v.key)}" data-act="include">恢复</button>`
                                              : `<button class="btn btn-sm btn-outline-danger pipeline-video-act" data-key="${this.esc(v.key)}" data-act="exclude">排除</button>`}</div>` : '';
            return `<tr>
                <td><div class="fw-semibold">${this.esc(v.key)} ${statusBadge}</div><div class="small text-muted text-truncate" style="max-width:220px" title="${this.esc(v.original_filename)}">${this.esc(v.original_filename)}</div>
                    ${v.error ? `<div class="small text-danger">${this.esc(v.error)}</div>` : ''}${ccText}</td>
                <td>${(v.classes || [v.class]).map(c => this.esc(c)).join('<br>')}</td>
                <td class="small">${v.duration ? v.duration.toFixed(1) + 's' : '-'}</td>
                <td class="small">抽 ${clean.extracted ?? st.extracted ?? '-'} → 留 ${clean.kept ?? '-'}${dropped ? `<div class="text-muted">${dropped}</div>` : ''}</td>
                <td class="small">${g.frames !== undefined ? `可训练 ${g.trainable}/${g.frames}<div class="text-muted">未检出 ${g.no_box}，SAM 回退 ${g.sam_fallback}，跳变 ${g.temporal}</div>` : '-'}</td>
                <td><a href="#" class="small pipeline-video-frames" data-video="${this.esc(v.key)}">看帧</a></td>
                <td>${ops}</td></tr>`;
        }).join('');
        return `<div class="card h-100"><div class="card-header">视频（帧数漏斗）</div><div class="card-body p-0" style="overflow:auto">
            <table class="table table-sm mb-0 align-middle"><thead><tr><th>视频</th><th>类别</th><th>时长</th><th>清洗</th><th>标注</th><th></th><th></th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
    }

    renderClasses(run) {
        const counts = (run.metrics && run.metrics.gate && run.metrics.gate.class_frames) || {};
        const split = run.metrics && run.metrics.dataset;
        const coverage = split && split.coverage;
        const refs = (run.artifacts && run.artifacts.references) || null;
        const refCell = (name) => {
            if (!refs) return '<span class="small text-muted">-</span>';
            const items = (refs.classes || {})[name] || [];
            if (!items.length) return '<span class="badge bg-warning text-dark" title="没有参考图，该类别的自动标注召回会明显偏低">无</span>';
            return items.map(it => {
                const how = { confirmed: '（已核对）', consensus: '（未经核对，取多个候选中外观最一致的）' }[it.verdict] || '（未经核对）';
                const tip = it.type === 'provided' ? '调用方提供' : `自动挑选：视频 ${it.video} 的 ${it.frame}${how}`;
                return `<img src="${API_URL}/pipeline/runs/${run.job_id}/references/${encodeURIComponent(it.file)}" title="${this.esc(tip)}" style="height:40px;max-width:64px;object-fit:contain;border:1px solid ${it.type === 'provided' || it.verdict === 'confirmed' ? '#ccc' : '#f0ad4e'}">`;
            }).join(' ');
        };
        const rows = (run.classes || []).map((c, i) => {
            const cov = coverage ? `${coverage.train[c.name] || 0} / ${coverage.val[c.name] || 0} / ${coverage.test[c.name] || 0}` : '-';
            const upload = run.status === 'needs_review' && refs ? `<label class="small text-primary d-block" style="cursor:pointer">上传…<input type="file" accept="image/*" class="d-none pipeline-ref-upload" data-class="${this.esc(c.name)}"></label>` : '';
            return `<tr><td>${i}</td><td>${this.esc(c.name)}${c.display_name ? `<div class="small text-muted">${this.esc(c.display_name)}</div>` : ''}</td><td>${refCell(c.name)}${upload}</td><td>${counts[c.name] ?? '-'}</td><td class="small">${cov}</td></tr>`;
        }).join('');
        const splitNote = { by_segment: '（测试集与训练集同源，指标偏乐观）',
                            hybrid: `（${(split && split.segment_classes || []).map(c => this.esc(c)).join('、')} 视频不足，按时间段划分，这些类别指标偏乐观）` };
        const splitText = split ? `<div class="small text-muted px-2 pb-2">划分方式：${this.esc(split.split_mode)}${splitNote[split.split_mode] || ''}</div>` : '';
        return `<div class="card mb-3"><div class="card-header">类别（顺序即 class_id，已冻结）</div><div class="card-body p-0">
            <table class="table table-sm mb-0 align-middle"><thead><tr><th>ID</th><th>类别</th><th title="随标注请求发给视觉模型的参考图；挑错了会把整个类别带偏">参考图</th><th>可训练帧</th><th>train/val/test</th></tr></thead><tbody>${rows}</tbody></table>${splitText}</div></div>`;
    }

    renderResults(run) {
        const ev = run.metrics && run.metrics.evaluate;
        const tf = run.metrics && run.metrics.tflite;
        const delivery = (run.artifacts && run.artifacts.delivery) || {};
        const usage = run.llm_usage || {};
        let html = `<div class="card"><div class="card-header">结果</div><div class="card-body small">`;
        html += `<div>视觉模型调用：${usage.calls || 0} 次（缓存命中 ${usage.cached || 0}，失败 ${usage.failures || 0}），费用 $${(usage.cost_usd || 0).toFixed(4)}</div>`;
        if (ev) html += `<div class="mt-1">测试集（${this.esc(ev.split)}）mAP50-95 <strong>${Number(ev.map50_95).toFixed(4)}</strong>，mAP50 ${Number(ev.map50).toFixed(4)}</div>`;
        if (tf && tf.gates) {
            const g = tf.gates;
            const ok = v => v && v.passed ? '✔' : '✘';
            html += `<div class="mt-1">TFLite 校验：结构 ${ok(g.structure)} 数值 ${ok(g.numeric)} 精度 ${ok(g.accuracy)}`;
            if (g.accuracy && g.accuracy.pt_map50_95 !== undefined) html += `（PT ${Number(g.accuracy.pt_map50_95).toFixed(4)} / TFLite ${Number(g.accuracy.tflite_map50_95).toFixed(4)}）`;
            html += `</div>`;
        }
        const names = Object.keys(delivery);
        if (names.length) {
            html += `<div class="mt-2">交付物：` + names.map(n => `<a class="me-2" href="${API_URL}/pipeline/runs/${run.job_id}/artifacts/${encodeURIComponent(n)}">${this.esc(n)}</a>`).join('') + `</div>`;
        }
        html += `<div class="mt-2"><a href="#" class="pipeline-stage-log" data-name="evaluate">评估日志</a> · <a href="#" class="pipeline-stage-log" data-name="export_verify">TFLite 导出日志</a></div>`;
        return html + `</div></div>`;
    }

    bindDetailEvents(run) {
        const root = document.getElementById('pipeline-detail');
        root.querySelectorAll('#pipeline-actions [data-act]').forEach(btn => btn.addEventListener('click', () => this.runAction(btn.dataset.act)));
        root.querySelectorAll('.pipeline-gate-frames, .pipeline-video-frames').forEach(a => a.addEventListener('click', (e) => {
            e.preventDefault();
            this.frameFilter = { video: a.dataset.video };
            if (a.dataset.reason) this.frameFilter.reason = a.dataset.reason;
            this.frameSkip = 0;
            this.syncFrameFilterInputs();
            this.loadFrames();
            document.getElementById('pipeline-frames-section').scrollIntoView({ behavior: 'smooth' });
        }));
        root.querySelectorAll('.pipeline-video-act').forEach(btn => btn.addEventListener('click', () => this.videoAction(btn.dataset.key, btn.dataset.act)));
        root.querySelectorAll('.pipeline-reassign').forEach(btn => btn.addEventListener('click', () => this.openReassign(btn.dataset.key)));
        root.querySelectorAll('.pipeline-ref-upload').forEach(input => input.addEventListener('change', () => {
            if (input.files.length) this.uploadReference(input.dataset.class, input.files[0]);
            input.value = '';
        }));
        root.querySelectorAll('.pipeline-stage-log').forEach(a => a.addEventListener('click', (e) => { e.preventDefault(); this.showStageLog(a.dataset.name); }));
    }

    async runAction(act) {
        const id = this.currentRunId;
        try {
            if (act === 'cancel') {
                if (!confirm('确定取消该任务？正在进行的训练会被停止。')) return;
                await this.api(`/runs/${id}/cancel`, { json: {} });
            } else if (act === 'resume') {
                const stages = (this.run.stages || []).map(s => s.name);
                const from = prompt(`从哪个阶段继续？直接确定表示从失败的阶段继续。\n可选：${stages.join(', ')}`, this.run.stage || '');
                if (from === null) return;
                await this.api(`/runs/${id}/resume`, { json: from ? { from_stage: from } : {} });
            } else if (act === 'approve') {
                return this.openApproveModal();
            } else if (act === 'reject') {
                const reason = prompt('驳回原因（会记录在任务事件里）', '');
                if (reason === null) return;
                await this.api(`/runs/${id}/review/reject`, { json: { reason } });
            } else if (act === 'trainlog') {
                const taskId = this.run.artifacts.training_task_id;
                if (window.trainingManager) window.trainingManager.viewTrainingLogs(taskId);
                return;
            }
            this.loadDetail(id);
        } catch (e) {
            alert(e.message);
        }
    }

    openApproveModal() {
        const gates = (this.run.gate_results || []).filter(g => g.status === 'pause' || g.status === 'warn');
        const metrics = [...new Set(gates.map(g => g.metric))];
        const budget = (this.run.review || {}).reason === 'budget';
        const html = `
            <p class="small">放行后任务从暂停处继续。被勾选的闸门在重新评估时不再导致暂停；“某类别没有任何可用帧”无法覆盖。</p>
            <div class="mb-2"><label class="form-label">未复核的帧如何处理</label>
                <select class="form-select form-select-sm" id="approve-include">
                    <option value="low_risk">只纳入低风险帧（推荐）</option>
                    <option value="none">都不纳入训练</option>
                    <option value="all">全部纳入训练</option></select></div>
            ${metrics.length ? `<div class="mb-2"><label class="form-label">覆盖以下闸门</label>${metrics.map(m => `<div class="form-check"><input class="form-check-input approve-override" type="checkbox" value="${this.esc(m)}" id="ov-${this.esc(m)}" checked><label class="form-check-label small" for="ov-${this.esc(m)}">${this.esc(gates.find(g => g.metric === m).label)}</label></div>`).join('')}</div>` : ''}
            ${budget ? `<div class="mb-2"><label class="form-label">新的费用预算（美元）</label><input class="form-control form-control-sm" id="approve-budget" type="number" min="0" step="0.5"></div>` : ''}
            <div class="mb-2"><label class="form-label">说明（记录在事件里）</label><input class="form-control form-control-sm" id="approve-reason" maxlength="500"></div>`;
        showModal('放行任务', html, async () => {
            const body = {
                include_unreviewed: document.getElementById('approve-include').value,
                override_gates: [...document.querySelectorAll('.approve-override:checked')].map(c => c.value),
                reason: document.getElementById('approve-reason').value || null,
            };
            const b = document.getElementById('approve-budget');
            if (b && b.value) body.budget_usd = parseFloat(b.value);
            try {
                await this.api(`/runs/${this.currentRunId}/review/approve`, { json: body });
                modal.hide();
                this.loadDetail(this.currentRunId);
            } catch (e) { alert(e.message); }
        });
    }

    openReassign(key) {
        const video = (this.run.videos || []).find(v => v.key === key) || {};
        const current = video.classes || [video.class];
        const boxes = (this.run.classes || []).map((c, i) => `<div class="form-check">
                <input class="form-check-input reassign-class" type="checkbox" id="reassign-${i}" value="${this.esc(c.name)}" ${current.includes(c.name) ? 'checked' : ''}>
                <label class="form-check-label" for="reassign-${i}">${this.esc(c.name)}${c.display_name ? '（' + this.esc(c.display_name) + '）' : ''}</label></div>`).join('');
        showModal(`修改视频 ${key} 的类别`, `<p class="small text-muted">勾选画面里实际出现的文物类别（可多选）。确定后会删除该视频的自动标注并重新标注，然后重新评估质量闸门。</p>${boxes}`, () => {
            const selected = [...document.querySelectorAll('.reassign-class:checked')].map(b => b.value);
            if (!selected.length) { alert('至少选择一个类别'); return; }
            modal.hide();
            this.videoAction(key, 'reassign_class', selected, true);
        });
    }

    async videoAction(key, action, classNames, confirmed) {
        const text = { exclude: `排除视频 ${key}？它的帧将不参与训练。`, include: `恢复视频 ${key}？` }[action];
        if (!confirmed && text && !confirm(text)) return;
        try {
            await this.api(`/runs/${this.currentRunId}/videos/${encodeURIComponent(key)}/action`, { json: { action, class_names: classNames || null } });
            this.loadDetail(this.currentRunId);
        } catch (e) { alert(e.message); }
    }

    async showStageLog(name) {
        try {
            const data = await this.api(`/runs/${this.currentRunId}/logs/${name}`);
            showModal(name === 'evaluate' ? '评估日志' : 'TFLite 导出日志', `<pre class="small" style="max-height:60vh;overflow:auto;white-space:pre-wrap">${this.esc(data.text)}</pre>`, null, 'xl');
        } catch (e) { alert(e.message); }
    }

    // ---------------------------------------------------------------- 帧浏览
    buildFramesSection() {
        const div = document.createElement('div');
        div.id = 'pipeline-frames-section';
        div.className = 'card mb-3';
        div.innerHTML = `<div class="card-header d-flex flex-wrap gap-2 align-items-center">
                <strong class="me-2">帧浏览</strong>
                <select class="form-select form-select-sm" id="pf-video" style="width:auto"><option value="">全部视频</option></select>
                <select class="form-select form-select-sm" id="pf-status" style="width:auto"><option value="">全部状态</option>
                    <option value="to_review">待复核</option><option value="auto_accepted">自动通过</option><option value="accepted,modified">人工通过</option><option value="discarded">已丢弃</option></select>
                <select class="form-select form-select-sm" id="pf-reason" style="width:auto"><option value="">全部风险</option>
                    ${Object.entries(this.reasonText).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
                <select class="form-select form-select-sm" id="pf-split" style="width:auto"><option value="">全部划分</option><option value="train">train</option><option value="val">val</option><option value="test">test</option><option value="excluded">未进数据集</option></select>
                <select class="form-select form-select-sm" id="pf-order" style="width:auto"><option value="time">按时间</option><option value="risk_desc">风险从高到低</option></select>
                <span class="ms-2 small">图层：</span>
                <label class="small"><input type="checkbox" id="pf-layer-vlm"> VLM 粗框</label>
                <label class="small"><input type="checkbox" id="pf-layer-sam"> SAM 框</label>
                <label class="small"><input type="checkbox" id="pf-layer-final" checked> 最终框</label>
                <div class="ms-auto d-flex gap-2"><button class="btn btn-sm btn-outline-success" id="pf-accept-page">本页全部通过</button></div>
            </div>
            <div class="card-body"><div id="pf-grid" class="d-flex flex-wrap gap-2"></div>
                <div class="d-flex justify-content-between align-items-center mt-2"><span class="small text-muted" id="pf-info"></span>
                <div class="btn-group"><button class="btn btn-sm btn-outline-secondary" id="pf-prev">上一页</button><button class="btn btn-sm btn-outline-secondary" id="pf-next">下一页</button></div></div></div>`;
        const onFilter = () => {
            this.frameFilter = {
                video: div.querySelector('#pf-video').value, review_status: div.querySelector('#pf-status').value,
                reason: div.querySelector('#pf-reason').value, split: div.querySelector('#pf-split').value,
                order: div.querySelector('#pf-order').value,
            };
            this.frameSkip = 0;
            this.loadFrames();
        };
        ['#pf-video', '#pf-status', '#pf-reason', '#pf-split', '#pf-order'].forEach(s => div.querySelector(s).addEventListener('change', onFilter));
        ['vlm', 'sam', 'final'].forEach(k => div.querySelector(`#pf-layer-${k}`).addEventListener('change', (e) => {
            this.layers[k] = e.target.checked;
            this.renderFrames(this.lastFrames);
        }));
        div.querySelector('#pf-prev').addEventListener('click', () => { this.frameSkip = Math.max(0, this.frameSkip - this.frameLimit); this.loadFrames(); });
        div.querySelector('#pf-next').addEventListener('click', () => { this.frameSkip += this.frameLimit; this.loadFrames(); });
        div.querySelector('#pf-accept-page').addEventListener('click', () => this.acceptPage());
        return div;
    }

    syncFrameFilterInputs() {
        const f = this.frameFilter;
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
        set('pf-video', f.video); set('pf-status', f.review_status); set('pf-reason', f.reason); set('pf-split', f.split);
        set('pf-order', f.order || 'time');
    }

    async loadFrames() {
        if (!this.currentRunId || !document.getElementById('pf-grid')) return;
        const sel = document.getElementById('pf-video');
        if (sel && this.run && sel.options.length <= 1) {
            (this.run.videos || []).forEach(v => sel.insertAdjacentHTML('beforeend', `<option value="${this.esc(v.key)}">${this.esc(v.key)}（${this.esc(v.class)}）</option>`));
            this.syncFrameFilterInputs();
        }
        const params = new URLSearchParams({ skip: String(this.frameSkip), limit: String(this.frameLimit) });
        Object.entries(this.frameFilter).forEach(([k, v]) => { if (v) params.set(k, v); });
        try {
            const data = await this.api(`/runs/${this.currentRunId}/frames?${params}`);
            this.lastFrames = data.items;
            this.renderFrames(data.items);
            document.getElementById('pf-info').textContent = data.total ? `共 ${data.total} 帧，显示 ${this.frameSkip + 1}-${Math.min(data.total, this.frameSkip + data.items.length)}` : '没有符合条件的帧';
        } catch (e) {
            document.getElementById('pf-grid').innerHTML = `<div class="text-danger small">${this.esc(e.message)}</div>`;
        }
    }

    boxesHtml(frame, scale = 1) {
        const size = (frame.auto_annotations && frame.auto_annotations.meta && frame.auto_annotations.meta.image_size) || null;
        const parts = [];
        const rect = (x1, y1, x2, y2, color, dash) => {
            if (!size) return '';
            const [w, h] = size;
            return `<div style="position:absolute;left:${x1 / w * 100}%;top:${y1 / h * 100}%;width:${(x2 - x1) / w * 100}%;height:${(y2 - y1) / h * 100}%;border:${2 * scale}px ${dash} ${color};pointer-events:none"></div>`;
        };
        if (this.layers.vlm && frame.auto_annotations) (frame.auto_annotations.vlm || []).forEach(b => parts.push(rect(...b.xyxy, '#ff9800', 'dashed')));
        if (this.layers.sam && frame.auto_annotations) (frame.auto_annotations.sam || []).forEach(s => { if (s.sam_box) parts.push(rect(...s.sam_box, '#03a9f4', 'dotted')); });
        if (this.layers.final) (frame.annotations || []).forEach(a => {
            parts.push(`<div style="position:absolute;left:${(a.x_center - a.width / 2) * 100}%;top:${(a.y_center - a.height / 2) * 100}%;width:${a.width * 100}%;height:${a.height * 100}%;border:${2 * scale}px solid #4caf50;pointer-events:none"></div>`);
        });
        return parts.join('');
    }

    renderFrames(frames) {
        const grid = document.getElementById('pf-grid');
        if (!grid) return;
        const statusColor = { to_review: '#ffc107', auto_accepted: '#6c757d', accepted: '#198754', modified: '#0d6efd', discarded: '#dc3545' };
        grid.innerHTML = frames.map(f => {
            const meta = f.pipeline_meta || {};
            const reasons = (f.risk_reasons || []).map(r => this.reasonText[r] || r).join('、');
            return `<div class="pipeline-frame border rounded" data-id="${f.id}" style="width:200px;cursor:pointer;border-color:${statusColor[f.review_status] || '#dee2e6'} !important;border-width:2px !important">
                <div style="position:relative"><img src="${f.image_url}" loading="lazy" style="width:100%;display:block">${this.boxesHtml(f)}</div>
                <div class="p-1 small"><div class="d-flex justify-content-between"><span>${this.esc(meta.video_key)} @${Number(meta.ts || 0).toFixed(1)}s</span>
                <span>${this.reviewText[f.review_status] || '-'}</span></div>
                <div class="text-muted text-truncate" title="${this.esc(reasons)}">风险 ${Number(f.risk_score || 0).toFixed(2)} ${this.esc(reasons)}</div></div></div>`;
        }).join('');
        grid.querySelectorAll('.pipeline-frame').forEach(el => el.addEventListener('click', () => this.openFrame(el.dataset.id)));
    }

    openFrame(id) {
        const f = this.lastFrames.find(x => x.id === id);
        if (!f) return;
        const meta = f.pipeline_meta || {};
        const auto = f.auto_annotations || {};
        const samInfo = (auto.sam || []).map(s => `${s.status}${s.reason ? '（' + s.reason + '）' : ''}${s.area_ratio ? '，面积比 ' + s.area_ratio : ''}`).join('；') || '-';
        const projectId = this.run.artifacts.annotation_project_id;
        const html = `<div style="position:relative">${`<img src="${f.image_url}" style="width:100%;display:block">`}${this.boxesHtml(f, 1)}</div>
            <div class="small mt-2">
                <div>视频 ${this.esc(meta.video_key)}（${(meta.classes || [meta.class_name]).map(c => this.esc(c)).join(' + ')}），第 ${meta.frame_index} 帧，${Number(meta.ts || 0).toFixed(2)}s，划分 ${this.esc(meta.split || '未进数据集')}</div>
                <div>复核状态：${this.reviewText[f.review_status] || '-'}；风险 ${Number(f.risk_score || 0).toFixed(2)}：${this.esc((f.risk_reasons || []).map(r => this.reasonText[r] || r).join('、') || '无')}</div>
                <div>视觉模型：${this.esc((auto.meta || {}).model)}${(auto.meta || {}).error ? `，错误：${this.esc(auto.meta.error)}` : ''}</div>
                <div>SAM：${this.esc(samInfo)}</div>
            </div>
            <div class="d-flex gap-2 mt-2 flex-wrap">
                <button class="btn btn-sm btn-success" id="frame-accept">通过</button>
                <button class="btn btn-sm btn-outline-danger" id="frame-discard">丢弃此帧</button>
                <a class="btn btn-sm btn-outline-primary" target="_blank" href="/static/annotation.html?project_id=${projectId}">到标注页修改框</a>
                ${this.run.status === 'needs_review' ? (f.annotations || []).map((a, i) => {
                    const c = (this.run.classes || [])[a.class_id] || {};
                    return `<button class="btn btn-sm btn-outline-secondary frame-set-ref" data-i="${i}" title="把这个框裁下来作为该类别的参考图，并重新标注含该类别的视频">设为 ${this.esc(c.name || a.class_id)} 的参考图</button>`;
                }).join('') : ''}
            </div>
            ${this.run.status === 'needs_review' ? '<div class="small text-muted mt-1">某类文物总是漏标时：找一帧把它框准（必要时先到标注页修改框），再设为参考图。</div>' : ''}`;
        showModal(`帧 ${f.image_name}`, html, null, 'xl');
        document.getElementById('frame-accept').addEventListener('click', () => this.reviewFrame(f, 'accept'));
        document.getElementById('frame-discard').addEventListener('click', () => this.reviewFrame(f, 'discard'));
        document.querySelectorAll('.frame-set-ref').forEach(btn => btn.addEventListener('click', () => this.setReferenceFromFrame(f, parseInt(btn.dataset.i, 10))));
    }

    async setReferenceFromFrame(f, boxIndex) {
        const a = (f.annotations || [])[boxIndex] || {};
        const c = ((this.run.classes || [])[a.class_id] || {}).name || a.class_id;
        if (!confirm(`把这个框作为 ${c} 的参考图？会重新标注含 ${c} 的视频（人工处理过的帧保留），然后重新评估质量闸门。`)) return;
        try {
            await this.api(`/runs/${this.currentRunId}/references/from-frame`, { json: { image_id: f.id, box_index: boxIndex } });
            modal.hide();
            this.loadDetail(this.currentRunId);
        } catch (e) { alert(e.message); }
    }

    async uploadReference(className, file) {
        if (!confirm(`用 ${file.name} 作为 ${className} 的参考图？会重新标注含 ${className} 的视频（人工处理过的帧保留），然后重新评估质量闸门。`)) return;
        const form = new FormData();
        form.append('class_name', className);
        form.append('image', file, file.name);
        try {
            const res = await authenticatedFetch(`${API_URL}/pipeline/runs/${this.currentRunId}/references/upload`, { method: 'POST', body: form });
            const data = await res.json();
            if (!res.ok) throw new Error((data.error && data.error.message) || data.detail || '上传失败');
            this.loadDetail(this.currentRunId);
        } catch (e) { alert(e.message); }
    }

    async reviewFrame(f, action) {
        try {
            await this.api(`/runs/${this.currentRunId}/frames/${f.id}/review`, { json: { action, version: f.version } });
            modal.hide();
            this.loadFrames();
            this.loadDetail(this.currentRunId, true);
        } catch (e) { alert(e.message); }
    }

    async acceptPage() {
        const items = this.lastFrames.filter(f => !['accepted', 'modified', 'discarded'].includes(f.review_status)).map(f => ({ image_id: f.id, version: f.version }));
        if (!items.length) { alert('本页没有需要处理的帧'); return; }
        if (!confirm(`将本页 ${items.length} 帧标记为“人工通过”？`)) return;
        try {
            const res = await this.api(`/runs/${this.currentRunId}/frames/batch-review`, { json: { action: 'accept', items } });
            const failed = res.results.filter(r => !r.ok);
            if (failed.length) alert(`${failed.length} 帧处理失败（可能被他人修改过），已刷新`);
            this.loadFrames();
            this.loadDetail(this.currentRunId, true);
        } catch (e) { alert(e.message); }
    }

    // ---------------------------------------------------------------- 事件
    buildEventsSection() {
        const div = document.createElement('div');
        div.id = 'pipeline-events-section';
        div.className = 'card mb-3';
        div.innerHTML = `<div class="card-header">事件时间线</div><div class="card-body p-0" style="max-height:360px;overflow:auto"><table class="table table-sm mb-0"><tbody id="pipeline-events-body"></tbody></table></div>`;
        return div;
    }

    async loadEvents() {
        const body = document.getElementById('pipeline-events-body');
        if (!body) return;
        try {
            const data = await this.api(`/runs/${this.currentRunId}/events?limit=2000`);
            const color = { warning: 'text-warning', error: 'text-danger' };
            body.innerHTML = data.items.slice().reverse().map(e => `<tr class="${color[e.level] || ''}">
                <td class="small text-nowrap">${this.fmtTime(e.ts)}</td><td class="small">${this.esc(e.stage || '')}</td>
                <td class="small text-nowrap">${this.esc(e.type)}</td><td class="small">${this.esc(e.message)}</td></tr>`).join('');
        } catch (e) { /* 忽略，下次刷新再试 */ }
    }

    // ---------------------------------------------------------------- 新建任务
    openCreateModal() {
        const html = `
            <p class="small text-muted">为每个视频勾选画面里出现的文物类别（通常一个视频一类，也可多选）。类别名用英文（会写入 labels.txt），展示名可用中文。</p>
            <div class="mb-2"><label class="form-label">任务名称</label><input class="form-control form-control-sm" id="pc-name" value="文物训练-${new Date().toISOString().slice(0, 10)}"></div>
            <div class="mb-2"><label class="form-label">类别（每行一个：英文名,中文展示名）</label><textarea class="form-control form-control-sm" id="pc-classes" rows="3" placeholder="JadeCup,玉杯&#10;AncientBowl,古碗"></textarea></div>
            <div class="mb-2"><label class="form-label">视频</label><input class="form-control form-control-sm" type="file" id="pc-videos" multiple accept="video/*"></div>
            <div id="pc-video-classes" class="mb-2"></div>
            <div class="mb-2"><label class="form-label">参考图（可选，强烈建议）</label><input class="form-control form-control-sm" type="file" id="pc-references" multiple accept="image/*">
                <div class="small text-muted">每类 1~3 张该文物的清晰照片，文件名以类别名开头（如 JadeCup_1.jpg）。没有提供的类别会从视频里自动挑选。</div></div>
            <div class="row g-2">
                <div class="col"><label class="form-label">复核模式</label><select class="form-select form-select-sm" id="pc-review"><option value="on_anomaly">按异常暂停（推荐）</option><option value="auto">全自动</option><option value="full">全量复核</option></select></div>
                <div class="col"><label class="form-label">基础模型</label><select class="form-select form-select-sm" id="pc-model"><option>yolo11n</option><option>yolo11s</option><option>yolov8n</option></select></div>
                <div class="col"><label class="form-label">训练轮数</label><input class="form-control form-control-sm" id="pc-epochs" type="number" value="100" min="1" max="300"></div>
                <div class="col"><label class="form-label">输入尺寸</label><input class="form-control form-control-sm" id="pc-imgsz" type="number" value="640" step="32"></div>
            </div>
            <div class="small text-muted mt-2">视觉模型、切帧间隔、闸门阈值等使用系统默认值；需要细调时请用对外接口提交完整配置。</div>`;
        showModal('新建一键训练任务', html, () => this.submitCreate());
        const refreshVideoClasses = () => {
            const classes = this.parseClasses();
            const files = document.getElementById('pc-videos').files;
            const guess = (name) => (classes.find(c => name.toLowerCase().startsWith(c.name.toLowerCase())) || classes[0] || {}).name || '';
            document.getElementById('pc-video-classes').innerHTML = [...files].map((f, i) => `<div class="d-flex gap-2 align-items-start mb-1 pc-video-row" data-i="${i}">
                <span class="small text-truncate" style="width:40%">${this.esc(f.name)}</span>
                <div class="d-flex flex-wrap gap-2">${classes.map((c, j) => `<div class="form-check form-check-inline m-0">
                    <input class="form-check-input pc-video-class" type="checkbox" id="pcv-${i}-${j}" value="${this.esc(c.name)}" ${c.name === guess(f.name) ? 'checked' : ''}>
                    <label class="form-check-label small" for="pcv-${i}-${j}">${this.esc(c.name)}</label></div>`).join('')}</div></div>`).join('');
        };
        document.getElementById('pc-videos').addEventListener('change', refreshVideoClasses);
        document.getElementById('pc-classes').addEventListener('input', refreshVideoClasses);
    }

    parseClasses() {
        return document.getElementById('pc-classes').value.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
            const [name, display] = l.split(/[,，]/).map(s => s.trim());
            return display ? { name, display_name: display } : { name };
        });
    }

    async submitCreate() {
        const files = document.getElementById('pc-videos').files;
        const classes = this.parseClasses();
        if (!classes.length || !files.length) { alert('请填写类别并选择视频'); return; }
        const videoClasses = [...document.querySelectorAll('.pc-video-row')].map(row => [...row.querySelectorAll('.pc-video-class:checked')].map(b => b.value));
        const empty = videoClasses.findIndex(cs => !cs.length);
        if (empty >= 0) { alert(`请为视频 ${files[empty].name} 至少勾选一个类别`); return; }
        // 参考图按文件名前缀归到类别（最长的类别名优先，避免 Cup 抢走 CupLid 的图）
        const refFiles = [...document.getElementById('pc-references').files];
        const byLength = [...classes].sort((a, b) => b.name.length - a.name.length);
        const unmatched = [];
        refFiles.forEach(f => {
            const c = byLength.find(c => f.name.toLowerCase().startsWith(c.name.toLowerCase()));
            if (!c) { unmatched.push(f.name); return; }
            c.references = c.references || [];
            if (c.references.length < 3) c.references.push({ file: f.name });
        });
        if (unmatched.length && !confirm(`以下参考图的文件名不以任何类别名开头，将被忽略：\n${unmatched.join('\n')}\n继续创建？`)) return;
        const spec = {
            name: document.getElementById('pc-name').value.trim() || 'pipeline',
            classes, review_mode: document.getElementById('pc-review').value,
            videos: [...files].map((f, i) => (videoClasses[i].length === 1 ? { class: videoClasses[i][0], file: f.name } : { classes: videoClasses[i], file: f.name })),
            config: { train: { model: document.getElementById('pc-model').value, epochs: parseInt(document.getElementById('pc-epochs').value, 10),
                               imgsz: parseInt(document.getElementById('pc-imgsz').value, 10) } },
        };
        const form = new FormData();
        form.append('spec', JSON.stringify(spec));
        [...files].forEach(f => form.append('videos', f, f.name));
        classes.forEach(c => (c.references || []).forEach(r => form.append('references', refFiles.find(f => f.name === r.file), r.file)));
        try {
            const res = await authenticatedFetch(`${API_URL}/pipeline/runs`, { method: 'POST', body: form });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || '创建失败');
            modal.hide();
            this.openDetail(data.job_id);
        } catch (e) { alert(e.message); }
    }

    // ---------------------------------------------------------------- API Key 管理
    async openApiKeys() {
        try {
            const data = await this.api('/api-keys');
            const rows = data.items.map(k => `<tr><td>${this.esc(k.name)}</td><td><code>myo_sk_${this.esc(k.prefix)}_…</code></td>
                <td class="small">${this.esc((k.scopes || []).join(', '))}</td><td class="small">${this.fmtTime(k.last_used_at)}</td>
                <td>${k.revoked_at ? '<span class="badge bg-secondary">已吊销</span>' : `<button class="btn btn-sm btn-outline-danger apikey-revoke" data-id="${k.id}">吊销</button>`}</td></tr>`).join('');
            showModal('API Key 管理', `
                <div class="input-group input-group-sm mb-3"><input class="form-control" id="apikey-name" placeholder="用途，如：业务系统A"><button class="btn btn-primary" id="apikey-create">创建</button></div>
                <div id="apikey-created"></div>
                <table class="table table-sm"><thead><tr><th>名称</th><th>Key</th><th>权限</th><th>最后使用</th><th></th></tr></thead><tbody>${rows || '<tr><td colspan="5" class="text-muted">暂无</td></tr>'}</tbody></table>
                <div class="small text-muted">调用方式：请求头 <code>X-API-Key: myo_sk_...</code>；接口文档 <a href="/api/v1/docs" target="_blank">/api/v1/docs</a></div>`);
            document.getElementById('apikey-create').addEventListener('click', async () => {
                const name = document.getElementById('apikey-name').value.trim();
                if (!name) return;
                try {
                    const k = await this.api('/api-keys', { json: { name } });
                    document.getElementById('apikey-created').innerHTML = `<div class="alert alert-success small">
                        <div><strong>请立即保存，关闭后无法再次查看：</strong></div>
                        <div class="mt-1">API Key：<code style="user-select:all">${this.esc(k.api_key)}</code></div>
                        <div class="mt-1">Webhook 签名密钥：<code style="user-select:all">${this.esc(k.webhook_secret)}</code></div></div>`;
                } catch (e) { alert(e.message); }
            });
            document.querySelectorAll('.apikey-revoke').forEach(b => b.addEventListener('click', async () => {
                if (!confirm('吊销后使用该 Key 的调用方将立即无法访问，确定？')) return;
                try { await this.api(`/api-keys/${b.dataset.id}`, { method: 'DELETE' }); modal.hide(); this.openApiKeys(); } catch (e) { alert(e.message); }
            }));
        } catch (e) { alert(e.message); }
    }
}

window.pipelineCenter = new PipelineCenter();
