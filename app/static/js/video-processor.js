// 视频处理模块
class VideoProcessor {
    constructor() {
        // 视频处理相关属性
        this.isDetecting = false;
        this.stream = null;
        this.animationFrameId = null;
        this.lastFrameTime = 0;
        this.fps = 0;
        this.detectedObjects = 0;
        
        // 目标物体监控相关变量
        this.targetObjects = [];
        this.lastAlertTime = 0;
        this.alertCooldown = 3000; // 默认3秒冷却时间
        this.alertThreshold = 0.5; // 默认报警置信度阈值
        this.visualAlertEnabled = true;
        this.soundAlertEnabled = true;
        this.isAlertActive = false;
        
        // 轨迹记录和预测相关变量
        this.trajectoryEnabled = false;
    }

    // 加载视频处理页面
    loadVideoPage() {
        console.log('Loading Video Processing page...');

        // 加载覆盖层已完全移除

        // 确保所有结果区域也是隐藏的
        const resultAreas = [
            'extract-frames-result',
            'detect-scenes-result',
            'detect-motion-result'
        ];

        resultAreas.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.style.display = 'none';
            }
        });

        // 加载模型列表（用于实时检测功能）
        fetch(`${API_URL}/models/`)
            .then(response => response.json())
            .then(models => {
                console.log('Loaded models for video detection:', models.length);

                const modelSelect = document.getElementById('rt-model-select');
                if (modelSelect) {
                    // 清空现有选项（除了第一个默认选项）
                    while (modelSelect.options.length > 1) {
                        modelSelect.remove(1);
                    }

                    // 添加检测模型选项
                    models.forEach(model => {
                        if (model.task === 'detect') {
                            const option = document.createElement('option');
                            option.value = model.id;
                            option.textContent = `${model.name} (${model.type})`;
                            modelSelect.appendChild(option);
                        }
                    });

                    // 如果没有检测模型，显示提示
                    if (modelSelect.options.length <= 1) {
                        const option = document.createElement('option');
                        option.value = "";
                        option.textContent = "没有可用的检测模型";
                        option.disabled = true;
                        modelSelect.appendChild(option);
                    }
                }
            })
            .catch(error => {
                console.error('加载模型失败:', error);

                // 在出错时添加错误选项
                const modelSelect = document.getElementById('rt-model-select');
                if (modelSelect) {
                    const option = document.createElement('option');
                    option.value = "";
                    option.textContent = "加载模型失败";
                    option.disabled = true;
                    modelSelect.appendChild(option);
                }
            });
    }

    // 绑定视频处理页面事件
    bindVideoEvents() {
        console.log('Binding Video Processing events...');

        // 加载覆盖层已完全移除

        // 使用setTimeout确保DOM元素已经加载
        setTimeout(() => {
            console.log('Delayed binding of Video Processing events...');
            this.bindVideoEventHandlers();
        }, 500);
    }

    // 实际绑定视频处理事件处理程序
    bindVideoEventHandlers() {
        console.log('开始绑定视频处理事件处理程序...');
        
        // 检查关键DOM元素是否存在
        const extractFramesForm = document.getElementById('extract-frames-form');
        const videoUpload = document.getElementById('video-upload');
        const interval = document.getElementById('interval');
        
        console.log('DOM元素检查:');
        console.log('extract-frames-form:', extractFramesForm);
        console.log('video-upload:', videoUpload);
        console.log('interval:', interval);
        
        // 提取帧相关事件
        const resizeFramesCheck = document.getElementById('resize-frames-check');
        const resizeFramesOptions = document.getElementById('resize-frames-options');
        if (resizeFramesCheck && resizeFramesOptions) {
            resizeFramesCheck.addEventListener('change', function() {
                resizeFramesOptions.style.display = this.checked ? 'block' : 'none';
            });
            console.log('调整帧大小事件已绑定');
        } else {
            console.log('调整帧大小元素未找到:', {resizeFramesCheck, resizeFramesOptions});
        }

        // 提取帧表单提交
        if (extractFramesForm) {
            console.log('找到提取帧表单，开始绑定提交事件...');
            extractFramesForm.addEventListener('submit', (e) => {
                e.preventDefault();

                const videoFile = document.getElementById('video-upload').files[0];
                if (!videoFile) {
                    alert('请选择视频文件');
                    return;
                }

                // 启用加载覆盖层
                const loadingOverlay = document.getElementById('video-loading-overlay');
                const loadingText = document.getElementById('video-loading-text');
                if (loadingOverlay) loadingOverlay.style.display = 'flex';
                if (loadingText) loadingText.textContent = '正在提取视频帧...';

                // 创建表单数据
                const formData = new FormData();

                // 手动添加表单字段，处理可选字段
                formData.append('video', document.getElementById('video-upload').files[0]);
                formData.append('interval', document.getElementById('interval').value);

                // 只有当max_frames有值时才添加
                const maxFrames = document.getElementById('max-frames').value;
                if (maxFrames.trim() !== '') {
                    formData.append('max_frames', maxFrames);
                }

                // 如果选择了调整帧大小，添加相关参数
                if (document.getElementById('resize-frames-check').checked) {
                    formData.append('resize_width', document.getElementById('resize-width').value);
                    formData.append('resize_height', document.getElementById('resize-height').value);
                }

                // 添加开始时间
                formData.append('start_time', document.getElementById('start-time').value);

                // 只有当end_time有值时才添加
                const endTime = document.getElementById('end-time').value;
                if (endTime.trim() !== '') {
                    formData.append('end_time', endTime);
                }

                // 发送请求
                // 显示加载状态
                    if (window.loadingOverlay === undefined) {
                        window.loadingOverlay = document.getElementById('video-loading-overlay');
                        window.loadingText = document.getElementById('video-loading-text');
                    }
                    if (window.loadingOverlay) window.loadingOverlay.style.display = 'flex';
                    if (window.loadingText) window.loadingText.textContent = '正在提取视频帧，请在\app\static\video_frames目录查看';

                    authenticatedFetch(`${API_URL}/video/extract-frames`, {
                        method: 'POST',
                        body: formData
                    })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || '提取帧失败'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 关闭加载覆盖层
                    if (window.loadingOverlay) window.loadingOverlay.style.display = 'none';
                    if (window.loadingText) window.loadingText.textContent = '提取完成';

                    // 显示提取结果
                    if (data && data.extraction_id) {
                        console.log('提取帧成功，提取ID:', data.extraction_id);
                        document.getElementById('extraction-id').textContent = data.extraction_id;
                        
                        // 显示结果区域
                        const resultArea = document.getElementById('extract-frames-result');
                        if (resultArea) resultArea.style.display = 'block';

                        // 显示处理中状态
                        document.getElementById('extracted-frames-count').textContent = '处理中...';
                        const framesGallery = document.getElementById('frames-gallery');
                        framesGallery.innerHTML = '<div class="col-12 text-center"><div class="alert alert-info">正在处理中，请稍候...</div></div>';
                        
                        // 显示输出目录
                        const outputDirElement = document.getElementById('output-dir-path');
                        if (outputDirElement) {
                            outputDirElement.textContent = data.output_dir;
                        }

                        // 绑定删除缓存按钮事件
                        const deleteCacheBtn = document.getElementById('delete-cache-btn');
                        if (deleteCacheBtn) {
                            deleteCacheBtn.onclick = () => {
                                if (confirm('确定要删除服务器上的帧缓存吗？')) {
                                    fetch(`${API_URL}/video/frames/${data.extraction_id}`, {
                                        method: 'DELETE'
                                    })
                                    .then(response => {
                                        if (response.ok) {
                                            return response.json();
                                        } else {
                                            return response.json().then(err => { throw new Error(err.detail || '删除失败'); });
                                        }
                                    })
                                    .then(result => {
                                        if (result.success) {
                                            alert('缓存已删除');
                                            // 隐藏结果区域
                                            if (resultArea) resultArea.style.display = 'none';
                                        } else {
                                            alert('删除失败: ' + result.message);
                                        }
                                    })
                                    .catch(error => {
                                        alert('删除失败: ' + error.message);
                                    });
                                }
                            };
                        }

                        // 开始轮询任务状态
                        const extractionId = data.extraction_id;
                        const statusInterval = setInterval(() => {
                            fetch(`${API_URL}/video/extraction-status/${extractionId}`)
                            .then(response => response.json())
                            .then(statusData => {
                                // 检查是否完成 - 无论info是否存在都要处理completed状态
                                if (statusData.status === 'completed') {
                                    clearInterval(statusInterval);
                                    
                                    // 显示提取结果
                                    const result = statusData.info?.result || {};
                                    document.getElementById('extracted-frames-count').textContent = result.extracted_frames || statusData.extracted_frames || 0;
                                    
                                    // 显示帧图像
                                    const framesGallery = document.getElementById('frames-gallery');
                                    framesGallery.innerHTML = '';

                                    // 检查帧数据是否存在
                                    const frames = result.frames || [];

                                    if (frames.length === 0) {
                                        framesGallery.innerHTML = '<div class="col-12 text-center"><div class="alert alert-info">未提取到帧</div></div>';
                                    } else {
                                        // 只显示前4帧，避免页面过长
                                        const framesToShow = frames.slice(0, 4);
                                        framesToShow.forEach(frame => {
                                            const col = document.createElement('div');
                                            col.className = 'col-md-3 mb-3';

                                            const card = document.createElement('div');
                                            card.className = 'card';

                                            const img = document.createElement('img');
                                            img.className = 'card-img-top';
                                            // 限制图片最大尺寸以提高加载性能
                                            img.style.maxWidth = '100%';
                                            img.style.height = '150px';
                                            img.style.objectFit = 'cover';
                                            // 请求调整尺寸后的图片以减少带宽使用
                                            img.src = `${API_URL}/video/frames/${data.extraction_id}/${frame}?width=300&height=200`;
                                            img.alt = `Frame ${frame}`;
                                            // 添加懒加载属性
                                            img.loading = 'lazy';

                                            const cardBody = document.createElement('div');
                                            cardBody.className = 'card-body';

                                            const cardText = document.createElement('p');
                                            cardText.className = 'card-text';
                                            cardText.textContent = `帧 ${frame}`;

                                            const downloadBtn = document.createElement('a');
                                            downloadBtn.className = 'btn btn-sm btn-primary';
                                            downloadBtn.href = `${API_URL}/video/frames/${data.extraction_id}/${frame}`;
                                            downloadBtn.download = frame;
                                            downloadBtn.textContent = '下载';

                                            cardBody.appendChild(cardText);
                                            cardBody.appendChild(downloadBtn);
                                            card.appendChild(img);
                                            card.appendChild(cardBody);
                                            col.appendChild(card);
                                            framesGallery.appendChild(col);
                                        });

                                        // 如果有更多帧，显示提示和预览全部按钮
                                        if (frames.length > 4) {
                                            const moreFrames = document.createElement('div');
                                            moreFrames.className = 'col-12 text-center mt-3';
                                            moreFrames.innerHTML = `
                                                <div class="alert alert-info">
                                                    还有 ${frames.length - 4} 帧未显示
                                                    <button class="btn btn-sm btn-outline-primary ms-2" id="preview-all-frames">预览全部</button>
                                                </div>
                                            `;
                                            framesGallery.appendChild(moreFrames);
                                            
                                            // 绑定预览全部按钮事件
                                            document.getElementById('preview-all-frames').addEventListener('click', function() {
                                                // 清空画廊
                                                framesGallery.innerHTML = '';
                                                
                                                // 分批显示帧，避免一次性加载过多图片
                                                const batchSize = 20; // 每批显示20帧
                                                let currentIndex = 0;
                                                
                                                const displayBatch = () => {
                                                    const batchEnd = Math.min(currentIndex + batchSize, frames.length);
                                                    const batchFrames = frames.slice(currentIndex, batchEnd);
                                                    
                                                    batchFrames.forEach(frame => {
                                                        const col = document.createElement('div');
                                                        col.className = 'col-md-3 mb-3';

                                                        const card = document.createElement('div');
                                                        card.className = 'card';

                                                        const img = document.createElement('img');
                                                        img.className = 'card-img-top';
                                                        // 限制图片最大尺寸以提高加载性能
                                                        img.style.maxWidth = '100%';
                                                        img.style.height = '150px';
                                                        img.style.objectFit = 'cover';
                                                        // 请求调整尺寸后的图片以减少带宽使用
                                                        img.src = `${API_URL}/video/frames/${data.extraction_id}/${frame}?width=300&height=200`;
                                                        img.alt = `Frame ${frame}`;
                                                        // 添加懒加载属性
                                                        img.loading = 'lazy';

                                                        const cardBody = document.createElement('div');
                                                        cardBody.className = 'card-body';

                                                        const cardText = document.createElement('p');
                                                        cardText.className = 'card-text';
                                                        cardText.textContent = `帧 ${frame}`;

                                                        const downloadBtn = document.createElement('a');
                                                        downloadBtn.className = 'btn btn-sm btn-primary';
                                                        downloadBtn.href = `${API_URL}/video/frames/${data.extraction_id}/${frame}`;
                                                        downloadBtn.download = frame;
                                                        downloadBtn.textContent = '下载';

                                                        cardBody.appendChild(cardText);
                                                        cardBody.appendChild(downloadBtn);
                                                        card.appendChild(img);
                                                        card.appendChild(cardBody);
                                                        col.appendChild(card);
                                                        framesGallery.appendChild(col);
                                                    });
                                                    
                                                    currentIndex = batchEnd;
                                                    
                                                    // 如果还有更多帧，添加"加载更多"按钮
                                                    if (currentIndex < frames.length) {
                                                        const loadMoreDiv = document.createElement('div');
                                                        loadMoreDiv.className = 'col-12 text-center mt-3';
                                                        loadMoreDiv.innerHTML = `
                                                            <button class="btn btn-outline-primary" id="load-more-frames">加载更多 (${frames.length - currentIndex} 帧剩余)</button>
                                                        `;
                                                        framesGallery.appendChild(loadMoreDiv);
                                                        
                                                        document.getElementById('load-more-frames').addEventListener('click', function() {
                                                            loadMoreDiv.remove();
                                                            displayBatch();
                                                        });
                                                    }
                                                };
                                                
                                                displayBatch();
                                            });
                                        }

                                        // 绑定下载所有帧按钮事件
                                        const downloadAllBtn = document.getElementById('download-all-frames');
                                        if (downloadAllBtn) {
                                            downloadAllBtn.style.display = 'block';
                                            downloadAllBtn.onclick = function() {
                                                // 创建一个临时的下载链接
                                                const downloadUrl = `${API_URL}/video/download-frames/${data.extraction_id}`;
                                                const link = document.createElement('a');
                                                link.href = downloadUrl;
                                                link.download = `frames_${data.extraction_id}.zip`;
                                                document.body.appendChild(link);
                                                link.click();
                                                document.body.removeChild(link);
                                            };
                                        }
                                    }
                                } else if (statusData.status === 'failed') {
                                    clearInterval(statusInterval);
                                    document.getElementById('extracted-frames-count').textContent = '0';
                                    framesGallery.innerHTML = `<div class="col-12 text-center"><div class="alert alert-danger">提取失败: ${statusData.error || '未知错误'}</div></div>`;
                                } else if (statusData.status === 'processing' || statusData.status === 'started') {
                                    // 更新进度
                                    document.getElementById('extracted-frames-count').textContent = statusData.extracted_frames || '0';
                                    const progressText = statusData.progress ? ` (${statusData.progress}%)` : '';
                                    framesGallery.innerHTML = `<div class="col-12 text-center"><div class="alert alert-info">正在处理中${progressText}，请稍候...</div>
                                    <div class="progress mt-2">
                                      <div class="progress-bar" role="progressbar" style="width: ${statusData.progress || 0}%" aria-valuenow="${statusData.progress || 0}" aria-valuemin="0" aria-valuemax="100">${statusData.progress || 0}%</div>
                                    </div></div>`;
                                }
                            })
                            .catch(error => {
                                console.error('获取任务状态失败:', error);
                                clearInterval(statusInterval);
                            });
                        }, 1000); // 每秒查询一次状态
                    } else {
                        console.error('提取帧响应数据格式错误:', data);
                    }
                })
                .catch(error => {
                    // 关闭加载覆盖层
                    if (window.loadingOverlay) window.loadingOverlay.style.display = 'none';
                    if (window.loadingText) window.loadingText.textContent = '提取完成';
                    alert('错误: ' + error.message);
                });
            });
        }

        // 场景检测相关事件
        const sceneThreshold = document.getElementById('scene-threshold');
        const sceneThresholdValue = document.getElementById('scene-threshold-value');
        if (sceneThreshold && sceneThresholdValue) {
            sceneThreshold.addEventListener('input', function() {
                sceneThresholdValue.textContent = this.value;
            });
        }

        // 场景检测表单提交
        const detectScenesForm = document.getElementById('detect-scenes-form');
        if (detectScenesForm) {
            detectScenesForm.addEventListener('submit', (e) => {
                e.preventDefault();

                const videoFile = document.getElementById('scenes-video-upload').files[0];
                if (!videoFile) {
                    alert('请选择视频文件');
                    return;
                }

                // 加载覆盖层已禁用
                // document.getElementById('video-loading-overlay').style.display = 'flex';
                // document.getElementById('video-loading-text').textContent = '正在检测视频场景...';

                // 创建表单数据
                const formData = new FormData(e.target);

                // 发送请求
                authenticatedFetch(`${API_URL}/video/detect-scenes`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || '检测场景失败'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 关闭加载覆盖层
                    if (window.loadingOverlay) window.loadingOverlay.style.display = 'none';
                    if (window.loadingText) window.loadingText.textContent = '提取完成';

                    // 显示任务信息
                    if (data && data.task_id) {
                        document.getElementById('scene-task-id').textContent = data.task_id;

                        // 显示结果区域
                        document.getElementById('detect-scenes-result').style.display = 'block';
                        document.getElementById('scene-count').textContent = '处理中...';

                        // 清空场景列表
                        const scenesTableBody = document.getElementById('scenes-table-body');
                        scenesTableBody.innerHTML = '<tr><td colspan="5" class="text-center">正在处理中，请稍候...</td></tr>';

                        // 轮询任务状态
                        const taskId = data.task_id;
                        const statusInterval = setInterval(() => {
                            authenticatedFetch(`${API_URL}/video/scene-detection-status/${taskId}`)
                            .then(response => response.json())
                            .then(statusData => {
                                if (statusData.status === 'completed' && statusData.info && statusData.info.result) {
                                    clearInterval(statusInterval);

                                    // 显示检测结果
                                    const result = statusData.info.result;
                                    document.getElementById('scene-count').textContent = result.scene_count || 0;

                                    // 显示场景列表
                                    const scenesTableBody = document.getElementById('scenes-table-body');
                                    scenesTableBody.innerHTML = '';

                                    // 检查场景数据是否存在
                                    const scenes = result.scenes || [];

                                    if (scenes.length === 0) {
                                        scenesTableBody.innerHTML = '<tr><td colspan="5" class="text-center">未检测到场景</td></tr>';
                                    } else {
                                        scenes.forEach((scene, index) => {
                                            const row = document.createElement('tr');

                                            const indexCell = document.createElement('td');
                                            indexCell.textContent = index + 1;

                                            const startTimeCell = document.createElement('td');
                                            startTimeCell.textContent = scene.start_time.toFixed(2) + ' 秒';

                                            const endTimeCell = document.createElement('td');
                                            endTimeCell.textContent = scene.end_time.toFixed(2) + ' 秒';

                                            const durationCell = document.createElement('td');
                                            durationCell.textContent = scene.duration.toFixed(2) + ' 秒';

                                            const actionsCell = document.createElement('td');
                                            const extractBtn = document.createElement('button');
                                            extractBtn.className = 'btn btn-sm btn-primary';
                                            extractBtn.textContent = '提取关键帧';
                                            extractBtn.onclick = function() {
                                                // 这里可以实现提取场景关键帧的功能
                                                alert('此功能尚未实现');
                                            };
                                            actionsCell.appendChild(extractBtn);

                                            row.appendChild(indexCell);
                                            row.appendChild(startTimeCell);
                                            row.appendChild(endTimeCell);
                                            row.appendChild(durationCell);
                                            row.appendChild(actionsCell);

                                            scenesTableBody.appendChild(row);
                                        });
                                    }
                                } else if (statusData.status === 'failed') {
                                    clearInterval(statusInterval);
                                    document.getElementById('scene-count').textContent = '0';
                                    scenesTableBody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">检测失败: ${statusData.error || '未知错误'}</td></tr>`;
                                }
                            })
                            .catch(error => {
                                console.error('获取任务状态失败:', error);
                            });
                        }, 2000);
                    } else {
                        console.error('检测场景响应数据格式错误:', data);
                    }
                })
                .catch(error => {
                    // 关闭加载覆盖层
                    if (window.loadingOverlay) window.loadingOverlay.style.display = 'none';
                    if (window.loadingText) window.loadingText.textContent = '提取完成';
                    alert('错误: ' + error.message);
                });
            });
        }

        // 运动检测相关事件
        const motionSensitivity = document.getElementById('motion-sensitivity');
        const motionSensitivityValue = document.getElementById('motion-sensitivity-value');
        if (motionSensitivity && motionSensitivityValue) {
            motionSensitivity.addEventListener('input', function() {
                motionSensitivityValue.textContent = this.value;
            });
        }

        // 运动检测表单提交
        const detectMotionForm = document.getElementById('detect-motion-form');
        if (detectMotionForm) {
            detectMotionForm.addEventListener('submit', (e) => {
                e.preventDefault();

                const videoFile = document.getElementById('motion-video-upload').files[0];
                if (!videoFile) {
                    alert('请选择视频文件');
                    return;
                }

                // 加载覆盖层已禁用
                // document.getElementById('video-loading-overlay').style.display = 'flex';
                // document.getElementById('video-loading-text').textContent = '正在检测视频运动...';

                // 创建表单数据
                const formData = new FormData(e.target);

                // 发送请求
                authenticatedFetch(`${API_URL}/video/detect-motion`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => { throw new Error(err.detail || '检测运动失败'); });
                    }
                    return response.json();
                })
                .then(data => {
                    // 关闭加载覆盖层
                    if (window.loadingOverlay) window.loadingOverlay.style.display = 'none';
                    if (window.loadingText) window.loadingText.textContent = '提取完成';

                    // 显示任务信息
                    if (data && data.task_id) {
                        document.getElementById('motion-task-id').textContent = data.task_id;

                        // 显示结果区域
                        document.getElementById('detect-motion-result').style.display = 'block';
                        document.getElementById('motion-frame-count').textContent = '处理中...';

                        // 清空运动帧列表
                        const motionTableBody = document.getElementById('motion-table-body');
                        motionTableBody.innerHTML = '<tr><td colspan="4" class="text-center">正在处理中，请稍候...</td></tr>';

                        // 轮询任务状态
                        const taskId = data.task_id;
                        const statusInterval = setInterval(() => {
                            authenticatedFetch(`${API_URL}/video/motion-detection-status/${taskId}`)
                            .then(response => response.json())
                            .then(statusData => {
                                if (statusData.status === 'completed' && statusData.info && statusData.info.result) {
                                    clearInterval(statusInterval);

                                    // 显示检测结果
                                    const result = statusData.info.result;
                                    document.getElementById('motion-frame-count').textContent = result.motion_frame_count || 0;

                                    // 显示运动帧列表
                                    const motionTableBody = document.getElementById('motion-table-body');
                                    motionTableBody.innerHTML = '';

                                    // 检查运动帧数据是否存在
                                    const motionFrames = result.motion_frames || [];

                                    if (motionFrames.length === 0) {
                                        motionTableBody.innerHTML = '<tr><td colspan="4" class="text-center">未检测到运动</td></tr>';
                                    } else {
                                        // 只显示前50帧，避免页面过长
                                        const framesToShow = motionFrames.slice(0, 50);
                                        framesToShow.forEach(frame => {
                                            const row = document.createElement('tr');

                                            const frameIndexCell = document.createElement('td');
                                            frameIndexCell.textContent = frame.frame_index;

                                            const timestampCell = document.createElement('td');
                                            timestampCell.textContent = frame.timestamp.toFixed(2) + ' 秒';

                                            const motionCountCell = document.createElement('td');
                                            motionCountCell.textContent = frame.motion_regions.length;

                                            const actionsCell = document.createElement('td');
                                            const viewBtn = document.createElement('button');
                                            viewBtn.className = 'btn btn-sm btn-primary';
                                            viewBtn.textContent = '查看详情';
                                            viewBtn.onclick = function() {
                                                // 这里可以实现查看运动详情的功能
                                                alert('此功能尚未实现');
                                            };
                                            actionsCell.appendChild(viewBtn);

                                            row.appendChild(frameIndexCell);
                                            row.appendChild(timestampCell);
                                            row.appendChild(motionCountCell);
                                            row.appendChild(actionsCell);

                                            motionTableBody.appendChild(row);
                                        });

                                        // 如果有更多帧，显示提示
                                        if (motionFrames.length > 50) {
                                            const row = document.createElement('tr');
                                            const cell = document.createElement('td');
                                            cell.colSpan = 4;
                                            cell.className = 'text-center';
                                            cell.innerHTML = `<div class="alert alert-info m-0">还有 ${motionFrames.length - 50} 帧未显示</div>`;
                                            row.appendChild(cell);
                                            motionTableBody.appendChild(row);
                                        }
                                    }
                                } else if (statusData.status === 'failed') {
                                    clearInterval(statusInterval);
                                    document.getElementById('motion-frame-count').textContent = '0';
                                    motionTableBody.innerHTML = `<tr><td colspan="4" class="text-center text-danger">检测失败: ${statusData.error || '未知错误'}</td></tr>`;
                                }
                            })
                            .catch(error => {
                                console.error('获取任务状态失败:', error);
                            });
                        }, 2000);
                    } else {
                        console.error('检测运动响应数据格式错误:', data);
                    }
                })
                .catch(error => {
                    // 关闭加载覆盖层
                    if (window.loadingOverlay) window.loadingOverlay.style.display = 'none';
                    if (window.loadingText) window.loadingText.textContent = '提取完成';
                    alert('错误: ' + error.message);
                });
            });
        }

        // 视频源选择事件
        const sourceWebcam = document.getElementById('source-webcam');
        const sourceFile = document.getElementById('source-file');
        const sourceStream = document.getElementById('source-stream');
        const webcamOptions = document.getElementById('webcam-options');
        const videoFileOptions = document.getElementById('video-file-options');
        const streamOptions = document.getElementById('stream-options');

        if (sourceWebcam && sourceFile && sourceStream && webcamOptions && videoFileOptions && streamOptions) {
            sourceWebcam.addEventListener('change', function() {
                if (this.checked) {
                    webcamOptions.style.display = 'block';
                    videoFileOptions.style.display = 'none';
                    streamOptions.style.display = 'none';
                }
            });

            sourceFile.addEventListener('change', function() {
                if (this.checked) {
                    webcamOptions.style.display = 'none';
                    videoFileOptions.style.display = 'block';
                    streamOptions.style.display = 'none';
                }
            });

            sourceStream.addEventListener('change', function() {
                if (this.checked) {
                    webcamOptions.style.display = 'none';
                    videoFileOptions.style.display = 'none';
                    streamOptions.style.display = 'block';
                    // 加载流媒体列表
                    window.videoProcessor.loadStreamsList();
                }
            });
        }

        // 实时检测阈值滑块事件
        const rtConfThreshold = document.getElementById('rt-conf-threshold');
        const rtConfValue = document.getElementById('rt-conf-value');
        if (rtConfThreshold && rtConfValue) {
            rtConfThreshold.addEventListener('input', function() {
                rtConfValue.textContent = this.value;
            });
        }

        const rtIouThreshold = document.getElementById('rt-iou-threshold');
        const rtIouValue = document.getElementById('rt-iou-value');
        if (rtIouThreshold && rtIouValue) {
            rtIouThreshold.addEventListener('input', function() {
                rtIouValue.textContent = this.value;
            });
        }

        // 实时检测功能
        const startDetectionBtn = document.getElementById('start-detection-btn');
        const stopDetectionBtn = document.getElementById('stop-detection-btn');
        const rtModelSelect = document.getElementById('rt-model-select');
        const videoElement = document.getElementById('video-element');
        const detectionCanvas = document.getElementById('detection-canvas');
        const fpsCounter = document.getElementById('fps-counter');
        const objectsCounter = document.getElementById('objects-counter');

        if (startDetectionBtn && stopDetectionBtn && rtModelSelect) {
            // 加载模型列表
            authenticatedFetch(`${API_URL}/models/?type=detection`)
                .then(response => response.json())
                .then(models => {
                    rtModelSelect.innerHTML = '<option value="">\u8bf7\u9009\u62e9\u6a21\u578b</option>';
                    models.forEach(model => {
                        const option = document.createElement('option');
                        option.value = model.id;
                        option.textContent = model.name;
                        rtModelSelect.appendChild(option);
                    });
                })
                .catch(error => {
                    console.error('加载模型列表失败:', error);
                    rtModelSelect.innerHTML = '<option value="">\u52a0\u8f7d\u6a21\u578b\u5931\u8d25</option>';
                });

            // 流媒体管理按钮事件
            const refreshStreamsBtn = document.getElementById('refresh-streams-btn');
            const manageStreamsBtn = document.getElementById('manage-streams-btn');
            
            if (refreshStreamsBtn) {
                refreshStreamsBtn.addEventListener('click', function() {
                    window.videoProcessor.loadStreamsList();
                });
            }
            
            if (manageStreamsBtn) {
                manageStreamsBtn.addEventListener('click', function() {
                    window.videoProcessor.showStreamManagementModal();
                });
            }

            // 加载摄像头列表
            const webcamSelect = document.getElementById('webcam-select');
            if (webcamSelect) {
                // 检查浏览器是否支持 mediaDevices API
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    console.error('浏览器不支持 mediaDevices API');
                    webcamSelect.innerHTML = '<option value="">浏览器不支持摄像头访问</option>';

                    // 添加一个默认选项，即使获取失败也可以尝试使用默认摄像头
                    const defaultOption = document.createElement('option');
                    defaultOption.value = 'default';
                    defaultOption.textContent = '使用默认摄像头';
                    webcamSelect.appendChild(defaultOption);
                    return;
                }

                // 首先请求摄像头权限，这样可以获取摄像头的完整标签
                navigator.mediaDevices.getUserMedia({ video: true })
                    .then(stream => {
                        // 关闭流，我们只是为了获取摄像头标签
                        stream.getTracks().forEach(track => track.stop());

                        // 现在获取摄像头列表
                        return navigator.mediaDevices.enumerateDevices();
                    })
                    .then(devices => {
                        const videoDevices = devices.filter(device => device.kind === 'videoinput');
                        webcamSelect.innerHTML = '';

                        if (videoDevices.length === 0) {
                            const option = document.createElement('option');
                            option.value = '';
                            option.textContent = '未检测到摄像头';
                            webcamSelect.appendChild(option);
                        } else {
                            // 添加一个默认选项
                            const defaultOption = document.createElement('option');
                            defaultOption.value = '';
                            defaultOption.textContent = '选择摄像头';
                            webcamSelect.appendChild(defaultOption);

                            // 添加所有检测到的摄像头
                            videoDevices.forEach((device, index) => {
                                const option = document.createElement('option');
                                option.value = device.deviceId;
                                option.textContent = device.label || `摄像头 ${index + 1}`;
                                webcamSelect.appendChild(option);
                                console.log(`检测到摄像头: ${option.textContent} (ID: ${device.deviceId})`);
                            });

                            // 如果只有一个摄像头，自动选中它
                            if (videoDevices.length === 1) {
                                webcamSelect.value = videoDevices[0].deviceId;
                            }
                        }
                    })
                    .catch(error => {
                        // 仅在DEBUG模式启用且当前页面需要摄像头功能时才显示错误日志
                        if (typeof DEBUG_MODE !== 'undefined' && DEBUG_MODE && typeof currentPage !== 'undefined' && currentPage === 'video') {
                            console.error('获取摄像头列表失败:', error);
                        }
                        webcamSelect.innerHTML = '<option value="">\u83b7\u53d6\u6444\u50cf\u5934\u5931\u8d25</option>';

                        // 添加一个默认选项，即使获取失败也可以尝试使用默认摄像头
                        const defaultOption = document.createElement('option');
                        defaultOption.value = 'default';
                        defaultOption.textContent = '使用默认摄像头';
                        webcamSelect.appendChild(defaultOption);
                    });
            }

            // 监听报警设置变化
            document.getElementById('alert-threshold').addEventListener('input', (e) => {
                this.alertThreshold = parseFloat(e.target.value);
                document.getElementById('alert-threshold-value').textContent = this.alertThreshold.toFixed(2);
            });

            document.getElementById('alert-cooldown').addEventListener('input', (e) => {
                this.alertCooldown = parseInt(e.target.value) * 1000; // 转换为毫秒
                document.getElementById('alert-cooldown-value').textContent = e.target.value;
            });

            document.getElementById('visual-alert-check').addEventListener('change', (e) => {
                this.visualAlertEnabled = e.target.checked;
            });

            document.getElementById('sound-alert-check').addEventListener('change', (e) => {
                this.soundAlertEnabled = e.target.checked;
            });

            // 监听轨迹设置变化
            const enableTrajectory = document.getElementById('enable-trajectory');
            const trajectorySettings = document.getElementById('trajectory-settings');

            if (enableTrajectory && trajectorySettings) {
                enableTrajectory.addEventListener('change', (e) => {
                    this.trajectoryEnabled = e.target.checked;
                    trajectorySettings.style.display = e.target.checked ? 'block' : 'none';

                    // 更新轨迹设置
                    if (window.trajectory) {
                        window.trajectory.updateTrajectorySettings({ enabled: this.trajectoryEnabled });

                        // 如果禁用，清空所有轨迹
                        if (!this.trajectoryEnabled) {
                            window.trajectory.clearAllTrajectories();
                        }
                    }
                });
            }

            // 轨迹长度滑块
            const trajectoryLength = document.getElementById('trajectory-length');
            const trajectoryLengthValue = document.getElementById('trajectory-length-value');

            if (trajectoryLength && trajectoryLengthValue) {
                trajectoryLength.addEventListener('input', (e) => {
                    const maxLength = parseInt(e.target.value);
                    trajectoryLengthValue.textContent = maxLength;

                    if (window.trajectory) {
                        window.trajectory.updateTrajectorySettings({ maxLength: maxLength });
                    }
                });
            }

            // 预测步数滑块
            const predictionSteps = document.getElementById('prediction-steps');
            const predictionStepsValue = document.getElementById('prediction-steps-value');

            if (predictionSteps && predictionStepsValue) {
                predictionSteps.addEventListener('input', (e) => {
                    const steps = parseInt(e.target.value);
                    predictionStepsValue.textContent = steps;

                    if (window.trajectory) {
                        window.trajectory.updateTrajectorySettings({ predictionSteps: steps });
                    }
                });
            }

            // 显示轨迹线复选框
            const showTrajectoryLine = document.getElementById('show-trajectory-line');
            if (showTrajectoryLine) {
                showTrajectoryLine.addEventListener('change', (e) => {
                    if (window.trajectory) {
                        window.trajectory.updateTrajectorySettings({ showTrajectoryLine: e.target.checked });
                    }
                });
            }

            // 显示预测线复选框
            const showPredictionLine = document.getElementById('show-prediction-line');
            if (showPredictionLine) {
                showPredictionLine.addEventListener('change', (e) => {
                    if (window.trajectory) {
                        window.trajectory.updateTrajectorySettings({ showPredictionLine: e.target.checked });
                    }
                });
            }

            // 添加目标物体按钮事件
            document.getElementById('add-target-btn').addEventListener('click', () => {
                this.addTargetObject();
            });

            // 目标输入框回车键事件
            document.getElementById('target-objects').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.addTargetObject();
                }
            });

            // 关闭报警按钮事件
            document.getElementById('close-alert-btn').addEventListener('click', () => {
                this.hideAlert();
            });

            // 清空报警历史按钮事件
            document.getElementById('clear-alerts-btn').addEventListener('click', () => {
                this.clearAlertHistory();
            });

            // 开始检测按钮事件
            startDetectionBtn.addEventListener('click', () => {
                const modelId = rtModelSelect.value;
                if (!modelId) {
                    alert('请选择模型');
                    return;
                }

                // 检查是否已经在检测中
                if (this.isDetecting) return;

                // 获取视频源
                const videoSource = document.querySelector('input[name="video-source"]:checked').value;

                if (videoSource === 'stream') {
                    // 流媒体模式
                    const streamId = document.getElementById('stream-select').value;
                    if (!streamId) {
                        alert('请选择一个流媒体源');
                        return;
                    }
                    
                    // 对于流媒体，我们使用不同的检测方式
                    // 直接使用流媒体的单帧API进行检测
                    this.startStreamDetection(modelId, streamId);
                    return;
                    
                } else if (videoSource === 'webcam') {
                    let webcamId = webcamSelect.value;

                    // 如果没有选择摄像头，但有可用的摄像头
                    if (!webcamId) {
                        // 检查是否有默认选项
                        const defaultOption = Array.from(webcamSelect.options).find(option => option.value === 'default');
                        if (defaultOption) {
                            webcamId = 'default';
                            console.log('使用默认摄像头选项');
                        } else {
                            // 如果有非空选项，选择第一个
                            const nonEmptyOptions = Array.from(webcamSelect.options).filter(option => option.value);
                            if (nonEmptyOptions.length > 0) {
                                webcamId = nonEmptyOptions[0].value;
                                console.log('自动选择第一个摄像头:', webcamId);
                            } else {
                                alert('请选择摄像头');
                                return;
                            }
                        }
                    }

                    // 打开摄像头
                    console.log('尝试打开摄像头:', webcamId);

                    // 准备摄像头配置
                    let videoConstraints;

                    if (webcamId === 'default') {
                        // 使用默认摄像头
                        videoConstraints = { facingMode: 'user' };
                        console.log('使用默认摄像头配置');
                    } else {
                        // 使用指定摄像头
                        videoConstraints = { deviceId: { exact: webcamId } };
                        console.log('使用指定摄像头配置:', webcamId);
                    }

                    // 检查浏览器是否支持 mediaDevices API
                    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                        const errorMessage = '浏览器不支持摄像头访问。请使用现代浏览器（如Chrome、Firefox、Edge）或通过HTTPS访问。';
                        console.error(errorMessage);
                        alert(errorMessage);

                        // 更新状态
                        document.getElementById('detection-status').innerHTML =
                            `<span class="badge bg-danger">浏览器不支持摄像头</span>`;
                        return;
                    }

                    navigator.mediaDevices.getUserMedia({
                        video: videoConstraints,
                        audio: false
                    })
                    .then(mediaStream => {
                        this.stream = mediaStream;
                        videoElement.srcObject = mediaStream;
                        videoElement.style.display = 'block';
                        videoElement.play();

                        // 更新状态
                        document.getElementById('detection-status').innerHTML =
                            `<span class="badge bg-info">摄像头已就绪</span>`;

                        // 设置画布大小
                        videoElement.onloadedmetadata = () => {
                            detectionCanvas.width = videoElement.videoWidth;
                            detectionCanvas.height = videoElement.videoHeight;

                            // 初始化报警区域
                            if (window.alertZone) {
                                window.alertZone.resizeAlertZone(detectionCanvas.width, detectionCanvas.height);
                                window.alertZone.drawAlertZone();
                            }

                            // 初始化轨迹设置
                            if (window.trajectory) {
                                // 获取当前设置
                                const settings = window.trajectory.getSettings();

                                // 更新UI元素
                                const enableTrajectory = document.getElementById('enable-trajectory');
                                if (enableTrajectory) {
                                    enableTrajectory.checked = settings.enabled;
                                    this.trajectoryEnabled = settings.enabled;

                                    // 显示/隐藏设置面板
                                    const trajectorySettings = document.getElementById('trajectory-settings');
                                    if (trajectorySettings) {
                                        trajectorySettings.style.display = settings.enabled ? 'block' : 'none';
                                    }
                                }

                                // 更新轨迹长度滑块
                                const trajectoryLength = document.getElementById('trajectory-length');
                                const trajectoryLengthValue = document.getElementById('trajectory-length-value');
                                if (trajectoryLength && trajectoryLengthValue) {
                                    trajectoryLength.value = settings.maxLength;
                                    trajectoryLengthValue.textContent = settings.maxLength;
                                }

                                // 更新预测步数滑块
                                const predictionSteps = document.getElementById('prediction-steps');
                                const predictionStepsValue = document.getElementById('prediction-steps-value');
                                if (predictionSteps && predictionStepsValue) {
                                    predictionSteps.value = settings.predictionSteps;
                                    predictionStepsValue.textContent = settings.predictionSteps;
                                }

                                // 更新显示轨迹线复选框
                                const showTrajectoryLine = document.getElementById('show-trajectory-line');
                                if (showTrajectoryLine) {
                                    showTrajectoryLine.checked = settings.showTrajectoryLine;
                                }

                                // 更新显示预测线复选框
                                const showPredictionLine = document.getElementById('show-prediction-line');
                                if (showPredictionLine) {
                                    showPredictionLine.checked = settings.showPredictionLine;
                                }
                            }

                            this.startRealTimeDetection(modelId);
                        };
                    })
                    .catch(error => {
                        console.error('打开摄像头失败:', error);

                        // 显示更详细的错误信息
                        let errorMessage = error.message;

                        // 处理常见错误
                        if (errorMessage.includes('Permission denied') || errorMessage.includes('NotAllowedError')) {
                            errorMessage = '摄像头访问权限被拒绝。请在浏览器设置中允许摄像头访问权限。';
                        } else if (errorMessage.includes('NotFoundError') || errorMessage.includes('OverconstrainedError')) {
                            errorMessage = '找不到指定的摄像头设备。请尝试选择其他摄像头或使用默认摄像头。';
                        } else if (errorMessage.includes('NotReadableError')) {
                            errorMessage = '摄像头已被其他应用程序占用。请关闭可能正在使用摄像头的其他应用程序。';
                        }

                        // 显示错误信息
                        alert('打开摄像头失败: ' + errorMessage);

                        // 更新状态
                        document.getElementById('detection-status').innerHTML =
                            `<span class="badge bg-danger">摄像头错误: ${errorMessage}</span>`;

                        // 尝试使用默认摄像头
                        if (webcamId !== 'default' && confirm('是否尝试使用默认摄像头？')) {
                            // 再次检查浏览器是否支持 mediaDevices API
                            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                                const errorMessage = '浏览器不支持摄像头访问。请使用现代浏览器（如Chrome、Firefox、Edge）或通过HTTPS访问。';
                                console.error(errorMessage);
                                alert(errorMessage);
                                return;
                            }

                            navigator.mediaDevices.getUserMedia({
                                video: { facingMode: 'user' },
                                audio: false
                            })
                            .then(mediaStream => {
                                this.stream = mediaStream;
                                videoElement.srcObject = stream;
                                videoElement.style.display = 'block';
                                videoElement.play();

                                // 更新状态
                                document.getElementById('detection-status').innerHTML =
                                    `<span class="badge bg-info">默认摄像头已就绪</span>`;

                                // 设置画布大小
                                videoElement.onloadedmetadata = () => {
                                    detectionCanvas.width = videoElement.videoWidth;
                                    detectionCanvas.height = videoElement.videoHeight;

                                    // 初始化报警区域
                                    if (window.alertZone) {
                                        window.alertZone.resizeAlertZone(detectionCanvas.width, detectionCanvas.height);
                                        window.alertZone.drawAlertZone();
                                    }

                                    this.startRealTimeDetection(modelId);
                                };
                            })
                            .catch(fallbackError => {
                                console.error('使用默认摄像头也失败:', fallbackError);
                                alert('使用默认摄像头也失败: ' + fallbackError.message);
                            });
                        }
                    });
                } else {
                    const videoFile = document.getElementById('rt-video-upload').files[0];
                    if (!videoFile) {
                        alert('请选择视频文件');
                        return;
                    }

                    // 创建URL对象
                    const videoURL = URL.createObjectURL(videoFile);
                    videoElement.src = videoURL;
                    videoElement.style.display = 'block';
                    videoElement.loop = true;
                    videoElement.play();

                    // 更新状态
                    document.getElementById('detection-status').innerHTML =
                        `<span class="badge bg-info">视频已就绪</span>`;

                    // 设置画布大小
                    videoElement.onloadedmetadata = () => {
                        detectionCanvas.width = videoElement.videoWidth;
                        detectionCanvas.height = videoElement.videoHeight;

                        console.log('视频文件元数据加载完成，画布大小:', detectionCanvas.width, detectionCanvas.height);

                        // 初始化报警区域
                        if (window.alertZone) {
                            console.log('初始化报警区域');
                            window.alertZone.resizeAlertZone(detectionCanvas.width, detectionCanvas.height);
                        }

                        this.startRealTimeDetection(modelId);
                    };
                }
            });

            // 停止检测按钮事件
            stopDetectionBtn.addEventListener('click', () => {
                this.stopRealTimeDetection();
            });
        }

        console.log('Video Processing events bound successfully');
    }

    // 添加目标物体函数
    addTargetObject() {
        const input = document.getElementById('target-objects');
        const value = input.value.trim();

        if (!value) return;

        // 分割输入，允许多个目标用逗号分隔
        const newTargets = value.split(',').map(t => t.trim().toLowerCase()).filter(t => t);

        // 添加新目标，去除重复
        newTargets.forEach(target => {
            if (!this.targetObjects.includes(target)) {
                this.targetObjects.push(target);
            }
        });

        // 更新目标列表显示
        this.updateTargetList();

        // 清空输入框
        input.value = '';
    }

    // 更新目标列表显示
    updateTargetList() {
        const targetList = document.getElementById('target-list');
        targetList.innerHTML = '';

        if (this.targetObjects.length === 0) {
            targetList.innerHTML = '<span class="badge bg-secondary">暂无监控目标</span>';
            return;
        }

        this.targetObjects.forEach(target => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-primary me-2 mb-2';
            badge.innerHTML = `${target} <button type="button" class="btn-close btn-close-white" aria-label="Close" data-target="${target}"></button>`;
            targetList.appendChild(badge);

            // 添加删除按钮事件
            const closeBtn = badge.querySelector('.btn-close');
            closeBtn.addEventListener('click', (e) => {
                const targetToRemove = e.target.getAttribute('data-target');
                this.targetObjects = this.targetObjects.filter(t => t !== targetToRemove);
                this.updateTargetList();
            });
        });
    }

    // 检查目标物体函数
    checkTargetObjects(detections) {
        if (this.targetObjects.length === 0) return;

        // 检查是否在冷却时间内
        const now = Date.now();
        if (now - this.lastAlertTime < this.alertCooldown) return;

        // 检查报警区域启用状态
        const zoneCheckbox = document.getElementById('enable-alert-zone');
        const zoneEnabled = zoneCheckbox ? zoneCheckbox.checked : false;

        console.log('检查目标物体: 报警区域启用状态:', zoneEnabled);

        // 查找符合目标物体的检测结果
        const matchedDetections = detections.filter(detection => {
            // 获取类别名称
            let className = '';
            if (detection.class_name) {
                className = detection.class_name.toLowerCase();
            } else if (detection.class) {
                className = detection.class.toLowerCase();
            }

            // 检查置信度是否超过阈值
            const confidence = detection.confidence || 0;

            // 检查是否匹配目标物体和置信度
            const isTargetObject = this.targetObjects.includes(className) && confidence >= this.alertThreshold;

            // 如果不是目标物体，直接返回false
            if (!isTargetObject) return false;

            // 检查是否在报警区域内
            let inAlertZone = true; // 默认为true

            // 只有启用报警区域时才检查
            if (zoneEnabled && window.alertZone) {
                inAlertZone = window.alertZone.isInAlertZone(detection);
                console.log(`检查目标物体: ${className} 是否在报警区域内: ${inAlertZone}`);
            }

            return isTargetObject && inAlertZone;
        });

        // 如果有匹配的目标物体，触发报警
        if (matchedDetections.length > 0) {
            // 获取置信度最高的检测结果
            const topMatch = matchedDetections.reduce((prev, current) => {
                return (prev.confidence > current.confidence) ? prev : current;
            });

            // 获取类别名称
            let className = '';
            if (topMatch.class_name) {
                className = topMatch.class_name.toLowerCase();
            } else if (topMatch.class) {
                className = topMatch.class.toLowerCase();
            }

            console.log(`触发报警: 检测到目标物体 ${className}, 置信度 ${(topMatch.confidence * 100).toFixed(1)}%`);

            // 触发报警
            this.triggerAlert(topMatch);

            // 更新最后报警时间
            this.lastAlertTime = now;
        }
    }

    // 触发报警函数
    triggerAlert(detection) {
        // 获取类别名称
        let className = '';
        if (detection.class_name) {
            className = detection.class_name;
        } else if (detection.class) {
            className = detection.class;
        }

        // 获取置信度
        const confidence = detection.confidence || 0;

        // 视觉报警
        if (this.visualAlertEnabled) {
            const alertContainer = document.getElementById('alert-container');
            const alertMessage = document.getElementById('alert-message');

            alertMessage.textContent = `检测到 ${className} (置信度: ${(confidence * 100).toFixed(1)}%)`;
            alertContainer.style.display = 'block';

            // 添加闪烁效果
            if (!this.isAlertActive) {
                this.isAlertActive = true;
                alertContainer.classList.add('alert-flash');
            }
        }

        // 声音报警
        if (this.soundAlertEnabled && window.alertSoundGenerator) {
            window.alertSoundGenerator.play();
        }

        // 添加到报警历史
        this.addAlertToHistory(className, confidence);
    }

    // 隐藏报警函数
    hideAlert() {
        const alertContainer = document.getElementById('alert-container');
        alertContainer.style.display = 'none';
        alertContainer.classList.remove('alert-flash');
        this.isAlertActive = false;
    }

    // 添加报警到历史记录
    addAlertToHistory(className, confidence) {
        const alertHistoryTable = document.getElementById('alert-history-table');

        // 如果是第一条记录，清空“暂无报警记录”
        if (alertHistoryTable.querySelector('td.text-center')) {
            alertHistoryTable.innerHTML = '';
        }

        // 创建新行
        const row = document.createElement('tr');

        // 时间单元格
        const now = new Date();
        const timeCell = document.createElement('td');
        timeCell.textContent = now.toLocaleTimeString();

        // 类别单元格
        const classCell = document.createElement('td');
        classCell.textContent = className;

        // 置信度单元格
        const confidenceCell = document.createElement('td');
        confidenceCell.textContent = `${(confidence * 100).toFixed(1)}%`;

        // 添加到行
        row.appendChild(timeCell);
        row.appendChild(classCell);
        row.appendChild(confidenceCell);

        // 添加到表格顶部
        alertHistoryTable.insertBefore(row, alertHistoryTable.firstChild);

        // 限制历史记录数量，保留最新的50条
        const rows = alertHistoryTable.querySelectorAll('tr');
        if (rows.length > 50) {
            alertHistoryTable.removeChild(rows[rows.length - 1]);
        }

        // 添加到统计分析系统
        if (window.alertStats) {
            const alertRecord = {
                time: now,
                category: className,
                confidence: confidence
            };
            window.alertStats.addAlertRecord(alertRecord);
        }
    }

    // 清空报警历史
    clearAlertHistory() {
        const alertHistoryTable = document.getElementById('alert-history-table');
        alertHistoryTable.innerHTML = '<tr><td colspan="3" class="text-center">暂无报警记录</td></tr>';

        // 清空统计数据
        if (window.alertStats) {
            window.alertStats.clearAlertRecords();
        }
    }

    // 开始流媒体检测
    startStreamDetection(modelId, streamId) {
        this.isDetecting = true;
        document.getElementById('start-detection-btn').style.display = 'none';
        document.getElementById('stop-detection-btn').style.display = 'inline-block';

        // 更新检测状态
        document.getElementById('detection-status').innerHTML =
            `<span class="badge bg-warning">正在连接流媒体...</span>`;

        // 获取阈值
        const confThreshold = parseFloat(document.getElementById('rt-conf-threshold').value);
        const iouThreshold = parseFloat(document.getElementById('rt-iou-threshold').value);

        // 定义流媒体检测函数
        const detectStreamFrame = (timestamp) => {
            if (!this.isDetecting) return;

            // 计算FPS
            if (this.lastFrameTime) {
                this.fps = 1000 / (timestamp - this.lastFrameTime);
                document.getElementById('fps-counter').textContent = this.fps.toFixed(1);
            }
            this.lastFrameTime = timestamp;

            // 从流媒体获取当前帧
            fetch(`${API_URL}/streaming/frame/${streamId}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('无法获取流媒体帧');
                    }
                    return response.blob();
                })
                .then(blob => {
                    // 在画布上显示当前帧
                    const img = new Image();
                    img.onload = () => {
                        const ctx = document.getElementById('detection-canvas').getContext('2d');
                        document.getElementById('detection-canvas').width = img.width;
                        document.getElementById('detection-canvas').height = img.height;
                        ctx.drawImage(img, 0, 0);
                        
                        // 同时在视频元素上显示（如果需要）
                        if (document.getElementById('video-element')) {
                            const videoCtx = document.getElementById('video-element').getContext ? document.getElementById('video-element').getContext('2d') : null;
                            if (videoCtx) {
                                document.getElementById('video-element').width = img.width;
                                document.getElementById('video-element').height = img.height;
                                videoCtx.drawImage(img, 0, 0);
                            }
                        }
                    };
                    img.src = URL.createObjectURL(blob);

                    // 创建一个有正确扩展名的文件
                    const fileName = `stream_frame_${Date.now()}.jpg`;
                    const imageFile = new File([blob], fileName, { type: 'image/jpeg' });

                    const formData = new FormData();
                    formData.append('file', imageFile);
                    formData.append('model_id', modelId);
                    formData.append('conf_thres', confThreshold);
                    formData.append('iou_thres', iouThreshold);

                    // 发送检测请求
                    return fetch(`${API_URL}/detection/`, {
                        method: 'POST',
                        body: formData
                    });
                })
                .then(response => {
                    if (!response.ok) {
                        return response.text().then(text => {
                            try {
                                const json = JSON.parse(text);
                                throw new Error(json.detail || '检测失败');
                            } catch (e) {
                                throw new Error(text || '检测失败');
                            }
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    if (data && data.id) {
                        // 获取检测结果
                        return fetch(`${API_URL}/detection/${data.id}/result`);
                    }
                })
                .then(response => response ? response.json() : null)
                .then(resultData => {
                    if (resultData && resultData.status === 'completed' && resultData.results && resultData.results.length > 0) {
                        // 获取第一个结果的检测内容
                        const detections = resultData.results[0].detections || [];

                        // 更新检测到的目标数量
                        this.detectedObjects = detections.length;
                        document.getElementById('objects-counter').textContent = this.detectedObjects;

                        // 更新检测状态
                        document.getElementById('detection-status').innerHTML =
                            `<span class="badge bg-success">正在检测</span>`;

                        // 在画布上绘制检测结果
                        this.drawDetections(detections);

                        // 更新检测结果表格
                        this.updateDetectionTable(detections);

                        // 处理报警逻辑
                        this.handleAlerts(detections);
                    }
                })
                .catch(error => {
                    console.error('流媒体检测错误:', error);
                    if (this.isDetecting) {
                        document.getElementById('detection-status').innerHTML =
                            `<span class="badge bg-danger">检测错误</span>`;
                    }
                });

            // 继续下一帧
            if (this.isDetecting) {
                this.animationFrameId = requestAnimationFrame(detectStreamFrame);
            }
        }

        // 开始检测循环
        this.animationFrameId = requestAnimationFrame(detectStreamFrame);
    }

    // 开始实时检测
    startRealTimeDetection(modelId) {
        this.isDetecting = true;
        document.getElementById('start-detection-btn').style.display = 'none';
        document.getElementById('stop-detection-btn').style.display = 'inline-block';

        // 更新检测状态
        document.getElementById('detection-status').innerHTML =
            `<span class="badge bg-warning">准备中...</span>`;

        // 获取阈值
        const confThreshold = parseFloat(document.getElementById('rt-conf-threshold').value);
        const iouThreshold = parseFloat(document.getElementById('rt-iou-threshold').value);

        // 定义检测函数
        const detectFrame = (timestamp) => {
            if (!this.isDetecting) return;

            // 计算FPS
            if (this.lastFrameTime) {
                this.fps = 1000 / (timestamp - this.lastFrameTime);
                document.getElementById('fps-counter').textContent = this.fps.toFixed(1);
            }
            this.lastFrameTime = timestamp;

            // 绘制当前帧
            const ctx = document.getElementById('detection-canvas').getContext('2d');
            const videoElement = document.getElementById('video-element');
            ctx.drawImage(videoElement, 0, 0, document.getElementById('detection-canvas').width, document.getElementById('detection-canvas').height);

            // 获取当前帧数据
            ctx.canvas.toBlob((blob) => {
                // 创建一个有正确扩展名的文件
                const fileName = `frame_${Date.now()}.jpg`;
                const imageFile = new File([blob], fileName, { type: 'image/jpeg' });

                const formData = new FormData();
                formData.append('file', imageFile);
                formData.append('model_id', modelId);
                formData.append('conf_thres', confThreshold);
                formData.append('iou_thres', iouThreshold);

                // 发送检测请求
                console.log('发送检测请求，文件名：', fileName);

                authenticatedFetch(`${API_URL}/detection/`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    console.log('检测响应状态：', response.status);
                    if (!response.ok) {
                        return response.text().then(text => {
                            try {
                                // 尝试解析JSON
                                const json = JSON.parse(text);
                                throw new Error(json.detail || '检测失败');
                            } catch (e) {
                                // 如果不是JSON，直接返回文本
                                throw new Error(text || '检测失败');
                            }
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Detection API response:', data);

                    // 检查是否有检测结果
                    if (data && data.id) {
                        // 获取检测结果
                        authenticatedFetch(`${API_URL}/detection/${data.id}/result`)
                            .then(response => response.json())
                            .then(resultData => {
                                console.log('Detection result:', resultData);

                                if (resultData.status === 'completed' && resultData.results && resultData.results.length > 0) {
                                    // 获取第一个结果的检测内容
                                    const detections = resultData.results[0].detections || [];

                                    // 更新检测到的目标数量
                                    this.detectedObjects = detections.length;
                                    document.getElementById('objects-counter').textContent = this.detectedObjects;

                                    // 处理轨迹记录和预测
                                    if (this.trajectoryEnabled && window.trajectory) {
                                        // 跟踪目标
                                        const trackedObjects = window.trajectory.trackObjects(detections);

                                        // 更新轨迹
                                        window.trajectory.updateTrajectories(trackedObjects);

                                        // 绘制检测框
                                        this.drawDetections(ctx, trackedObjects);

                                        // 绘制轨迹
                                        window.trajectory.drawTrajectories(ctx);

                                        // 更新检测对象列表
                                        this.updateDetectionTable(trackedObjects);

                                        // 检查目标物体并触发报警
                                        this.checkTargetObjects(trackedObjects);
                                    } else {
                                        // 绘制检测框
                                        this.drawDetections(ctx, detections);

                                        // 更新检测对象列表
                                        this.updateDetectionTable(detections);

                                        // 检查目标物体并触发报警
                                        this.checkTargetObjects(detections);
                                    }

                                    // 更新检测状态
                                    document.getElementById('detection-status').innerHTML =
                                        `<span class="badge bg-success">正在检测</span>`;
                                } else if (resultData.status === 'pending' || resultData.status === 'running') {
                                    // 更新检测状态
                                    document.getElementById('detection-status').innerHTML =
                                        `<span class="badge bg-warning">处理中...</span>`;
                                } else {
                                    // 更新检测状态
                                    document.getElementById('detection-status').innerHTML =
                                        `<span class="badge bg-danger">检测失败</span>`;
                                }
                            })
                            .catch(error => {
                                console.error('获取检测结果失败:', error);
                                document.getElementById('detection-status').innerHTML =
                                    `<span class="badge bg-danger">获取结果失败</span>`;
                            });
                    } else {
                        // 更新检测状态
                        document.getElementById('detection-status').innerHTML =
                            `<span class="badge bg-danger">检测失败</span>`;
                    }

                    // 继续检测下一帧
                    if (this.isDetecting) {
                        this.animationFrameId = requestAnimationFrame(detectFrame);
                    }
                })
                .catch(error => {
                    console.error('检测失败:', error);

                    // 显示错误信息
                    document.getElementById('detection-status').innerHTML =
                        `<span class="badge bg-danger">错误: ${error.message}</span>`;

                    // 清空检测对象列表
                    const tableBody = document.getElementById('detection-results-table');
                    tableBody.innerHTML = '<tr><td colspan="3" class="text-center text-danger">检测失败: ' + error.message + '</td></tr>';

                    // 继续检测下一帧
                    if (this.isDetecting) {
                        this.animationFrameId = requestAnimationFrame(detectFrame);
                    }
                });
            }, 'image/jpeg');
        }

        // 绘制检测框
        this.drawDetections = (ctx, detections) => {
            // 清除上一帧的检测框
            ctx.drawImage(document.getElementById('video-element'), 0, 0, document.getElementById('detection-canvas').width, document.getElementById('detection-canvas').height);

            // 绘制新的检测框
            detections.forEach(detection => {
                // 检查检测框格式
                let x, y, width, height, className, confidence;

                if (Array.isArray(detection.bbox)) {
                    // 如果是数组格式 [x1, y1, x2, y2]
                    const [x1, y1, x2, y2] = detection.bbox;
                    x = x1;
                    y = y1;
                    width = x2 - x1;
                    height = y2 - y1;
                } else if (detection.bbox && typeof detection.bbox === 'object') {
                    // 如果是对象格式 {x, y, width, height}
                    x = detection.bbox.x;
                    y = detection.bbox.y;
                    width = detection.bbox.width;
                    height = detection.bbox.height;
                } else {
                    console.error('检测框格式错误:', detection);
                    return;
                }

                // 获取类别名称
                if (detection.class_name) {
                    className = detection.class_name;
                } else if (detection.class) {
                    className = detection.class;
                } else {
                    className = 'Unknown';
                }

                // 获取置信度
                confidence = detection.confidence;

                // 创建标签
                const label = `${className} ${(confidence * 100).toFixed(1)}%`;

                // 随机生成颜色
                const hue = (className.length * 5) % 360;
                ctx.strokeStyle = `hsl(${hue}, 100%, 50%)`;
                ctx.lineWidth = 2;
                ctx.strokeRect(x, y, width, height);

                // 绘制标签背景
                ctx.fillStyle = `hsl(${hue}, 100%, 50%)`;
                const textWidth = ctx.measureText(label).width;
                ctx.fillRect(x, y - 20, textWidth + 10, 20);

                // 绘制标签文字
                ctx.fillStyle = 'white';
                ctx.font = '14px Arial';
                ctx.fillText(label, x + 5, y - 5);
            });
        }

        // 开始检测
        this.animationFrameId = requestAnimationFrame(detectFrame);
    }

    // 绘制检测结果
    drawDetections(detections) {
        const ctx = document.getElementById('detection-canvas').getContext('2d');
        
        detections.forEach(detection => {
            const { bbox, class_name, confidence } = detection;
            const [x, y, width, height] = bbox;
            
            // 绘制边界框
            ctx.strokeStyle = '#00ff00';
            ctx.lineWidth = 2;
            ctx.strokeRect(x, y, width, height);
            
            // 绘制标签
            ctx.fillStyle = '#00ff00';
            ctx.font = '16px Arial';
            const label = `${class_name} ${(confidence * 100).toFixed(1)}%`;
            const textWidth = ctx.measureText(label).width;
            
            // 绘制标签背景
            ctx.fillRect(x, y - 25, textWidth + 10, 25);
            
            // 绘制文本
            ctx.fillStyle = '#000000';
            ctx.fillText(label, x + 5, y - 5);
        });
    }
    
    // 更新检测结果表格
    updateDetectionTable(detections) {
        const tableBody = document.getElementById('detection-results-table');
        if (!tableBody) return;
        
        if (detections.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="3" class="text-center">暂无检测结果</td></tr>';
            return;
        }
        
        let html = '';
        detections.forEach(detection => {
            const { class_name, confidence, bbox } = detection;
            const [x, y, width, height] = bbox;
            const position = `(${Math.round(x)}, ${Math.round(y)}, ${Math.round(width)}, ${Math.round(height)})`;
            
            html += `
                <tr>
                    <td>${class_name}</td>
                    <td>${(confidence * 100).toFixed(1)}%</td>
                    <td>${position}</td>
                </tr>
            `;
        });
        
        tableBody.innerHTML = html;
    }
    
    // 处理报警逻辑
    handleAlerts(detections) {
        // 这里可以添加报警逻辑，例如检测到特定目标时发出报警
        // 目前保持空实现，可以根据需要扩展
    }

    // 停止实时检测
    stopRealTimeDetection() {
        this.isDetecting = false;

        // 更新检测状态
        document.getElementById('detection-status').innerHTML =
            `<span class="badge bg-secondary">已停止</span>`;

        // 取消动画帧
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }

        // 关闭摄像头
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        // 重置视频元素
        const videoElement = document.getElementById('video-element');
        videoElement.srcObject = null;
        videoElement.src = '';
        videoElement.pause();
        videoElement.load(); // 确保清理流媒体连接

        // 重置按钮状态
        document.getElementById('start-detection-btn').style.display = 'inline-block';
        document.getElementById('stop-detection-btn').style.display = 'none';

        // 清除画布
        const ctx = document.getElementById('detection-canvas').getContext('2d');
        ctx.clearRect(0, 0, document.getElementById('detection-canvas').width, document.getElementById('detection-canvas').height);

        // 重置计数器
        document.getElementById('fps-counter').textContent = '0';
        document.getElementById('objects-counter').textContent = '0';

        // 清空检测对象列表
        const tableBody = document.getElementById('detection-results-table');
        tableBody.innerHTML = '<tr><td colspan="3" class="text-center">暂无检测结果</td></tr>';
    }

    // 加载流媒体列表
    loadStreamsList() {
        const streamSelect = document.getElementById('stream-select');
        if (!streamSelect) return;
        
        // 显示加载状态
        streamSelect.innerHTML = '<option value="">加载中...</option>';
        
        authenticatedFetch(`${API_URL}/streaming/list`)
            .then(response => response.json())
            .then(data => {
                streamSelect.innerHTML = '<option value="">请选择流媒体...</option>';
                
                if (data.success && data.streams) {
                    const streams = Object.entries(data.streams);
                    if (streams.length === 0) {
                        streamSelect.innerHTML += '<option value="" disabled>暂无可用的流媒体</option>';
                    } else {
                        streams.forEach(([streamId, streamInfo]) => {
                            if (streamInfo.is_running) {
                                const option = document.createElement('option');
                                option.value = streamId;
                                option.textContent = `${streamInfo.source} (${streamInfo.type}) - 运行中`;
                                streamSelect.appendChild(option);
                            }
                        });
                    }
                } else {
                    streamSelect.innerHTML += '<option value="" disabled>加载失败</option>';
                }
            })
            .catch(error => {
                console.error('加载流媒体列表失败:', error);
                streamSelect.innerHTML = '<option value="" disabled>加载失败</option>';
            });
    }
    
    // 显示流媒体管理模态框
    showStreamManagementModal() {
        const modalTitle = document.querySelector('#mainModal .modal-title');
        const modalBody = document.querySelector('#mainModal .modal-body');
        const modalSubmit = document.getElementById('modalSubmit');
        
        modalTitle.textContent = '流媒体管理';
        modalSubmit.style.display = 'none';
        
        modalBody.innerHTML = `
            <div class="mb-3">
                <h6>创建新流媒体</h6>
                <form id="create-stream-form">
                    <div class="mb-3">
                        <label for="stream-source" class="form-label">流媒体地址</label>
                        <input type="text" class="form-control" id="stream-source" placeholder="rtsp://username:password@ip:port/path 或 0,1,2... (摄像头ID)" required>
                        <div class="form-text">
                            支持格式：
                            <ul class="small mt-1">
                                <li>RTSP: rtsp://username:password@192.168.1.100:554/stream</li>
                                <li>RTMP: rtmp://server/app/stream</li>
                                <li>HTTP: http://192.168.1.100:8080/video.mjpg</li>
                                <li>摄像头: 0, 1, 2...</li>
                            </ul>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label for="stream-type" class="form-label">流类型</label>
                        <select class="form-select" id="stream-type">
                            <option value="auto">自动检测</option>
                            <option value="rtsp">RTSP</option>
                            <option value="rtmp">RTMP</option>
                            <option value="http">HTTP</option>
                            <option value="webcam">摄像头</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <button type="button" class="btn btn-outline-secondary" id="test-stream-btn">测试连接</button>
                        <button type="submit" class="btn btn-primary">创建流媒体</button>
                    </div>
                    <div id="stream-test-result" class="mt-2"></div>
                </form>
            </div>
            
            <hr>
            
            <div class="mb-3">
                <h6>当前流媒体列表</h6>
                <div id="streams-list">
                    <div class="text-center">
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">加载中...</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 绑定事件
        this.bindStreamManagementEvents();
        
        // 加载流媒体列表
        this.loadStreamsManagementList();
        
        modal.show();
    }
    
    // 绑定流媒体管理事件
    bindStreamManagementEvents() {
        const createStreamForm = document.getElementById('create-stream-form');
        const testStreamBtn = document.getElementById('test-stream-btn');
        
        if (testStreamBtn) {
            testStreamBtn.addEventListener('click', function() {
                const source = document.getElementById('stream-source').value;
                const type = document.getElementById('stream-type').value;
                const resultDiv = document.getElementById('stream-test-result');
                
                if (!source) {
                    resultDiv.innerHTML = '<div class="alert alert-warning">请输入流媒体地址</div>';
                    return;
                }
                
                resultDiv.innerHTML = '<div class="alert alert-info">正在测试连接...</div>';
                
                const formData = new FormData();
                formData.append('source', source);
                formData.append('stream_type', type);
                
                authenticatedFetch(`${API_URL}/streaming/test-connection`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        resultDiv.innerHTML = `
                            <div class="alert alert-success">
                                <strong>连接成功！</strong><br>
                                ${data.info ? `分辨率: ${data.info.width}x${data.info.height}` : ''}
                            </div>
                        `;
                    } else {
                        resultDiv.innerHTML = `<div class="alert alert-danger">连接失败: ${data.message}</div>`;
                    }
                })
                .catch(error => {
                    resultDiv.innerHTML = `<div class="alert alert-danger">测试失败: ${error.message}</div>`;
                });
            });
        }
        
        if (createStreamForm) {
            createStreamForm.addEventListener('submit', (e) => {
                e.preventDefault();
                
                const source = document.getElementById('stream-source').value;
                const type = document.getElementById('stream-type').value;
                
                const formData = new FormData();
                formData.append('source', source);
                formData.append('stream_type', type);
                
                authenticatedFetch(`${API_URL}/streaming/create`, {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // 创建成功，启动流媒体
                        return authenticatedFetch(`${API_URL}/streaming/start/${data.stream_id}`, {
                            method: 'POST'
                        });
                    } else {
                        throw new Error(data.message || '创建流媒体失败');
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('流媒体创建并启动成功！');
                        // 重新加载列表
                        this.loadStreamsManagementList();
                        this.loadStreamsList();
                        // 清空表单
                        createStreamForm.reset();
                        document.getElementById('stream-test-result').innerHTML = '';
                    } else {
                        throw new Error(data.message || '启动流媒体失败');
                    }
                })
                .catch(error => {
                    alert('错误: ' + error.message);
                });
            });
        }
    }
    
    // 加载流媒体管理列表
    loadStreamsManagementList() {
        const streamsList = document.getElementById('streams-list');
        if (!streamsList) return;
        
        authenticatedFetch(`${API_URL}/streaming/list`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.streams) {
                    const streams = Object.entries(data.streams);
                    if (streams.length === 0) {
                        streamsList.innerHTML = '<div class="alert alert-info">暂无流媒体</div>';
                    } else {
                        let html = '<div class="list-group">';
                        streams.forEach(([streamId, streamInfo]) => {
                            const statusBadge = streamInfo.is_running ? 
                                '<span class="badge bg-success">运行中</span>' : 
                                '<span class="badge bg-secondary">已停止</span>';
                            
                            html += `
                                <div class="list-group-item d-flex justify-content-between align-items-center">
                                    <div>
                                        <strong>${streamInfo.source}</strong><br>
                                        <small class="text-muted">类型: ${streamInfo.type} | ID: ${streamId}</small>
                                    </div>
                                    <div>
                                        ${statusBadge}
                                        ${streamInfo.is_running ? 
                                            `<button class="btn btn-sm btn-outline-danger ms-2" onclick="stopStream('${streamId}')">停止</button>` :
                                            `<button class="btn btn-sm btn-outline-success ms-2" onclick="startStream('${streamId}')">启动</button>`
                                        }
                                        <button class="btn btn-sm btn-outline-secondary ms-1" onclick="deleteStream('${streamId}')">删除</button>
                                    </div>
                                </div>
                            `;
                        });
                        html += '</div>';
                        streamsList.innerHTML = html;
                    }
                } else {
                    streamsList.innerHTML = '<div class="alert alert-danger">加载失败</div>';
                }
            })
            .catch(error => {
                console.error('加载流媒体列表失败:', error);
                streamsList.innerHTML = '<div class="alert alert-danger">加载失败</div>';
            });
    }
}

// 创建全局实例
window.videoProcessor = new VideoProcessor();

// 全局暴露函数，以便在HTML中直接调用
window.startStream = (streamId) => videoProcessor.startStream(streamId);
window.stopStream = (streamId) => videoProcessor.stopStream(streamId);
window.deleteStream = (streamId) => videoProcessor.deleteStream(streamId);

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VideoProcessor;
}
