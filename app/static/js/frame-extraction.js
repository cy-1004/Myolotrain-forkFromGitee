// 视频抽帧与自动命名模块
(function () {
    const API = '/api/frame-extraction';

    let currentTaskId = null;
    let pollTimer = null;
    let selectedFiles = [];

    function el(id) { return document.getElementById(id); }

    function bindEvents() {
        currentTaskId = null;
        selectedFiles = [];
        stopPolling();

        // 输入模式：多选文件 / 整个文件夹
        document.querySelectorAll('input[name="fe-input-mode"]').forEach(r => {
            r.addEventListener('change', function () {
                const input = el('fe-video-input');
                if (this.value === 'folder') {
                    input.setAttribute('webkitdirectory', '');
                    input.setAttribute('directory', '');
                } else {
                    input.removeAttribute('webkitdirectory');
                    input.removeAttribute('directory');
                }
                input.value = '';
                selectedFiles = [];
                el('fe-selected-list').textContent = '';
            });
        });

        // 文件选择：只保留受支持的视频
        el('fe-video-input').addEventListener('change', function () {
            const exts = ['.mp4', '.avi', '.mov', '.mkv'];
            selectedFiles = Array.from(this.files).filter(f =>
                exts.some(e => f.name.toLowerCase().endsWith(e))
            );
            const listEl = el('fe-selected-list');
            if (selectedFiles.length === 0) {
                listEl.innerHTML = '<span class="text-danger">未选中受支持的视频文件</span>';
            } else {
                listEl.textContent = `已选择 ${selectedFiles.length} 个视频：` +
                    selectedFiles.slice(0, 8).map(f => f.name).join('、') +
                    (selectedFiles.length > 8 ? ' …' : '');
            }
        });

        // 抽帧方式切换
        document.querySelectorAll('input[name="fe-method"]').forEach(r => {
            r.addEventListener('change', function () {
                el('fe-time-row').style.display = this.value === 'time' ? '' : 'none';
                el('fe-frame-row').style.display = this.value === 'frame' ? '' : 'none';
            });
        });

        // 命名模板预设 / 自定义
        el('fe-template-preset').addEventListener('change', function () {
            const custom = el('fe-template-custom');
            if (this.value === '__custom__') {
                custom.style.display = '';
                custom.focus();
            } else {
                custom.style.display = 'none';
                custom.value = this.value;
            }
            el('fe-template-feedback').textContent = '';
        });
        el('fe-template-custom').addEventListener('input', validateTemplate);

        // 图像格式 -> 质量可见性
        el('fe-format').addEventListener('change', function () {
            el('fe-quality-col').style.display = this.value === 'jpg' ? '' : 'none';
        });

        // 调整尺寸
        el('fe-resize-check').addEventListener('change', function () {
            el('fe-resize-options').style.display = this.checked ? '' : 'none';
        });

        el('fe-start-btn').addEventListener('click', startExtraction);
        el('fe-download-btn').addEventListener('click', function () {
            if (currentTaskId) window.open(`${API}/download/${currentTaskId}`, '_blank');
        });
        el('fe-delete-btn').addEventListener('click', deleteCache);
        el('fe-to-annotation-btn').addEventListener('click', function () {
            const modal = new bootstrap.Modal(el('fe-annotation-modal'));
            modal.show();
        });
        el('fe-anno-create-btn').addEventListener('click', createAnnotationProject);
    }

    function getTemplate() {
        const preset = el('fe-template-preset').value;
        return preset === '__custom__' ? el('fe-template-custom').value.trim() : preset;
    }

    async function validateTemplate() {
        const tpl = el('fe-template-custom').value.trim();
        const fb = el('fe-template-feedback');
        if (!tpl) { fb.textContent = ''; return true; }
        try {
            const resp = await authenticatedFetch(`${API}/validate-template`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ template: tpl })
            });
            const data = await resp.json();
            if (data.valid) {
                fb.innerHTML = '<span class="text-success">模板可用 ✓</span>';
                return true;
            }
            fb.innerHTML = `<span class="text-danger">${data.message}</span>`;
            return false;
        } catch (e) {
            return true; // 校验接口异常不阻塞提交，交由后端最终校验
        }
    }

    async function startExtraction() {
        if (selectedFiles.length === 0) {
            alert('请先选择至少一个视频文件');
            return;
        }
        const template = getTemplate();
        if (!template) { alert('命名模板不能为空'); return; }

        const method = document.querySelector('input[name="fe-method"]:checked').value;
        const structure = document.querySelector('input[name="fe-structure"]:checked').value;

        const fd = new FormData();
        selectedFiles.forEach(f => fd.append('videos', f, f.name));
        fd.append('method', method);
        fd.append('interval_seconds', el('fe-interval-seconds').value || '1.0');
        fd.append('interval_frames', el('fe-interval-frames').value || '5');
        fd.append('skip_start', el('fe-skip-start').value || '0');
        fd.append('skip_end', el('fe-skip-end').value || '0');
        fd.append('naming_template', template);
        fd.append('image_format', el('fe-format').value);
        fd.append('jpg_quality', el('fe-quality').value || '95');
        fd.append('subfolder', structure === 'subfolder' ? 'true' : 'false');
        if (el('fe-resize-check').checked) {
            fd.append('resize_width', el('fe-resize-width').value || '640');
            fd.append('resize_height', el('fe-resize-height').value || '480');
        }

        const btn = el('fe-start-btn');
        btn.disabled = true;
        btn.textContent = '正在上传…';
        el('fe-idle').style.display = 'none';
        el('fe-result-area').style.display = 'none';
        el('fe-progress-area').style.display = '';
        el('fe-video-log').innerHTML = '';
        setProgress(0, '正在上传视频…');

        try {
            const resp = await authenticatedFetch(`${API}/extract`, { method: 'POST', body: fd });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: '请求失败' }));
                throw new Error(err.detail || '抽帧任务启动失败');
            }
            const data = await resp.json();
            currentTaskId = data.task_id;
            setProgress(2, `任务已启动，共 ${data.video_count} 个视频，正在处理…`);
            startPolling();
        } catch (e) {
            alert('错误: ' + e.message);
            el('fe-progress-area').style.display = 'none';
            el('fe-idle').style.display = '';
        } finally {
            btn.disabled = false;
            btn.textContent = '开始抽帧';
        }
    }

    function startPolling() {
        stopPolling();
        pollTimer = setInterval(pollStatus, 1500);
        pollStatus();
    }

    function stopPolling() {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    async function pollStatus() {
        if (!currentTaskId) return;
        try {
            const resp = await authenticatedFetch(`${API}/status/${currentTaskId}`);
            if (!resp.ok) return;
            const s = await resp.json();
            renderStatus(s);
            if (s.status === 'completed') {
                stopPolling();
                onCompleted(s);
            }
        } catch (e) { /* 网络抖动，下次轮询重试 */ }
    }

    function renderStatus(s) {
        const total = s.total_videos || 0;
        const processed = s.processed_videos || 0;
        let pct = total ? Math.round(processed / total * 100) : 0;
        // 处理中的视频叠加其内部进度，进度条更平滑
        if (s.status === 'processing' && total && typeof s.current_progress === 'number') {
            pct = Math.min(99, Math.round(((processed + s.current_progress / 100) / total) * 100));
        }
        let text = `已处理 ${processed}/${total} 个视频，已导出 ${s.total_frames || 0} 张图片`;
        if (s.current_video) text += `｜当前：${s.current_video}`;
        setProgress(pct, text);

        if (Array.isArray(s.videos)) {
            el('fe-video-log').innerHTML = s.videos.map(v => {
                if (v.status === 'success') {
                    return `<li class="list-group-item d-flex justify-content-between">
                        <span>✅ ${escapeHtml(v.video)}</span><span class="text-muted">${v.extracted_frames} 帧</span></li>`;
                }
                return `<li class="list-group-item text-danger">⚠️ ${escapeHtml(v.video)}：${escapeHtml(v.error || '处理失败')}（已跳过）</li>`;
            }).join('');
        }
    }

    function onCompleted(s) {
        setProgress(100, '处理完成');
        const okVideos = (s.videos || []).filter(v => v.status === 'success').length;
        el('fe-result-area').style.display = '';
        el('fe-total-frames').textContent = s.total_frames || 0;
        el('fe-ok-videos').textContent = okVideos;
        el('fe-all-videos').textContent = s.total_videos || 0;
        el('fe-progress-bar').classList.remove('progress-bar-animated');
        loadGallery();
    }

    async function loadGallery() {
        if (!currentTaskId) return;
        try {
            const resp = await authenticatedFetch(`${API}/frames/${currentTaskId}?limit=24`);
            const data = await resp.json();
            const gallery = el('fe-gallery');
            const token = localStorage.getItem('access_token');
            gallery.innerHTML = (data.frames || []).map(rel => {
                const url = `${API}/frame/${currentTaskId}/${encodeURI(rel)}`;
                return `<div class="col-3"><img src="${url}" class="img-fluid rounded border" title="${escapeHtml(rel)}" loading="lazy"></div>`;
            }).join('');
            if (data.total > (data.frames || []).length) {
                gallery.innerHTML += `<div class="col-12 text-muted small mt-2">仅预览前 ${data.frames.length} 张，共 ${data.total} 张。</div>`;
            }
        } catch (e) { /* 忽略预览失败 */ }
    }

    async function createAnnotationProject() {
        if (!currentTaskId) return;
        const name = el('fe-anno-name').value.trim();
        const classesRaw = el('fe-anno-classes').value.trim();
        if (!name) { alert('请填写项目名称'); return; }
        if (!classesRaw) { alert('请至少填写一个类别'); return; }
        const classes = classesRaw.split(',').map(c => c.trim()).filter(Boolean);

        const btn = el('fe-anno-create-btn');
        btn.disabled = true;
        btn.textContent = '创建中…';
        try {
            const resp = await authenticatedFetch(`${API}/to-annotation/${currentTaskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    project_type: el('fe-anno-type').value,
                    classes: classes
                })
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: '创建失败' }));
                throw new Error(err.detail || '创建标注项目失败');
            }
            const data = await resp.json();
            bootstrap.Modal.getInstance(el('fe-annotation-modal')).hide();
            if (confirm(`已创建标注项目（${data.image_count} 张图片）。是否立即前往在线标注？`)) {
                loadPage('annotation');
            }
        } catch (e) {
            alert('错误: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = '创建并跳转';
        }
    }

    async function deleteCache() {
        if (!currentTaskId) return;
        if (!confirm('确定删除服务器上本次抽帧的缓存吗？')) return;
        try {
            await authenticatedFetch(`${API}/${currentTaskId}`, { method: 'DELETE' });
            currentTaskId = null;
            el('fe-result-area').style.display = 'none';
            el('fe-progress-area').style.display = 'none';
            el('fe-idle').style.display = '';
            el('fe-idle').textContent = '缓存已删除。可重新设置参数抽帧。';
        } catch (e) { alert('删除缓存失败: ' + e.message); }
    }

    function setProgress(pct, text) {
        const bar = el('fe-progress-bar');
        bar.style.width = pct + '%';
        bar.textContent = pct + '%';
        if (text) el('fe-progress-text').textContent = text;
    }

    function escapeHtml(str) {
        return String(str).replace(/[&<>"']/g, c => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
        ));
    }

    window.frameExtraction = { bindEvents };
})();
