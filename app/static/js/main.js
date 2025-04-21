// 全局变量
const API_URL = '/api';  // API路径
let currentPage = '';
let modal;

// 测试API端点
function testApiEndpoints() {
    console.log('Testing API endpoints...');

    // 测试数据集列表API
    fetch(`${API_URL}/datasets`)
        .then(response => {
            console.log('Datasets API status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Datasets API response:', data);
            if (data.length > 0) {
                console.log('First dataset structure:', JSON.stringify(data[0], null, 2));
                console.log('Has train_count:', 'train_count' in data[0]);
                console.log('Has val_count:', 'val_count' in data[0]);
                console.log('Has test_count:', 'test_count' in data[0]);
            }
        })
        .catch(error => {
            console.error('Datasets API error:', error);
        });

    // 测试本地目录API
    fetch(`${API_URL}/datasets/local-available`)
        .then(response => {
            console.log('Local directories API status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Local directories API response:', data);
        })
        .catch(error => {
            console.error('Local directories API error:', error);
        });
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化Bootstrap模态框
    modal = new bootstrap.Modal(document.getElementById('mainModal'));

    // 导航菜单点击事件
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = this.getAttribute('data-page');
            loadPage(page);
        });
    });

    // 测试API端点
    testApiEndpoints();

    // 默认加载数据集页面
    loadPage('datasets');
});

// 加载页面内容
function loadPage(page) {
    if (currentPage === page) return;
    currentPage = page;

    // 更新导航菜单激活状态
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('data-page') === page) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // 获取页面模板
    const template = document.getElementById(`${page}-template`);
    if (!template) return;

    // 加载页面内容
    const pageContent = document.getElementById('page-content');
    pageContent.innerHTML = template.innerHTML;

    // 根据页面类型加载数据和绑定事件
    switch (page) {
        case 'datasets':
            loadDatasets();
            bindDatasetEvents();
            break;
        case 'models':
            loadModels();
            bindModelEvents();
            break;
        case 'training':
            loadTrainingTasks();
            bindTrainingEvents();
            break;
        case 'detection':
            loadDetectionForm();
            bindDetectionEvents();
            break;
    }
}

// ==================== 数据集管理 ====================

// 显示数据集分割模态框
function showSplitDatasetModal(datasetId) {
    const modalTitle = document.querySelector('.modal-title');
    const modalBody = document.querySelector('.modal-body');
    const modalSubmit = document.getElementById('modalSubmit');

    modalTitle.textContent = '分割数据集';

    // 获取模板内容
    const template = document.getElementById('split-dataset-template');
    modalBody.innerHTML = template.innerHTML;

    // 显示模态框
    modal.show();

    // 绑定比例调整事件
    bindRatioSliders('split-train-ratio', 'split-val-ratio', 'split-test-ratio');

    // 绑定提交按钮事件
    modalSubmit.onclick = function() {
        submitSplitDataset(datasetId);
    };
}

// 提交分割数据集请求
function submitSplitDataset(datasetId) {
    const trainRatio = document.getElementById('split-train-ratio');
    const valRatio = document.getElementById('split-val-ratio');
    const testRatio = document.getElementById('split-test-ratio');
    const randomSeed = document.getElementById('split-random-seed');
    const splitMode = document.getElementById('split-mode');

    // 禁用提交按钮
    const modalSubmit = document.getElementById('modalSubmit');
    modalSubmit.disabled = true;
    modalSubmit.textContent = '处理中...';

    // 准备请求数据
    const data = {
        train_ratio: trainRatio ? parseFloat(trainRatio.value) : 0.7,
        val_ratio: valRatio ? parseFloat(valRatio.value) : 0.15,
        test_ratio: testRatio ? parseFloat(testRatio.value) : 0.15,
        random_seed: randomSeed ? parseInt(randomSeed.value) : 42,
        mode: splitMode ? splitMode.value : 'from_train'
    };

    // 发送请求
    fetch(`${API_URL}/datasets/${datasetId}/split`, {
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
                throw new Error(data.detail || '分割数据集失败');
            });
        }
    })
    .then(result => {
        // 关闭模态框
        modal.hide();
        // 重新加载数据集列表
        loadDatasets();
        // 显示成功消息
        alert(`数据集分割成功！\n训练集: ${result.result.train}张图像\n验证集: ${result.result.val}张图像\n测试集: ${result.result.test}张图像`);
    })
    .catch(error => {
        console.error('Error splitting dataset:', error);
        alert('分割数据集失败: ' + error.message);
        // 重置按钮状态
        modalSubmit.disabled = false;
        modalSubmit.textContent = '确定';
    });
}

// 加载数据集列表
function loadDatasets() {
    console.log('Loading datasets...');

    // 获取表格头并检查列数
    const tableHead = document.querySelector('#datasets-template table thead tr');
    if (tableHead) {
        const columnCount = tableHead.querySelectorAll('th').length;
        console.log('Dataset table has', columnCount, 'columns');
    }

    fetch(`${API_URL}/datasets`)
        .then(response => {
            console.log('Datasets response status:', response.status);
            return response.json();
        })
        .then(datasets => {
            console.log('Received', datasets.length, 'datasets');

            const tableBody = document.getElementById('datasets-table-body');
            if (!tableBody) {
                console.error('datasets-table-body element not found');
                return;
            }

            tableBody.innerHTML = '';

            if (datasets.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="9" class="text-center">暂无数据集</td></tr>';
                return;
            }

            // 检查第一个数据集的属性
            const firstDataset = datasets[0];
            console.log('First dataset properties:', Object.keys(firstDataset));
            console.log('train_count present:', 'train_count' in firstDataset);
            console.log('val_count present:', 'val_count' in firstDataset);
            console.log('test_count present:', 'test_count' in firstDataset);

            datasets.forEach(dataset => {
                // 计算训练集、验证集和测试集图像数量
                const trainCount = dataset.train_count !== undefined ? dataset.train_count : '-';
                const valCount = dataset.val_count !== undefined ? dataset.val_count : '-';
                const testCount = dataset.test_count !== undefined ? dataset.test_count : '-';

                console.log(`Dataset ${dataset.name} counts:`, { trainCount, valCount, testCount });

                const row = document.createElement('tr');

                // 检查是否为外部数据集和验证状态
                const isExternal = dataset.is_external === true;
                const isValidated = dataset.valid_structure === true;

                // 构建数据集名称显示
                let datasetNameHtml = dataset.name;

                // 添加验证状态标识
                if (isValidated) {
                    datasetNameHtml += ` <span class="badge bg-success ms-1">已验证</span>`;
                } else {
                    datasetNameHtml += ` <span class="badge bg-warning ms-1">未验证</span>`;
                }

                row.innerHTML = `
                    <td>${datasetNameHtml}</td>
                    <td>${dataset.description || '-'}</td>
                    <td>${dataset.classes.length}</td>
                    <td>${trainCount}</td>
                    <td>${valCount}</td>
                    <td>${testCount}</td>
                    <td><span class="badge ${getStatusBadgeClass(dataset.status)}">${getStatusText(dataset.status)}</span></td>
                    <td>${new Date(dataset.created_at).toLocaleString()}</td>
                    <td>
                        <div class="btn-group">
                            <button class="btn btn-sm btn-info split-dataset-btn" data-id="${dataset.id}">分割数据集</button>
                            <button class="btn btn-sm btn-danger delete-dataset" data-id="${dataset.id}">删除</button>
                        </div>
                    </td>
                `;
                tableBody.appendChild(row);
            });

            // 绑定分割按钮事件
            console.log('Binding split dataset buttons...');
            const splitButtons = document.querySelectorAll('.split-dataset-btn');
            console.log('Found', splitButtons.length, 'split dataset buttons');

            splitButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const datasetId = this.getAttribute('data-id');
                    console.log('Split dataset button clicked for dataset:', datasetId);
                    showSplitDatasetModal(datasetId);
                });
            });

            // 绑定删除按钮事件
            document.querySelectorAll('.delete-dataset').forEach(button => {
                button.addEventListener('click', function() {
                    const datasetId = this.getAttribute('data-id');
                    deleteDataset(datasetId);
                });
            });
        })
        .catch(error => {
            console.error('Error loading datasets:', error);
            alert('加载数据集失败');
        });
}

// 绑定数据集页面事件
function bindDatasetEvents() {
    console.log('Binding dataset events');
    const addButton = document.getElementById('add-dataset-btn');
    if (addButton) {
        console.log('Found add-dataset-btn, binding click event');
        addButton.addEventListener('click', showAddDatasetModal);
    } else {
        console.error('add-dataset-btn not found');
    }

    const importLocalButton = document.getElementById('import-local-dataset-btn');
    if (importLocalButton) {
        console.log('Found import-local-dataset-btn, binding click event');
        importLocalButton.addEventListener('click', function() {
            console.log('Import local dataset button clicked');
            showImportLocalDatasetModal();
        });
    } else {
        console.error('import-local-dataset-btn not found');
    }

    // 已删除注册外部数据集功能
}

// 显示添加数据集模态框
function showAddDatasetModal() {
    console.log('Showing add dataset modal');
    const modalTitle = document.querySelector('.modal-title');
    const modalBody = document.querySelector('.modal-body');
    const modalSubmit = document.getElementById('modalSubmit');

    if (!modalTitle || !modalBody || !modalSubmit) {
        console.error('Modal elements not found:', { modalTitle, modalBody, modalSubmit });
        return;
    }

    modalTitle.textContent = '添加数据集';

    // 获取模板内容
    const template = document.getElementById('add-dataset-template');
    if (!template) {
        console.error('add-dataset-template not found');
        return;
    }

    modalBody.innerHTML = template.innerHTML;

    // 确保按钮状态正确
    if (modalSubmit) {
        modalSubmit.disabled = false;
        modalSubmit.textContent = '确定';
    }

    // 显示模态框
    modal.show();

    // 使用setTimeout确保 DOM 已经更新
    setTimeout(() => {
        // 绑定分割选项显示/隐藏
        const splitCheckbox = document.getElementById('split-dataset-enabled');
        const splitOptions = document.getElementById('split-options');

        console.log('Split elements:', { splitCheckbox, splitOptions });

        if (splitCheckbox && splitOptions) {
            // 直接设置显示属性
            splitOptions.style.display = 'none';

            // 使用直接的事件处理方式
            splitCheckbox.onchange = function() {
                console.log('Split checkbox changed:', this.checked);
                splitOptions.style.display = this.checked ? 'block' : 'none';
            };

            // 绑定比例调整事件
            bindRatioSliders('train-ratio', 'val-ratio', 'test-ratio');
        } else {
            console.error('Split checkbox or options not found after timeout');
        }

        // 绑定提交按钮事件
        modalSubmit.onclick = submitAddDataset;
    }, 100); // 短暂延迟确保 DOM 已加载
}

// 提交添加数据集表单
async function submitAddDataset() {
    const form = document.getElementById('add-dataset-form');
    const nameInput = document.getElementById('dataset-name');
    const descriptionInput = document.getElementById('dataset-description');
    const fileInput = document.getElementById('dataset-file');
    const splitEnabled = document.getElementById('split-dataset-enabled');
    const trainRatio = document.getElementById('train-ratio');
    const valRatio = document.getElementById('val-ratio');
    const testRatio = document.getElementById('test-ratio');
    const randomSeed = document.getElementById('random-seed');
    const progressContainer = document.querySelector('.progress-container');
    const progressBar = document.querySelector('.progress');
    const progressBarInner = document.querySelector('.progress-bar');
    const progressStatus = document.querySelector('.progress-status');
    const progressDetails = document.querySelector('.progress-details');
    const cancelButton = document.querySelector('.cancel-upload');

    if (!nameInput.value || !fileInput.files[0]) {
        alert('请填写必填字段');
        return;
    }

    // 显示进度容器
    progressContainer.style.display = 'block';
    progressStatus.textContent = '初始化上传...';
    progressDetails.innerHTML = '';

    try {
        // 第1步：初始化上传，获取文件ID
        const initFormData = new FormData();
        initFormData.append('name', nameInput.value);
        initFormData.append('file', fileInput.files[0]);

        const initResponse = await fetch(`${API_URL}/datasets/upload-init`, {
            method: 'POST',
            body: initFormData
        });

        if (!initResponse.ok) {
            throw new Error('初始化上传失败');
        }

        const initData = await initResponse.json();
        const fileId = initData.file_id;

        // 第2步：上传文件
        progressStatus.textContent = '上传中...';

        // 创建FormData对象
        const formData = new FormData();
        formData.append('name', nameInput.value);
        formData.append('description', descriptionInput.value || '');
        formData.append('file', fileInput.files[0]);
        formData.append('file_id', fileId);

        // 添加分割选项
        if (splitEnabled && splitEnabled.checked) {
            formData.append('split_dataset_enabled', 'true');
            formData.append('train_ratio', trainRatio ? trainRatio.value : '0.7');
            formData.append('val_ratio', valRatio ? valRatio.value : '0.15');
            formData.append('test_ratio', testRatio ? testRatio.value : '0.15');
            formData.append('random_seed', randomSeed ? randomSeed.value : '42');
        } else {
            formData.append('split_dataset_enabled', 'false');
        }

        // 创建XMLHttpRequest对象以支持上传进度
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_URL}/datasets`, true);

        // 上传进度事件
        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progressBarInner.style.width = percentComplete + '%';
                progressBarInner.textContent = Math.round(percentComplete) + '%';

                // 计算上传速度和剩余时间
                const uploadedMB = (e.loaded / (1024 * 1024)).toFixed(2);
                const totalMB = (e.total / (1024 * 1024)).toFixed(2);
                progressDetails.innerHTML = `已上传: ${uploadedMB} MB / ${totalMB} MB`;
            }
        };

        // 第3步：轮询上传状态
        let statusCheckInterval;

        // 上传完成事件
        xhr.onload = function() {
            if (xhr.status === 200 || xhr.status === 201) {
                // 上传成功，开始轮询处理状态
                statusCheckInterval = setInterval(async () => {
                    try {
                        const statusResponse = await fetch(`${API_URL}/datasets/upload-status/${fileId}`);
                        if (!statusResponse.ok) {
                            clearInterval(statusCheckInterval);
                            throw new Error('获取上传状态失败');
                        }

                        const statusData = await statusResponse.json();

                        // 更新进度条和状态信息
                        progressBarInner.style.width = statusData.progress + '%';
                        progressBarInner.textContent = statusData.progress + '%';
                        progressStatus.textContent = statusData.message;

                        // 对于大文件，显示更详细的进度信息
                        if (statusData.total_size > 100 * 1024 * 1024) { // 大于100MB的文件
                            const totalSizeGB = (statusData.total_size / (1024 * 1024 * 1024)).toFixed(2);
                            const uploadedSizeGB = (statusData.uploaded_size / (1024 * 1024 * 1024)).toFixed(2);
                            if (totalSizeGB >= 1) {
                                // 如果文件大小超过1GB，显示GB单位
                                progressBarInner.textContent = `${statusData.progress}% (${uploadedSizeGB}/${totalSizeGB} GB)`;
                            }
                        }

                        // 根据状态更新详细信息
                        if (statusData.status === 'uploading') {
                            const uploadSpeed = (statusData.upload_speed / (1024 * 1024)).toFixed(2);
                            const remainingTime = statusData.estimated_time > 0 ?
                                formatTime(statusData.estimated_time) : '计算中...';

                            progressDetails.innerHTML = `
                                已上传: ${(statusData.uploaded_size / (1024 * 1024)).toFixed(2)} MB /
                                ${(statusData.total_size / (1024 * 1024)).toFixed(2)} MB<br>
                                速度: ${uploadSpeed} MB/s<br>
                                预计剩余时间: ${remainingTime}
                            `;
                        } else if (statusData.status === 'extracting') {
                            // 对于大文件，显示更详细的解压信息
                            const totalSizeMB = (statusData.total_size / (1024 * 1024)).toFixed(2);
                            const elapsedTime = formatTime(statusData.elapsed_time);
                            progressDetails.innerHTML = `
                                正在解压文件 (${totalSizeMB} MB)，请耐心等待...<br>
                                已用时间: ${elapsedTime}<br>
                                <small class="text-muted">大文件解压可能需要几分钟时间，请不要关闭浏览器</small>
                            `;
                        } else if (statusData.status === 'validating') {
                            const elapsedTime = formatTime(statusData.elapsed_time);
                            progressDetails.innerHTML = `
                                正在验证数据集结构，请耐心等待...<br>
                                已用时间: ${elapsedTime}<br>
                                <small class="text-muted">正在处理文件名和生成配置文件</small>
                            `;
                        } else if (statusData.status === 'completed') {
                            clearInterval(statusCheckInterval);
                            modal.hide();
                            loadDatasets();
                        } else if (statusData.status === 'failed') {
                            clearInterval(statusCheckInterval);
                            progressStatus.textContent = '上传失败';
                            progressDetails.innerHTML = `错误: ${statusData.error || '未知错误'}`;
                            alert('上传数据集失败: ' + (statusData.error || '未知错误'));
                        }
                    } catch (error) {
                        console.error('Error checking upload status:', error);
                    }
                }, 1000); // 每秒检查一次状态
            } else {
                progressStatus.textContent = '上传失败';
                alert('上传数据集失败: ' + xhr.statusText);
            }
        };

        // 上传错误事件
        xhr.onerror = function() {
            progressStatus.textContent = '上传失败';
            progressDetails.innerHTML = '网络错误，请检查您的网络连接';
            alert('上传数据集失败: 网络错误');
        };

        // 取消上传按钮
        if (cancelButton) {
            cancelButton.style.display = 'inline-block';
            cancelButton.onclick = function() {
                xhr.abort();
                if (statusCheckInterval) {
                    clearInterval(statusCheckInterval);
                }
                progressStatus.textContent = '上传已取消';
                progressDetails.innerHTML = '';
                cancelButton.style.display = 'none';
            };
        }

        // 发送请求
        xhr.send(formData);
    } catch (error) {
        console.error('Error uploading dataset:', error);
        progressStatus.textContent = '上传失败';
        progressDetails.innerHTML = `错误: ${error.message}`;
        alert('上传数据集失败: ' + error.message);
    }
}

// 格式化时间（秒）为可读格式
function formatTime(seconds) {
    if (seconds < 60) {
        return `${Math.round(seconds)}秒`;
    } else if (seconds < 3600) {
        return `${Math.floor(seconds / 60)}分${Math.round(seconds % 60)}秒`;
    } else {
        return `${Math.floor(seconds / 3600)}小时${Math.floor((seconds % 3600) / 60)}分`;
    }
}

// 绑定比例滑块事件，确保总和为100%
function bindRatioSliders(trainId, valId, testId) {
    const trainSlider = document.getElementById(trainId);
    const valSlider = document.getElementById(valId);
    const testSlider = document.getElementById(testId);

    const trainValue = document.getElementById(`${trainId}-value`);
    const valValue = document.getElementById(`${valId}-value`);
    const testValue = document.getElementById(`${testId}-value`);

    if (!trainSlider || !valSlider || !testSlider) return;

    // 更新显示值的函数
    function updateValues() {
        trainValue.textContent = `${Math.round(trainSlider.value * 100)}%`;
        valValue.textContent = `${Math.round(valSlider.value * 100)}%`;
        testValue.textContent = `${Math.round(testSlider.value * 100)}%`;
    }

    // 调整比例以确保总和为1
    function adjustRatios(changedSlider) {
        const train = parseFloat(trainSlider.value);
        const val = parseFloat(valSlider.value);
        const test = parseFloat(testSlider.value);
        const total = train + val + test;

        // 如果总和不为1，调整其他滑块
        if (Math.abs(total - 1.0) > 0.001) {
            if (changedSlider === trainSlider) {
                // 如果调整了训练集比例，按比例调整验证集和测试集
                const remaining = 1.0 - train;
                const ratio = val / (val + test);
                valSlider.value = (remaining * ratio).toFixed(2);
                testSlider.value = (remaining * (1 - ratio)).toFixed(2);
            } else if (changedSlider === valSlider) {
                // 如果调整了验证集比例，保持训练集不变，调整测试集
                testSlider.value = (1.0 - train - val).toFixed(2);
            } else if (changedSlider === testSlider) {
                // 如果调整了测试集比例，保持训练集不变，调整验证集
                valSlider.value = (1.0 - train - test).toFixed(2);
            }
        }

        updateValues();
    }

    // 绑定滑块事件
    trainSlider.addEventListener('input', function() {
        adjustRatios(trainSlider);
    });

    valSlider.addEventListener('input', function() {
        adjustRatios(valSlider);
    });

    testSlider.addEventListener('input', function() {
        adjustRatios(testSlider);
    });

    // 初始化显示值
    updateValues();
}

// 设置本地数据集模态框事件
function setupLocalDatasetModalEvents() {
    console.log('Setting up local dataset modal events');

    // 设置浏览目录按钮
    setupBrowseDatasetDirButton();

    // 设置验证按钮
    setupValidateDatasetDirButton();

    // 检查是否有选中的目录
    const selectedDirJson = localStorage.getItem('selectedDirectory');
    if (selectedDirJson) {
        try {
            const selectedDir = JSON.parse(selectedDirJson);
            console.log('Found selected directory in localStorage:', selectedDir.name);

            // 设置输入框值
            const dirPathInput = document.getElementById('local-dataset-dir-path');
            if (dirPathInput) {
                dirPathInput.value = selectedDir.name;
                console.log('Set directory path input value from localStorage:', selectedDir.name);

                // 显示数据集信息
                showLocalDatasetInfo(selectedDir.info);
            }
        } catch (error) {
            console.error('Error parsing selected directory from localStorage:', error);
        }
    }

    // 绑定分割选项显示/隐藏
    const splitCheckbox = document.getElementById('local-split-dataset-enabled');
    const splitOptions = document.getElementById('local-split-options');

    if (splitCheckbox && splitOptions) {
        console.log('Found local split elements, binding events');
        // 直接设置显示属性
        splitOptions.style.display = splitCheckbox.checked ? 'block' : 'none';

        // 使用直接的事件处理方式
        splitCheckbox.onchange = function() {
            console.log('Local split checkbox changed:', this.checked);
            splitOptions.style.display = this.checked ? 'block' : 'none';
        };

        // 绑定比例调整事件
        bindRatioSliders('local-train-ratio', 'local-val-ratio', 'local-test-ratio');
    } else {
        console.error('Local split elements not found:', { splitCheckbox, splitOptions });
    }

    // 绑定提交按钮事件
    const modalSubmit = document.getElementById('modalSubmit');
    if (modalSubmit) {
        modalSubmit.onclick = submitImportLocalDataset;
    }
}

// 显示从本地目录导入数据集模态框
function showImportLocalDatasetModal() {
    console.log('showImportLocalDatasetModal called');

    // 获取模态框元素
    const modalElement = document.getElementById('mainModal');
    if (!modalElement) {
        console.error('Modal element not found');
        return;
    }

    // 使用Bootstrap API直接显示模态框
    const bsModal = bootstrap.Modal.getInstance(modalElement) || new bootstrap.Modal(modalElement);

    // 设置模态框内容
    const modalTitle = modalElement.querySelector('.modal-title');
    const modalBody = modalElement.querySelector('.modal-body');
    const modalSubmit = document.getElementById('modalSubmit');

    if (!modalTitle || !modalBody || !modalSubmit) {
        console.error('Modal elements not found:', { modalTitle, modalBody, modalSubmit });
        return;
    }

    modalTitle.textContent = '服务器数据集';

    // 获取模板内容
    const template = document.getElementById('import-local-dataset-template');
    if (!template) {
        console.error('import-local-dataset-template not found');
        return;
    }

    console.log('Setting modal body content');
    modalBody.innerHTML = template.innerHTML;

    // 确保按钮状态正确
    if (modalSubmit) {
        modalSubmit.disabled = false;
        modalSubmit.textContent = '确定';
    }

    // 显示模态框
    console.log('Showing modal');
    bsModal.show();

    // 使用setTimeout确保 DOM 已经更新
    setTimeout(() => {
        // 设置模态框事件
        setupLocalDatasetModalEvents();
    }, 100); // 短暂延迟确保 DOM 已加载

    // 注意：我们已经在setTimeout中处理了这些事件绑定
}

// 处理浏览数据集目录按钮点击
function setupBrowseDatasetDirButton() {
    console.log('Setting up browse dataset directory button');
    const browseButton = document.getElementById('browse-dataset-dir-btn');
    const dirPathInput = document.getElementById('local-dataset-dir-path');

    if (!browseButton || !dirPathInput) {
        console.error('Browse button or directory path input not found:', { browseButton, dirPathInput });
        return;
    }

    browseButton.onclick = function() {
        console.log('Browse button clicked');

        // 模拟选择目录
        // 在真实应用中，这里应该调用文件选择器API
        // 由于浏览器安全限制，我们这里使用模拟对话框

        // 创建一个模拟的目录选择对话框
        const modalTitle = document.querySelector('.modal-title');
        const modalBody = document.querySelector('.modal-body');
        const modalSubmit = document.getElementById('modalSubmit');
        const currentModal = bootstrap.Modal.getInstance(document.getElementById('mainModal'));

        // 保存当前模态框内容
        const savedTitle = modalTitle.textContent;
        const savedBody = modalBody.innerHTML;
        const savedSubmitText = modalSubmit.textContent;
        const savedSubmitAction = modalSubmit.onclick;

        // 设置目录选择对话框
        modalTitle.textContent = '选择服务器数据集文件夹';
        modalBody.innerHTML = `
            <div class="alert alert-info">
                请选择 datasets_import 目录下的数据集文件夹。文件夹应包含以下结构：
                <ul>
                    <li>train/images/ - 训练图像目录</li>
                    <li>val/images/ - 验证图像目录</li>
                    <li>test/images/ - 测试图像目录（可选）</li>
                    <li>classes.txt - 类别列表文件</li>
                </ul>
                <p>如果缺少这些文件或目录，系统将尝试自动创建，但可能会影响训练效果。</p>
            </div>
            <div class="list-group" id="directory-list">
                <div class="d-flex justify-content-center">
                    <div class="spinner-border" role="status">
                        <span class="visually-hidden">加载中...</span>
                    </div>
                </div>
            </div>
        `;
        modalSubmit.textContent = '确定';

        // 加载目录列表
        fetch(`${API_URL}/datasets/local-available`)
            .then(response => {
                console.log('API response received:', response.status);
                return response.json();
            })
            .then(directories => {
                console.log('Directories received:', directories);
                const directoryList = document.getElementById('directory-list');

                if (!directoryList) {
                    console.error('Directory list element not found');
                    return;
                }

                // 清空加载中状态
                directoryList.innerHTML = '';

                if (directories.length === 0) {
                    directoryList.innerHTML = `
                        <div class="alert alert-warning">
                            没有找到可用的数据集目录。请将数据集放入 datasets_import 目录。
                        </div>
                    `;
                    return;
                }

                // 添加目录选项
                directories.forEach(dir => {
                    const item = document.createElement('button');
                    item.type = 'button';
                    item.className = 'list-group-item list-group-item-action';
                    item.dataset.value = dir.name;
                    item.dataset.info = JSON.stringify(dir);
                    item.innerHTML = `
                        <div class="d-flex w-100 justify-content-between">
                            <h5 class="mb-1">${dir.name}</h5>
                            <small>图像: ${dir.total_images}</small>
                        </div>
                        <p class="mb-1">类别: ${dir.classes.join(', ')}</p>
                        <small>训练图像: ${dir.train_images}, 验证图像: ${dir.val_images}</small>
                    `;

                    // 添加点击事件
                    item.onclick = function() {
                        // 选中目录
                        const dirName = this.dataset.value;
                        const dirInfo = JSON.parse(this.dataset.info);

                        console.log('Selected directory:', dirName);

                        // 保存选中的目录信息
                        const selectedDirInfo = {
                            name: dirName,
                            info: dirInfo
                        };

                        // 将选中的目录信息存储在 localStorage 中
                        localStorage.setItem('selectedDirectory', JSON.stringify(selectedDirInfo));

                        // 恢复原模态框
                        modalTitle.textContent = savedTitle;
                        modalBody.innerHTML = savedBody;
                        modalSubmit.textContent = savedSubmitText;
                        modalSubmit.onclick = savedSubmitAction;

                        // 重新绑定事件
                        setupLocalDatasetModalEvents();

                        // 在模态框恢复后，设置输入框值并显示数据集信息
                        setTimeout(() => {
                            const dirPathInput = document.getElementById('local-dataset-dir-path');
                            if (dirPathInput) {
                                dirPathInput.value = dirName;
                                console.log('Set directory path input value:', dirName);
                            } else {
                                console.error('local-dataset-dir-path input not found after modal restore');
                            }

                            // 显示数据集信息
                            showLocalDatasetInfo(dirInfo);
                        }, 100);
                    };

                    directoryList.appendChild(item);
                });
            })
            .catch(error => {
                console.error('Error loading local dataset directories:', error);
                const directoryList = document.getElementById('directory-list');
                if (directoryList) {
                    directoryList.innerHTML = `
                        <div class="alert alert-danger">
                            加载目录列表失败: ${error.message}
                        </div>
                    `;
                }
            });

        // 取消按钮事件
        modalSubmit.onclick = function() {
            // 恢复原模态框
            modalTitle.textContent = savedTitle;
            modalBody.innerHTML = savedBody;
            modalSubmit.textContent = savedSubmitText;
            modalSubmit.onclick = savedSubmitAction;

            // 重新绑定事件
            setupLocalDatasetModalEvents();
        };
    };

}

// 显示本地数据集信息
function showLocalDatasetInfo(directoryInfo) {
    console.log('Showing local dataset info:', directoryInfo);
    const infoContainer = document.getElementById('local-dataset-info');
    if (!infoContainer) {
        console.error('local-dataset-info container not found');
        return;
    }

    try {
        // 显示加载中状态
        infoContainer.style.display = 'block';

        // 如果传入的是字符串，尝试从 API 获取信息
        if (typeof directoryInfo === 'string') {
            infoContainer.innerHTML = `
                <div class="d-flex align-items-center p-3">
                    <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                        <span class="visually-hidden">加载中...</span>
                    </div>
                    <span>正在加载数据集信息...</span>
                </div>
            `;

            // 从 API 获取目录信息
            console.log(`Fetching directory info for: ${directoryInfo}`);
            fetch(`${API_URL}/datasets/directory-info?name=${encodeURIComponent(directoryInfo)}`)
                .then(response => {
                    console.log(`Received response with status: ${response.status}`);
                    if (!response.ok) {
                        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(info => {
                    console.log('Received directory info:', info);
                    updateDatasetInfoDisplay(info);

                    // 如果数据集名称输入框为空，自动填充目录名称
                    const nameInput = document.getElementById('local-dataset-name');
                    if (nameInput && !nameInput.value && info.name) {
                        nameInput.value = info.name;
                    }
                })
                .catch(error => {
                    console.error('Error fetching directory info:', error);
                    infoContainer.innerHTML = `
                        <div class="alert alert-warning">
                            <i class="bi bi-exclamation-triangle-fill me-2"></i>加载数据集信息失败
                            <div class="mt-2">
                                <strong>注意:</strong> 您仍然可以使用此数据集，但可能无法显示详细信息。
                            </div>
                        </div>
                    `;
                });
        } else {
            // 直接使用传入的对象
            console.log('Using provided directory info object');
            updateDatasetInfoDisplay(directoryInfo);

            // 如果数据集名称输入框为空，自动填充目录名称
            const nameInput = document.getElementById('local-dataset-name');
            if (nameInput && !nameInput.value && directoryInfo.name) {
                nameInput.value = directoryInfo.name;
            }
        }
    } catch (error) {
        console.error('Error processing dataset info:', error);
        infoContainer.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-circle-fill me-2"></i>处理数据集信息时出错
                <div class="mt-2">
                    <pre>${error.message}</pre>
                </div>
            </div>
        `;
    }
}

// 更新数据集信息显示
function updateDatasetInfoDisplay(datasetInfo) {
    console.log('Updating dataset info display:', datasetInfo);

    // 获取信息容器
    const infoContainer = document.getElementById('local-dataset-info');
    if (!infoContainer) {
        console.error('local-dataset-info container not found');
        return;
    }

    // 确保信息容器可见
    infoContainer.style.display = 'block';

    // 创建数据集信息卡片
    let html = `
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">数据集信息</h5>
                <div class="mb-2">
                    <strong>训练图像：</strong> <span>${datasetInfo.train_images || '0'}</span>
                </div>
                <div class="mb-2">
                    <strong>验证图像：</strong> <span>${datasetInfo.val_images || '0'}</span>
                </div>
                <div class="mb-2">
                    <strong>测试图像：</strong> <span>${datasetInfo.test_images || '0'}</span>
                </div>
                <div class="mb-2">
                    <strong>类别数量：</strong> <span>${datasetInfo.classes_count || datasetInfo.classes?.length || '0'}</span>
                </div>
                <div class="mb-2">
                    <strong>类别列表：</strong> <span>${datasetInfo.classes?.join(', ') || '-'}</span>
                </div>
                <div class="mb-2">
                    <strong>目录结构：</strong>
                    ${datasetInfo.valid_structure ?
                        '<span class="badge bg-success">有效</span>' :
                        '<span class="badge bg-danger">无效</span>'}
                </div>
            </div>
        </div>
    `;

    // 更新信息容器内容
    infoContainer.innerHTML = html;
}

// 隐藏本地数据集信息
function hideLocalDatasetInfo() {
    const infoContainer = document.getElementById('local-dataset-info');
    if (infoContainer) {
        infoContainer.style.display = 'none';
    }
}

// 设置验证数据集目录按钮
function setupValidateDatasetDirButton() {
    console.log('Setting up validate dataset directory button');
    const validateButton = document.getElementById('validate-dataset-dir-btn');
    const dirPathInput = document.getElementById('local-dataset-dir-path');

    if (!validateButton || !dirPathInput) {
        console.error('Validate button or directory path input not found:', { validateButton, dirPathInput });
        return;
    }

    validateButton.onclick = function() {
        console.log('Validate button clicked');
        const dirPath = dirPathInput.value.trim();

        if (!dirPath) {
            alert('请先选择数据集文件夹');
            return;
        }

        // 显示验证中状态
        const infoContainer = document.getElementById('local-dataset-info');
        if (infoContainer) {
            // 显示加载中状态
            infoContainer.style.display = 'block';
            infoContainer.innerHTML = `
                <div class="d-flex align-items-center p-3">
                    <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                        <span class="visually-hidden">验证中...</span>
                    </div>
                    <span>正在验证目录...</span>
                </div>
            `;

            // 发送验证请求
            console.log(`Sending validation request for directory: ${dirPath}`);
            fetch(`${API_URL}/datasets/directory-info?name=${encodeURIComponent(dirPath)}`)
                .then(response => {
                    console.log(`Received response with status: ${response.status}`);
                    if (!response.ok) {
                        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(info => {
                    console.log('Received directory info:', info);
                    // 更新数据集信息显示
                    updateDatasetInfoDisplay(info);
                })
                .catch(error => {
                    console.error('Error validating directory:', error);
                    infoContainer.innerHTML = `
                        <div class="alert alert-warning">
                            <i class="bi bi-exclamation-triangle-fill me-2"></i>目录验证失败，但仍可使用
                            <div class="mt-2">
                                <strong>注意:</strong> 验证是可选的，不验证也可以导入数据集。
                            </div>
                        </div>
                    `;
                });
        } else {
            console.error('local-dataset-info container not found');
            alert('验证失败：无法显示验证结果');
        }
    };
}

// 提交导入本地数据集表单
function submitImportLocalDataset() {
    console.log('Submitting import local dataset form');
    const nameInput = document.getElementById('local-dataset-name');
    const descriptionInput = document.getElementById('local-dataset-description');
    const dirPathInput = document.getElementById('local-dataset-dir-path');
    const splitEnabled = document.getElementById('local-split-dataset-enabled');
    const trainRatio = document.getElementById('local-train-ratio');
    const valRatio = document.getElementById('local-val-ratio');
    const testRatio = document.getElementById('local-test-ratio');
    const randomSeed = document.getElementById('local-random-seed');

    if (!nameInput || !descriptionInput || !dirPathInput) {
        alert('表单字段缺失');
        return;
    }

    const name = nameInput.value.trim();
    const description = descriptionInput.value.trim();
    const directoryName = dirPathInput.value.trim();

    if (!name) {
        alert('请输入数据集名称');
        nameInput.focus();
        return;
    }

    if (!directoryName) {
        alert('请选择数据集目录');
        return;
    }

    // 禁用提交按钮
    const modalSubmit = document.getElementById('modalSubmit');
    if (modalSubmit) {
        modalSubmit.disabled = true;
        modalSubmit.textContent = '导入中...';
    }

    // 准备请求数据
    const data = {
        name: name,
        description: description,
        directory_name: directoryName
    };

    // 添加分割选项
    if (splitEnabled && splitEnabled.checked) {
        data.split_dataset_enabled = true;
        data.train_ratio = trainRatio ? parseFloat(trainRatio.value) : 0.7;
        data.val_ratio = valRatio ? parseFloat(valRatio.value) : 0.15;
        data.test_ratio = testRatio ? parseFloat(testRatio.value) : 0.15;
        data.random_seed = randomSeed ? parseInt(randomSeed.value) : 42;

        console.log('Split parameters:', {
            train_ratio: data.train_ratio,
            val_ratio: data.val_ratio,
            test_ratio: data.test_ratio,
            random_seed: data.random_seed
        });
    } else {
        data.split_dataset_enabled = false;
    }

    console.log('Sending import request with data:', data);

    // 发送请求
    fetch(`${API_URL}/datasets/import-local`, {
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
                throw new Error(data.detail || '导入数据集失败');
            });
        }
    })
    .then(result => {
        console.log('Import successful:', result);
        // 清除localStorage中的选择
        localStorage.removeItem('selectedDirectory');
        // 关闭模态框
        const mainModal = bootstrap.Modal.getInstance(document.getElementById('mainModal'));
        if (mainModal) {
            mainModal.hide();
        }
        // 重新加载数据集列表
        loadDatasets();
        // 显示成功消息
        alert('数据集导入成功');
    })
    .catch(error => {
        console.error('Error importing local dataset:', error);
        alert('导入数据集失败: ' + error.message);
        // 重置按钮状态
        if (modalSubmit) {
            modalSubmit.disabled = false;
            modalSubmit.textContent = '确定';
        }
    });
}

// 删除数据集
function deleteDataset(datasetId) {
    // 创建确认对话框
    const modal = createModal();

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
    title.textContent = '确认删除数据集';
    modalContent.appendChild(title);

    // 添加确认信息
    const confirmText = document.createElement('p');
    confirmText.textContent = '您确定要删除这个数据集吗？如果有训练任务正在使用该数据集，则无法删除。';
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
    confirmButton.onclick = function() {
        // 显示加载中状态
        confirmButton.disabled = true;
        confirmButton.textContent = '删除中...';

        // 发送删除请求
        fetch(`${API_URL}/datasets/${datasetId}`, {
            method: 'DELETE'
        })
        .then(response => {
            if (response.ok) {
                // 关闭模态框
                document.body.removeChild(modal);
                // 重新加载数据集列表
                loadDatasets();
                // 显示成功消息
                alert('数据集删除成功');
            } else {
                // 如果响应不成功，尝试解析错误消息
                return response.json().then(data => {
                    throw new Error(data.detail || '删除数据集失败');
                });
            }
        })
        .catch(error => {
            console.error('Error deleting dataset:', error);
            // 显示错误消息
            alert(`删除数据集失败: ${error.message}`);
            // 重置按钮状态
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

// ==================== 模型管理 ====================

// 加载模型列表
function loadModels() {
    fetch(`${API_URL}/models`)
        .then(response => response.json())
        .then(models => {
            const tableBody = document.getElementById('models-table-body');
            tableBody.innerHTML = '';

            if (models.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="7" class="text-center">暂无模型</td></tr>';
                return;
            }

            models.forEach(model => {
                const row = document.createElement('tr');
                // 直接使用模型名称
                const displayName = model.name || `${model.type} (自定义模型)`;

                row.innerHTML = `
                    <td>${displayName}</td>
                    <td>${model.description || '-'}</td>
                    <td>${model.type}</td>
                    <td>${getTaskText(model.task)}</td>
                    <td>${getSourceText(model.source)}</td>
                    <td>${new Date(model.created_at).toLocaleString()}</td>
                    <td>
                        <button class="btn btn-sm btn-danger delete-model" data-id="${model.id}">删除</button>
                    </td>
                `;
                tableBody.appendChild(row);
            });

            // 绑定删除按钮事件
            document.querySelectorAll('.delete-model').forEach(button => {
                button.addEventListener('click', function() {
                    const modelId = this.getAttribute('data-id');
                    deleteModel(modelId);
                });
            });
        })
        .catch(error => {
            console.error('Error loading models:', error);
            alert('加载模型失败');
        });
}

// 绑定模型页面事件
function bindModelEvents() {
    const addButton = document.getElementById('add-model-btn');
    if (addButton) {
        addButton.addEventListener('click', showAddModelModal);
    }
}

// 显示添加模型模态框
function showAddModelModal() {
    const modalTitle = document.querySelector('.modal-title');
    const modalBody = document.querySelector('.modal-body');
    const modalSubmit = document.getElementById('modalSubmit');

    modalTitle.textContent = '添加模型';

    // 获取模板内容
    const template = document.getElementById('add-model-template');
    modalBody.innerHTML = template.innerHTML;

    // 显示模态框
    modal.show();

    // 确保按钮状态正确
    if (modalSubmit) {
        modalSubmit.disabled = false;
        modalSubmit.textContent = '确定';
    }

    // 绑定提交按钮事件
    modalSubmit.onclick = submitAddModel;
}

// 提交添加模型表单
function submitAddModel() {
    const form = document.getElementById('add-model-form');
    const nameInput = document.getElementById('model-name');
    const descriptionInput = document.getElementById('model-description');
    const typeInput = document.getElementById('model-type');
    const taskInput = document.getElementById('model-task');
    const fileInput = document.getElementById('model-file');
    const progressBar = document.querySelector('.progress');
    const progressBarInner = document.querySelector('.progress-bar');
    const submitButton = document.getElementById('modalSubmit');

    // 检查必填字段
    if (!typeInput.value || !taskInput.value || !fileInput.files[0]) {
        alert('请填写必填字段');
        return;
    }

    // 如果模型名称为空，使用默认名称
    if (!nameInput.value || nameInput.value.trim() === "") {
        nameInput.value = `${typeInput.value} (自定义模型)`;
        console.log(`使用默认模型名称: ${nameInput.value}`);
    }

    // 显示进度条
    progressBar.style.display = 'block';

    // 禁用提交按钮并更改文本
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = '导入中...';
    }

    // 创建FormData对象
    const formData = new FormData();
    formData.append('name', nameInput.value);
    formData.append('description', descriptionInput.value || '');
    formData.append('type', typeInput.value);
    formData.append('task', taskInput.value);
    formData.append('file', fileInput.files[0]);

    // 创建XMLHttpRequest对象以支持上传进度
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_URL}/models`, true);

    // 上传进度事件
    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            progressBarInner.style.width = percentComplete + '%';
            progressBarInner.textContent = Math.round(percentComplete) + '%';
        }
    };

    // 上传完成事件
    xhr.onload = function() {
        if (xhr.status === 200 || xhr.status === 201) {
            // 重置按钮状态
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = '确定';
            }
            modal.hide();
            loadModels();
        } else {
            // 重置按钮状态
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = '确定';
            }
            alert('上传模型失败: ' + xhr.statusText);
        }
    };

    // 上传错误事件
    xhr.onerror = function() {
        // 重置按钮状态
        if (submitButton) {
            submitButton.disabled = false;
            submitButton.textContent = '确定';
        }
        alert('上传模型失败');
    };

    // 设置超时处理
    setTimeout(function() {
        if (submitButton && submitButton.disabled) {
            submitButton.disabled = false;
            submitButton.textContent = '确定';
            alert('上传操作超时，请刷新页面后重试');
        }
    }, 60000); // 60秒超时

    // 发送请求
    xhr.send(formData);
}

// 删除模型
function deleteModel(modelId) {
    if (!confirm('确定要删除这个模型吗？此操作不可恢复。')) {
        return;
    }

    fetch(`${API_URL}/models/${modelId}`, {
        method: 'DELETE'
    })
        .then(response => {
            if (response.ok) {
                loadModels();
                return;
            }

            // 处理错误响应
            return response.json().then(data => {
                throw new Error(data.detail || '删除模型失败');
            });
        })
        .catch(error => {
            console.error('Error deleting model:', error);

            // 显示更友好的错误提示
            if (error.message.includes('being used by training tasks')) {
                alert('无法删除模型：该模型正在被训练任务使用');
            } else if (error.message.includes('output of training tasks')) {
                alert('无法删除模型：该模型是训练任务的输出模型');
            } else if (error.message.includes('being used by detection tasks')) {
                alert('无法删除模型：该模型正在被检测任务使用');
            } else {
                alert('删除模型失败: ' + error.message);
            }
        });
}

// ==================== 训练管理 ====================

// 加载训练任务列表
function loadTrainingTasks() {
    fetch(`${API_URL}/training`)
        .then(response => response.json())
        .then(tasks => {
            const tableBody = document.getElementById('training-table-body');
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
                    <td><span class="badge ${getStatusBadgeClass(task.status)}">${getStatusText(task.status)}</span></td>
                    <td>${task.start_time ? new Date(task.start_time).toLocaleString() : '-'}</td>
                    <td>${task.end_time ? new Date(task.end_time).toLocaleString() : '-'}</td>
                    <td>
                        ${task.status === 'pending' ? `<button class="btn btn-sm btn-success start-training" data-id="${task.id}">开始训练</button>` : ''}
                        ${task.status === 'running' || task.status === 'training' || task.status === 'downloading_model' || task.status === 'pending' ? `<button class="btn btn-sm btn-warning stop-training" data-id="${task.id}">停止训练</button>` : ''}
                        ${(task.status === 'cancelled' || task.status === 'completed' || task.status === 'failed') ? `<button class="btn btn-sm btn-success resume-training" data-id="${task.id}">继续训练</button>` : ''}
                        ${task.status === 'running' || task.status === 'completed' || task.status === 'cancelled' ? `<button class="btn btn-sm btn-info tensorboard" data-id="${task.id}">TensorBoard</button>` : ''}
                        ${task.status === 'running' || task.status === 'training' || task.status === 'downloading_model' ? `<button class="btn btn-sm btn-primary view-details" data-id="${task.id}">训练详情</button>` : ''}
                        ${task.status === 'running' || task.status === 'training' || task.status === 'downloading_model' || task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled' ? `<button class="btn btn-sm btn-secondary view-logs" data-id="${task.id}">查看日志</button>` : ''}
                        ${task.status !== 'running' && task.status !== 'training' && task.status !== 'downloading_model' ? `<button class="btn btn-sm btn-danger delete-training" data-id="${task.id}">删除</button>` : ''}
                    </td>
                `;
                tableBody.appendChild(row);
            });

            // 绑定按钮事件
            document.querySelectorAll('.start-training').forEach(button => {
                button.addEventListener('click', function() {
                    const taskId = this.getAttribute('data-id');
                    startTraining(taskId);
                });
            });

            document.querySelectorAll('.stop-training').forEach(button => {
                button.addEventListener('click', function() {
                    const taskId = this.getAttribute('data-id');
                    stopTraining(taskId);
                });
            });

            document.querySelectorAll('.resume-training').forEach(button => {
                button.addEventListener('click', function() {
                    const taskId = this.getAttribute('data-id');
                    resumeTraining(taskId);
                });
            });

            document.querySelectorAll('.tensorboard').forEach(button => {
                button.addEventListener('click', function() {
                    const taskId = this.getAttribute('data-id');
                    openTensorBoard(taskId);
                });
            });

            // 绑定训练详情按钮事件
            document.querySelectorAll('.view-details').forEach(button => {
                button.addEventListener('click', function() {
                    const taskId = this.getAttribute('data-id');
                    viewTrainingDetails(taskId);
                });
            });

            // 绑定查看日志按钮事件
            document.querySelectorAll('.view-logs').forEach(button => {
                button.addEventListener('click', function() {
                    const taskId = this.getAttribute('data-id');
                    viewTrainingLogs(taskId);
                });
            });

            // 绑定删除按钮事件
            document.querySelectorAll('.delete-training').forEach(button => {
                button.addEventListener('click', function() {
                    const taskId = this.getAttribute('data-id');
                    deleteTraining(taskId);
                });
            });
        })
        .catch(error => {
            console.error('Error loading training tasks:', error);
            alert('加载训练任务失败');
        });
}

// 绑定训练页面事件
function bindTrainingEvents() {
    const addButton = document.getElementById('add-training-btn');
    if (addButton) {
        addButton.addEventListener('click', showAddTrainingModal);
    }
}

// 显示添加训练任务模态框
function showAddTrainingModal() {
    const modalTitle = document.querySelector('.modal-title');
    const modalBody = document.querySelector('.modal-body');
    const modalSubmit = document.getElementById('modalSubmit');

    modalTitle.textContent = '创建训练任务';

    // 获取模板内容
    const template = document.getElementById('add-training-template');
    modalBody.innerHTML = template.innerHTML;

    // 加载数据集和模型选项
    loadDatasetOptions();
    loadModelOptions();

    // 已删除数据集来源选择事件和本地数据集相关代码

    // 显示模态框
    modal.show();

    // 绑定设备类型选择事件
    const deviceTypeSelect = document.getElementById('device-type');
    if (deviceTypeSelect) {
        deviceTypeSelect.addEventListener('change', function() {
            const cpuOptions = document.querySelectorAll('.cpu-option');
            const gpuOptions = document.querySelectorAll('.gpu-option');

            if (this.value === 'cpu') {
                cpuOptions.forEach(option => option.style.display = 'block');
                gpuOptions.forEach(option => option.style.display = 'none');
            } else {
                cpuOptions.forEach(option => option.style.display = 'none');
                gpuOptions.forEach(option => option.style.display = 'block');
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
        getGpuInfoBtn.addEventListener('click', async function() {
            try {
                // 显示加载中状态
                getGpuInfoBtn.disabled = true;
                getGpuInfoBtn.textContent = '获取中...';

                const response = await fetch(`${API_URL}/training/all-gpus-info`);
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

    // 绑定GPU选择改变事件
    if (gpuSelect) {
        gpuSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
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
        });
    }

    // 绑定验证显存设置按钮事件
    if (validateMemoryBtn) {
        validateMemoryBtn.addEventListener('click', async function() {
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
    modalSubmit.onclick = submitAddTraining;
}

// 加载数据集选项
function loadDatasetOptions() {
    fetch(`${API_URL}/datasets`)
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
function loadModelOptions() {
    fetch(`${API_URL}/models`)
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

// 已删除验证本地数据集路径功能

// 提交添加训练任务表单
function submitAddTraining() {
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
    } else {
        // 获取GPU显存和GPU ID
        hardwareConfig.gpu_memory = parseInt(gpuMemoryInput.value);

        // 如果用户选择了特定GPU，添加GPU ID
        const gpuSelect = document.getElementById('gpu-select');
        if (gpuSelect && gpuSelect.value) {
            hardwareConfig.gpu_index = parseInt(gpuSelect.value);
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
    fetch(`${API_URL}/training`, {
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
        loadTrainingTasks();
    })
    .catch(error => {
        console.error('Error creating training task:', error);
        alert('创建训练任务失败: ' + error.message);
    });
}

// 开始训练
function startTraining(taskId) {
    // 检查任务状态
    fetch(`${API_URL}/training/${taskId}`)
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
            fetch(`${API_URL}/training/${taskId}/start`, {
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
                    loadTrainingTasks();

                    // 打开训练日志页面
                    viewTrainingLogs(taskId);
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
function stopTraining(taskId) {
    if (!confirm('确定要停止这个训练任务吗？这将终止当前的训练过程。')) {
        return;
    }

    fetch(`${API_URL}/training/${taskId}/stop`, {
        method: 'POST'
    })
        .then(response => {
            if (response.ok) {
                alert('训练已停止');
                loadTrainingTasks();
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
function resumeTraining(taskId) {
    // 检查任务状态
    fetch(`${API_URL}/training/${taskId}`)
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
            fetch(`${API_URL}/training/${taskId}/resume`, {
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
                    loadTrainingTasks();

                    // 打开训练日志页面
                    viewTrainingLogs(taskId);
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
function openTensorBoard(taskId) {
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

    fetch(`${API_URL}/training/${taskId}/tensorboard`)
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
                window.open(data.url, '_blank');
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
            alert('打开TensorBoard失败: ' + error.message);
        });
}

// 创建模态框函数
function createModal() {
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

// 删除训练任务
function deleteTraining(taskId) {
    // 创建确认对话框
    const modal = createModal();

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
    confirmButton.onclick = function() {
        // 显示加载中状态
        confirmButton.disabled = true;
        confirmButton.textContent = '删除中...';

        // 发送删除请求
        fetch(`${API_URL}/training/${taskId}`, {
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
            loadTrainingTasks();
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
function viewTrainingLogs(taskId) {
    // 创建一个模态框来显示日志
    const modal = createModal();

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
    refreshBtn.onclick = function() {
        fetchLogs();
    };
    leftButtons.appendChild(refreshBtn);

    // 添加TensorBoard按钮
    const tensorboardBtn = document.createElement('button');
    tensorboardBtn.textContent = '打开TensorBoard';
    tensorboardBtn.className = 'btn btn-info';
    tensorboardBtn.style.marginRight = '10px';
    tensorboardBtn.onclick = function() {
        // 直接调用已经实现的openTensorBoard函数
        openTensorBoard(taskId);
    };
    leftButtons.appendChild(tensorboardBtn);

    // 添加停止训练按钮（只在训练中显示）
    const stopBtn = document.createElement('button');
    stopBtn.textContent = '停止训练';
    stopBtn.className = 'btn btn-danger';
    stopBtn.style.marginRight = '10px';
    stopBtn.style.display = 'none'; // 默认隐藏，根据状态显示
    stopBtn.onclick = function() {
        if (confirm('确定要停止训练吗？这将终止当前的训练过程。')) {
            fetch(`${API_URL}/training/${taskId}/stop`, {
                method: 'POST'
            })
            .then(response => {
                if (response.ok) {
                    alert('训练已停止');
                    // 重新加载训练任务列表
                    loadTrainingTasks();
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
    function fetchLogs() {
        // 获取任务状态
        fetch(`${API_URL}/training/${taskId}`)
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
        fetch(`${API_URL}/training/${taskId}/logs`)
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
    const autoRefresh = setInterval(fetchLogs, 5000);

    // 将定时器添加到轮询管理器
    if (typeof PollingManager !== 'undefined') {
        PollingManager.addPoll(`training_logs_${taskId}`, autoRefresh);
    }



    // 当模态框关闭时清除定时器
    modal.addEventListener('remove', function() {
        clearInterval(autoRefresh);

        // 从轮询管理器中移除
        if (typeof PollingManager !== 'undefined') {
            PollingManager.removePoll(`training_logs_${taskId}`);
        }
    });

    // 点击模态框外部关闭
    window.onclick = function(event) {
        if (event.target === modal) {
            document.body.removeChild(modal);
            clearInterval(autoRefresh);

            // 从轮询管理器中移除
            if (typeof PollingManager !== 'undefined') {
                PollingManager.removePoll(`training_logs_${taskId}`);
            }
        }
    };
}

// 查看训练详情
function viewTrainingDetails(taskId) {
    // 创建一个模态框来显示训练详情
    const modal = createModal();

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
    logsBtn.onclick = function() {
        viewTrainingLogs(taskId);
    };
    leftButtons.appendChild(logsBtn);

    // 添加TensorBoard按钮
    const tensorboardBtn = document.createElement('button');
    tensorboardBtn.textContent = '打开TensorBoard';
    tensorboardBtn.className = 'btn btn-info';
    tensorboardBtn.style.marginRight = '10px';
    tensorboardBtn.onclick = function() {
        openTensorBoard(taskId);
    };
    leftButtons.appendChild(tensorboardBtn);

    // 添加停止训练按钮
    const stopBtn = document.createElement('button');
    stopBtn.textContent = '停止训练';
    stopBtn.className = 'btn btn-danger';
    stopBtn.style.marginRight = '10px';
    stopBtn.onclick = function() {
        if (confirm('确定要停止训练吗？这将终止当前的训练过程。')) {
            stopTraining(taskId);
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
    fetch(`${API_URL}/training/${taskId}`)
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
                                <td><span class="badge ${getStatusBadgeClass(task.status)}">${getStatusText(task.status)}</span></td>
                            </tr>
                            <tr>
                                <th>数据集</th>
                                <td>${task.dataset_name || '未指定'}</td>
                            </tr>
                            <tr>
                                <th>模型类型</th>
                                <td>${task.model_type || '未指定'}</td>
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
                const statusRefresh = setInterval(() => {
                    fetch(`${API_URL}/training/${taskId}`)
                        .then(response => response.json())
                        .then(updatedTask => {
                            // 更新状态
                            const statusCell = detailsContainer.querySelector('span.badge');
                            if (statusCell) {
                                statusCell.className = `badge ${getStatusBadgeClass(updatedTask.status)}`;
                                statusCell.textContent = getStatusText(updatedTask.status);
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
                                clearInterval(statusRefresh);
                                stopBtn.style.display = 'none';
                            }
                        })
                        .catch(error => {
                            console.error('Error updating task status:', error);
                        });
                }, 5000);

                // 当模态框关闭时清除定时器
                modal.addEventListener('remove', function() {
                    clearInterval(statusRefresh);
                });

                // 点击模态框外部关闭时清除定时器
                window.onclick = function(event) {
                    if (event.target === modal) {
                        document.body.removeChild(modal);
                        clearInterval(statusRefresh);
                    }
                };
            }
        })
        .catch(error => {
            console.error('Error fetching training details:', error);
            detailsContainer.innerHTML = `<div class="alert alert-danger">获取训练详情失败: ${error.message}</div>`;
        });
}

// ==================== 验证功能 ====================

// 加载检测表单
function loadDetectionForm() {
    // 加载模型选项
    fetch(`${API_URL}/models`)
        .then(response => response.json())
        .then(models => {
            const select = document.getElementById('model-select');
            select.innerHTML = '<option value="">请选择模型</option>';

            models.forEach(model => {
                if (model.task === 'detect') {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = `${model.name} (${model.type})`;
                    select.appendChild(option);
                }
            });
        })
        .catch(error => {
            console.error('Error loading model options:', error);
        });
}

// 绑定检测页面事件
function bindDetectionEvents() {
    // 绑定表单提交事件
    const form = document.getElementById('detection-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            submitDetection();
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
function submitDetection() {
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
    formData.append('conf_thres', confThreshold.value);
    formData.append('iou_thres', iouThreshold.value);

    // 发送请求
    fetch(`${API_URL}/detection`, {
        method: 'POST',
        body: formData
    })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('检测失败');
            }
        })
        .then(result => {
            // 获取检测结果
            return fetch(`${API_URL}/detection/${result.id}/result`);
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('获取检测结果失败');
            }
        })
        .then(resultData => {
            // 显示检测结果
            console.log('Detection result:', resultData);

            if (resultData.status !== 'completed' || !resultData.results || resultData.results.length === 0) {
                resultContentContainer.innerHTML = `<div class="alert alert-warning">${resultData.message || '未找到检测结果'}</div>`;
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

            resultContentContainer.innerHTML = resultHtml;
        })
        .catch(error => {
            console.error('Error in detection:', error);
            resultContentContainer.innerHTML = `<div class="alert alert-danger">检测失败: ${error.message}</div>`;
        });
}

// ==================== 辅助函数 ====================

// 获取状态文本
function getStatusText(status) {
    switch (status) {
        case 'processing':
            return '处理中';
        case 'available':
            return '可用';
        case 'error':
            return '错误';
        case 'pending':
            return '等待中';
        case 'running':
            return '运行中';
        case 'completed':
            return '已完成';
        case 'failed':
            return '失败';
        case 'cancelled':
            return '已取消';
        default:
            return status;
    }
}

// 获取状态徽章样式
function getStatusBadgeClass(status) {
    switch (status) {
        case 'processing':
        case 'pending':
            return 'bg-warning';
        case 'available':
        case 'completed':
            return 'bg-success';
        case 'error':
        case 'failed':
            return 'bg-danger';
        case 'running':
            return 'bg-primary';
        case 'cancelled':
            return 'bg-secondary';
        default:
            return 'bg-secondary';
    }
}

// 获取任务类型文本
function getTaskText(task) {
    switch (task) {
        case 'detect':
            return '检测 (Detection)';
        case 'segment':
            return '分割 (Segmentation)';
        case 'classify':
            return '分类 (Classification)';
        case 'pose':
            return '姿态估计 (Pose)';
        default:
            return task;
    }
}

// 获取来源文本
function getSourceText(source) {
    switch (source) {
        case 'upload':
            return '上传';
        case 'training':
            return '训练';
        default:
            return source;
    }
}

// ==================== 已删除外部数据集注册功能 ====================

// 显示文件浏览器模态框
function browseLocalDirectory(targetInputId) {
    console.log('Opening file browser modal for:', targetInputId);

    // 创建模态框
    const fileBrowserModal = new bootstrap.Modal(document.getElementById('file-browser-modal'));

    // 保存目标输入框ID
    window.currentTargetInputId = targetInputId;

    // 加载根目录
    loadFileBrowserItems();

    // 绑定选择目录按钮事件
    const selectButton = document.getElementById('select-directory-btn');
    if (selectButton) {
        selectButton.onclick = function() {
            selectCurrentDirectory();
        };
    }

    // 显示模态框
    fileBrowserModal.show();
}

// 加载文件浏览器项目
function loadFileBrowserItems(path = '') {
    console.log('Loading file browser items for path:', path);

    const itemsContainer = document.getElementById('file-browser-items');
    const breadcrumb = document.getElementById('file-browser-breadcrumb');
    const selectButton = document.getElementById('select-directory-btn');

    if (!itemsContainer || !breadcrumb || !selectButton) {
        console.error('File browser elements not found');
        return;
    }

    // 显示加载中状态
    itemsContainer.innerHTML = `
        <div class="d-flex justify-content-center py-3">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">加载中...</span>
            </div>
        </div>
    `;

    // 保存当前路径
    window.currentBrowserPath = path;

    // 发送请求
    fetch(`${API_URL}/datasets/browse-filesystem?path=${encodeURIComponent(path)}`)
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                return response.json().then(data => {
                    throw new Error(data.detail || '加载文件系统失败');
                });
            }
        })
        .then(data => {
            console.log('File browser items loaded:', data);

            // 更新面包屑
            updateFileBrowserBreadcrumb(data.current_path, breadcrumb);

            // 清空容器
            itemsContainer.innerHTML = '';

            // 添加上一级目录项
            if (data.parent_path) {
                const parentItem = document.createElement('a');
                parentItem.href = '#';
                parentItem.className = 'list-group-item list-group-item-action';
                parentItem.innerHTML = `<i class="bi bi-arrow-up-circle me-2"></i>..上一级目录`;
                parentItem.onclick = function(e) {
                    e.preventDefault();
                    loadFileBrowserItems(data.parent_path);
                };
                itemsContainer.appendChild(parentItem);
            }

            // 添加目录项
            if (data.items && data.items.length > 0) {
                data.items.forEach(item => {
                    if (item.is_dir) {
                        const dirItem = document.createElement('a');
                        dirItem.href = '#';
                        dirItem.className = 'list-group-item list-group-item-action';
                        dirItem.innerHTML = `<i class="bi bi-folder me-2"></i>${item.name}`;
                        dirItem.onclick = function(e) {
                            e.preventDefault();
                            loadFileBrowserItems(item.path);
                        };
                        itemsContainer.appendChild(dirItem);
                    }
                });
            } else {
                // 没有目录项
                const noItems = document.createElement('div');
                noItems.className = 'list-group-item text-center text-muted';
                noItems.textContent = '没有可用的目录';
                itemsContainer.appendChild(noItems);
            }
        })
        .catch(error => {
            console.error('Error loading file browser items:', error);
            itemsContainer.innerHTML = `
                <div class="alert alert-danger">
                    加载文件系统失败: ${error.message}
                </div>
            `;
        });
}

// 更新文件浏览器面包屑
function updateFileBrowserBreadcrumb(path, breadcrumb) {
    breadcrumb.innerHTML = '';

    // 添加根目录项
    const rootItem = document.createElement('li');
    rootItem.className = 'breadcrumb-item';
    if (!path) {
        rootItem.className += ' active';
        rootItem.setAttribute('aria-current', 'page');
        rootItem.textContent = '根目录';
    } else {
        const rootLink = document.createElement('a');
        rootLink.href = '#';
        rootLink.textContent = '根目录';
        rootLink.onclick = function(e) {
            e.preventDefault();
            loadFileBrowserItems('');
        };
        rootItem.appendChild(rootLink);
    }
    breadcrumb.appendChild(rootItem);

    // 如果有路径，添加路径项
    if (path) {
        // 将路径分割为部分
        const parts = path.split(/[\\\/]/).filter(part => part);
        let currentPath = '';

        parts.forEach((part, index) => {
            currentPath += (currentPath ? '/' : '') + part;

            const item = document.createElement('li');
            item.className = 'breadcrumb-item';

            if (index === parts.length - 1) {
                item.className += ' active';
                item.setAttribute('aria-current', 'page');
                item.textContent = part;
            } else {
                const link = document.createElement('a');
                link.href = '#';
                link.textContent = part;
                link.onclick = function(e) {
                    e.preventDefault();
                    loadFileBrowserItems(currentPath);
                };
                item.appendChild(link);
            }

            breadcrumb.appendChild(item);
        });
    }
}

// 选择当前目录
function selectCurrentDirectory() {
    const path = window.currentBrowserPath;
    const targetInputId = window.currentTargetInputId;

    if (!targetInputId) {
        console.error('No target input ID');
        return;
    }

    console.log(`Selecting directory: ${path} for input: ${targetInputId}`);

    // 设置目标输入框的值
    const targetInput = document.getElementById(targetInputId);
    if (targetInput) {
        targetInput.value = path;

        // 触发change事件
        const event = new Event('change');
        targetInput.dispatchEvent(event);
    }

    // 关闭模态框
    const fileBrowserModal = bootstrap.Modal.getInstance(document.getElementById('file-browser-modal'));
    if (fileBrowserModal) {
        fileBrowserModal.hide();
    }
}

// 已删除外部数据集相关功能
