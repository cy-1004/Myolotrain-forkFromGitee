/**
 * 批量图像处理 + 拼图工坊
 *
 * 三块功能：
 * 1. 批量预处理：上传多张 / 直接吃服务器上的数据集与标注项目，支持按比例随机抽样，
 *    异步执行 + 进度轮询 + zip 打包下载；
 * 2. 快速网格预览：把一批图拼成网格，纯看图用，不产出标注；
 * 3. Mosaic 训练样本：批量随机生成 -> 逐张人工审核（采纳 / 丢弃 / 暂留）-> 采纳的写进单独的数据集。
 */
class BatchProcessingManager {
    constructor() {
        this.pollTimer = null;
        this.initialized = false;
    }

    init() {
        // 页面用模板渲染，每次切到"图像处理"页都要重新绑定
        const form = document.getElementById('batch-form');
        if (!form) return;

        this.bindOperationToggles();
        this.bindBatchForm();
        this.bindGridForm();
        this.bindMosaic();
        this.loadSources();
        this.initialized = true;
    }

    // ==================== 操作勾选 ====================

    bindOperationToggles() {
        document.querySelectorAll('.batch-op').forEach(cb => {
            cb.addEventListener('change', () => {
                const params = document.getElementById(cb.id + '-params');
                if (params) params.style.display = cb.checked ? '' : 'none';
            });
        });

        const bindRange = (id, valId, fmt) => {
            const el = document.getElementById(id);
            const out = document.getElementById(valId);
            if (el && out) el.addEventListener('input', () => { out.textContent = fmt(el.value); });
        };
        bindRange('b-denoise-strength', 'b-denoise-val', v => v);
        bindRange('b-brightness', 'b-brightness-val', v => v);
        bindRange('b-contrast', 'b-contrast-val', v => (v / 10).toFixed(1));
        bindRange('b-sharpen-amount', 'b-sharpen-val', v => (v / 10).toFixed(1));
        bindRange('b-perspective-strength', 'b-perspective-val', v => (v / 10).toFixed(1));
    }

    /** 把勾选状态收集成后端认识的操作列表 */
    collectOperations() {
        const ops = [];
        const on = id => {
            const el = document.getElementById(id);
            return el && el.checked;
        };
        const num = id => parseFloat(document.getElementById(id).value);

        if (on('b-resize')) {
            ops.push({ name: 'resize_image', params: { width: num('b-resize-w'), height: num('b-resize-h') } });
        }
        if (on('b-denoise')) {
            ops.push({ name: 'denoise_image', params: { strength: num('b-denoise-strength') } });
        }
        if (on('b-bc')) {
            ops.push({ name: 'adjust_brightness_contrast', params: { brightness: num('b-brightness'), contrast: num('b-contrast') / 10 } });
        }
        if (on('b-sharpen')) {
            ops.push({ name: 'sharpen_image', params: { amount: num('b-sharpen-amount') / 10 } });
        }
        // flip_code 用 cv2 语义：1 = 左右镜像，0 = 上下翻转
        if (on('b-fliph')) ops.push({ name: 'flip_image', params: { flip_code: 1 } });
        if (on('b-flipv')) ops.push({ name: 'flip_image', params: { flip_code: 0 } });
        if (on('b-rotate')) {
            ops.push({ name: 'rotate_image', params: { angle: num('b-rotate-angle') } });
        }
        if (on('b-perspective')) {
            ops.push({ name: 'apply_perspective_transform', params: { strength: num('b-perspective-strength') / 10 } });
        }
        return ops;
    }

    // ==================== 来源下拉 ====================

    loadSources() {
        const fill = (selectId, items, labelFn) => {
            const sel = document.getElementById(selectId);
            if (!sel) return;
            sel.innerHTML = items.length
                ? items.map(it => `<option value="${it.id}">${labelFn(it)}</option>`).join('')
                : '<option value="">（没有可用项）</option>';
        };

        authenticatedFetch(`${API_URL}/datasets/`)
            .then(r => r.json())
            .then(data => {
                const list = Array.isArray(data) ? data : (data.items || []);
                fill('batch-dataset', list, d => `${d.name} (${d.image_count || 0} 张)`);
                fill('mosaic-dataset', list, d => `${d.name} (${d.image_count || 0} 张)`);
            })
            .catch(err => console.error('加载数据集失败:', err));

        authenticatedFetch(`${API_URL}/annotation/projects/`)
            .then(r => r.json())
            .then(data => {
                const list = Array.isArray(data) ? data : (data.items || []);
                fill('batch-project', list, p => p.name);
            })
            .catch(err => console.error('加载标注项目失败:', err));
    }

    // ==================== 批量处理 ====================

    bindBatchForm() {
        const sourceSel = document.getElementById('batch-source');
        const sampleMode = document.getElementById('batch-sample-mode');

        const syncSourceUI = () => {
            const source = sourceSel.value;
            document.querySelectorAll('.batch-source-block').forEach(el => {
                el.style.display = el.dataset.for === source ? '' : 'none';
            });
            // 抽样和子集只对服务器目录有意义
            const serverSide = source !== 'upload';
            document.querySelectorAll('.batch-server-only').forEach(el => {
                el.style.display = serverSide ? '' : 'none';
            });
        };
        sourceSel.addEventListener('change', syncSourceUI);
        syncSourceUI();

        const syncSampleUI = () => {
            const wrap = document.getElementById('batch-sample-value-wrap');
            const label = document.getElementById('batch-sample-value-label');
            const input = document.getElementById('batch-sample-value');
            if (sampleMode.value === 'all') {
                wrap.style.display = 'none';
                return;
            }
            wrap.style.display = '';
            if (sampleMode.value === 'ratio') {
                label.textContent = '比例 (%)';
                input.value = 20;
                input.max = 100;
            } else {
                label.textContent = '张数';
                input.value = 100;
                input.removeAttribute('max');
            }
        };
        sampleMode.addEventListener('change', syncSampleUI);
        syncSampleUI();

        document.getElementById('batch-form').addEventListener('submit', e => {
            e.preventDefault();
            this.submitBatch();
        });
    }

    submitBatch() {
        const operations = this.collectOperations();
        if (operations.length === 0) {
            alert('请至少选择一个处理操作');
            return;
        }

        const source = document.getElementById('batch-source').value;
        const formData = new FormData();
        formData.append('operations', JSON.stringify(operations));

        let url;
        if (source === 'upload') {
            const files = document.getElementById('batch-files').files;
            if (!files.length) {
                alert('请选择要处理的图片');
                return;
            }
            for (const f of files) formData.append('images', f);
            url = `${API_URL}/opencv/batch-process`;
        } else {
            url = `${API_URL}/opencv/batch-process-directory`;
            formData.append('source', source);
            if (source === 'dataset') {
                const id = document.getElementById('batch-dataset').value;
                if (!id) { alert('请选择数据集'); return; }
                formData.append('source_id', id);
            } else if (source === 'annotation_project') {
                const id = document.getElementById('batch-project').value;
                if (!id) { alert('请选择标注项目'); return; }
                formData.append('source_id', id);
            } else {
                const path = document.getElementById('batch-path').value.trim();
                if (!path) { alert('请填写目录路径'); return; }
                formData.append('source_path', path);
            }

            formData.append('split', document.getElementById('batch-split').value);
            const mode = document.getElementById('batch-sample-mode').value;
            formData.append('sample_mode', mode);
            if (mode !== 'all') {
                const raw = parseFloat(document.getElementById('batch-sample-value').value);
                // 比例在界面上按百分比填，接口要的是 0~1
                formData.append('sample_value', mode === 'ratio' ? raw / 100 : raw);
            }
            const seed = document.getElementById('batch-seed').value;
            if (seed !== '') formData.append('sample_seed', seed);
        }

        const btn = document.getElementById('batch-submit');
        btn.disabled = true;
        btn.textContent = '提交中...';

        authenticatedFetch(url, { method: 'POST', body: formData })
            .then(r => r.json().then(data => {
                if (!r.ok) throw new Error(data.detail || '提交失败');
                return data;
            }))
            .then(data => {
                document.getElementById('batch-result').style.display = '';
                document.getElementById('batch-task-id').textContent = data.task_id;
                document.getElementById('batch-actions').style.display = 'none';
                document.getElementById('batch-errors').innerHTML = '';

                const seedInfo = document.getElementById('batch-seed-info');
                seedInfo.textContent = data.seed
                    ? `随机种子 ${data.seed}　从 ${data.candidate_count} 张中抽取 ${data.total} 张` +
                      (data.labeled_count ? `（含标注 ${data.labeled_count} 张）` : '')
                    : `共 ${data.total} 张`;

                this.renderWarnings(data.warnings);
                this.pollBatch(data.task_id);
            })
            .catch(err => alert('提交失败: ' + err.message))
            .finally(() => {
                btn.disabled = false;
                btn.textContent = '开始批量处理';
            });
    }

    renderWarnings(warnings) {
        const box = document.getElementById('batch-warnings');
        if (!warnings || !warnings.length) { box.innerHTML = ''; return; }
        box.innerHTML = `<div class="alert alert-warning py-2">
            <strong>注意：</strong><ul class="mb-0">${warnings.map(w => `<li>${w}</li>`).join('')}</ul>
        </div>`;
    }

    pollBatch(taskId) {
        if (this.pollTimer) clearInterval(this.pollTimer);

        const bar = document.getElementById('batch-progress');
        const text = document.getElementById('batch-status-text');

        const tick = () => {
            authenticatedFetch(`${API_URL}/opencv/batch-status/${taskId}`)
                .then(r => r.json())
                .then(st => {
                    const pct = st.progress || 0;
                    bar.style.width = pct + '%';
                    bar.textContent = pct + '%';

                    if (st.status === 'completed') {
                        clearInterval(this.pollTimer);
                        this.pollTimer = null;
                        bar.classList.remove('progress-bar-animated');
                        text.textContent = `完成：成功 ${st.processed} 张，失败 ${st.failed} 张` +
                            (st.labels_written ? `，同步输出 ${st.labels_written} 个标签文件` : '');
                        document.getElementById('batch-actions').style.display = '';
                        document.getElementById('batch-download').href =
                            `${API_URL}/opencv/batch-download/${taskId}`;
                        document.getElementById('batch-manifest').href =
                            `${API_URL}/opencv/batch-manifest/${taskId}`;
                        this.renderErrors(st.errors);
                    } else if (st.status === 'failed') {
                        clearInterval(this.pollTimer);
                        this.pollTimer = null;
                        bar.classList.remove('progress-bar-animated');
                        bar.classList.add('bg-danger');
                        text.textContent = '任务失败: ' + (st.error || '未知错误');
                    } else {
                        text.textContent = `处理中... ${st.processed || 0} / ${st.total || 0}` +
                            (st.failed ? `（失败 ${st.failed}）` : '');
                    }
                })
                .catch(err => console.error('轮询失败:', err));
        };

        tick();
        this.pollTimer = setInterval(tick, 1500);
    }

    renderErrors(errors) {
        const box = document.getElementById('batch-errors');
        if (!errors || !errors.length) { box.innerHTML = ''; return; }
        box.innerHTML = `<div class="alert alert-danger py-2">
            <strong>${errors.length} 张处理失败（最多显示 50 条）：</strong>
            <ul class="mb-0 small">${errors.map(e => `<li>${e.image}: ${e.error}</li>`).join('')}</ul>
        </div>`;
    }

    // ==================== 快速网格 ====================

    bindGridForm() {
        const form = document.getElementById('grid-form');
        if (!form) return;

        form.addEventListener('submit', e => {
            e.preventDefault();
            const files = document.getElementById('grid-files').files;
            if (!files.length) { alert('请选择图片'); return; }

            const formData = new FormData();
            for (const f of files) formData.append('images', f);
            formData.append('rows', document.getElementById('grid-rows').value);
            formData.append('cols', document.getElementById('grid-cols').value);
            const cw = document.getElementById('grid-cell-w').value;
            const ch = document.getElementById('grid-cell-h').value;
            if (cw && ch) {
                formData.append('cell_width', cw);
                formData.append('cell_height', ch);
            }
            formData.append('shuffle', document.getElementById('grid-shuffle').checked);

            authenticatedFetch(`${API_URL}/opencv/create-grid`, { method: 'POST', body: formData })
                .then(r => r.json().then(data => {
                    if (!r.ok) throw new Error(data.detail || '生成失败');
                    return data;
                }))
                .then(data => {
                    document.getElementById('grid-result').style.display = '';
                    const img = document.getElementById('grid-output');
                    img.src = data.output_path + '?t=' + Date.now();
                    document.getElementById('grid-download').href = data.output_path;
                    // 供图多于格子数时会被截断，说清楚用了几张，别让人以为全拼进去了
                    document.getElementById('grid-note').textContent =
                        `提供 ${data.supplied} 张，实际使用 ${data.used} 张` +
                        (data.supplied > data.used ? `（多余的 ${data.supplied - data.used} 张未使用）` : '');
                })
                .catch(err => alert('生成网格失败: ' + err.message));
        });
    }

    // ==================== Mosaic 审核 ====================

    bindMosaic() {
        const genForm = document.getElementById('mosaic-gen-form');
        if (!genForm) return;

        genForm.addEventListener('submit', e => {
            e.preventDefault();
            const datasetId = document.getElementById('mosaic-dataset').value;
            if (!datasetId) { alert('请选择来源数据集'); return; }

            const formData = new FormData();
            formData.append('dataset_id', datasetId);
            formData.append('split', document.getElementById('mosaic-split').value);
            formData.append('count', document.getElementById('mosaic-count').value);
            const seed = document.getElementById('mosaic-seed').value;
            if (seed !== '') formData.append('seed', seed);

            authenticatedFetch(`${API_URL}/opencv/mosaic/generate`, { method: 'POST', body: formData })
                .then(r => r.json().then(data => {
                    if (!r.ok) throw new Error(data.detail || '生成失败');
                    return data;
                }))
                .then(data => {
                    let msg = `生成 ${data.generated} 张（种子 ${data.seed}）`;
                    if (data.failed) msg += `，失败 ${data.failed} 张`;
                    if (data.message) msg += '\n' + data.message;
                    alert(msg);
                    document.getElementById('mosaic-filter').value = 'pending';
                    this.loadMosaicCandidates();
                })
                .catch(err => alert('生成拼图失败: ' + err.message));
        });

        document.getElementById('mosaic-refresh')
            .addEventListener('click', () => this.loadMosaicCandidates());
        document.getElementById('mosaic-filter')
            .addEventListener('change', () => this.loadMosaicCandidates());

        this.loadMosaicCandidates();
    }

    loadMosaicCandidates() {
        const status = document.getElementById('mosaic-filter').value;
        authenticatedFetch(`${API_URL}/opencv/mosaic/candidates?status=${status}&limit=100`)
            .then(r => r.json())
            .then(data => {
                document.getElementById('mosaic-pending-count').textContent = data.pending_total;
                document.getElementById('mosaic-pending-limit').textContent = data.pending_limit;
                this.renderMosaicCandidates(data.items || []);
            })
            .catch(err => console.error('加载拼图候选失败:', err));
    }

    renderMosaicCandidates(items) {
        const box = document.getElementById('mosaic-candidates');
        if (!items.length) {
            box.innerHTML = '<div class="col"><p class="text-muted">没有符合条件的拼图。</p></div>';
            return;
        }

        box.innerHTML = items.map(it => {
            const pending = it.status === 'pending';
            const badge = { pending: 'bg-warning text-dark', accepted: 'bg-success', discarded: 'bg-secondary' }[it.status] || 'bg-secondary';
            const label = { pending: '待审核', accepted: '已采纳', discarded: '已丢弃' }[it.status] || it.status;
            // 优先显示带标注框的预览图 —— 只看拼图本身审不出标签有没有拼对
            const src = it.preview_url || it.image_url;
            const img = src && it.status !== 'discarded'
                ? `<img src="${src}" class="card-img-top" alt="拼图预览">`
                : '<div class="p-4 text-center text-muted small">文件已删除</div>';

            return `
            <div class="col-md-4 mb-3" data-candidate="${it.id}">
                <div class="card h-100">
                    ${img}
                    <div class="card-body p-2">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="badge ${badge}">${label}</span>
                            <small class="text-muted">${it.box_count} 个框</small>
                        </div>
                        <details class="small text-muted">
                            <summary>源图 / 种子</summary>
                            <div class="mt-1">种子 ${it.seed}</div>
                            <ul class="mb-0 ps-3">${(it.source_images || []).map(p => `<li>${p}</li>`).join('')}</ul>
                        </details>
                    </div>
                    ${pending ? `
                    <div class="card-footer p-2 d-flex gap-1">
                        <button class="btn btn-sm btn-success flex-fill mosaic-accept" data-id="${it.id}">加入训练集</button>
                        <button class="btn btn-sm btn-outline-danger flex-fill mosaic-discard" data-id="${it.id}">丢弃</button>
                    </div>` : ''}
                </div>
            </div>`;
        }).join('');

        box.querySelectorAll('.mosaic-accept').forEach(btn => {
            btn.addEventListener('click', () => this.reviewMosaic(btn.dataset.id, 'accept', btn));
        });
        box.querySelectorAll('.mosaic-discard').forEach(btn => {
            btn.addEventListener('click', () => this.reviewMosaic(btn.dataset.id, 'discard', btn));
        });
    }

    reviewMosaic(id, action, btn) {
        const card = btn.closest('[data-candidate]');
        card.querySelectorAll('button').forEach(b => { b.disabled = true; });

        authenticatedFetch(`${API_URL}/opencv/mosaic/${id}/${action}`, { method: 'POST' })
            .then(r => r.json().then(data => {
                if (!r.ok) throw new Error(data.detail || '操作失败');
                return data;
            }))
            .then(data => {
                if (action === 'accept' && data.target_dataset_name) {
                    const hint = document.getElementById('mosaic-accept-hint') || (() => {
                        const el = document.createElement('div');
                        el.id = 'mosaic-accept-hint';
                        el.className = 'alert alert-success py-2 small';
                        document.getElementById('mosaic-candidates').before(el);
                        return el;
                    })();
                    hint.textContent = `已写入数据集「${data.target_dataset_name}」，` +
                        `当前共 ${data.target_image_count} 张。拼图单独存放，不会污染源数据集。`;
                }
                // 当前筛选是"待审核"时，处理过的应该从列表里消失
                if (document.getElementById('mosaic-filter').value === 'pending') {
                    card.remove();
                }
                this.loadMosaicCandidates();
            })
            .catch(err => {
                alert('操作失败: ' + err.message);
                card.querySelectorAll('button').forEach(b => { b.disabled = false; });
            });
    }

    destroy() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
    }
}

window.batchProcessingManager = new BatchProcessingManager();
