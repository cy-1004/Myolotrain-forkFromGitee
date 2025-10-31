// 数据集管理模块
class DatasetManager {
    constructor() {
        // 数据集管理相关属性
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
                return 'bg-primary';
            case 'cancelled':
                return 'bg-secondary';
            default:
                return 'bg-secondary';
        }
    }

    // 加载数据集列表
    loadDatasets() {
        console.log('Loading datasets...');

        // 获取表格头并检查列数
        const tableHead = document.querySelector('#datasets-template table thead tr');
        if (tableHead) {
            const columnCount = tableHead.querySelectorAll('th').length;
            console.log('Dataset table has', columnCount, 'columns');
        }

        authenticatedFetch(`${API_URL}/datasets/`)
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
                        <td><span class="badge ${this.getStatusBadgeClass(dataset.status)}">${this.getStatusText(dataset.status)}</span></td>
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
                    button.addEventListener('click', (e) => {
                        const datasetId = e.target.getAttribute('data-id');
                        console.log('Split dataset button clicked for dataset:', datasetId);
                        this.showSplitDatasetModal(datasetId);
                    });
                });

                // 绑定删除按钮事件
                document.querySelectorAll('.delete-dataset').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const datasetId = e.target.getAttribute('data-id');
                        this.deleteDataset(datasetId);
                    });
                });
            })
            .catch(error => {
                console.error('Error loading datasets:', error);
                alert('加载数据集失败');
            });
    }

    // 绑定数据集页面事件
    bindDatasetEvents() {
        console.log('Binding dataset events');

        // 绑定添加数据集按钮
        const addButton = document.getElementById('add-dataset-btn');
        if (addButton) {
            console.log('Found add-dataset-btn, binding click event');
            addButton.addEventListener('click', () => this.showAddDatasetModal());
        } else {
            console.error('add-dataset-btn not found');
        }

        // 绑定导入本地数据集按钮
        const importLocalButton = document.getElementById('import-local-dataset-btn');
        if (importLocalButton) {
            console.log('Found import-local-dataset-btn, binding click event');
            importLocalButton.addEventListener('click', () => {
                console.log('Import local dataset button clicked');
                this.showImportLocalDatasetModal();
            });
        } else {
            console.error('import-local-dataset-btn not found');
        }

        // 绑定COCO格式JSON转换按钮
        const convertCocoButton = document.getElementById('convert-coco-btn');
        if (convertCocoButton) {
            console.log('Found convert-coco-btn, binding click event');
            convertCocoButton.onclick = () => {
                console.log('Convert COCO button clicked');
                this.showConvertCocoModal();
                return false;
            };
        } else {
            console.error('convert-coco-btn not found');
        }
    }

    // 显示添加数据集模态框
    showAddDatasetModal() {
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
                this.bindRatioSliders('train-ratio', 'val-ratio', 'test-ratio');
            } else {
                console.error('Split checkbox or options not found after timeout');
            }

            // 绑定提交按钮事件
            modalSubmit.onclick = () => this.submitAddDataset();
        }, 100); // 短暂延迟确保 DOM 已加载
    }

    // 提交添加数据集表单
    async submitAddDataset() {
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

            const initResponse = await authenticatedFetch(`${API_URL}/datasets/upload-init`, {
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
            xhr.open('POST', `${API_URL}/datasets/`, true);

            // 上传进度事件
            xhr.upload.onprogress = (e) => {
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
            xhr.onload = () => {
                if (xhr.status === 200 || xhr.status === 201) {
                    // 上传成功，开始轮询处理状态
                    statusCheckInterval = window.memoryManager.setInterval(async () => {
                        try {
                            const statusResponse = await authenticatedFetch(`${API_URL}/datasets/upload-status/${fileId}`);
                            if (!statusResponse.ok) {
                                window.memoryManager.clearInterval(statusCheckInterval);
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
                                    this.formatTime(statusData.estimated_time) : '计算中...';

                                progressDetails.innerHTML = `
                                    已上传: ${(statusData.uploaded_size / (1024 * 1024)).toFixed(2)} MB /
                                    ${(statusData.total_size / (1024 * 1024)).toFixed(2)} MB<br>
                                    速度: ${uploadSpeed} MB/s<br>
                                    预计剩余时间: ${remainingTime}
                                `;
                            } else if (statusData.status === 'extracting') {
                                // 对于大文件，显示更详细的解压信息
                                const totalSizeMB = (statusData.total_size / (1024 * 1024)).toFixed(2);
                                const elapsedTime = this.formatTime(statusData.elapsed_time);
                                progressDetails.innerHTML = `
                                    正在解压文件 (${totalSizeMB} MB)，请耐心等待...<br>
                                    已用时间: ${elapsedTime}<br>
                                    <small class="text-muted">大文件解压可能需要几分钟时间，请不要关闭浏览器</small>
                                `;
                            } else if (statusData.status === 'validating') {
                                const elapsedTime = this.formatTime(statusData.elapsed_time);
                                progressDetails.innerHTML = `
                                    正在验证数据集结构，请耐心等待...<br>
                                    已用时间: ${elapsedTime}<br>
                                    <small class="text-muted">正在处理文件名和生成配置文件</small>
                                `;
                            } else if (statusData.status === 'completed') {
                                window.memoryManager.clearInterval(statusCheckInterval);
                                modal.hide();
                                this.loadDatasets();
                            } else if (statusData.status === 'failed') {
                                window.memoryManager.clearInterval(statusCheckInterval);
                                progressStatus.textContent = '上传失败';
                                progressDetails.innerHTML = `错误: ${statusData.error || '未知错误'}`;
                                alert('上传数据集失败: ' + (statusData.error || '未知错误'));
                            }
                        } catch (error) {
                            console.error('Error checking upload status:', error);
                            // 在错误情况下停止轮询
                            window.memoryManager.clearInterval(statusCheckInterval);
                        }
                    }, 1000); // 每秒检查一次状态
                } else {
                    progressStatus.textContent = '上传失败';
                    alert('上传数据集失败: ' + xhr.statusText);
                }
            };

            // 上传错误事件
            xhr.onerror = () => {
                progressStatus.textContent = '上传失败';
                progressDetails.innerHTML = '网络错误，请检查您的网络连接';
                alert('上传数据集失败: 网络错误');
            };

            // 取消上传按钮
            if (cancelButton) {
                cancelButton.style.display = 'inline-block';
                cancelButton.onclick = () => {
                    xhr.abort();
                    if (statusCheckInterval) {
                        window.memoryManager.clearInterval(statusCheckInterval);
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
    formatTime(seconds) {
        if (seconds < 60) {
            return `${Math.round(seconds)}秒`;
        } else if (seconds < 3600) {
            return `${Math.floor(seconds / 60)}分${Math.round(seconds % 60)}秒`;
        } else {
            return `${Math.floor(seconds / 3600)}小时${Math.floor((seconds % 3600) / 60)}分`;
        }
    }

    // 绑定比例滑块事件，确保总和为100%
    bindRatioSliders(trainId, valId, testId) {
        const trainSlider = document.getElementById(trainId);
        const valSlider = document.getElementById(valId);
        const testSlider = document.getElementById(testId);

        const trainValue = document.getElementById(`${trainId}-value`);
        const valValue = document.getElementById(`${valId}-value`);
        const testValue = document.getElementById(`${testId}-value`);

        if (!trainSlider || !valSlider || !testSlider) return;

        // 更新显示值的函数
        const updateValues = () => {
            trainValue.textContent = `${Math.round(trainSlider.value * 100)}%`;
            valValue.textContent = `${Math.round(valSlider.value * 100)}%`;
            testValue.textContent = `${Math.round(testSlider.value * 100)}%`;
        }

        // 调整比例以确保总和为1
        const adjustRatios = (changedSlider) => {
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
        trainSlider.addEventListener('input', () => {
            adjustRatios(trainSlider);
        });

        valSlider.addEventListener('input', () => {
            adjustRatios(valSlider);
        });

        testSlider.addEventListener('input', () => {
            adjustRatios(testSlider);
        });

        // 初始化显示值
        updateValues();
    }

    // 设置本地数据集模态框事件
    setupLocalDatasetModalEvents() {
        console.log('Setting up local dataset modal events');

        // 设置浏览目录按钮
        this.setupBrowseDatasetDirButton();

        // 设置验证按钮
        this.setupValidateDatasetDirButton();

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
                    this.showLocalDatasetInfo(selectedDir.info);
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
            this.bindRatioSliders('local-train-ratio', 'local-val-ratio', 'local-test-ratio');
        } else {
            console.error('Local split elements not found:', { splitCheckbox, splitOptions });
        }

        // 绑定提交按钮事件
        const modalSubmit = document.getElementById('modalSubmit');
        if (modalSubmit) {
            modalSubmit.onclick = () => this.submitImportLocalDataset();
        }
    }

    // 显示从本地目录导入数据集模态框
    showImportLocalDatasetModal() {
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
            this.setupLocalDatasetModalEvents();
        }, 100); // 短暂延迟确保 DOM 已加载
    }

    // 处理浏览数据集目录按钮点击
    setupBrowseDatasetDirButton() {
        console.log('Setting up browse dataset directory button');
        const browseButton = document.getElementById('browse-dataset-dir-btn');
        const dirPathInput = document.getElementById('local-dataset-dir-path');

        if (!browseButton || !dirPathInput) {
            console.error('Browse button or directory path input not found:', { browseButton, dirPathInput });
            return;
        }

        browseButton.onclick = () => {
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
            authenticatedFetch(`${API_URL}/datasets/local-available`)
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
                        item.onclick = () => {
                            // 选中目录
                            const dirName = item.dataset.value;
                            const dirInfo = JSON.parse(item.dataset.info);

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
                            this.setupLocalDatasetModalEvents();

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
                                this.showLocalDatasetInfo(dirInfo);
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
            modalSubmit.onclick = () => {
                // 恢复原模态框
                modalTitle.textContent = savedTitle;
                modalBody.innerHTML = savedBody;
                modalSubmit.textContent = savedSubmitText;
                modalSubmit.onclick = savedSubmitAction;

                // 重新绑定事件
                this.setupLocalDatasetModalEvents();
            };
        };
    }

    // 显示本地数据集信息
    showLocalDatasetInfo(directoryInfo) {
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
                authenticatedFetch(`${API_URL}/datasets/directory-info?name=${encodeURIComponent(directoryInfo)}`)
                    .then(response => {
                        console.log(`Received response with status: ${response.status}`);
                        if (!response.ok) {
                            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
                        }
                        return response.json();
                    })
                    .then(info => {
                        console.log('Received directory info:', info);
                        this.updateDatasetInfoDisplay(info);

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
                this.updateDatasetInfoDisplay(directoryInfo);

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
    updateDatasetInfoDisplay(datasetInfo) {
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
    hideLocalDatasetInfo() {
        const infoContainer = document.getElementById('local-dataset-info');
        if (infoContainer) {
            infoContainer.style.display = 'none';
        }
    }

    // 显示COCO格式JSON转换模态框
    showConvertCocoModal() {
        console.log('Showing convert COCO modal');

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

        modalTitle.textContent = 'COCO格式JSON转换';

        // 获取模板内容
        const template = document.getElementById('convert-coco-template');
        if (!template) {
            console.error('convert-coco-template not found');
            alert('找不到COCO格式JSON转换模板，请刷新页面重试');
            return;
        }

        console.log('Setting modal body content for COCO conversion');
        modalBody.innerHTML = template.innerHTML;

        // 确保按钮状态正确
        if (modalSubmit) {
            modalSubmit.disabled = false;
            modalSubmit.textContent = '确定';
        }

        // 显示模态框
        console.log('Showing modal for COCO conversion');
        bsModal.show();

        // 使用setTimeout确保DOM已经更新
        setTimeout(() => {
            // 绑定分割选项显示/隐藏
            const splitCheckbox = document.getElementById('coco-split-enabled');
            const splitOptions = document.getElementById('coco-split-options');

            if (splitCheckbox && splitOptions) {
                console.log('Binding COCO split checkbox events');
                // 设置初始状态
                splitOptions.style.display = splitCheckbox.checked ? 'block' : 'none';

                // 绑定事件
                splitCheckbox.addEventListener('change', function() {
                    console.log('COCO split checkbox changed:', this.checked);
                    splitOptions.style.display = this.checked ? 'block' : 'none';
                });

                // 绑定比例滑块
                this.bindRatioSliders('coco-train-ratio', 'coco-val-ratio', 'coco-test-ratio');
            } else {
                console.error('COCO split elements not found:', { splitCheckbox, splitOptions });
            }

            // 绑定提交按钮事件
            if (modalSubmit) {
                modalSubmit.onclick = () => this.submitConvertCoco();
            }

            // 绑定打开文件夹按钮事件
            const openFolderBtn = document.getElementById('open-output-folder');
            if (openFolderBtn) {
                openFolderBtn.addEventListener('click', () => {
                    const outputPath = document.getElementById('coco-output-path');
                    if (outputPath && outputPath.value) {
                        // 使用API打开文件夹
                        authenticatedFetch(`${API_URL}/datasets/open-folder`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ path: outputPath.value })
                        })
                        .then(response => {
                            if (!response.ok) {
                                return response.json().then(err => { throw new Error(err.detail || '打开文件夹失败'); });
                            }
                            return response.json();
                        })
                        .then(data => {
                            console.log('打开文件夹成功:', data);
                        })
                        .catch(error => {
                            console.error('打开文件夹失败:', error);
                            alert('打开文件夹失败: ' + error.message);
                        });
                    }
                });
            }

            // 绑定下载ZIP按钮事件
            const downloadZipBtn = document.getElementById('download-labels-zip');
            if (downloadZipBtn) {
                downloadZipBtn.addEventListener('click', () => {
                    const outputPath = document.getElementById('coco-output-path');
                    if (outputPath && outputPath.value) {
                        // 创建下载链接
                        const downloadUrl = `${API_URL}/datasets/download-labels-zip?path=${encodeURIComponent(outputPath.value)}`;

                        // 创建一个隐藏的a标签并触发点击
                        const a = document.createElement('a');
                        a.style.display = 'none';
                        a.href = downloadUrl;
                        a.download = 'yolo_labels.zip';
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                    }
                });
            }
        }, 100);
    }

    // 提交COCO格式JSON转换表单
    async submitConvertCoco() {
        console.log('Submitting convert COCO form');
        const fileInput = document.getElementById('coco-json-file');
        const splitEnabled = document.getElementById('coco-split-enabled');
        const trainRatio = document.getElementById('coco-train-ratio');
        const valRatio = document.getElementById('coco-val-ratio');
        const testRatio = document.getElementById('coco-test-ratio');
        const randomSeed = document.getElementById('coco-random-seed');
        const progressContainer = document.getElementById('coco-convert-progress-container');
        const progressBar = document.getElementById('coco-convert-progress-bar');
        const statusContainer = document.getElementById('coco-convert-status');
        const resultContainer = document.getElementById('coco-convert-result');
        const outputPathInput = document.getElementById('coco-output-path');
        const modalSubmit = document.getElementById('modalSubmit');

        if (!fileInput || !fileInput.files[0]) {
            alert('请选择COCO格式的JSON文件');
            return;
        }

        // 验证文件类型
        if (!fileInput.files[0].name.endsWith('.json')) {
            alert('请选择JSON格式的COCO数据集文件');
            return;
        }

        // 禁用提交按钮
        modalSubmit.disabled = true;
        modalSubmit.textContent = '处理中...';

        // 显示进度容器
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        statusContainer.style.display = 'block';
        statusContainer.textContent = '正在上传COCO数据集文件...';
        resultContainer.style.display = 'none';

        try {
            // 创建FormData对象
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('split_enabled', splitEnabled ? splitEnabled.checked : 'true');
            formData.append('train_ratio', trainRatio ? trainRatio.value : '0.7');
            formData.append('val_ratio', valRatio ? valRatio.value : '0.15');
            formData.append('test_ratio', testRatio ? testRatio.value : '0.15');
            formData.append('random_seed', randomSeed ? randomSeed.value : '42');

            // 创建XMLHttpRequest对象以支持上传进度
            const xhr = new XMLHttpRequest();
            xhr.open('POST', `${API_URL}/datasets/convert-coco`, true);

            // 上传进度事件
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    progressBar.style.width = percentComplete + '%';
                    progressBar.textContent = Math.round(percentComplete) + '%';
                    statusContainer.textContent = `正在上传COCO数据集文件... ${Math.round(percentComplete)}%`;
                }
            };

            // 上传完成事件
            xhr.onload = () => {
                if (xhr.status === 200 || xhr.status === 201) {
                    // 上传成功
                    progressBar.style.width = '100%';
                    progressBar.textContent = '100%';
                    statusContainer.textContent = '转换成功！';

                    try {
                        // 解析响应
                        const response = JSON.parse(xhr.responseText);

                        // 显示结果
                        resultContainer.style.display = 'block';
                        if (outputPathInput) {
                            outputPathInput.value = response.output_dir;
                        }

                        // 重置按钮状态
                        modalSubmit.disabled = false;
                        modalSubmit.textContent = '关闭';
                        modalSubmit.onclick = function() {
                            modal.hide();
                        };
                    } catch (e) {
                        statusContainer.textContent = `解析响应失败: ${e.message}`;

                        // 重置按钮状态
                        modalSubmit.disabled = false;
                        modalSubmit.textContent = '确定';
                    }
                } else {
                    // 上传失败
                    try {
                        const response = JSON.parse(xhr.responseText);
                        statusContainer.textContent = `转换失败: ${response.detail || '未知错误'}`;
                        alert(`COCO格式JSON转换失败: ${response.detail || '未知错误'}`);
                    } catch (e) {
                        statusContainer.textContent = `转换失败: ${xhr.statusText}`;
                        alert(`COCO格式JSON转换失败: ${xhr.statusText}`);
                    }

                    // 重置按钮状态
                    modalSubmit.disabled = false;
                    modalSubmit.textContent = '确定';
                }
            };

            // 上传错误事件
            xhr.onerror = () => {
                statusContainer.textContent = '转换失败: 网络错误';
                alert('COCO格式JSON转换失败: 网络错误');

                // 重置按钮状态
                modalSubmit.disabled = false;
                modalSubmit.textContent = '确定';
            };

            // 发送请求
            xhr.send(formData);
        } catch (error) {
            console.error('Error converting COCO JSON:', error);
            statusContainer.textContent = `转换失败: ${error.message}`;
            alert('COCO格式JSON转换失败: ' + error.message);

            // 重置按钮状态
            modalSubmit.disabled = false;
            modalSubmit.textContent = '确定';
        }
    }

    // 显示COCO数据集导入模态框
    showImportCocoDatasetModal() {
        console.log('Showing import COCO dataset modal - 开始执行');

        try {
            // 获取模态框元素
            const modalElement = document.getElementById('mainModal');
            if (!modalElement) {
                console.error('Modal element not found');
                alert('找不到模态框元素，请刷新页面重试');
                return;
            }

            console.log('Modal element found:', modalElement);

            // 使用Bootstrap API直接显示模态框
            let bsModal;
            try {
                bsModal = bootstrap.Modal.getInstance(modalElement);
                if (!bsModal) {
                    console.log('Creating new Bootstrap modal instance');
                    bsModal = new bootstrap.Modal(modalElement);
                }
            } catch (error) {
                console.error('Error creating Bootstrap modal:', error);
                alert('创建模态框实例失败: ' + error.message);
                return;
            }

            // 设置模态框内容
            const modalTitle = modalElement.querySelector('.modal-title');
            const modalBody = modalElement.querySelector('.modal-body');
            const modalSubmit = document.getElementById('modalSubmit');

            if (!modalTitle || !modalBody || !modalSubmit) {
                console.error('Modal elements not found:', { modalTitle, modalBody, modalSubmit });
                alert('找不到模态框内部元素，请刷新页面重试');
                return;
            }

            console.log('Modal elements found:', { modalTitle, modalBody, modalSubmit });
            modalTitle.textContent = '导入COCO数据集';

            // 获取模板内容
            const template = document.getElementById('import-coco-dataset-template');
            if (!template) {
                console.error('import-coco-dataset-template not found');
                alert('找不到COCO数据集导入模板，请刷新页面重试');
                return;
            }

            console.log('Template found:', template);
            console.log('Setting modal body content for COCO import');
            modalBody.innerHTML = template.innerHTML;

            // 确保按钮状态正确
            if (modalSubmit) {
                modalSubmit.disabled = false;
                modalSubmit.textContent = '确定';
            }

            // 显示模态框
            console.log('Showing modal for COCO import');
            try {
                bsModal.show();
                console.log('Modal shown successfully');
            } catch (error) {
                console.error('Error showing modal:', error);
                alert('显示模态框失败: ' + error.message);

                // 尝试使用原生方法显示
                modalElement.style.display = 'block';
                modalElement.classList.add('show');
                document.body.classList.add('modal-open');

                // 创建背景遮罩
                const backdrop = document.createElement('div');
                backdrop.className = 'modal-backdrop fade show';
                document.body.appendChild(backdrop);
            }

            // 使用setTimeout确保DOM已经更新
            setTimeout(() => {
                try {
                    // 绑定分割选项显示/隐藏
                    const splitCheckbox = document.getElementById('coco-split-dataset-enabled');
                    const splitOptions = document.getElementById('coco-split-options');

                    if (splitCheckbox && splitOptions) {
                        console.log('Binding COCO split checkbox events');
                        // 设置初始状态
                        splitOptions.style.display = splitCheckbox.checked ? 'block' : 'none';

                        // 绑定事件
                        splitCheckbox.addEventListener('change', function() {
                            console.log('COCO split checkbox changed:', this.checked);
                            splitOptions.style.display = this.checked ? 'block' : 'none';
                        });

                        // 绑定比例滑块
                        this.bindRatioSliders('coco-train-ratio', 'coco-val-ratio', 'coco-test-ratio');
                    } else {
                        console.error('COCO split elements not found:', { splitCheckbox, splitOptions });
                    }

                    // 绑定提交按钮事件
                    if (modalSubmit) {
                        console.log('Binding submit button click event');
                        modalSubmit.onclick = () => {
                            console.log('Submit button clicked');
                            this.submitImportCocoDataset();
                        };
                    }
                } catch (error) {
                    console.error('Error in setTimeout callback:', error);
                }
            }, 100);

            console.log('showImportCocoDatasetModal completed successfully');
        } catch (error) {
            console.error('Unhandled error in showImportCocoDatasetModal:', error);
            alert('显示COCO数据集导入模态框时发生错误: ' + error.message);
        }
    }

    // 提交导入COCO数据集表单
    async submitImportCocoDataset() {
        console.log('Submitting import COCO dataset form');
        const nameInput = document.getElementById('coco-dataset-name');
        const descriptionInput = document.getElementById('coco-dataset-description');
        const fileInput = document.getElementById('coco-dataset-file');
        const splitEnabled = document.getElementById('coco-split-dataset-enabled');
        const trainRatio = document.getElementById('coco-train-ratio');
        const valRatio = document.getElementById('coco-val-ratio');
        const testRatio = document.getElementById('coco-test-ratio');
        const randomSeed = document.getElementById('coco-random-seed');
        const progressContainer = document.getElementById('coco-upload-progress-container');
        const progressBar = document.getElementById('coco-upload-progress-bar');
        const statusContainer = document.getElementById('coco-upload-status');
        const modalSubmit = document.getElementById('modalSubmit');

        if (!nameInput || !fileInput || !fileInput.files[0]) {
            alert('请填写必填字段并选择COCO格式的JSON文件');
            return;
        }

        // 验证文件类型
        if (!fileInput.files[0].name.endsWith('.json')) {
            alert('请选择JSON格式的COCO数据集文件');
            return;
        }

        // 禁用提交按钮
        modalSubmit.disabled = true;
        modalSubmit.textContent = '处理中...';

        // 显示进度容器
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        statusContainer.style.display = 'block';
        statusContainer.textContent = '正在上传COCO数据集文件...';

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
            xhr.open('POST', `${API_URL}/datasets/import-coco`, true);

            // 上传进度事件
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    progressBar.style.width = percentComplete + '%';
                    progressBar.textContent = Math.round(percentComplete) + '%';
                    statusContainer.textContent = `正在上传COCO数据集文件... ${Math.round(percentComplete)}%`;
                }
            };

            // 上传完成事件
            xhr.onload = () => {
                if (xhr.status === 200 || xhr.status === 201) {
                    // 上传成功
                    progressBar.style.width = '100%';
                    progressBar.textContent = '100%';
                    statusContainer.textContent = '导入成功！正在刷新数据集列表...';

                    // 关闭模态框
                    modal.hide();

                    // 重新加载数据集列表
                    this.loadDatasets();

                    // 显示成功消息
                    alert('COCO数据集导入成功！');
                } else {
                    // 上传失败
                    try {
                        const response = JSON.parse(xhr.responseText);
                        statusContainer.textContent = `导入失败: ${response.detail || '未知错误'}`;
                        alert(`导入COCO数据集失败: ${response.detail || '未知错误'}`);
                    } catch (e) {
                        statusContainer.textContent = `导入失败: ${xhr.statusText}`;
                        alert(`导入COCO数据集失败: ${xhr.statusText}`);
                    }

                    // 重置按钮状态
                    modalSubmit.disabled = false;
                    modalSubmit.textContent = '确定';
                }
            };

            // 上传错误事件
            xhr.onerror = () => {
                statusContainer.textContent = '导入失败: 网络错误';
                alert('导入COCO数据集失败: 网络错误');

                // 重置按钮状态
                modalSubmit.disabled = false;
                modalSubmit.textContent = '确定';
            };

            // 发送请求
            xhr.send(formData);
        } catch (error) {
            console.error('Error importing COCO dataset:', error);
            statusContainer.textContent = `导入失败: ${error.message}`;
            alert('导入COCO数据集失败: ' + error.message);

            // 重置按钮状态
            modalSubmit.disabled = false;
            modalSubmit.textContent = '确定';
        }
    }

    // 设置验证数据集目录按钮
    setupValidateDatasetDirButton() {
        console.log('Setting up validate dataset directory button');
        const validateButton = document.getElementById('validate-dataset-dir-btn');
        const dirPathInput = document.getElementById('local-dataset-dir-path');

        if (!validateButton || !dirPathInput) {
            console.error('Validate button or directory path input not found:', { validateButton, dirPathInput });
            return;
        }

        validateButton.onclick = () => {
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
                authenticatedFetch(`${API_URL}/datasets/directory-info?name=${encodeURIComponent(dirPath)}`)
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
                        this.updateDatasetInfoDisplay(info);
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
    submitImportLocalDataset() {
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
        authenticatedFetch(`${API_URL}/datasets/import-local`, {
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
            this.loadDatasets();
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
    deleteDataset(datasetId) {
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
        confirmButton.onclick = () => {
            // 显示加载中状态
            confirmButton.disabled = true;
            confirmButton.textContent = '删除中...';

            // 发送删除请求
                    authenticatedFetch(`${API_URL}/datasets/${datasetId}`, {
                        method: 'DELETE'
                    })
            .then(response => {
                if (response.ok) {
                    // 关闭模态框
                    document.body.removeChild(modal);
                    // 重新加载数据集列表
                    this.loadDatasets();
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
        window.onclick = (event) => {
            if (event.target === modal) {
                document.body.removeChild(modal);
            }
        };
    }

    // 显示数据集分割模态框
    showSplitDatasetModal(datasetId) {
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
        this.bindRatioSliders('split-train-ratio', 'split-val-ratio', 'split-test-ratio');

        // 绑定提交按钮事件
        modalSubmit.onclick = () => {
            this.submitSplitDataset(datasetId);
        };
    }

    // 提交分割数据集请求
    submitSplitDataset(datasetId) {
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
        authenticatedFetch(`${API_URL}/datasets/${datasetId}/split`, {
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
            this.loadDatasets();
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

    // 隐藏加载中覆盖层
    hideLoadingOverlay() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }
}

// 创建全局实例
window.datasetManager = new DatasetManager();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DatasetManager;
}