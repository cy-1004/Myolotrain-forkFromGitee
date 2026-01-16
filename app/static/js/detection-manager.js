// 检测功能模块
class DetectionManager {
    constructor() {
        // 构造函数
    }

    // 加载检测表单
    loadDetectionForm() {
        // 监听任务类型选择变化
        const taskTypeSelect = document.getElementById('model-task-type');
        if (taskTypeSelect) {
            taskTypeSelect.addEventListener('change', () => {
                this.loadModelOptions();
                this.loadCompareModelOptions();
            });
        }
        
        // 监听对比模式切换
        const compareModeToggle = document.getElementById('compare-mode-toggle');
        if (compareModeToggle) {
            compareModeToggle.addEventListener('change', (e) => {
                this.toggleCompareMode(e.target.checked);
            });
        }
        
        // 监听对比任务类型选择变化
        const compareTaskTypeSelect = document.getElementById('compare-model-task-type');
        if (compareTaskTypeSelect) {
            compareTaskTypeSelect.addEventListener('change', () => {
                this.loadCompareModelOptions();
            });
        }
        
        // 监听对比检测按钮点击
        const compareDetectionBtn = document.getElementById('start-compare-detection');
        if (compareDetectionBtn) {
            compareDetectionBtn.addEventListener('click', () => {
                this.submitCompareDetection();
            });
        }
        
        // 监听对比模式下的滑块值显示
        this.bindCompareSliderEvents();
        
        // 初始加载模型选项
        this.loadModelOptions();
        this.loadCompareModelOptions();
    }
    
    // 切换对比模式
    toggleCompareMode(isEnabled) {
        const singleForm = document.querySelector('.single-detection-form');
        const compareForm = document.getElementById('compare-detection-form');
        
        if (isEnabled) {
            singleForm.style.display = 'none';
            compareForm.style.display = 'block';
        } else {
            singleForm.style.display = 'block';
            compareForm.style.display = 'none';
        }
    }
    
    // 绑定对比模式滑块事件
    bindCompareSliderEvents() {
        // 模型A滑块事件
        const confThresholdA = document.getElementById('conf-threshold-a');
        const confValueA = document.getElementById('conf-value-a');
        if (confThresholdA && confValueA) {
            confThresholdA.addEventListener('input', function() {
                confValueA.textContent = this.value;
            });
        }

        const iouThresholdA = document.getElementById('iou-threshold-a');
        const iouValueA = document.getElementById('iou-value-a');
        if (iouThresholdA && iouValueA) {
            iouThresholdA.addEventListener('input', function() {
                iouValueA.textContent = this.value;
            });
        }
        
        // 模型B滑块事件
        const confThresholdB = document.getElementById('conf-threshold-b');
        const confValueB = document.getElementById('conf-value-b');
        if (confThresholdB && confValueB) {
            confThresholdB.addEventListener('input', function() {
                confValueB.textContent = this.value;
            });
        }

        const iouThresholdB = document.getElementById('iou-threshold-b');
        const iouValueB = document.getElementById('iou-value-b');
        if (iouThresholdB && iouValueB) {
            iouThresholdB.addEventListener('input', function() {
                iouValueB.textContent = this.value;
            });
        }
    }
    
    // 根据任务类型加载模型选项
    loadModelOptions() {
        const taskType = document.getElementById('model-task-type')?.value || 'detect';
        
        fetch(`${API_URL}/models/`)
            .then(response => response.json())
            .then(models => {
                const select = document.getElementById('model-select');
                select.innerHTML = '<option value="">请选择模型</option>';

                models.forEach(model => {
                    if (model.task === taskType) {
                        const option = document.createElement('option');
                        option.value = model.id;
                        option.textContent = `${model.name} (${model.type})`;
                        select.appendChild(option);
                    }
                });
                
                // 如果没有匹配的模型，添加提示
                if (select.children.length <= 1) {
                    const option = document.createElement('option');
                    option.value = '';
                    option.textContent = `没有适用于${this.getTaskTypeText(taskType)}的模型`;
                    option.disabled = true;
                    select.appendChild(option);
                }
            })
            .catch(error => {
                console.error('Error loading model options:', error);
            });
    }
    
    // 根据任务类型加载对比模型选项
    loadCompareModelOptions() {
        const taskType = document.getElementById('compare-model-task-type')?.value || 'detect';
        
        fetch(`${API_URL}/models/`)
            .then(response => response.json())
            .then(models => {
                // 更新模型A选择器
                const selectA = document.getElementById('model-select-a');
                if (selectA) {
                    selectA.innerHTML = '<option value="">请选择模型 A</option>';

                    models.forEach(model => {
                        if (model.task === taskType) {
                            const option = document.createElement('option');
                            option.value = model.id;
                            option.textContent = `${model.name} (${model.type})`;
                            selectA.appendChild(option);
                        }
                    });
                    
                    // 如果没有匹配的模型，添加提示
                    if (selectA.children.length <= 1) {
                        const option = document.createElement('option');
                        option.value = '';
                        option.textContent = `没有适用于${this.getTaskTypeText(taskType)}的模型`;
                        option.disabled = true;
                        selectA.appendChild(option);
                    }
                }
                
                // 更新模型B选择器
                const selectB = document.getElementById('model-select-b');
                if (selectB) {
                    selectB.innerHTML = '<option value="">请选择模型 B</option>';

                    models.forEach(model => {
                        if (model.task === taskType) {
                            const option = document.createElement('option');
                            option.value = model.id;
                            option.textContent = `${model.name} (${model.type})`;
                            selectB.appendChild(option);
                        }
                    });
                    
                    // 如果没有匹配的模型，添加提示
                    if (selectB.children.length <= 1) {
                        const option = document.createElement('option');
                        option.value = '';
                        option.textContent = `没有适用于${this.getTaskTypeText(taskType)}的模型`;
                        option.disabled = true;
                        selectB.appendChild(option);
                    }
                }
            })
            .catch(error => {
                console.error('Error loading compare model options:', error);
            });
    }
    
    // 获取任务类型文本
    getTaskTypeText(taskType) {
        switch (taskType) {
            case 'detect':
                return '目标检测';
            case 'segment':
                return '实例分割';
            case 'pose':
                return '关键点/姿态估计';
            case 'obb':
                return '旋转框检测';
            default:
                return taskType;
        }
    }

    // 绑定检测页面事件
    bindDetectionEvents() {
        // 绑定表单提交事件
        const form = document.getElementById('detection-form');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitDetection();
            });
        }

        // 绑定滑块值显示
        const confThreshold = document.getElementById('conf-threshold');
        const confValue = document.getElementById('conf-value');
        if (confThreshold && confValue) {
            confThreshold.addEventListener('input', function() {
                confValue.textContent = this.value;
            });
        }

        const iouThreshold = document.getElementById('iou-threshold');
        const iouValue = document.getElementById('iou-value');
        if (iouThreshold && iouValue) {
            iouThreshold.addEventListener('input', function() {
                iouValue.textContent = this.value;
            });
        }
    }

    // 提交检测请求
    submitDetection() {
        const modelSelect = document.getElementById('model-select');
        const fileInput = document.getElementById('detection-file');
        const confThreshold = document.getElementById('conf-threshold');
        const iouThreshold = document.getElementById('iou-threshold');
        const resultContainer = document.getElementById('detection-result');
        const resultContentContainer = document.getElementById('result-container');

        if (!modelSelect.value || !fileInput.files[0]) {
            alert('请选择模型和上传文件');
            return;
        }

        // 显示加载中
        resultContainer.style.display = 'block';
        resultContentContainer.innerHTML = '<div class="text-center my-5"><div class="spinner-border text-primary" role="status"></div><p class="mt-3">正在处理，请稍候...</p></div>';

        // 创建FormData对象
        const formData = new FormData();
        formData.append('model_id', modelSelect.value);
        formData.append('file', fileInput.files[0]);
        formData.append('conf_thres', parseFloat(confThreshold.value));
        formData.append('iou_thres', parseFloat(iouThreshold.value));

        // 发送请求到单模型检测API
        authenticatedFetch(`${API_URL}/detection`, {
            method: 'POST',
            body: formData
        })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    return response.json().then(errData => {
                        throw new Error(errData.detail || '检测失败');
                    });
                }
            })
            .then(async result => {
                // 等待检测完成并获取结果
                let detectionResult;
                let attempts = 0;
                const maxAttempts = 60; // 最多等待30秒 (60次 * 500毫秒)
                
                while (attempts < maxAttempts) {
                    try {
                        const resultResponse = await authenticatedFetch(`${API_URL}/detection/${result.id}/result`);
                        if (resultResponse.ok) {
                            detectionResult = await resultResponse.json();
                            if (detectionResult.status === 'completed') {
                                break;
                            }
                        }
                    } catch (err) {
                        console.error('获取检测结果失败:', err);
                    }
                    
                    attempts++;
                    await new Promise(resolve => setTimeout(resolve, 500)); // 等待500毫秒
                }
                
                if (!detectionResult || detectionResult.status !== 'completed') {
                    throw new Error('检测超时或未完成');
                }
                
                // 显示检测结果
                console.log('Detection result:', detectionResult);

                if (!detectionResult.results || detectionResult.results.length === 0) {
                    resultContentContainer.innerHTML = `<div class="alert alert-warning">${detectionResult.message || '未找到检测结果'}</div>`;
                    return;
                }

                // 构建结果显示
                let resultHtml = '';

                detectionResult.results.forEach(result => {
                    // 添加检测图像
                    resultHtml += `<div class="card mb-4">
                        <div class="card-header">检测到 ${result.count} 个目标</div>
                        <div class="card-body">
                            <div class="text-center mb-3">
                                <img src="${result.image_url}" alt="检测结果" class="img-fluid">
                            </div>
                            <div class="table-responsive">
                                <table class="table table-striped">
                                    <thead>
                                        <tr>
                                            <th>类别</th>
                                            <th>置信度</th>
                                            <th>位置</th>
                                        </tr>
                                    </thead>
                                    <tbody>`;

                    // 添加检测结果表格
                    result.detections.forEach(detection => {
                        const confidence = (detection.confidence * 100).toFixed(2);
                        const bbox = detection.bbox.map(v => Math.round(v)).join(', ');

                        resultHtml += `<tr>
                            <td>${detection.class_name}</td>
                            <td>${confidence}%</td>
                            <td>[${bbox}]</td>
                        </tr>`;
                    });

                    resultHtml += `</tbody>
                                </table>
                            </div>
                        </div>
                    </div>`;
                });

                resultContentContainer.innerHTML = resultHtml;
            })
            .catch(error => {
                console.error('Error in detection:', error);
                resultContentContainer.innerHTML = `<div class="alert alert-danger">检测失败: ${error.message}</div>`;
            });
    }
    
    // 提交对比检测请求
    async submitCompareDetection() {
        const modelSelectA = document.getElementById('model-select-a');
        const modelSelectB = document.getElementById('model-select-b');
        const fileInput = document.getElementById('compare-detection-file');
        const confThresholdA = document.getElementById('conf-threshold-a');
        const iouThresholdA = document.getElementById('iou-threshold-a');
        const confThresholdB = document.getElementById('conf-threshold-b');
        const iouThresholdB = document.getElementById('iou-threshold-b');
        
        if (!modelSelectA.value || !modelSelectB.value || !fileInput.files[0]) {
            alert('请选择两个模型和上传文件');
            return;
        }

        // 显示加载中
        const resultContainer = document.getElementById('compare-detection-result');
        const resultContainerA = document.getElementById('result-container-a');
        const resultContainerB = document.getElementById('result-container-b');
        resultContainer.style.display = 'block';
        resultContainerA.innerHTML = '<div class="text-center my-5"><div class="spinner-border text-primary" role="status"></div><p class="mt-3">模型 A 正在处理，请稍候...</p></div>';
        resultContainerB.innerHTML = '<div class="text-center my-5"><div class="spinner-border text-primary" role="status"></div><p class="mt-3">模型 B 正在处理，请稍候...</p></div>';

        // 获取模型名称
        const modelNameA = modelSelectA.options[modelSelectA.selectedIndex].text;
        const modelNameB = modelSelectB.options[modelSelectB.selectedIndex].text;
        document.getElementById('model-a-name').textContent = `(${modelNameA})`;
        document.getElementById('model-b-name').textContent = `(${modelNameB})`;
        
        try {
            // 创建FormData对象
            const formData = new FormData();
            formData.append('model_a_id', modelSelectA.value);
            formData.append('model_b_id', modelSelectB.value);
            formData.append('file', fileInput.files[0]);
            formData.append('conf_thres_a', parseFloat(confThresholdA.value));
            formData.append('iou_thres_a', parseFloat(iouThresholdA.value));
            formData.append('conf_thres_b', parseFloat(confThresholdB.value));
            formData.append('iou_thres_b', parseFloat(iouThresholdB.value));
            
            // 发送对比检测请求
            const response = await authenticatedFetch(`${API_URL}/comparison/compare-detection`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '对比检测失败');
            }
            
            const comparisonResult = await response.json();
            
            // 调试日志：打印返回的数据结构
            console.log("Comparison result data:", comparisonResult);
            
            // 获取真实的推理时间，提供合理的默认值
            const actualInferenceTimeA = (comparisonResult.model_a.result.inference_time_ms !== undefined && comparisonResult.model_a.result.inference_time_ms !== null) 
                ? comparisonResult.model_a.result.inference_time_ms 
                : comparisonResult.model_a.execution_time_ms || 0;
            const actualInferenceTimeB = (comparisonResult.model_b.result.inference_time_ms !== undefined && comparisonResult.model_b.result.inference_time_ms !== null) 
                ? comparisonResult.model_b.result.inference_time_ms 
                : comparisonResult.model_b.execution_time_ms || 0;
            
            console.log(`Actual inference time A: ${actualInferenceTimeA}ms`);
            console.log(`Actual inference time B: ${actualInferenceTimeB}ms`);
            
            // 显示模型A的结果
            this.displayDetectionResult(comparisonResult.model_a.result, 'result-container-a', 'timing-info-a', 'Model A');
            document.getElementById('timing-info-a').textContent = `推理时间: ${actualInferenceTimeA.toFixed(2)} ms`;
            
            // 显示模型B的结果
            this.displayDetectionResult(comparisonResult.model_b.result, 'result-container-b', 'timing-info-b', 'Model B');
            document.getElementById('timing-info-b').textContent = `推理时间: ${actualInferenceTimeB.toFixed(2)} ms`;
            
            // 显示时间对比，使用真实的推理时间
            this.displayTimingComparison(actualInferenceTimeA, actualInferenceTimeB);
            
        } catch (error) {
            console.error('Error in compare detection:', error);
            resultContainerA.innerHTML = `<div class="alert alert-danger">模型 A 检测失败: ${error.message}</div>`;
            resultContainerB.innerHTML = `<div class="alert alert-danger">模型 B 检测失败: ${error.message}</div>`;
        }
    }
    
    // 显示检测结果
    displayDetectionResult(resultData, containerId, timingInfoId, modelName) {
        const resultContainer = document.getElementById(containerId);
        
        if (resultData.status !== 'completed' || !resultData.results || resultData.results.length === 0) {
            resultContainer.innerHTML = `<div class="alert alert-warning">${resultData.message || '未找到检测结果'}</div>`;
            return;
        }

        // 构建结果显示
        let resultHtml = '';

        resultData.results.forEach(result => {
            // 添加检测图像
            resultHtml += `<div class="card mb-4">
                <div class="card-header">检测到 ${result.count} 个目标</div>
                <div class="card-body">
                    <div class="text-center mb-3">
                        <img src="${result.image_url}" alt="检测结果" class="img-fluid">
                    </div>
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>类别</th>
                                    <th>置信度</th>
                                    <th>位置</th>
                                </tr>
                            </thead>
                            <tbody>`;

            // 添加检测结果表格
            result.detections.forEach(detection => {
                const confidence = (detection.confidence * 100).toFixed(2);
                const bbox = detection.bbox.map(v => Math.round(v)).join(', ');

                resultHtml += `<tr>
                    <td>${detection.class_name}</td>
                    <td>${confidence}%</td>
                    <td>[${bbox}]</td>
                </tr>`;
            });

            resultHtml += `</tbody>
                        </table>
                    </div>
                </div>
            </div>`;
        });

        resultContainer.innerHTML = resultHtml;
    }
    
    // 显示时间对比
    displayTimingComparison(timeA, timeB) {
        const comparisonDiv = document.getElementById('timing-comparison');
        
        // 计算时间差异
        const difference = Math.abs(timeA - timeB);
        const fasterModel = timeA < timeB ? '模型 A' : '模型 B';
        const slowerModel = timeA < timeB ? '模型 B' : '模型 A';
        const fasterTime = Math.min(timeA, timeB);
        const slowerTime = Math.max(timeA, timeB);
        
        // 计算百分比差异
        const percentageDiff = ((slowerTime - fasterTime) / slowerTime * 100).toFixed(2);
        
        let comparisonHtml = `
        <div class="row">
            <div class="col-md-4">
                <div class="card text-center">
                    <div class="card-header bg-primary text-white">
                        <h5>模型 A 时间</h5>
                    </div>
                    <div class="card-body">
                        <h4>${timeA.toFixed(2)} ms</h4>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-center">
                    <div class="card-header bg-success text-white">
                        <h5>模型 B 时间</h5>
                    </div>
                    <div class="card-body">
                        <h4>${timeB.toFixed(2)} ms</h4>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-center">
                    <div class="card-header bg-info text-white">
                        <h5>性能对比</h5>
                    </div>
                    <div class="card-body">
                        <h4>${fasterModel} 更快</h4>
                        <p>快 ${percentageDiff}%</p>
                    </div>
                </div>
            </div>
        </div>`;
        
        comparisonDiv.innerHTML = comparisonHtml;
    }
}

// 创建全局实例
window.detectionManager = new DetectionManager();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DetectionManager;
}
