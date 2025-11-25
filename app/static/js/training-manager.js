// 训练管理模块
class TrainingManager {
    constructor() {
        // 训练管理相关属性
        this.trainingTasksRefreshInterval = null;
    }

    // 获取状态文本
    getStatusText(status) {
        switch (status) {
            case 'processing':
                return '处理中';
            case 'available':
                return '可用';
            case 'error':
                return '错误';
            case 'pending':
                return '未训练';
            case 'running':
                return '运行中';
            case 'training':
                return '训练中';
            case 'completed':
                return '已完成';
            case 'failed':
                return '失败';
            case 'cancelled':
                return '已取消';
            case 'active':
                return '进行中';
            case 'inactive':
                return '已完成';
            case 'downloading_model':
                return '下载模型中';
            default:
                return status;
        }
    }

    // 获取状态徽章样式
    getStatusBadgeClass(status) {
        switch (status) {
            case 'processing':
            case 'pending':
                return 'bg-warning';
            case 'available':
            case 'completed':
            case 'inactive':
                return 'bg-success';
            case 'error':
            case 'failed':
                return 'bg-danger';
            case 'running':
            case 'training':
            case 'active':
            case 'downloading_model':
                return 'bg-primary';
            case 'cancelled':
                return 'bg-secondary';
            default:
                return 'bg-secondary';
        }
    }

    // 加载训练任务列表
    loadTrainingTasks() {
        authenticatedFetch(`${API_URL}/training/`)
            .then(response => response.json())
            .then(tasks => {
                const tableBody = document.getElementById('training-table-body');
                
                // 检查元素是否存在，避免在不相关页面调用时出错
                if (!tableBody) {
                    console.log('训练任务表格元素不存在，跳过更新');
                    return;
                }
                
                tableBody.innerHTML = '';

                if (tasks.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="7" class="text-center">暂无训练任务</td></tr>';
                    return;
                }

                tasks.forEach(task => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${task.name}</td>
                        <td>${task.dataset_id}</td>
                        <td>${task.model_id || '-'}</td>
                        <td><span class="badge ${this.getStatusBadgeClass(task.status)}">${this.getStatusText(task.status)}</span></td>
                        <td>${task.start_time ? new Date(task.start_time).toLocaleString() : '-'}</td>
                        <td>${task.end_time ? new Date(task.end_time).toLocaleString() : '-'}</td>
                        <td>
                            ${task.status === 'pending' ? `<button class="btn btn-sm btn-success start-training" data-id="${task.id}">开始训练</button>` : ''}
                            ${task.status === 'running' || task.status === 'training' || task.status === 'downloading_model' || task.status === 'pending' ? `<button class="btn btn-sm btn-warning stop-training" data-id="${task.id}">停止训练</button>` : ''}
                            ${(task.status === 'cancelled' || task.status === 'failed') ? `<button class="btn btn-sm btn-success resume-training" data-id="${task.id}">继续训练</button>` : ''}
                            ${task.status === 'running' || task.status === 'completed' ? `<button class="btn btn-sm btn-info tensorboard" data-id="${task.id}">TensorBoard</button>` : ''}
                            <button class="btn btn-sm btn-primary view-details" data-id="${task.id}">训练详情</button>
                            ${task.status === 'running' || task.status === 'training' || task.status === 'downloading_model' || task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled' ? `<button class="btn btn-sm btn-secondary view-logs" data-id="${task.id}">查看日志</button>` : ''}
                            ${task.status === 'completed' ? `<button class="btn btn-sm btn-success export-models" data-id="${task.id}">导出模型</button>` : ''}
                            ${task.status !== 'running' && task.status !== 'training' && task.status !== 'downloading_model' ? `<button class="btn btn-sm btn-danger delete-training" data-id="${task.id}">删除</button>` : ''}
                        </td>
                    `;
                    tableBody.appendChild(row);
                });

                // 绑定按钮事件
                document.querySelectorAll('.start-training').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const taskId = e.target.getAttribute('data-id');
                        this.startTraining(taskId);
                    });
                });

                document.querySelectorAll('.stop-training').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const taskId = e.target.getAttribute('data-id');
                        this.stopTraining(taskId);
                    });
                });

                document.querySelectorAll('.resume-training').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const taskId = e.target.getAttribute('data-id');
                        this.resumeTraining(taskId);
                    });
                });

                document.querySelectorAll('.tensorboard').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const taskId = e.target.getAttribute('data-id');
                        this.openTensorBoard(taskId);
                    });
                });

                // 绑定训练详情按钮事件
                document.querySelectorAll('.view-details').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const taskId = e.target.getAttribute('data-id');
                        this.viewTrainingDetails(taskId);
                    });
                });

                // 绑定查看日志按钮事件
                document.querySelectorAll('.view-logs').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const taskId = e.target.getAttribute('data-id');
                        this.viewTrainingLogs(taskId);
                    });
                });

                // 绑定导出模型按钮事件
                document.querySelectorAll('.export-models').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const taskId = e.target.getAttribute('data-id');
                        if (typeof exportModelsManager !== 'undefined') {
                            exportModelsManager.exportModels(taskId);
                        } else {
                            console.error('ExportModelsManager is not available');
                            alert('导出模型功能不可用');
                        }
                    });
                });

                // 绑定删除按钮事件
                document.querySelectorAll('.delete-training').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const taskId = e.target.getAttribute('data-id');
                        this.deleteTraining(taskId);
                    });
                });
            })
            .catch(error => {
                console.error('Error loading training tasks:', error);
                alert('加载训练任务失败');
            });
    }

    // 启动训练任务列表的自动刷新
    startTrainingTasksAutoRefresh() {
        // 清除已有定时器
        if (this.trainingTasksRefreshInterval) {
            clearInterval(this.trainingTasksRefreshInterval);
        }
        
        // 每10秒自动刷新一次
        this.trainingTasksRefreshInterval = setInterval(() => this.loadTrainingTasks(), 10000);
    }

    // 停止训练任务列表的自动刷新
    stopTrainingTasksAutoRefresh() {
        if (this.trainingTasksRefreshInterval) {
            clearInterval(this.trainingTasksRefreshInterval);
            this.trainingTasksRefreshInterval = null;
        }
    }

    // 绑定训练页面事件
    bindTrainingEvents() {
        // 启动自动刷新
        this.startTrainingTasksAutoRefresh();
        
        const addButton = document.getElementById('add-training-btn');
        if (addButton) {
            addButton.addEventListener('click', () => this.showAddTrainingModal());
        }

        // 绑定重启TensorBoard按钮事件
        const restartTensorboardBtn = document.getElementById('restart-tensorboard-btn');
        if (restartTensorboardBtn) {
            restartTensorboardBtn.addEventListener('click', () => this.restartTensorBoard());
        }
    }

    // 显示添加训练任务模态框
    showAddTrainingModal() {
        const modalTitle = document.querySelector('.modal-title');
        const modalBody = document.querySelector('.modal-body');
        const modalSubmit = document.getElementById('modalSubmit');

        modalTitle.textContent = '创建训练任务';

        // 获取模板内容
        const template = document.getElementById('add-training-template');
        modalBody.innerHTML = template.innerHTML;

        // 加载数据集和模型选项
        this.loadDatasetOptions();
        this.loadModelOptions();

        // 显示模态框
        modal.show();

        // 绑定设备类型选择事件
        const deviceTypeSelect = document.getElementById('device-type');
        if (deviceTypeSelect) {
            deviceTypeSelect.addEventListener('change', function() {
                const cpuOptions = document.querySelectorAll('.cpu-option');
                const gpuOptions = document.querySelectorAll('.gpu-option');
                const ascendOptions = document.querySelectorAll('.ascend-option');

                if (this.value === 'cpu') {
                    cpuOptions.forEach(option => option.style.display = 'block');
                    gpuOptions.forEach(option => option.style.display = 'none');
                    ascendOptions.forEach(option => option.style.display = 'none');
                } else if (this.value === 'gpu') {
                    cpuOptions.forEach(option => option.style.display = 'none');
                    gpuOptions.forEach(option => option.style.display = 'block');
                    ascendOptions.forEach(option => option.style.display = 'none');
                } else if (this.value === 'ascend') {
                    cpuOptions.forEach(option => option.style.display = 'none');
                    gpuOptions.forEach(option => option.style.display = 'none');
                    ascendOptions.forEach(option => option.style.display = 'block');
                }
            });
        }

        // 绑定获取GPU信息按钮事件
        const getGpuInfoBtn = document.getElementById('get-gpu-info');
        const gpuInfoDiv = document.getElementById('gpu-info');
        const gpuSelect = document.getElementById('gpu-select');
        const gpuMemoryInput = document.getElementById('gpu-memory');
        const memoryInfoDiv = document.getElementById('memory-info');
        const validateMemoryBtn = document.getElementById('validate-memory');
        const validationResultDiv = document.getElementById('validation-result');

        if (getGpuInfoBtn) {
            getGpuInfoBtn.addEventListener('click', async () => {
                try {
                    // 显示加载中状态
                    getGpuInfoBtn.disabled = true;
                    getGpuInfoBtn.textContent = '获取中...';

                    const response = await authenticatedFetch(`${API_URL}/training/all-gpus-info`);
                    const data = await response.json();

                    // 恢复按钮状态
                    getGpuInfoBtn.disabled = false;
                    getGpuInfoBtn.textContent = '获取GPU信息';

                    if (data.has_gpu) {
                        // 清空GPU选择框
                        gpuSelect.innerHTML = '';

                        // 添加GPU选项
                        data.gpus.forEach(gpu => {
                            const option = document.createElement('option');
                            option.value = gpu.index;
                            option.textContent = gpu.display_name;
                            option.dataset.memory = gpu.free_memory;
                            option.dataset.recommended = gpu.recommended_memory;
                            option.dataset.totalMemory = gpu.total_memory;
                            option.dataset.usedMemory = gpu.used_memory;
                            option.dataset.name = gpu.name;
                            gpuSelect.appendChild(option);
                        });

                        // 设置默认显存值
                        const selectedGpu = data.gpus[0];
                        gpuMemoryInput.value = selectedGpu.recommended_memory;
                        memoryInfoDiv.innerHTML = `
                            <div>GPU名称: ${selectedGpu.name}</div>
                            <div>总显存: ${selectedGpu.total_memory} MB</div>
                            <div>已用显存: ${selectedGpu.used_memory} MB</div>
                            <div>可用显存: ${selectedGpu.free_memory} MB</div>
                            <div class="text-success">推荐显存: ${selectedGpu.recommended_memory} MB</div>
                        `;

                        // 显示GPU信息
                        gpuInfoDiv.style.display = 'block';
                    } else {
                        alert('没有可用的GPU，请使用CPU模式训练');
                        deviceTypeSelect.value = 'cpu';
                        deviceTypeSelect.dispatchEvent(new Event('change'));
                    }
                } catch (error) {
                    console.error('获取GPU信息失败:', error);
                    alert('获取GPU信息失败，请检查网络连接');

                    // 恢复按钮状态
                    getGpuInfoBtn.disabled = false;
                    getGpuInfoBtn.textContent = '获取GPU信息';
                }
            });
        }

        // 绑定获取昇腾NPU信息按钮事件
        const getAscendInfoBtn = document.getElementById('get-ascend-info');
        const ascendInfoDiv = document.getElementById('ascend-info');
        const ascendSelect = document.getElementById('ascend-select');
        const ascendMemoryInput = document.getElementById('ascend-memory');
        const ascendMemoryInfoDiv = document.getElementById('ascend-memory-info');
        const validateAscendMemoryBtn = document.getElementById('validate-ascend-memory');
        const ascendValidationResultDiv = document.getElementById('ascend-validation-result');

        if (getAscendInfoBtn) {
            getAscendInfoBtn.addEventListener('click', async () => {
                try {
                    // 显示加载中状态
                    getAscendInfoBtn.disabled = true;
                    getAscendInfoBtn.textContent = '获取中...';

                    const response = await authenticatedFetch(`${API_URL}/training/ascend-info`);
                    const data = await response.json();

                    // 恢复按钮状态
                    getAscendInfoBtn.disabled = false;
                    getAscendInfoBtn.textContent = '获取昇腾信息';

                    if (data.has_ascend) {
                        // 清空昇腾选择框
                        ascendSelect.innerHTML = '';

                        // 添加昇腾NPU选项
                        data.ascends.forEach(ascend => {
                            const option = document.createElement('option');
                            option.value = ascend.index;
                            option.textContent = ascend.display_name;
                            option.dataset.memory = ascend.free_memory;
                            option.dataset.recommended = ascend.recommended_memory;
                            option.dataset.totalMemory = ascend.total_memory;
                            option.dataset.usedMemory = ascend.used_memory;
                            option.dataset.name = ascend.name;
                            ascendSelect.appendChild(option);
                        });

                        // 设置默认内存值
                        const selectedAscend = data.ascends[0];
                        ascendMemoryInput.value = selectedAscend.recommended_memory;
                        ascendMemoryInfoDiv.innerHTML = `
                            <div>昇腾NPU型号: ${selectedAscend.name}</div>
                            <div>总内存: ${selectedAscend.total_memory} MB</div>
                            <div>已用内存: ${selectedAscend.used_memory} MB</div>
                            <div>可用内存: ${selectedAscend.free_memory} MB</div>
                            <div class="text-success">推荐内存: ${selectedAscend.recommended_memory} MB</div>
                        `;

                        // 显示昇腾信息
                        ascendInfoDiv.style.display = 'block';
                    } else {
                        alert('没有可用的昇腾NPU，请使用其他模式训练');
                        deviceTypeSelect.value = 'cpu';
                        deviceTypeSelect.dispatchEvent(new Event('change'));
                    }
                } catch (error) {
                    console.error('获取昇腾NPU信息失败:', error);
                    alert('获取昇腾NPU信息失败，请检查网络连接');

                    // 恢复按钮状态
                    getAscendInfoBtn.disabled = false;
                    getAscendInfoBtn.textContent = '获取昇腾信息';
                }
            });
        }

        // 绑定自动选择GPU复选框事件
        const autoSelectGpuCheckbox = document.getElementById('auto-select-gpu');
        const manualGpuSelection = document.getElementById('manual-gpu-selection');
        
        if (autoSelectGpuCheckbox) {
            autoSelectGpuCheckbox.addEventListener('change', function() {
                if (this.checked) {
                    // 如果勾选了自动选择GPU，则禁用手动GPU选择
                    if (gpuSelect) {
                        gpuSelect.disabled = true;
                        gpuSelect.selectedIndex = -1; // 清除选择
                    }
                    // 显存限制显示为自动且不可修改
                    gpuMemoryInput.value = '-1';
                    gpuMemoryInput.disabled = true;
                    memoryInfoDiv.innerHTML = '<div class="text-info">自动选择最空闲的GPU进行训练</div>';
                } else {
                    // 如果取消勾选，则启用手动GPU选择
                    if (gpuSelect) {
                        gpuSelect.disabled = false;
                    }
                    gpuMemoryInput.disabled = false;
                    // 如果有选中的GPU，更新显存信息
                    if (gpuSelect && gpuSelect.selectedIndex >= 0) {
                        const selectedOption = gpuSelect.options[gpuSelect.selectedIndex];
                        const freeMemory = parseInt(selectedOption.dataset.memory);
                        const recommendedMemory = parseInt(selectedOption.dataset.recommended);
                        const totalMemory = parseInt(selectedOption.dataset.totalMemory);
                        const usedMemory = parseInt(selectedOption.dataset.usedMemory);
                        const gpuName = selectedOption.dataset.name;

                        gpuMemoryInput.value = recommendedMemory;

                        memoryInfoDiv.innerHTML = `
                            <div>GPU名称: ${gpuName}</div>
                            <div>总显存: ${totalMemory} MB</div>
                            <div>已用显存: ${usedMemory} MB</div>
                            <div>可用显存: ${freeMemory} MB</div>
                            <div class="text-success">推荐显存: ${recommendedMemory} MB</div>
                        `;
                    }
                }
            });
        }

        // 绑定GPU选择改变事件
        if (gpuSelect) {
            gpuSelect.addEventListener('change', function() {
                // 如果启用了自动选择GPU，则不处理手动选择
                if (autoSelectGpuCheckbox && autoSelectGpuCheckbox.checked) {
                    return;
                }
                
                // 获取所有选中的选项（多选情况）
                const selectedOptions = Array.from(this.selectedOptions);
                
                if (selectedOptions.length > 0) {
                    // 计算选中GPU的总显存
                    let totalMemory = 0;
                    let usedMemory = 0;
                    let freeMemory = 0;
                    let recommendedMemory = 0;
                    let gpuNames = [];
                    
                    selectedOptions.forEach(option => {
                        totalMemory += parseInt(option.dataset.totalMemory);
                        usedMemory += parseInt(option.dataset.usedMemory);
                        freeMemory += parseInt(option.dataset.memory);
                        recommendedMemory += parseInt(option.dataset.recommended);
                        gpuNames.push(option.dataset.name);
                    });
                    
                    // 对于多GPU，使用总的推荐显存
                    if (selectedOptions.length > 1) {
                        gpuMemoryInput.value = recommendedMemory;
                        memoryInfoDiv.innerHTML = `
                            <div>选中GPU: ${selectedOptions.length} 个</div>
                            <div>GPU名称: ${gpuNames.join(', ')}</div>
                            <div>总显存: ${totalMemory} MB</div>
                            <div>已用显存: ${usedMemory} MB</div>
                            <div>可用显存: ${freeMemory} MB</div>
                            <div class="text-success">推荐显存(总和): ${recommendedMemory} MB</div>
                        `;
                    } else {
                        // 单GPU情况
                        const selectedOption = selectedOptions[0];
                        const freeMemory = parseInt(selectedOption.dataset.memory);
                        const recommendedMemory = parseInt(selectedOption.dataset.recommended);
                        const totalMemory = parseInt(selectedOption.dataset.totalMemory);
                        const usedMemory = parseInt(selectedOption.dataset.usedMemory);
                        const gpuName = selectedOption.dataset.name;

                        gpuMemoryInput.value = recommendedMemory;

                        memoryInfoDiv.innerHTML = `
                            <div>GPU名称: ${gpuName}</div>
                            <div>总显存: ${totalMemory} MB</div>
                            <div>已用显存: ${usedMemory} MB</div>
                            <div>可用显存: ${freeMemory} MB</div>
                            <div class="text-success">推荐显存: ${recommendedMemory} MB</div>
                        `;
                    }
                } else {
                    // 没有选择GPU
                    memoryInfoDiv.innerHTML = '<div class="text-warning">请选择至少一个GPU</div>';
                }
            });
        }

        // 绑定验证显存设置按钮事件
        if (validateMemoryBtn) {
            validateMemoryBtn.addEventListener('click', async () => {
                const gpuMemory = parseInt(gpuMemoryInput.value);
                const gpuIndex = parseInt(gpuSelect.value);

                if (isNaN(gpuMemory) || gpuMemory <= 0) {
                    validationResultDiv.innerHTML = '<div class="text-danger">请输入有效的显存值</div>';
                    return;
                }

                try {
                    // 显示加载中状态
                    validateMemoryBtn.disabled = true;
                    validateMemoryBtn.textContent = '验证中...';

                    const response = await fetch(`${API_URL}/training/validate-gpu-memory`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            gpu_memory: gpuMemory,
                            gpu_index: gpuIndex
                        })
                    });

                    const data = await response.json();

                    // 恢复按钮状态
                    validateMemoryBtn.disabled = false;
                    validateMemoryBtn.textContent = '验证显存设置';

                    if (data.valid) {
                        validationResultDiv.innerHTML = `<div class="text-success">${data.message}</div>`;
                    } else {
                        validationResultDiv.innerHTML = `<div class="text-danger">${data.message}</div>`;
                    }
                } catch (error) {
                    console.error('验证显存设置失败:', error);
                    validationResultDiv.innerHTML = '<div class="text-danger">验证显存设置失败，请检查网络连接</div>';

                    // 恢复按钮状态
                    validateMemoryBtn.disabled = false;
                    validateMemoryBtn.textContent = '验证显存设置';
                }
            });
        }

        // 绑定昇腾NPU选择改变事件
        if (ascendSelect) {
            ascendSelect.addEventListener('change', function() {
                const selectedOption = this.options[this.selectedIndex];
                const freeMemory = parseInt(selectedOption.dataset.memory);
                const recommendedMemory = parseInt(selectedOption.dataset.recommended);
                const totalMemory = parseInt(selectedOption.dataset.totalMemory);
                const usedMemory = parseInt(selectedOption.dataset.usedMemory);
                const ascendName = selectedOption.dataset.name;

                ascendMemoryInput.value = recommendedMemory;

                ascendMemoryInfoDiv.innerHTML = `
                    <div>昇腾NPU型号: ${ascendName}</div>
                    <div>总内存: ${totalMemory} MB</div>
                    <div>已用内存: ${usedMemory} MB</div>
                    <div>可用内存: ${freeMemory} MB</div>
                    <div class="text-success">推荐内存: ${recommendedMemory} MB</div>
                `;
            });
        }

        // 绑定验证昇腾内存设置按钮事件
        if (validateAscendMemoryBtn) {
            validateAscendMemoryBtn.addEventListener('click', async () => {
                const ascendMemory = parseInt(ascendMemoryInput.value);
                const ascendIndex = parseInt(ascendSelect.value);

                if (isNaN(ascendMemory) || ascendMemory <= 0) {
                    ascendValidationResultDiv.innerHTML = '<div class="text-danger">请输入有效的内存值</div>';
                    return;
                }

                try {
                    // 显示加载中状态
                    validateAscendMemoryBtn.disabled = true;
                    validateAscendMemoryBtn.textContent = '验证中...';

                    const response = await authenticatedFetch(`${API_URL}/training/validate-ascend-memory`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            ascend_memory: ascendMemory,
                            ascend_index: ascendIndex
                        })
                    });

                    const data = await response.json();

                    // 恢复按钮状态
                    validateAscendMemoryBtn.disabled = false;
                    validateAscendMemoryBtn.textContent = '验证内存设置';

                    if (data.valid) {
                        ascendValidationResultDiv.innerHTML = `<div class="text-success">${data.message}</div>`;
                    } else {
                        ascendValidationResultDiv.innerHTML = `<div class="text-danger">${data.message}</div>`;
                    }
                } catch (error) {
                    console.error('验证昇腾内存设置失败:', error);
                    ascendValidationResultDiv.innerHTML = '<div class="text-danger">验证昇腾内存设置失败，请检查网络连接</div>';

                    // 恢复按钮状态
                    validateAscendMemoryBtn.disabled = false;
                    validateAscendMemoryBtn.textContent = '验证内存设置';
                }
            });
        }

        // 绑定矩形训练模式切换事件
        const enableRectTraining = document.getElementById('enable-rect-training');
        if (enableRectTraining) {
            enableRectTraining.addEventListener('change', function() {
                const squareSizeContainer = document.getElementById('square-size-container');
                const rectSizeContainer = document.getElementById('rect-size-container');

                if (this.checked) {
                    // 启用矩形训练模式
                    squareSizeContainer.style.display = 'none';
                    rectSizeContainer.style.display = 'block';
                } else {
                    // 禁用矩形训练模式
                    squareSizeContainer.style.display = 'block';
                    rectSizeContainer.style.display = 'none';
                }
            });
        }

        // 绑定提交按钮事件
        modalSubmit.onclick = () => this.submitAddTraining();
    }

    // 加载数据集选项
    loadDatasetOptions() {
        authenticatedFetch(`${API_URL}/datasets/`)
            .then(response => response.json())
            .then(datasets => {
                const select = document.getElementById('training-dataset');

                // 清空现有选项（保留第一个默认选项）
                while (select.options.length > 1) {
                    select.remove(1);
                }

                // 添加内部数据集组
                const internalGroup = document.createElement('optgroup');
                internalGroup.label = '内部数据集';

                // 添加外部数据集组
                const externalGroup = document.createElement('optgroup');
                externalGroup.label = '外部数据集';

                // 计数器
                let internalCount = 0;
                let externalCount = 0;

                datasets.forEach(dataset => {
                    if (dataset.status === 'available') {
                        const option = document.createElement('option');
                        option.value = dataset.id;

                        // 判断是否为外部数据集
                        if (dataset.is_external) {
                            option.textContent = `${dataset.name}`;
                            externalGroup.appendChild(option);
                            externalCount++;
                        } else {
                            option.textContent = dataset.name;
                            internalGroup.appendChild(option);
                            internalCount++;
                        }
                    }
                });

                // 添加组到选择框
                if (internalCount > 0) {
                    select.appendChild(internalGroup);
                }

                if (externalCount > 0) {
                    select.appendChild(externalGroup);
                }

                // 如果没有数据集，添加提示
                if (internalCount === 0 && externalCount === 0) {
                    const option = document.createElement('option');
                    option.value = '';
                    option.textContent = '没有可用的数据集';
                    option.disabled = true;
                    select.appendChild(option);
                }
            })
            .catch(error => {
                console.error('Error loading dataset options:', error);
            });
    }

    // 加载模型选项
    loadModelOptions() {
        authenticatedFetch(`${API_URL}/models/`)
            .then(response => response.json())
            .then(models => {
                const select = document.getElementById('training-model');

                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = `${model.name} (${model.type})`;
                    select.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Error loading model options:', error);
            });
    }

    // 提交添加训练任务表单
    submitAddTraining() {
        const nameInput = document.getElementById('training-name');
        const epochsInput = document.getElementById('training-epochs');
        const batchSizeInput = document.getElementById('training-batch-size');
        const imgSizeInput = document.getElementById('training-img-size');
        const lrInput = document.getElementById('training-lr');

        const datasetSelect = document.getElementById('training-dataset');

        // 检查必填字段
        if (!nameInput.value || !epochsInput.value || !batchSizeInput.value || !imgSizeInput.value || !lrInput.value) {
            alert('请填写必填字段');
            return;
        }

        // 检查数据集选择
        if (!datasetSelect.value) {
            alert('请选择数据集');
            return;
        }
        const datasetId = datasetSelect.value;

        const modelSelect = document.getElementById('training-model');

        // 获取硬件配置参数
        const deviceTypeSelect = document.getElementById('device-type');
        const cpuCoresInput = document.getElementById('cpu-cores');
        const gpuMemoryInput = document.getElementById('gpu-memory');
        const memoryInput = document.getElementById('memory');

        // 创建硬件配置对象
        const hardwareConfig = {
            device_type: deviceTypeSelect.value
        };

        // 根据设备类型添加相应的参数
        if (deviceTypeSelect.value === 'cpu') {
            hardwareConfig.cpu_cores = parseInt(cpuCoresInput.value);
        } else if (deviceTypeSelect.value === 'gpu') {
            // 处理GPU配置
            const autoSelectGpuCheckbox = document.getElementById('auto-select-gpu');
            const gpuSelect = document.getElementById('gpu-select');
            
            // 如果启用了自动选择GPU
            if (autoSelectGpuCheckbox && autoSelectGpuCheckbox.checked) {
                // 设置自动选择GPU标志
                hardwareConfig.auto_select_gpu = true;
                // 显存设置为-1表示自动
                hardwareConfig.gpu_memory = -1;
            } else {
                // 手动选择GPU模式
                hardwareConfig.auto_select_gpu = false;
                
                // 获取GPU显存
                if (gpuMemoryInput.value === '自动') {
                    hardwareConfig.gpu_memory = -1; // 自动
                } else {
                    hardwareConfig.gpu_memory = parseInt(gpuMemoryInput.value);
                }

                // 如果用户选择了GPU，添加GPU索引
                if (gpuSelect && gpuSelect.selectedOptions.length > 0) {
                    // 获取所有选中的GPU索引
                    const selectedIndices = Array.from(gpuSelect.selectedOptions).map(option => parseInt(option.value));
                    
                    if (selectedIndices.length === 1) {
                        // 单GPU
                        hardwareConfig.gpu_index = selectedIndices[0];
                    } else {
                        // 多GPU
                        hardwareConfig.gpu_indices = selectedIndices;
                    }
                }
            }
        } else if (deviceTypeSelect.value === 'ascend') {
            // 获取昇腾NPU内存和NPU ID
            hardwareConfig.ascend_memory = parseInt(ascendMemoryInput.value);

            // 如果用户选择了特定昇腾NPU，添加NPU ID
            const ascendSelect = document.getElementById('ascend-select');
            if (ascendSelect && ascendSelect.value) {
                hardwareConfig.ascend_index = parseInt(ascendSelect.value);
            }
        }

        // 添加内存参数
        hardwareConfig.memory = parseInt(memoryInput.value);

        // 获取矩形训练模式设置
        const enableRectTraining = document.getElementById('enable-rect-training').checked;

        // 创建训练参数对象
        const parameters = {
            epochs: parseInt(epochsInput.value),
            batch_size: parseInt(batchSizeInput.value),
            lr0: parseFloat(lrInput.value)
        };

        // 根据矩形训练模式设置图像大小
        if (enableRectTraining) {
            // 矩形训练模式，使用宽高数组
            const imgWidth = parseInt(document.getElementById('training-img-width').value);
            const imgHeight = parseInt(document.getElementById('training-img-height').value);
            parameters.img_size = [imgWidth, imgHeight];
            parameters.rect = true; // 启用矩形训练
        } else {
            // 正方形模式，使用单一尺寸
            parameters.img_size = parseInt(imgSizeInput.value);
        }

        // 创建请求数据
        const data = {
            name: nameInput.value,
            model_id: modelSelect.value || null,
            parameters: parameters,
            hardware_config: hardwareConfig
        };

        // 添加数据集ID
        data.dataset_id = datasetId;

        // 发送请求
        authenticatedFetch(`${API_URL}/training/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                return response.json().then(data => {
                    throw new Error(data.detail || '创建训练任务失败');
                });
            }
        })
        .then(result => {
            modal.hide();
            this.loadTrainingTasks();
        })
        .catch(error => {
            console.error('Error creating training task:', error);
            alert('创建训练任务失败: ' + error.message);
        });
    }

    // 开始训练
    startTraining(taskId) {
        // 检查任务状态
        authenticatedFetch(`${API_URL}/training/${taskId}`)
            .then(response => response.json())
            .then(task => {
                // 如果任务已经在运行中，显示提示并返回
                if (task.status === 'running' || task.status === 'training' || task.status === 'downloading_model') {
                    alert('该训练任务已经在运行中，请等待完成。');
                    return;
                }

                // 显示加载中提示
                const loadingToast = document.createElement('div');
                loadingToast.className = 'toast show';
                loadingToast.style.position = 'fixed';
                loadingToast.style.top = '20px';
                loadingToast.style.right = '20px';
                loadingToast.style.backgroundColor = '#007bff';
                loadingToast.style.color = 'white';
                loadingToast.style.padding = '10px 20px';
                loadingToast.style.borderRadius = '4px';
                loadingToast.style.zIndex = '9999';
                loadingToast.innerHTML = '正在启动训练任务，请稍候...';
                document.body.appendChild(loadingToast);

                // 发送请求开始训练
                authenticatedFetch(`${API_URL}/training/${taskId}/start`, {
                    method: 'POST'
                })
                .then(response => {
                    // 移除加载中提示
                    document.body.removeChild(loadingToast);

                    if (response.ok) {
                        // 显示成功提示
                        const successToast = document.createElement('div');
                        successToast.className = 'toast show';
                        successToast.style.position = 'fixed';
                        successToast.style.top = '20px';
                        successToast.style.right = '20px';
                        successToast.style.backgroundColor = '#28a745';
                        successToast.style.color = 'white';
                        successToast.style.padding = '10px 20px';
                        successToast.style.borderRadius = '4px';
                        successToast.style.zIndex = '9999';
                        successToast.innerHTML = '训练任务已启动，请等待完成。';
                        document.body.appendChild(successToast);

                        // 3秒后自动移除提示
                        setTimeout(() => {
                            document.body.removeChild(successToast);
                        }, 3000);

                        // 重新加载训练任务列表
                        this.loadTrainingTasks();

                        // 打开训练日志页面
                        this.viewTrainingLogs(taskId);
                    } else {
                        throw new Error('开始训练失败');
                    }
                })
                .catch(error => {
                    // 移除加载中提示
                    if (document.body.contains(loadingToast)) {
                        document.body.removeChild(loadingToast);
                    }
                    console.error('Error starting training:', error);
                    alert('开始训练失败');
                });
            })
            .catch(error => {
                console.error('Error checking task status:', error);
                alert('检查任务状态失败');
            });
    }

    // 停止训练
    stopTraining(taskId) {
        if (!confirm('确定要停止这个训练任务吗？这将终止当前的训练过程。')) {
            return;
        }

        authenticatedFetch(`${API_URL}/training/${taskId}/stop`, {
            method: 'POST'
        })
            .then(response => {
                if (response.ok) {
                    alert('训练已停止');
                    this.loadTrainingTasks();
                } else {
                    throw new Error('停止训练失败');
                }
            })
            .catch(error => {
                console.error('Error stopping training:', error);
                alert('停止训练失败');
            });
    }

    // 继续训练
    resumeTraining(taskId) {
        // 检查任务状态
        authenticatedFetch(`${API_URL}/training/${taskId}`)
            .then(response => response.json())
            .then(task => {
                // 如果任务已经在运行中，显示提示并返回
                if (task.status === 'running' || task.status === 'training' || task.status === 'downloading_model') {
                    alert('该训练任务已经在运行中，请等待完成。');
                    return;
                }

                // 显示加载中提示
                const loadingToast = document.createElement('div');
                loadingToast.className = 'toast show';
                loadingToast.style.position = 'fixed';
                loadingToast.style.top = '20px';
                loadingToast.style.right = '20px';
                loadingToast.style.backgroundColor = '#007bff';
                loadingToast.style.color = 'white';
                loadingToast.style.padding = '10px 20px';
                loadingToast.style.borderRadius = '4px';
                loadingToast.style.zIndex = '9999';
                loadingToast.innerHTML = '正在继续训练任务，请稍候...';
                document.body.appendChild(loadingToast);

                // 发送请求继续训练
                authenticatedFetch(`${API_URL}/training/${taskId}/resume`, {
                    method: 'POST'
                })
                .then(response => {
                    // 移除加载中提示
                    document.body.removeChild(loadingToast);

                    if (response.ok) {
                        // 显示成功提示
                        const successToast = document.createElement('div');
                        successToast.className = 'toast show';
                        successToast.style.position = 'fixed';
                        successToast.style.top = '20px';
                        successToast.style.right = '20px';
                        successToast.style.backgroundColor = '#28a745';
                        successToast.style.color = 'white';
                        successToast.style.padding = '10px 20px';
                        successToast.style.borderRadius = '4px';
                        successToast.style.zIndex = '9999';
                        successToast.innerHTML = '训练任务已继续，请等待完成。';
                        document.body.appendChild(successToast);

                        // 3秒后自动移除提示
                        setTimeout(() => {
                            document.body.removeChild(successToast);
                        }, 3000);

                        // 重新加载训练任务列表
                        this.loadTrainingTasks();

                        // 打开训练日志页面
                        this.viewTrainingLogs(taskId);
                    } else {
                        return response.json().then(data => {
                            throw new Error(data.detail || '继续训练失败');
                        });
                    }
                })
                .catch(error => {
                    // 移除加载中提示
                    if (document.body.contains(loadingToast)) {
                        document.body.removeChild(loadingToast);
                    }
                    console.error('Error resuming training:', error);
                    alert('继续训练失败: ' + error.message);
                });
            })
            .catch(error => {
                console.error('Error checking task status:', error);
                alert('检查任务状态失败');
            });
    }

    // 打开TensorBoard
    openTensorBoard(taskId) {
        // 显示加载中提示
        const loadingToast = document.createElement('div');
        loadingToast.className = 'toast show';
        loadingToast.style.position = 'fixed';
        loadingToast.style.top = '20px';
        loadingToast.style.right = '20px';
        loadingToast.style.backgroundColor = '#007bff';
        loadingToast.style.color = 'white';
        loadingToast.style.padding = '10px 20px';
        loadingToast.style.borderRadius = '4px';
        loadingToast.style.zIndex = '9999';
        loadingToast.innerHTML = '正在获取TensorBoard URL...';
        document.body.appendChild(loadingToast);

        authenticatedFetch(`${API_URL}/training/${taskId}/tensorboard`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('获取TensorBoard URL失败');
                }
                return response.json();
            })
            .then(data => {
                // 移除加载中提示
                document.body.removeChild(loadingToast);

                if (data.url) {
                    // 打开TensorBoard
                    const tbWindow = window.open(data.url, '_blank');

                    // 检查窗口是否被阻止
                    if (!tbWindow || tbWindow.closed || typeof tbWindow.closed === 'undefined') {
                        // 窗口被阻止，显示提示
                        this.showModal('TensorBoard打开失败',
                            `<p>浏览器阻止了打开TensorBoard窗口。请允许弹出窗口，或者手动访问以下链接：</p>
                            <p><a href="${data.url}" target="_blank">${data.url}</a></p>
                            <p>如果TensorBoard无法显示数据，请尝试以下操作：</p>
                            <div class="d-flex justify-content-center mt-3">
                                <button id="restart-tensorboard-btn" class="btn btn-warning me-2">重启TensorBoard服务</button>
                                <button id="open-logs-folder-btn" class="btn btn-info">打开日志目录</button>
                            </div>`,
                            () => {
                                // 绑定重启按钮事件
                                document.getElementById('restart-tensorboard-btn').addEventListener('click', () => {
                                    this.restartTensorBoard();
                                });

                                // 绑定打开日志目录按钮事件
                                document.getElementById('open-logs-folder-btn').addEventListener('click', () => {
                                    this.openTensorBoardLogsFolder(taskId);
                                });
                            }
                        );
                    }
                } else {
                    throw new Error('TensorBoard URL不可用');
                }
            })
            .catch(error => {
                // 移除加载中提示
                if (document.body.contains(loadingToast)) {
                    document.body.removeChild(loadingToast);
                }
                console.error('Error opening TensorBoard:', error);

                // 显示错误提示，并提供重启选项
                this.showModal('TensorBoard打开失败',
                    `<p>打开TensorBoard时发生错误: ${error.message}</p>
                    <p>请尝试重启TensorBoard服务：</p>
                    <button id="restart-tensorboard-btn" class="btn btn-warning">重启TensorBoard服务</button>`,
                    () => {
                        // 绑定重启按钮事件
                        document.getElementById('restart-tensorboard-btn').addEventListener('click', () => {
                            this.restartTensorBoard();
                        });
                    }
                );
            });
    }

    // 重启TensorBoard服务
    restartTensorBoard() {
        console.log('Restarting TensorBoard service');

        // 显示加载提示
        const loadingToast = this.showToast('正在重启TensorBoard服务...', 'info', 10000);

        // 调用重启API
        authenticatedFetch(`${API_URL}/training/restart-tensorboard`, {
            method: 'POST'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to restart TensorBoard');
            }
            return response.json();
        })
        .then(data => {
            // 隐藏加载提示
            this.hideToast(loadingToast);

            if (data.success) {
                this.showToast('TensorBoard服务已重启，请重新打开TensorBoard', 'success', 5000);
            } else {
                this.showToast('TensorBoard服务重启失败: ' + data.message, 'error', 5000);
            }
        })
        .catch(error => {
            // 隐藏加载提示
            this.hideToast(loadingToast);

            console.error('Error restarting TensorBoard:', error);
            this.showToast('重启TensorBoard服务失败: ' + error.message, 'error', 5000);
        });
    }

    // 打开TensorBoard日志目录
    openTensorBoardLogsFolder(taskId) {
        console.log('Opening TensorBoard logs folder for task:', taskId);

        // 显示加载提示
        const loadingToast = this.showToast('正在打开日志目录...', 'info', 10000);

        // 调用API获取日志目录路径
        authenticatedFetch(`${API_URL}/training/${taskId}/logs-folder`)
        .then(response => {
            if (!response.ok) {
                throw new Error('获取日志目录路径失败');
            }
            return response.json();
        })
        .then(data => {
            // 隐藏加载提示
            this.hideToast(loadingToast);

            if (data.path) {
                // 显示成功提示
                this.showToast('已打开日志目录', 'success', 3000);
            } else {
                throw new Error('日志目录路径不可用');
            }
        })
        .catch(error => {
            // 隐藏加载提示
            this.hideToast(loadingToast);

            console.error('Error opening logs folder:', error);
            this.showToast('打开日志目录失败: ' + error.message, 'error', 5000);
        });
    }

    // 删除训练任务
    deleteTraining(taskId) {
        // 创建确认对话框
        const modal = this.createModal();

        // 创建模态框内容
        const modalContent = document.createElement('div');
        modalContent.className = 'modal-content';
        modalContent.style.backgroundColor = '#fefefe';
        modalContent.style.margin = '15% auto';
        modalContent.style.padding = '20px';
        modalContent.style.border = '1px solid #888';
        modalContent.style.width = '50%';
        modalContent.style.textAlign = 'center';

        // 添加标题
        const title = document.createElement('h3');
        title.textContent = '确认删除';
        modalContent.appendChild(title);

        // 添加确认信息
        const confirmText = document.createElement('p');
        confirmText.textContent = '您确定要删除这个训练任务吗？这将删除所有相关文件和数据库记录。';
        confirmText.style.marginBottom = '20px';
        modalContent.appendChild(confirmText);

        // 添加按钮容器
        const buttonContainer = document.createElement('div');
        buttonContainer.style.display = 'flex';
        buttonContainer.style.justifyContent = 'center';
        buttonContainer.style.gap = '10px';

        // 添加取消按钮
        const cancelButton = document.createElement('button');
        cancelButton.textContent = '取消';
        cancelButton.className = 'btn btn-secondary';
        cancelButton.onclick = function() {
            document.body.removeChild(modal);
        };
        buttonContainer.appendChild(cancelButton);

        // 添加确认按钮
        const confirmButton = document.createElement('button');
        confirmButton.textContent = '确认删除';
        confirmButton.className = 'btn btn-danger';
        confirmButton.onclick = () => {
            // 显示加载中状态
            confirmButton.disabled = true;
            confirmButton.textContent = '删除中...';

            // 发送删除请求
                authenticatedFetch(`${API_URL}/training/${taskId}`, {
                    method: 'DELETE'
                })
            .then(response => {
                if (response.ok) {
                    return response.json();
                } else {
                    throw new Error('删除失败');
                }
            })
            .then(data => {
                // 关闭模态框
                document.body.removeChild(modal);

                // 显示成功消息
                alert(`删除成功: ${data.message}`);

                // 重新加载训练任务列表
                this.loadTrainingTasks();
            })
            .catch(error => {
                console.error('Error deleting training task:', error);
                alert('删除训练任务失败');
                confirmButton.disabled = false;
                confirmButton.textContent = '确认删除';
            });
        };
        buttonContainer.appendChild(confirmButton);

        modalContent.appendChild(buttonContainer);
        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        // 点击模态框外部关闭
        window.onclick = function(event) {
            if (event.target === modal) {
                document.body.removeChild(modal);
            }
        };
    }

    // 查看训练日志
    viewTrainingLogs(taskId) {
        // 创建一个模态框来显示日志
        const modal = this.createModal();

        // 创建模态框内容
        const modalContent = document.createElement('div');
        modalContent.className = 'modal-content';
        modalContent.style.backgroundColor = '#fefefe';
        modalContent.style.margin = '5% auto';
        modalContent.style.padding = '20px';
        modalContent.style.border = '1px solid #888';
        modalContent.style.width = '80%';
        modalContent.style.maxHeight = '80%';
        modalContent.style.overflow = 'auto';

        // 添加标题
        const title = document.createElement('h2');
        title.textContent = '训练日志';
        modalContent.appendChild(title);

        // 添加关闭按钮
        const closeBtn = document.createElement('span');
        closeBtn.textContent = '\u00D7';
        closeBtn.style.color = '#aaa';
        closeBtn.style.float = 'right';
        closeBtn.style.fontSize = '28px';
        closeBtn.style.fontWeight = 'bold';
        closeBtn.style.cursor = 'pointer';
        closeBtn.onclick = function() {
            document.body.removeChild(modal);
        };
        modalContent.appendChild(closeBtn);

        // 添加日志内容区域
        const logContent = document.createElement('pre');
        logContent.style.backgroundColor = '#f8f9fa';
        logContent.style.padding = '10px';
        logContent.style.borderRadius = '4px';
        logContent.style.maxHeight = '500px';
        logContent.style.overflow = 'auto';
        logContent.style.whiteSpace = 'pre-wrap';
        logContent.style.overflowWrap = 'break-word';
        logContent.textContent = '正在加载日志...';
        modalContent.appendChild(logContent);

        // 添加按钮容器
        const buttonContainer = document.createElement('div');
        buttonContainer.style.display = 'flex';
        buttonContainer.style.justifyContent = 'space-between';
        buttonContainer.style.marginTop = '15px';
        modalContent.appendChild(buttonContainer);

        // 添加左侧按钮组
        const leftButtons = document.createElement('div');
        buttonContainer.appendChild(leftButtons);

        // 添加刷新按钮
        const refreshBtn = document.createElement('button');
        refreshBtn.textContent = '刷新日志';
        refreshBtn.className = 'btn btn-primary';
        refreshBtn.style.marginRight = '10px';
        refreshBtn.onclick = () => {
            fetchLogs();
        };
        leftButtons.appendChild(refreshBtn);

        // 添加下载日志按钮
        const downloadLogBtn = document.createElement('button');
        downloadLogBtn.textContent = '下载日志';
        downloadLogBtn.className = 'btn btn-success';
        downloadLogBtn.style.marginRight = '10px';
        downloadLogBtn.onclick = () => {
            // 创建下载链接
            const downloadUrl = `${API_URL}/training/${taskId}/logs/download`;
            // 创建一个隐藏的a标签用于下载
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = `training_logs_${taskId}.txt`;
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        };
        leftButtons.appendChild(downloadLogBtn);

        // 添加TensorBoard按钮
        const tensorboardBtn = document.createElement('button');
        tensorboardBtn.textContent = '打开TensorBoard';
        tensorboardBtn.className = 'btn btn-info';
        tensorboardBtn.style.marginRight = '10px';
        // 保存TrainingManager实例的引用
        const self = this;
        tensorboardBtn.onclick = function() {
            // 使用保存的实例引用调用openTensorBoard函数
            self.openTensorBoard(taskId);
        };
        leftButtons.appendChild(tensorboardBtn);

        // 添加停止训练按钮（只在训练中显示）
        const stopBtn = document.createElement('button');
        stopBtn.textContent = '停止训练';
        stopBtn.className = 'btn btn-danger';
        stopBtn.style.marginRight = '10px';
        stopBtn.style.display = 'none'; // 默认隐藏，根据状态显示
        stopBtn.onclick = () => {
            if (confirm('确定要停止训练吗？这将终止当前的训练过程。')) {
                fetch(`${API_URL}/training/${taskId}/stop`, {
                    method: 'POST'
                })
                .then(response => {
                    if (response.ok) {
                        alert('训练已停止');
                        // 重新加载训练任务列表
                        this.loadTrainingTasks();
                        // 刷新日志
                        fetchLogs();
                        // 隐藏停止按钮
                        stopBtn.style.display = 'none';
                    } else {
                        throw new Error('停止训练失败');
                    }
                })
                .catch(error => {
                    console.error('Error stopping training:', error);
                    alert('停止训练失败: ' + error.message);
                });
            }
        };
        leftButtons.appendChild(stopBtn);

        // 添加右侧按钮组
        const rightButtons = document.createElement('div');
        buttonContainer.appendChild(rightButtons);

        // 添加关闭按钮
        const closeButton = document.createElement('button');
        closeButton.textContent = '关闭';
        closeButton.className = 'btn btn-secondary';
        closeButton.onclick = function() {
            document.body.removeChild(modal);
        };
        rightButtons.appendChild(closeButton);

        // 将模态框添加到文档中
        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        // 获取日志内容和任务状态
        const fetchLogs = () => {
            // 获取任务状态
            authenticatedFetch(`${API_URL}/training/${taskId}`)
                .then(response => {
                    if (!response.ok) {
                        // 如果是404错误，表示任务不存在
                        if (response.status === 404) {
                            // 停止轮询
                            clearInterval(autoRefresh);
                            if (typeof PollingManager !== 'undefined') {
                                PollingManager.removePoll(`training_logs_${taskId}`);
                            }

                            // 显示错误信息
                            logContent.innerHTML = '<div class="alert alert-warning">该训练任务不存在或已被删除</div>';

                            // 隐藏所有按钮
                            refreshBtn.style.display = 'none';
                            tensorboardBtn.style.display = 'none';
                            stopBtn.style.display = 'none';

                            throw new Error('训练任务不存在或已被删除');
                        }
                        throw new Error('获取任务状态失败');
                    }
                    return response.json();
                })
                .then(taskData => {
                    // 根据任务状态显示/隐藏停止按钮
                    if (taskData.status === 'training' || taskData.status === 'running' ||
                        taskData.status === 'pending' || taskData.status === 'downloading_model') {
                        stopBtn.style.display = 'inline-block';
                    } else {
                        stopBtn.style.display = 'none';
                        
                        // 如果任务已完成，停止轮询
                        if (taskData.status === 'completed') {
                            clearInterval(autoRefresh);
                            if (typeof PollingManager !== 'undefined') {
                                PollingManager.removePoll(`training_logs_${taskId}`);
                            }
                        }
                    }
                })
                .catch(error => {
                    console.error('Error fetching task status:', error);
                    // 如果不是任务不存在的错误，显示错误信息
                    if (!error.message.includes('不存在')) {
                        logContent.innerHTML += `<div class="alert alert-danger">获取任务状态失败: ${error.message}</div>`;
                    }
                });

            // 获取日志
            authenticatedFetch(`${API_URL}/training/${taskId}/logs`)
                .then(response => {
                    if (!response.ok) {
                        // 如果是404错误，表示任务不存在
                        if (response.status === 404) {
                            // 停止轮询
                            clearInterval(autoRefresh);
                            if (typeof PollingManager !== 'undefined') {
                                PollingManager.removePoll(`training_logs_${taskId}`);
                            }

                            // 显示错误信息
                            logContent.innerHTML = '<div class="alert alert-warning">该训练任务不存在或已被删除</div>';

                            // 隐藏所有按钮
                            refreshBtn.style.display = 'none';
                            tensorboardBtn.style.display = 'none';
                            stopBtn.style.display = 'none';

                            throw new Error('训练任务不存在或已被删除');
                        }
                        throw new Error('获取日志失败');
                    }
                    return response.json();
                })
                .then(data => {
                    logContent.textContent = data.logs || '暂无日志';
                    // 滚动到日志底部
                    logContent.scrollTop = logContent.scrollHeight;
                })
                .catch(error => {
                    console.error('Error fetching logs:', error);
                    // 如果不是任务不存在的错误，显示错误信息
                    if (!error.message.includes('不存在')) {
                        logContent.textContent = '获取日志失败';
                    }
                });
        }

        // 初始加载日志
        fetchLogs();

        // 每 5 秒自动刷新一次日志
        const autoRefresh = window.memoryManager.setInterval(fetchLogs, 5000);

        // 将定时器添加到轮询管理器
        if (typeof PollingManager !== 'undefined') {
            PollingManager.addPoll(`training_logs_${taskId}`, autoRefresh);
        }

        // 当模态框关闭时清除定时器
        modal.addEventListener('remove', function() {
            window.memoryManager.clearInterval(autoRefresh);

            // 从轮询管理器中移除
            if (typeof PollingManager !== 'undefined') {
                PollingManager.removePoll(`training_logs_${taskId}`);
            }
        });

        // 点击模态框外部关闭
        window.onclick = (event) => {
            if (event.target === modal) {
                document.body.removeChild(modal);
                window.memoryManager.clearInterval(autoRefresh);

                // 从轮询管理器中移除
                if (typeof PollingManager !== 'undefined') {
                    PollingManager.removePoll(`training_logs_${taskId}`);
                }
            }
        };
    }

    // 查看训练详情
    viewTrainingDetails(taskId) {
        // 创建一个模态框来显示训练详情
        const modal = this.createModal();

        // 创建模态框内容
        const modalContent = document.createElement('div');
        modalContent.className = 'modal-content';
        modalContent.style.backgroundColor = '#fefefe';
        modalContent.style.margin = '5% auto';
        modalContent.style.padding = '20px';
        modalContent.style.border = '1px solid #888';
        modalContent.style.width = '80%';
        modalContent.style.maxHeight = '80%';
        modalContent.style.overflow = 'auto';

        // 添加标题
        const title = document.createElement('h2');
        title.textContent = '训练任务详情';
        modalContent.appendChild(title);

        // 添加关闭按钮
        const closeBtn = document.createElement('span');
        closeBtn.textContent = '\u00D7';
        closeBtn.style.color = '#aaa';
        closeBtn.style.float = 'right';
        closeBtn.style.fontSize = '28px';
        closeBtn.style.fontWeight = 'bold';
        closeBtn.style.cursor = 'pointer';
        closeBtn.onclick = function() {
            document.body.removeChild(modal);
        };
        modalContent.appendChild(closeBtn);

        // 添加详情内容区域
        const detailsContainer = document.createElement('div');
        detailsContainer.className = 'details-container';
        detailsContainer.style.marginBottom = '20px';
        detailsContainer.innerHTML = '<p>正在加载训练详情...</p>';
        modalContent.appendChild(detailsContainer);

        // 添加进度监控区域
        const progressContainer = document.createElement('div');
        progressContainer.className = 'progress-container';
        progressContainer.style.marginBottom = '20px';
        modalContent.appendChild(progressContainer);

        // 添加按钮容器
        const buttonContainer = document.createElement('div');
        buttonContainer.style.display = 'flex';
        buttonContainer.style.justifyContent = 'space-between';
        buttonContainer.style.marginTop = '15px';
        modalContent.appendChild(buttonContainer);

        // 添加左侧按钮组
        const leftButtons = document.createElement('div');
        buttonContainer.appendChild(leftButtons);

        // 添加查看日志按钮
        const logsBtn = document.createElement('button');
        logsBtn.textContent = '查看日志';
        logsBtn.className = 'btn btn-secondary';
        logsBtn.style.marginRight = '10px';
        logsBtn.onclick = () => {
            this.viewTrainingLogs(taskId);
        };
        leftButtons.appendChild(logsBtn);

        // 添加TensorBoard按钮
        const tensorboardBtn = document.createElement('button');
        tensorboardBtn.textContent = '打开TensorBoard';
        tensorboardBtn.className = 'btn btn-info';
        tensorboardBtn.style.marginRight = '10px';
        tensorboardBtn.onclick = () => {
            this.openTensorBoard(taskId);
        };
        leftButtons.appendChild(tensorboardBtn);

        // 添加停止训练按钮
        const stopBtn = document.createElement('button');
        stopBtn.textContent = '停止训练';
        stopBtn.className = 'btn btn-danger';
        stopBtn.style.marginRight = '10px';
        stopBtn.onclick = () => {
            if (confirm('确定要停止训练吗？这将终止当前的训练过程。')) {
                this.stopTraining(taskId);
                document.body.removeChild(modal);
            }
        };
        leftButtons.appendChild(stopBtn);

        // 添加右侧按钮组
        const rightButtons = document.createElement('div');
        buttonContainer.appendChild(rightButtons);

        // 添加关闭按钮
        const closeButton = document.createElement('button');
        closeButton.textContent = '关闭';
        closeButton.className = 'btn btn-secondary';
        closeButton.onclick = function() {
            document.body.removeChild(modal);
        };
        rightButtons.appendChild(closeButton);

        // 将模态框添加到文档中
        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        // 获取训练任务详情
        authenticatedFetch(`${API_URL}/training/${taskId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('获取训练任务详情失败');
                }
                return response.json();
            })
            .then(task => {
                // 根据任务状态显示/隐藏停止按钮
                if (task.status === 'training' || task.status === 'running' ||
                    task.status === 'pending' || task.status === 'downloading_model') {
                    stopBtn.style.display = 'inline-block';
                } else {
                    stopBtn.style.display = 'none';
                }

                // 构建详情HTML
                let detailsHtml = `
                    <div class="card mb-4">
                        <div class="card-header">基本信息</div>
                        <div class="card-body">
                            <table class="table table-striped">
                                <tr>
                                    <th>任务ID</th>
                                    <td>${task.id}</td>
                                </tr>
                                <tr>
                                    <th>状态</th>
                                    <td><span class="badge ${this.getStatusBadgeClass(task.status)}">${this.getStatusText(task.status)}</span></td>
                                </tr>
                                <tr>
                                    <th>开始时间</th>
                                    <td>${task.start_time ? new Date(task.start_time).toLocaleString() : '-'}</td>
                                </tr>
                                <tr>
                                    <th>结束时间</th>
                                    <td>${task.end_time ? new Date(task.end_time).toLocaleString() : '-'}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                `;

                // 添加训练参数信息
                if (task.parameters) {
                    detailsHtml += `
                        <div class="card mb-4">
                            <div class="card-header">训练参数</div>
                            <div class="card-body">
                                <table class="table table-striped">
                    `;

                    for (const [key, value] of Object.entries(task.parameters)) {
                        if (key !== 'error') { // 不显示错误信息
                            detailsHtml += `
                                <tr>
                                    <th>${key}</th>
                                    <td>${JSON.stringify(value)}</td>
                                </tr>
                            `;
                        }
                    }

                    detailsHtml += `
                                </table>
                            </div>
                        </div>
                    `;
                }

                // 显示详情
                detailsContainer.innerHTML = detailsHtml;

                // 如果训练正在进行，每5秒刷新一次状态
                if (task.status === 'training' || task.status === 'running' ||
                    task.status === 'pending' || task.status === 'downloading_model') {
                    const statusRefresh = window.memoryManager.setInterval(() => {
                        fetch(`${API_URL}/training/${taskId}`)
                            .then(response => response.json())
                            .then(updatedTask => {
                                // 更新状态
                                const statusCell = detailsContainer.querySelector('span.badge');
                                if (statusCell) {
                                    statusCell.className = `badge ${this.getStatusBadgeClass(updatedTask.status)}`;
                                    statusCell.textContent = this.getStatusText(updatedTask.status);
                                }

                                // 更新结束时间
                                if (updatedTask.end_time) {
                                    const endTimeCell = detailsContainer.querySelectorAll('td')[5]; // 第6个单元格是结束时间
                                    if (endTimeCell) {
                                        endTimeCell.textContent = new Date(updatedTask.end_time).toLocaleString();
                                    }
                                }

                                // 如果状态变为非运行状态，停止刷新并隐藏停止按钮
                                if (updatedTask.status !== 'training' && updatedTask.status !== 'running' &&
                                    updatedTask.status !== 'pending' && updatedTask.status !== 'downloading_model') {
                                    window.memoryManager.clearInterval(statusRefresh);
                                    stopBtn.style.display = 'none';
                                }
                            })
                            .catch(error => {
                                console.error('Error updating task status:', error);
                                // 在错误情况下停止刷新
                                window.memoryManager.clearInterval(statusRefresh);
                            });
                    }, 5000);

                    // 当模态框关闭时清除定时器
                    modal.addEventListener('remove', function() {
                        window.memoryManager.clearInterval(statusRefresh);
                    });

                    // 点击模态框外部关闭时清除定时器
                    window.onclick = (event) => {
                        if (event.target === modal) {
                            document.body.removeChild(modal);
                            window.memoryManager.clearInterval(statusRefresh);
                        }
                    };
                }
            })
            .catch(error => {
                console.error('Error fetching training details:', error);
                detailsContainer.innerHTML = `<div class="alert alert-danger">获取训练详情失败: ${error.message}</div>`;
            });
    }

    // 创建模态框函数
    createModal() {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'block';
        modal.style.position = 'fixed';
        modal.style.zIndex = '1000';
        modal.style.left = '0';
        modal.style.top = '0';
        modal.style.width = '100%';
        modal.style.height = '100%';
        modal.style.overflow = 'auto';
        modal.style.backgroundColor = 'rgba(0,0,0,0.4)';
        return modal;
    }

    // 显示模态框
    showModal(title, content, callback) {
        // 创建模态框
        const modal = this.createModal();

        // 创建模态框内容
        const modalContent = document.createElement('div');
        modalContent.className = 'modal-content';
        modalContent.style.backgroundColor = '#fefefe';
        modalContent.style.margin = '15% auto';
        modalContent.style.padding = '20px';
        modalContent.style.border = '1px solid #888';
        modalContent.style.width = '50%';
        modalContent.style.textAlign = 'center';

        // 添加标题
        const titleElement = document.createElement('h3');
        titleElement.textContent = title;
        modalContent.appendChild(titleElement);

        // 添加内容
        const contentElement = document.createElement('div');
        contentElement.innerHTML = content;
        modalContent.appendChild(contentElement);

        // 添加关闭按钮
        const closeButton = document.createElement('button');
        closeButton.textContent = '关闭';
        closeButton.className = 'btn btn-secondary mt-3';
        closeButton.onclick = function() {
            document.body.removeChild(modal);
        };
        modalContent.appendChild(closeButton);

        // 将模态框添加到文档中
        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        // 点击模态框外部关闭
        window.onclick = (event) => {
            if (event.target === modal) {
                document.body.removeChild(modal);
            }
        };

        // 执行回调函数
        if (typeof callback === 'function') {
            callback();
        }

        return modal;
    }

    // 显示Toast提示
    showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = 'toast show';
        toast.style.position = 'fixed';
        toast.style.top = '20px';
        toast.style.right = '20px';
        toast.style.padding = '10px 20px';
        toast.style.borderRadius = '4px';
        toast.style.zIndex = '9999';
        toast.style.color = 'white';

        // 根据类型设置背景色
        switch (type) {
            case 'success':
                toast.style.backgroundColor = '#28a745';
                break;
            case 'error':
                toast.style.backgroundColor = '#dc3545';
                break;
            case 'warning':
                toast.style.backgroundColor = '#ffc107';
                toast.style.color = '#212529';
                break;
            case 'info':
            default:
                toast.style.backgroundColor = '#007bff';
                break;
        }

        toast.innerHTML = message;
        document.body.appendChild(toast);

        // 如果设置了持续时间，则自动关闭
        if (duration > 0) {
            setTimeout(() => {
                this.hideToast(toast);
            }, duration);
        }

        return toast;
    }

    // 隐藏Toast提示
    hideToast(toast) {
        if (document.body.contains(toast)) {
            document.body.removeChild(toast);
        }
    }
}

// 创建全局实例
window.trainingManager = new TrainingManager();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TrainingManager;
}