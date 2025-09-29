// 全局变量
const API_URL = '/api';  // API路径
let currentPage = '';
let modal;
let DEBUG_MODE = false;  // 全局DEBUG模式开关

// 从localStorage加载DEBUG模式设置
function loadDebugMode() {
    const savedDebugMode = localStorage.getItem('debugMode');
    DEBUG_MODE = savedDebugMode === 'true';
    console.log(`DEBUG模式已${DEBUG_MODE ? '启用' : '禁用'}`);
}

// 保存DEBUG模式设置到localStorage
function saveDebugMode(debugMode) {
    DEBUG_MODE = debugMode;
    localStorage.setItem('debugMode', debugMode);
    console.log(`DEBUG模式已${DEBUG_MODE ? '启用' : '禁用'}`);
}

// 包装console.log，只在DEBUG模式下输出
function log() {
    if (DEBUG_MODE) {
        console.log.apply(console, arguments);
    }
}

// 包装console.error，只在DEBUG模式下输出
function error() {
    if (DEBUG_MODE) {
        console.error.apply(console, arguments);
    }
}

// 包装console.warn，只在DEBUG模式下输出
function warn() {
    if (DEBUG_MODE) {
        console.warn.apply(console, arguments);
    }
}

// 流媒体管理全局函数
window.startStream = function(streamId) {
    fetch(`${API_URL}/streaming/start/${streamId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('流媒体启动成功！');
            // 重新加载列表
            if (typeof window.loadStreamsManagementList === 'function') {
                window.loadStreamsManagementList();
            }
            if (typeof window.loadStreamsList === 'function') {
                window.loadStreamsList();
            }
        } else {
            alert('启动失败: ' + (data.message || '未知错误'));
        }
    })
    .catch(error => {
        alert('启动失败: ' + error.message);
    });
};

window.stopStream = function(streamId) {
    fetch(`${API_URL}/streaming/stop/${streamId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('流媒体停止成功！');
            // 重新加载列表
            if (typeof window.loadStreamsManagementList === 'function') {
                window.loadStreamsManagementList();
            }
            if (typeof window.loadStreamsList === 'function') {
                window.loadStreamsList();
            }
        } else {
            alert('停止失败: ' + (data.message || '未知错误'));
        }
    })
    .catch(error => {
        alert('停止失败: ' + error.message);
    });
};

window.deleteStream = function(streamId) {
    if (confirm('确定要删除这个流媒体吗？')) {
        // 先停止流媒体
        fetch(`${API_URL}/streaming/stop/${streamId}`, {
            method: 'POST'
        })
        .then(() => {
            // 再删除流媒体（如果有删除API的话）
            alert('流媒体已停止！');
            // 重新加载列表
            if (typeof window.loadStreamsManagementList === 'function') {
                window.loadStreamsManagementList();
            }
            if (typeof window.loadStreamsList === 'function') {
                window.loadStreamsList();
            }
        })
        .catch(error => {
            alert('删除失败: ' + error.message);
        });
    }
};

// 测试API端点
function testApiEndpoints() {
    log('Testing API endpoints...');

    // 测试数据集列表API
    fetch(`${API_URL}/datasets/`)
        .then(response => {
            log('Datasets API status:', response.status);
            return response.json();
        })
        .then(data => {
            log('Datasets API response:', data);
            if (data.length > 0) {
                log('First dataset structure:', JSON.stringify(data[0], null, 2));
                log('Has train_count:', 'train_count' in data[0]);
                log('Has val_count:', 'val_count' in data[0]);
                log('Has test_count:', 'test_count' in data[0]);
            }
        })
        .catch(error => {
            error('Datasets API error:', error);
        });

    // 测试本地目录API
    fetch(`${API_URL}/datasets/local-available`)
        .then(response => {
            log('Local directories API status:', response.status);
            return response.json();
        })
        .then(data => {
            log('Local directories API response:', data);
        })
        .catch(error => {
            error('Local directories API error:', error);
        });
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 加载DEBUG模式设置
    loadDebugMode();
    
    // 初始化Bootstrap模态框
    try {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            modal = new bootstrap.Modal(document.getElementById('mainModal'));
            log('Bootstrap模态框初始化成功');
        } else {
            warn('Bootstrap未加载，跳过模态框初始化');
            // 创建一个空对象，避免后续代码出错
            modal = {
                show: function() { warn('模态框功能不可用'); },
                hide: function() { warn('模态框功能不可用'); }
            };
        }
    } catch (error) {
        error('初始化Bootstrap模态框失败:', error);
        // 创建一个空对象，避免后续代码出错
        modal = {
            show: function() { warn('模态框功能不可用'); },
            hide: function() { warn('模态框功能不可用'); }
        };
    }

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
    
    // 获取后端DEBUG模式状态
    getBackendDebugMode();

    // 已在导航栏中配置为data-page="settings"，由loadPage处理

    // 添加调试代码 - 5秒后检查COCO按钮是否存在并强制绑定事件
    setTimeout(function() {
        log('DEBUG: 检查COCO按钮并强制绑定事件');
        const cocoButton = document.getElementById('import-coco-dataset-btn');
        if (cocoButton) {
            log('DEBUG: 找到COCO按钮:', cocoButton);
            log('DEBUG: COCO按钮当前onclick:', cocoButton.onclick);

            // 直接绑定全局函数
            window.showCocoModal = function() {
                log('DEBUG: 通过全局函数调用showImportCocoDatasetModal');
                showImportCocoDatasetModal();
                return false;
            };

            // 强制重新绑定事件
            cocoButton.onclick = window.showCocoModal;

            // 添加内联事件处理
            cocoButton.setAttribute('onclick', 'return window.showCocoModal();');

            log('DEBUG: COCO按钮事件已强制重新绑定');
        } else {
            error('DEBUG: 5秒后仍未找到COCO按钮');
        }
    }, 5000);
});

// ==================== 标注页面 ====================

// 加载标注页面
function loadAnnotationPage() {
    log('Loading annotation page...');
    loadAnnotationProjects();
}

// 绑定标注页面事件
function bindAnnotationEvents() {
    // 创建标注项目按钮
    const createProjectBtn = document.getElementById('create-annotation-project-btn');
    if (createProjectBtn) {
        createProjectBtn.addEventListener('click', showCreateAnnotationProjectModal);
    }
}

// 从后端获取DEBUG模式状态
function getBackendDebugMode() {
    if (DEBUG_MODE) {
        fetch(`${API_URL}/settings/debug-mode`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    log(`后端DEBUG模式状态: ${data.debug_mode}`);
                }
            })
            .catch(err => {
                error('获取后端DEBUG模式状态失败:', err);
            });
    }
}

// 加载设置页面
function loadSettingsPage() {
    // 设置当前DEBUG模式状态
    const debugModeToggle = document.getElementById('debugModeToggle');
    if (debugModeToggle) {
        debugModeToggle.checked = DEBUG_MODE;
    }
}

// 加载标注项目列表
function loadAnnotationProjects() {
    fetch(`${API_URL}/annotation/projects/`)
        .then(response => response.json())
        .then(data => {
            const tableBody = document.getElementById('annotation-projects-table-body');
            if (!tableBody) return;
            
            tableBody.innerHTML = '';
            
            if (data.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="8" class="text-center">暂无标注项目</td></tr>';
                return;
            }
            
            data.forEach(project => {
                const row = document.createElement('tr');
                const progressPercent = project.total_images > 0 ? 
                    Math.round((project.completed_images / project.total_images) * 100) : 0;
                
                row.innerHTML = `
                    <td>${project.name}</td>
                    <td>${project.description || '-'}</td>
                    <td>${project.classes.length}</td>
                    <td>${project.total_images || 0}</td>
                    <td>${project.completed_images || 0}</td>
                    <td>
                        <div class="progress" style="height: 20px;">
                            <div class="progress-bar" role="progressbar" style="width: ${progressPercent}%">
                                ${progressPercent}%
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="badge ${project.status === 'active' ? 'bg-success' : 'bg-secondary'}">
                            ${project.status === 'active' ? '进行中' : '已完成'}
                        </span>
                    </td>
                    <td>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-primary" onclick="openAnnotationTool('${project.id}')">
                                <i class="fas fa-edit"></i> 标注
                            </button>
                            <button class="btn btn-info" onclick="viewProjectStats('${project.id}')">
                                <i class="fas fa-chart-bar"></i> 统计
                            </button>
                            <button class="btn btn-success" onclick="exportProject('${project.id}')">
                                <i class="fas fa-download"></i> 导出
                            </button>
                            <button class="btn btn-danger" onclick="deleteAnnotationProject('${project.id}')">
                                <i class="fas fa-trash"></i> 删除
                            </button>
                        </div>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('加载标注项目失败:', error);
            const tableBody = document.getElementById('annotation-projects-table-body');
            if (tableBody) {
                tableBody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">加载失败</td></tr>';
            }
        });
}

// 显示创建标注项目模态框
function showCreateAnnotationProjectModal() {
    const template = document.getElementById('create-annotation-project-template');
    if (!template) {
        console.error('创建标注项目模板未找到');
        return;
    }
    
    const modalTitle = document.querySelector('#mainModal .modal-title');
    const modalBody = document.querySelector('#mainModal .modal-body');
    const modalSubmit = document.getElementById('modalSubmit');
    
    modalTitle.textContent = '创建标注项目';
    modalBody.innerHTML = template.innerHTML;
    modalSubmit.textContent = '创建项目';
    
    // 加载数据集列表
    loadDatasetsForAnnotation();
    
    // 绑定事件
    bindCreateAnnotationProjectEvents();
    
    // 显示模态框
    modal.show();
}

// 加载数据集列表用于标注项目
function loadDatasetsForAnnotation() {
    fetch(`${API_URL}/datasets/`)
        .then(response => response.json())
        .then(data => {
            const datasetSelect = document.getElementById('annotation-dataset-id');
            if (datasetSelect) {
                datasetSelect.innerHTML = '<option value="">选择数据集</option>';
                data.forEach(dataset => {
                    const option = document.createElement('option');
                    option.value = dataset.id;
                    option.textContent = `${dataset.name} (${dataset.classes.length}类)`;
                    datasetSelect.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('加载数据集失败:', error);
        });
}

// 绑定创建标注项目事件
function bindCreateAnnotationProjectEvents() {
    // 图片来源选择事件
    const imageSourceRadios = document.querySelectorAll('input[name="image-source"]');
    imageSourceRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            // 隐藏所有容器
            document.getElementById('dataset-source-container').style.display = 'none';
            document.getElementById('directory-source-container').style.display = 'none';
            document.getElementById('upload-source-container').style.display = 'none';
            document.getElementById('folder-source-container').style.display = 'none';
            
            // 显示选中的容器
            switch(this.value) {
                case 'dataset':
                    document.getElementById('dataset-source-container').style.display = 'block';
                    break;
                case 'directory':
                    document.getElementById('directory-source-container').style.display = 'block';
                    break;
                case 'upload':
                    document.getElementById('upload-source-container').style.display = 'block';
                    break;
                case 'folder':
                    document.getElementById('folder-source-container').style.display = 'block';
                    break;
            }
        });
    });
    
    // 提交按钮事件
    const modalSubmit = document.getElementById('modalSubmit');
    modalSubmit.onclick = createAnnotationProject;
}

// 创建标注项目
function createAnnotationProject() {
    const form = document.getElementById('create-annotation-project-form');
    const formData = new FormData(form);
    
    const name = document.getElementById('annotation-project-name').value;
    const description = document.getElementById('annotation-project-description').value;
    const classes = document.getElementById('annotation-classes').value.split('\n').filter(c => c.trim());
    const imageSource = document.querySelector('input[name="image-source"]:checked').value;
    
    if (!name || classes.length === 0) {
        alert('请填写项目名称和类别列表');
        return;
    }
    
    let requestData = {
        name: name,
        description: description,
        classes: classes
    };
    
    let apiUrl = `${API_URL}/annotation/projects/`;
    let requestMethod = 'POST';
    let requestBody;
    
    switch(imageSource) {
        case 'dataset':
            const datasetId = document.getElementById('annotation-dataset-id').value;
            if (!datasetId) {
                alert('请选择数据集');
                return;
            }
            requestData.dataset_id = datasetId;
            requestBody = JSON.stringify(requestData);
            break;
            
        case 'directory':
            const directory = document.getElementById('annotation-image-directory').value;
            if (!directory) {
                alert('请选择图片目录');
                return;
            }
            requestData.image_directory = directory;
            requestBody = JSON.stringify(requestData);
            break;
            
        case 'upload':
            const zipFile = document.getElementById('annotation-images-zip').files[0];
            if (!zipFile) {
                alert('请选择ZIP文件');
                return;
            }
            apiUrl = `${API_URL}/annotation/projects/upload`;
            const uploadFormData = new FormData();
            uploadFormData.append('name', name);
            uploadFormData.append('description', description);
            uploadFormData.append('classes', JSON.stringify(classes));
            uploadFormData.append('images_zip', zipFile);
            requestBody = uploadFormData;
            break;
            
        case 'folder':
            const folderFiles = document.getElementById('annotation-images-folder').files;
            if (folderFiles.length === 0) {
                alert('请选择图片文件夹');
                return;
            }
            apiUrl = `${API_URL}/annotation/projects/upload-folder`;
            const folderFormData = new FormData();
            folderFormData.append('name', name);
            folderFormData.append('description', description);
            folderFormData.append('classes', JSON.stringify(classes));
            for (let file of folderFiles) {
                folderFormData.append('images', file);
            }
            requestBody = folderFormData;
            break;
    }
    
    const headers = {};
    if (imageSource === 'dataset' || imageSource === 'directory') {
        headers['Content-Type'] = 'application/json';
    }
    
    fetch(apiUrl, {
        method: requestMethod,
        headers: headers,
        body: requestBody
    })
    .then(response => response.json())
    .then(data => {
        if (data.id) {
            alert('标注项目创建成功！');
            modal.hide();
            loadAnnotationProjects();
        } else {
            alert('创建失败: ' + (data.detail || '未知错误'));
        }
    })
    .catch(error => {
        console.error('创建标注项目失败:', error);
        alert('创建失败: ' + error.message);
    });
}

// 打开标注工具
function openAnnotationTool(projectId) {
    window.open(`/static/annotation.html?project_id=${projectId}`, '_blank');
}

// 查看项目统计
function viewProjectStats(projectId) {
    fetch(`${API_URL}/annotation/projects/${projectId}/stats`)
        .then(response => response.json())
        .then(data => {
            alert(`项目统计:\n总图片: ${data.total_images}\n已完成: ${data.completed_images}\n进度: ${data.progress_percentage}%`);
        })
        .catch(error => {
            console.error('获取项目统计失败:', error);
            alert('获取统计信息失败');
        });
}

// 导出项目
function exportProject(projectId) {
    const exportData = {
        format: 'yolo',
        split_data: true,
        include_images: true,
        train_ratio: 0.7,
        val_ratio: 0.2,
        test_ratio: 0.1
    };
    
    fetch(`${API_URL}/annotation/projects/${projectId}/export`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(exportData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.export_path) {
            alert('导出成功！文件路径: ' + data.export_path);
        } else {
            alert('导出失败: ' + (data.detail || '未知错误'));
        }
    })
    .catch(error => {
        console.error('导出项目失败:', error);
        alert('导出失败: ' + error.message);
    });
}

// 删除标注项目
function deleteAnnotationProject(projectId) {
    if (confirm('确定要删除这个标注项目吗？此操作不可撤销。')) {
        fetch(`${API_URL}/annotation/projects/${projectId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            alert('项目删除成功！');
            loadAnnotationProjects();
        })
        .catch(error => {
            console.error('删除项目失败:', error);
            alert('删除失败: ' + error.message);
        });
    }
}

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
        case 'opencv':
            loadOpenCVPage();
            bindOpenCVEvents();
            break;
        case 'video':
            loadVideoPage();
            bindVideoEvents();
            break;
        case 'tracking':
            initTrackingPage();
            break;
        case 'annotation':
            loadAnnotationPage();
            bindAnnotationEvents();
            break;
        case 'settings':
            loadSettingsPage();
            bindSettingsEvents();
            break;
    }
}

// ==================== 设置页面 ====================

// 绑定设置页面事件
function bindSettingsEvents() {
    // 保存设置按钮事件
    const saveBtn = document.getElementById('saveSettingsBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            const debugModeToggle = document.getElementById('debugModeToggle');
            if (debugModeToggle) {
                const newDebugMode = debugModeToggle.checked;
                saveDebugMode(newDebugMode);
                
                // 显示保存成功消息
                showSettingsSaveMessage(`DEBUG模式已${newDebugMode ? '启用' : '禁用'}`);
            }
        });
    }
}

// 显示设置保存消息
function showSettingsSaveMessage(message) {
    const messageElement = document.getElementById('settings-save-message');
    if (messageElement) {
        messageElement.textContent = message;
        messageElement.className = 'mt-2 alert alert-success';
        messageElement.style.display = 'block';
        
        // 3秒后隐藏消息
        setTimeout(function() {
            messageElement.style.display = 'none';
        }, 3000);
    }
}

// ==================== OpenCV 工具 ====================

// 加载 OpenCV 页面
function loadOpenCVPage() {
    console.log('Loading OpenCV page...');

    // 加载覆盖层已完全移除

    // 确保所有结果区域也是隐藏的
    const resultAreas = [
        'preprocess-result',
        'analyze-result',
        'augment-result'
    ];

    resultAreas.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.style.display = 'none';
        }
    });

    // 加载数据集列表（用于数据增强功能）
    fetch(`${API_URL}/datasets/`)
        .then(response => response.json())
        .then(data => {
            console.log('Loaded datasets for OpenCV:', data.length);
            console.log('Dataset data:', data); // 输出数据集数据以进行调试

            const datasetSelect = document.getElementById('dataset-path');
            if (datasetSelect) {
                // 清空现有选项（除了第一个默认选项）
                while (datasetSelect.options.length > 1) {
                    datasetSelect.remove(1);
                }

                // 添加新选项
                data.forEach(dataset => {
                    const option = document.createElement('option');
                    // 确保数据集路径存在
                    if (dataset.path) {
                        option.value = dataset.path;
                        option.textContent = dataset.name;
                        datasetSelect.appendChild(option);
                        console.log(`Added dataset option: ${dataset.name} with path: ${dataset.path}`);
                    } else {
                        console.warn(`Dataset ${dataset.name} has no path property`);
                    }
                });

                // 如果没有数据集，显示提示
                if (datasetSelect.options.length <= 1) {
                    const option = document.createElement('option');
                    option.value = "";
                    option.textContent = "没有可用的数据集";
                    option.disabled = true;
                    datasetSelect.appendChild(option);
                }
            } else {
                console.error('dataset-path select element not found');
            }
        })
        .catch(error => {
            console.error('加载数据集失败:', error);

            // 在出错时添加错误选项
            const datasetSelect = document.getElementById('dataset-path');
            if (datasetSelect) {
                const option = document.createElement('option');
                option.value = "";
                option.textContent = "加载数据集失败";
                option.disabled = true;
                datasetSelect.appendChild(option);
            }
        });
}

// 绑定 OpenCV 页面事件
function bindOpenCVEvents() {
    console.log('Binding OpenCV events...');

    // 确保加载覆盖层是隐藏的
    const loadingOverlay = document.getElementById('opencv-loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }

    // 使用setTimeout确保DOM元素已经加载
    setTimeout(() => {
        console.log('Delayed binding of OpenCV events...');
        bindOpenCVEventHandlers();
    }, 500);
}

// 实际绑定事件处理程序
function bindOpenCVEventHandlers() {

    // 图像预处理相关脚本
    // 显示/隐藏选项
    const resizeCheck = document.getElementById('resize-check');
    const resizeOptions = document.getElementById('resize-options');
    if (resizeCheck && resizeOptions) {
        resizeCheck.addEventListener('change', function() {
            resizeOptions.style.display = this.checked ? 'block' : 'none';
        });
    }

    const denoiseCheck = document.getElementById('denoise-check');
    const denoiseOptions = document.getElementById('denoise-options');
    if (denoiseCheck && denoiseOptions) {
        denoiseCheck.addEventListener('change', function() {
            denoiseOptions.style.display = this.checked ? 'block' : 'none';
        });
    }

    const brightnessContrastCheck = document.getElementById('brightness-contrast-check');
    const brightnessContrastOptions = document.getElementById('brightness-contrast-options');
    if (brightnessContrastCheck && brightnessContrastOptions) {
        brightnessContrastCheck.addEventListener('change', function() {
            brightnessContrastOptions.style.display = this.checked ? 'block' : 'none';
        });
    }

    const sharpenCheck = document.getElementById('sharpen-check');
    const sharpenOptions = document.getElementById('sharpen-options');
    if (sharpenCheck && sharpenOptions) {
        sharpenCheck.addEventListener('change', function() {
            sharpenOptions.style.display = this.checked ? 'block' : 'none';
        });
    }

    // 更新滑块值显示
    const denoiseStrength = document.getElementById('denoise-strength');
    if (denoiseStrength) {
        denoiseStrength.addEventListener('input', function() {
            document.getElementById('denoise-strength-value').textContent = this.value;
        });
    }

    const brightness = document.getElementById('brightness');
    if (brightness) {
        brightness.addEventListener('input', function() {
            document.getElementById('brightness-value').textContent = this.value;
        });
    }

    const contrast = document.getElementById('contrast');
    if (contrast) {
        contrast.addEventListener('input', function() {
            document.getElementById('contrast-value').textContent = (this.value / 10).toFixed(1);
        });
    }

    const sharpenAmount = document.getElementById('sharpen-amount');
    if (sharpenAmount) {
        sharpenAmount.addEventListener('input', function() {
            document.getElementById('sharpen-amount-value').textContent = (this.value / 10).toFixed(1);
        });
    }

    // 绑定表单提交事件
    // 1. 预处理表单
    const preprocessForm = document.getElementById('preprocess-form');
    if (preprocessForm) {
        preprocessForm.addEventListener('submit', function(event) {
            // 阻止表单的默认提交行为
            event.preventDefault();
            console.log('Process image button clicked');

            const imageFile = document.getElementById('image-upload').files[0];
            if (!imageFile) {
                alert('请选择图像文件');
                return;
            }

            // 构建操作列表
            const operations = [];

            if (document.getElementById('resize-check').checked) {
                operations.push({
                    name: 'resize_image',
                    params: {
                        width: parseInt(document.getElementById('resize-width').value),
                        height: parseInt(document.getElementById('resize-height').value)
                    }
                });
            }

            if (document.getElementById('denoise-check').checked) {
                operations.push({
                    name: 'denoise_image',
                    params: {
                        strength: parseInt(document.getElementById('denoise-strength').value)
                    }
                });
            }

            if (document.getElementById('brightness-contrast-check').checked) {
                operations.push({
                    name: 'adjust_brightness_contrast',
                    params: {
                        brightness: parseInt(document.getElementById('brightness').value),
                        contrast: parseFloat(document.getElementById('contrast').value) / 10
                    }
                });
            }

            if (document.getElementById('sharpen-check').checked) {
                operations.push({
                    name: 'sharpen_image',
                    params: {
                        amount: parseFloat(document.getElementById('sharpen-amount').value) / 10
                    }
                });
            }

            if (operations.length === 0) {
                alert('请至少选择一个预处理操作');
                return;
            }

            // 创建表单数据
            const formData = new FormData();
            formData.append('image', imageFile);
            formData.append('operations', JSON.stringify(operations));

            // 显示原始图像
            const originalImage = document.getElementById('original-image');
            const reader = new FileReader();
            reader.onload = function(e) {
                originalImage.src = e.target.result;
            };
            reader.readAsDataURL(imageFile);

            // 发送请求
            fetch(`${API_URL}/opencv/preprocess`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || '处理图像失败'); });
                }
                return response.blob();
            })
            .then(blob => {
                // 显示处理后的图像
                const processedImage = document.getElementById('processed-image');
                const downloadLink = document.getElementById('download-processed');

                const url = window.memoryManager.createObjectURL(blob);
                processedImage.src = url;
                downloadLink.href = url;
                downloadLink.download = 'processed_' + imageFile.name;
                
                // 在图像加载完成后释放旧URL（如果有）
                processedImage.onload = function() {
                    // 延迟释放，确保图像已加载
                    setTimeout(() => {
                        if (processedImage.dataset.oldUrl) {
                            window.memoryManager.revokeObjectURL(processedImage.dataset.oldUrl);
                        }
                        processedImage.dataset.oldUrl = url;
                    }, 1000);
                };

                // 显示结果区域
                document.getElementById('preprocess-result').style.display = 'block';
            })
            .catch(error => {
                alert('错误: ' + error.message);
            });
        });
    }

    // 2. 图像分割表单
    const segmentationMethod = document.getElementById('segmentation-method');
    if (segmentationMethod) {
        segmentationMethod.addEventListener('change', function() {
            const numSegmentsContainer = document.getElementById('num-segments-container');
            numSegmentsContainer.style.display = this.value === 'kmeans' ? 'block' : 'none';
        });
    }

    const segmentationForm = document.getElementById('segmentation-form');
    if (segmentationForm) {
        segmentationForm.addEventListener('submit', function(event) {
            // 阻止表单的默认提交行为
            event.preventDefault();
            console.log('Segment image button clicked');

            const imageFile = document.getElementById('segmentation-image-upload').files[0];
            if (!imageFile) {
                alert('请选择图像文件');
                return;
            }

            // 创建表单数据
            const formData = new FormData();
            formData.append('image', imageFile);
            formData.append('method', document.getElementById('segmentation-method').value);
            formData.append('num_segments', document.getElementById('num-segments').value);

            // 显示原始图像
            const originalImage = document.getElementById('original-segmentation-image');
            const reader = new FileReader();
            reader.onload = function(e) {
                originalImage.src = e.target.result;
            };
            reader.readAsDataURL(imageFile);

            // 发送请求
            fetch(`${API_URL}/opencv/segment-image`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || '图像分割失败'); });
                }
                return response.blob();
            })
            .then(blob => {
                // 显示分割后的图像
                const segmentedImage = document.getElementById('segmented-image');
                const downloadLink = document.getElementById('download-segmented');

                const url = window.memoryManager.createObjectURL(blob);
                segmentedImage.src = url;
                downloadLink.href = url;
                downloadLink.download = 'segmented_' + imageFile.name;
                
                // 在图像加载完成后释放旧URL（如果有）
                segmentedImage.onload = function() {
                    // 延迟释放，确保图像已加载
                    setTimeout(() => {
                        if (segmentedImage.dataset.oldUrl) {
                            window.memoryManager.revokeObjectURL(segmentedImage.dataset.oldUrl);
                        }
                        segmentedImage.dataset.oldUrl = url;
                    }, 1000);
                };

                // 显示结果区域
                document.getElementById('segmentation-result').style.display = 'block';
            })
            .catch(error => {
                alert('错误: ' + error.message);
            });
        });
    }

    // 3. 特征提取表单
    const extractFeaturesForm = document.getElementById('extract-features-form');
    if (extractFeaturesForm) {
        extractFeaturesForm.addEventListener('submit', function(event) {
            // 阻止表单的默认提交行为
            event.preventDefault();
            console.log('Extract features button clicked');

            const imageFile = document.getElementById('features-image-upload').files[0];
            if (!imageFile) {
                alert('请选择图像文件');
                return;
            }

            // 创建表单数据
            const formData = new FormData();
            formData.append('image', imageFile);
            formData.append('method', document.getElementById('feature-method').value);
            formData.append('max_features', document.getElementById('max-features').value);

            // 发送请求
            fetch(`${API_URL}/opencv/extract-features`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || '特征提取失败'); });
                }
                return response.json();
            })
            .then(data => {
                // 显示特征提取结果
                if (data) {
                    document.getElementById('features-image').src = data.result_image || '';
                    document.getElementById('feature-count').textContent = data.feature_count || '0';
                    document.getElementById('feature-method-used').textContent = data.method || '';
                } else {
                    console.error('特征提取响应数据格式错误:', data);
                }

                // 显示结果区域
                document.getElementById('extract-features-result').style.display = 'block';
            })
            .catch(error => {
                alert('错误: ' + error.message);
            });
        });
    }

    // 4. 特征匹配表单
    const matchFeaturesForm = document.getElementById('match-features-form');
    if (matchFeaturesForm) {
        matchFeaturesForm.addEventListener('submit', function(event) {
            // 阻止表单的默认提交行为
            event.preventDefault();
            console.log('Match features button clicked');

            const image1File = document.getElementById('match-image1-upload').files[0];
            const image2File = document.getElementById('match-image2-upload').files[0];
            if (!image1File || !image2File) {
                alert('请选择两张图像文件');
                return;
            }

            // 创建表单数据
            const formData = new FormData();
            formData.append('image1', image1File);
            formData.append('image2', image2File);
            formData.append('method', document.getElementById('match-feature-method').value);
            formData.append('max_features', document.getElementById('match-max-features').value);
            formData.append('match_method', document.getElementById('match-method').value);

            // 发送请求
            fetch(`${API_URL}/opencv/match-features`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || '特征匹配失败'); });
                }
                return response.json();
            })
            .then(data => {
                // 显示特征匹配结果
                if (data) {
                    document.getElementById('matches-image').src = data.result_image || '';
                    document.getElementById('match-count').textContent = data.match_count || '0';
                    document.getElementById('feature-count1').textContent = data.feature_count1 || '0';
                    document.getElementById('feature-count2').textContent = data.feature_count2 || '0';
                    document.getElementById('match-feature-method-used').textContent = data.method || '';
                    document.getElementById('match-method-used').textContent = data.match_method || '';
                } else {
                    console.error('特征匹配响应数据格式错误:', data);
                }

                // 显示结果区域
                document.getElementById('match-features-result').style.display = 'block';
            })
            .catch(error => {
                alert('错误: ' + error.message);
            });
        });
    }

    // 5. 数据增强表单
    const augmentForm = document.getElementById('augment-form');
    if (augmentForm) {
        augmentForm.addEventListener('submit', function(event) {
            // 阻止表单的默认提交行为
            event.preventDefault();
            console.log('Augment button clicked');

            const datasetPath = document.getElementById('dataset-path').value;
            if (!datasetPath) {
                alert('请选择数据集');
                return;
            }

            // 构建增强选项
            const augmentationOptions = {
                flip: document.getElementById('flip-check').checked,
                rotate: document.getElementById('rotate-check').checked ? {
                    angles: [90, 180, 270]
                } : false,
                noise: document.getElementById('noise-check').checked ? {
                    types: ['gaussian'],
                    amount: 0.05
                } : false,
                brightness_contrast: document.getElementById('brightness-contrast-aug-check').checked ? {
                    brightness: [-20, 20],
                    contrast: [0.8, 1.2]
                } : false,
                perspective: document.getElementById('perspective-check').checked,
                perspective_strength: 0.2
            };

            // 创建表单数据
            const formData = new FormData();
            formData.append('dataset_path', datasetPath);
            formData.append('augmentation_options', JSON.stringify(augmentationOptions));
            formData.append('multiplier', document.getElementById('multiplier').value);

            // 加载提示已禁用
            // document.getElementById('opencv-loading-overlay').style.display = 'block';
            // document.getElementById('opencv-loading-text').textContent = '正在准备数据增强...';
            // document.getElementById('opencv-loading-details').textContent = '请稍候，正在准备数据集并启动增强任务';

            // 发送请求
            fetch(`${API_URL}/opencv/augment-dataset`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || '启动数据增强任务失败'); });
                }
                return response.json();
            })
            .then(data => {
                // 显示任务信息
                if (data) {
                    document.getElementById('augmentation-id').textContent = data.augmentation_id || '';
                    document.getElementById('output-dir').textContent = data.output_dir || '';
                } else {
                    console.error('数据增强响应数据格式错误:', data);
                    document.getElementById('augmentation-id').textContent = '未知';
                    document.getElementById('output-dir').textContent = '未知';
                }

                // 显示结果区域
                document.getElementById('augment-result').style.display = 'block';
                document.getElementById('augment-stats').style.display = 'none';

                // 加载提示已禁用
                // document.getElementById('opencv-loading-overlay').style.display = 'none';

                // 开始轮询任务状态
                const augmentationId = data.augmentation_id;
                const statusInterval = window.memoryManager.setInterval(() => {
                    fetch(`${API_URL}/opencv/augmentation-status/${augmentationId}`)
                    .then(response => response.json())
                    .then(statusData => {
                        if (statusData) {
                            document.getElementById('augment-status-text').textContent = statusData.status || '未知';

                            if (statusData.status === 'completed' && statusData.stats) {
                                window.memoryManager.clearInterval(statusInterval);
                                document.getElementById('augment-progress').style.width = '100%';

                                // 显示统计信息
                                document.getElementById('original-images-count').textContent = statusData.stats.original_images || '0';
                                document.getElementById('augmented-images-count').textContent = statusData.stats.augmented_images || '0';
                                document.getElementById('total-images-count').textContent = statusData.stats.total_images || '0';

                                // 显示应用的增强
                                const appliedAugmentations = document.getElementById('applied-augmentations');
                                appliedAugmentations.innerHTML = '';

                                if (statusData.stats.augmentations_applied) {
                                    for (const [key, value] of Object.entries(statusData.stats.augmentations_applied)) {
                                        const li = document.createElement('li');
                                        li.textContent = `${key}: ${value} 张图像`;
                                        appliedAugmentations.appendChild(li);
                                    }
                                }

                                document.getElementById('augment-stats').style.display = 'block';
                            } else if (statusData.status === 'failed') {
                                window.memoryManager.clearInterval(statusInterval);
                                document.getElementById('augment-progress').style.width = '100%';
                                document.getElementById('augment-progress').classList.remove('bg-info');
                                document.getElementById('augment-progress').classList.add('bg-danger');
                                document.getElementById('augment-status-text').textContent = '失败: ' + statusData.error;
                            } else {
                                // 更新进度条
                                document.getElementById('augment-progress').style.width = '50%';
                            }
                        }
                    })
                    .catch(error => {
                        console.error('获取任务状态失败:', error);
                        // 在多次失败后停止轮询
                        window.memoryManager.clearInterval(statusInterval);
                    });
                }, 2000);
            })
            .catch(error => {
                // 加载提示已禁用
                // document.getElementById('opencv-loading-overlay').style.display = 'none';
                alert('错误: ' + error.message);
            });
        });
    }

    // 高级数据增强相关事件

    // CutMix Alpha 参数滑块
    const cutmixAlpha = document.getElementById('cutmix-alpha');
    const cutmixAlphaValue = document.getElementById('cutmix-alpha-value');
    if (cutmixAlpha && cutmixAlphaValue) {
        cutmixAlpha.addEventListener('input', function() {
            cutmixAlphaValue.textContent = this.value;
        });
    }

    // MixUp Alpha 参数滑块
    const mixupAlpha = document.getElementById('mixup-alpha');
    const mixupAlphaValue = document.getElementById('mixup-alpha-value');
    if (mixupAlpha && mixupAlphaValue) {
        mixupAlpha.addEventListener('input', function() {
            mixupAlphaValue.textContent = this.value;
        });
    }

    // 天气强度滑块
    const weatherIntensity = document.getElementById('weather-intensity');
    const weatherIntensityValue = document.getElementById('weather-intensity-value');
    if (weatherIntensity && weatherIntensityValue) {
        weatherIntensity.addEventListener('input', function() {
            weatherIntensityValue.textContent = this.value;
        });
    }

    // CutMix 表单提交
    const cutmixForm = document.getElementById('cutmix-form');
    if (cutmixForm) {
        cutmixForm.addEventListener('submit', function(event) {
            event.preventDefault();

            // 获取表单数据
            const formData = new FormData(this);

            // 显示原始图像
            const image1 = document.getElementById('cutmix-image1').files[0];
            const image2 = document.getElementById('cutmix-image2').files[0];

            if (!image1 || !image2) {
                alert('请选择两张图像');
                return;
            }

            // 显示原始图像预览
            const reader1 = new FileReader();
            reader1.onload = function(e) {
                document.getElementById('cutmix-original1').src = e.target.result;
            };
            reader1.readAsDataURL(image1);

            const reader2 = new FileReader();
            reader2.onload = function(e) {
                document.getElementById('cutmix-original2').src = e.target.result;
            };
            reader2.readAsDataURL(image2);

            // 发送请求
            fetch(`${API_URL}/opencv/advanced-augmentation`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || 'CutMix 增强失败'); });
                }
                return response.json();
            })
            .then(data => {
                // 显示结果
                document.getElementById('cutmix-result').style.display = 'block';
                document.getElementById('cutmix-output').src = data.output_path;
                document.getElementById('download-cutmix').href = data.output_path;
            })
            .catch(error => {
                alert('错误: ' + error.message);
            });
        });
    }

    // MixUp 表单提交
    const mixupForm = document.getElementById('mixup-form');
    if (mixupForm) {
        mixupForm.addEventListener('submit', function(event) {
            event.preventDefault();

            // 获取表单数据
            const formData = new FormData(this);

            // 显示原始图像
            const image1 = document.getElementById('mixup-image1').files[0];
            const image2 = document.getElementById('mixup-image2').files[0];

            if (!image1 || !image2) {
                alert('请选择两张图像');
                return;
            }

            // 显示原始图像预览
            const reader1 = new FileReader();
            reader1.onload = function(e) {
                document.getElementById('mixup-original1').src = e.target.result;
            };
            reader1.readAsDataURL(image1);

            const reader2 = new FileReader();
            reader2.onload = function(e) {
                document.getElementById('mixup-original2').src = e.target.result;
            };
            reader2.readAsDataURL(image2);

            // 发送请求
            fetch(`${API_URL}/opencv/advanced-augmentation`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || 'MixUp 增强失败'); });
                }
                return response.json();
            })
            .then(data => {
                // 显示结果
                document.getElementById('mixup-result').style.display = 'block';
                document.getElementById('mixup-output').src = data.output_path;
                document.getElementById('download-mixup').href = data.output_path;
            })
            .catch(error => {
                alert('错误: ' + error.message);
            });
        });
    }

    // Mosaic 表单提交
    const mosaicForm = document.getElementById('mosaic-form');
    if (mosaicForm) {
        mosaicForm.addEventListener('submit', function(event) {
            event.preventDefault();

            // 获取表单数据
            const formData = new FormData(this);

            // 检查是否选择了四张图像
            const image1 = document.getElementById('mosaic-image1').files[0];
            const image2 = document.getElementById('mosaic-image2').files[0];
            const image3 = document.getElementById('mosaic-image3').files[0];
            const image4 = document.getElementById('mosaic-image4').files[0];

            if (!image1 || !image2 || !image3 || !image4) {
                alert('请选择四张图像');
                return;
            }

            // 发送请求
            fetch(`${API_URL}/opencv/advanced-augmentation`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || 'Mosaic 增强失败'); });
                }
                return response.json();
            })
            .then(data => {
                // 显示结果
                document.getElementById('mosaic-result').style.display = 'block';
                document.getElementById('mosaic-output').src = data.output_path;
                document.getElementById('download-mosaic').href = data.output_path;
            })
            .catch(error => {
                alert('错误: ' + error.message);
            });
        });
    }

    // 天气模拟表单提交
    const weatherForm = document.getElementById('weather-form');
    if (weatherForm) {
        weatherForm.addEventListener('submit', function(event) {
            event.preventDefault();

            // 获取表单数据
            const formData = new FormData(this);

            // 显示原始图像
            const image = document.getElementById('weather-image').files[0];

            if (!image) {
                alert('请选择图像');
                return;
            }

            // 显示原始图像预览
            const reader = new FileReader();
            reader.onload = function(e) {
                document.getElementById('weather-original').src = e.target.result;
            };
            reader.readAsDataURL(image);

            // 发送请求
            fetch(`${API_URL}/opencv/advanced-augmentation`, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.detail || '天气模拟增强失败'); });
                }
                return response.json();
            })
            .then(data => {
                // 显示结果
                document.getElementById('weather-result').style.display = 'block';
                document.getElementById('weather-output').src = data.output_path;
                document.getElementById('download-weather').href = data.output_path;
            })
            .catch(error => {
                alert('错误: ' + error.message);
            });
        });
    }

    console.log('OpenCV events bound successfully');

    // 添加调试信息
    console.log('Process image button:', document.getElementById('process-image-btn'));
    console.log('Segment image button:', document.getElementById('segment-image-btn'));
    console.log('Extract features button:', document.getElementById('extract-features-btn'));
    console.log('Match features button:', document.getElementById('match-features-btn'));
    console.log('Augment button:', document.getElementById('augment-btn'));
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

    fetch(`${API_URL}/datasets/`)
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

    // 绑定添加数据集按钮
    const addButton = document.getElementById('add-dataset-btn');
    if (addButton) {
        console.log('Found add-dataset-btn, binding click event');
        addButton.addEventListener('click', showAddDatasetModal);
    } else {
        console.error('add-dataset-btn not found');
    }

    // 绑定导入本地数据集按钮
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

    // 绑定COCO格式JSON转换按钮
    const convertCocoButton = document.getElementById('convert-coco-btn');
    if (convertCocoButton) {
        console.log('Found convert-coco-btn, binding click event');
        convertCocoButton.onclick = function() {
            console.log('Convert COCO button clicked');
            showConvertCocoModal();
            return false;
        };
    } else {
        console.error('convert-coco-btn not found');
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
        xhr.open('POST', `${API_URL}/datasets/`, true);

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
                statusCheckInterval = window.memoryManager.setInterval(async () => {
                    try {
                        const statusResponse = await fetch(`${API_URL}/datasets/upload-status/${fileId}`);
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
                            window.memoryManager.clearInterval(statusCheckInterval);
                            modal.hide();
                            loadDatasets();
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

// 绑定比例滑块
function bindRatioSliders(trainId, valId, testId) {
    const trainSlider = document.getElementById(trainId);
    const valSlider = document.getElementById(valId);
    const testSlider = document.getElementById(testId);
    const trainValue = document.getElementById(`${trainId}-value`);
    const valValue = document.getElementById(`${valId}-value`);
    const testValue = document.getElementById(`${testId}-value`);

    if (!trainSlider || !valSlider || !testSlider || !trainValue || !valValue || !testValue) {
        console.error('Ratio sliders or value elements not found');
        return;
    }

    // 更新显示值
    function updateValues() {
        trainValue.textContent = `${Math.round(trainSlider.value * 100)}%`;
        valValue.textContent = `${Math.round(valSlider.value * 100)}%`;
        testValue.textContent = `${Math.round(testSlider.value * 100)}%`;
    }

    // 调整比例，确保总和为1
    function adjustRatios(changedSlider) {
        const train = parseFloat(trainSlider.value);
        const val = parseFloat(valSlider.value);
        const test = parseFloat(testSlider.value);
        const total = train + val + test;

        if (Math.abs(total - 1.0) > 0.001) {
            if (changedSlider === 'train') {
                // 调整验证集和测试集
                const remaining = 1.0 - train;
                const ratio = remaining > 0 ? (val + test) / remaining : 0;
                if (ratio > 0) {
                    valSlider.value = (val / (val + test)) * remaining;
                    testSlider.value = remaining - valSlider.value;
                } else {
                    valSlider.value = remaining / 2;
                    testSlider.value = remaining / 2;
                }
            } else if (changedSlider === 'val') {
                // 调整测试集
                testSlider.value = 1.0 - train - val;
            } else if (changedSlider === 'test') {
                // 调整验证集
                valSlider.value = 1.0 - train - test;
            }
        }

        updateValues();
    }

    // 绑定事件
    trainSlider.addEventListener('input', function() {
        adjustRatios('train');
    });

    valSlider.addEventListener('input', function() {
        adjustRatios('val');
    });

    testSlider.addEventListener('input', function() {
        adjustRatios('test');
    });

    // 初始化显示
    updateValues();
}

// 显示COCO格式JSON转换模态框
function showConvertCocoModal() {
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
            bindRatioSliders('coco-train-ratio', 'coco-val-ratio', 'coco-test-ratio');
        } else {
            console.error('COCO split elements not found:', { splitCheckbox, splitOptions });
        }

        // 绑定提交按钮事件
        if (modalSubmit) {
            modalSubmit.onclick = submitConvertCoco;
        }

        // 绑定打开文件夹按钮事件
        const openFolderBtn = document.getElementById('open-output-folder');
        if (openFolderBtn) {
            openFolderBtn.addEventListener('click', function() {
                const outputPath = document.getElementById('coco-output-path');
                if (outputPath && outputPath.value) {
                    // 使用API打开文件夹
                    fetch(`${API_URL}/datasets/open-folder`, {
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
            downloadZipBtn.addEventListener('click', function() {
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
async function submitConvertCoco() {
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
        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progressBar.style.width = percentComplete + '%';
                progressBar.textContent = Math.round(percentComplete) + '%';
                statusContainer.textContent = `正在上传COCO数据集文件... ${Math.round(percentComplete)}%`;
            }
        };

        // 上传完成事件
        xhr.onload = function() {
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
        xhr.onerror = function() {
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
function showImportCocoDatasetModal() {
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
                    bindRatioSliders('coco-train-ratio', 'coco-val-ratio', 'coco-test-ratio');
                } else {
                    console.error('COCO split elements not found:', { splitCheckbox, splitOptions });
                }

                // 绑定提交按钮事件
                if (modalSubmit) {
                    console.log('Binding submit button click event');
                    modalSubmit.onclick = function() {
                        console.log('Submit button clicked');
                        submitImportCocoDataset();
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
async function submitImportCocoDataset() {
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
        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progressBar.style.width = percentComplete + '%';
                progressBar.textContent = Math.round(percentComplete) + '%';
                statusContainer.textContent = `正在上传COCO数据集文件... ${Math.round(percentComplete)}%`;
            }
        };

        // 上传完成事件
        xhr.onload = function() {
            if (xhr.status === 200 || xhr.status === 201) {
                // 上传成功
                progressBar.style.width = '100%';
                progressBar.textContent = '100%';
                statusContainer.textContent = '导入成功！正在刷新数据集列表...';

                // 关闭模态框
                modal.hide();

                // 重新加载数据集列表
                loadDatasets();

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
        xhr.onerror = function() {
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
    fetch(`${API_URL}/models/`)
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
                    <td style="display: none;">${model.path}</td><!-- 路径列默认隐藏，可通过DEBUG模式开启显示 -->
                    <td>
                        <div class="btn-group" role="group">
                            <button class="btn btn-sm btn-primary download-model-pt" data-id="${model.id}" title="下载PT格式模型">
                                <i class="bi bi-download"></i> PT
                            </button>
                            <button class="btn btn-sm btn-secondary download-model-onnx" data-id="${model.id}" title="转换并下载ONNX格式模型">
                                <i class="bi bi-exchange"></i> ONNX
                            </button>
                            <button class="btn btn-sm btn-danger delete-model" data-id="${model.id}">删除</button>
                        </div>
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

            // 绑定PT模型下载按钮事件
            document.querySelectorAll('.download-model-pt').forEach(button => {
                button.addEventListener('click', function() {
                    const modelId = this.getAttribute('data-id');
                    const downloadUrl = `${API_URL}/models/${modelId}/download/pt`;
                    console.log('PT模型下载URL:', downloadUrl);
                    window.location.href = downloadUrl;
                });
            });

            // 绑定ONNX模型下载按钮事件
            document.querySelectorAll('.download-model-onnx').forEach(button => {
                button.addEventListener('click', function() {
                    const modelId = this.getAttribute('data-id');
                    const downloadUrl = `${API_URL}/models/${modelId}/download/onnx`;
                    console.log('ONNX模型下载URL:', downloadUrl);
                    // 显示加载指示器
                    this.innerHTML = '<i class="bi bi-arrow-clockwise spinner-border spinner-border-sm"></i> 转换中...';
                    this.disabled = true;
                    
                    // 开始下载
                    window.location.href = downloadUrl;
                    
                    // 设置一个超时，恢复按钮状态（即使下载中断）
                    setTimeout(() => {
                        this.innerHTML = '<i class="bi bi-exchange"></i> ONNX';
                        this.disabled = false;
                    }, 30000); // 30秒超时
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
    
    const loadDefaultModelsButton = document.getElementById('load-default-models-btn');
    if (loadDefaultModelsButton) {
        loadDefaultModelsButton.addEventListener('click', loadDefaultModels);
    }
}

// 加载预置模型
function loadDefaultModels() {
    if (confirm('确定要加载预置模型吗？这将会导入models目录和项目根目录下的.pt模型文件到系统中。\n注意：已存在的模型将被跳过。')) {
        // 显示加载中提示
        showLoadingOverlay('正在加载预置模型，请稍候...');
        
        fetch(`${API_URL}/models/import-default`, {
            method: 'POST'
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || '加载预置模型失败');
                });
            }
            return response.json();
        })
        .then(data => {
            // 隐藏加载中提示
            hideLoadingOverlay();
            
            // 显示成功消息
            if (data.success) {
                const message = `加载预置模型成功！\n共找到 ${data.total} 个模型文件，导入了 ${data.imported} 个新模型。`;
                alert(message);
                // 重新加载模型列表
                loadModels();
            } else {
                alert('加载预置模型失败：' + (data.message || '未知错误'));
            }
        })
        .catch(error => {
            // 隐藏加载中提示
            hideLoadingOverlay();
            alert('加载预置模型失败：' + error.message);
        });
    }
}

// 显示加载中覆盖层
function showLoadingOverlay(message) {
    // 检查是否已存在加载覆盖层
    let overlay = document.getElementById('loading-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            flex-direction: column;
        `;
        
        const spinner = document.createElement('div');
        spinner.className = 'spinner-border text-primary';
        spinner.style.width = '3rem';
        spinner.style.height = '3rem';
        spinner.role = 'status';
        
        const span = document.createElement('span');
        span.className = 'sr-only';
        span.textContent = '加载中...';
        
        const text = document.createElement('div');
        text.id = 'loading-text';
        text.style.color = 'white';
        text.style.marginTop = '1rem';
        text.style.fontSize = '1.2rem';
        
        spinner.appendChild(span);
        overlay.appendChild(spinner);
        overlay.appendChild(text);
        document.body.appendChild(overlay);
    }
    
    // 设置加载文本
    const loadingText = document.getElementById('loading-text');
    if (loadingText) {
        loadingText.textContent = message || '加载中...';
    }
    
    overlay.style.display = 'flex';
}

// 隐藏加载中覆盖层
function hideLoadingOverlay() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
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
    xhr.open('POST', `${API_URL}/models/`, true);

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
                    <td><span class="badge ${getStatusBadgeClass(task.status)}">${getStatusText(task.status)}</span></td>
                    <td>${task.start_time ? new Date(task.start_time).toLocaleString() : '-'}</td>
                    <td>${task.end_time ? new Date(task.end_time).toLocaleString() : '-'}</td>
                    <td>
                        ${task.status === 'pending' ? `<button class="btn btn-sm btn-success start-training" data-id="${task.id}">开始训练</button>` : ''}
                        ${task.status === 'running' || task.status === 'training' || task.status === 'downloading_model' || task.status === 'pending' ? `<button class="btn btn-sm btn-warning stop-training" data-id="${task.id}">停止训练</button>` : ''}
                        ${(task.status === 'cancelled' || task.status === 'failed') ? `<button class="btn btn-sm btn-success resume-training" data-id="${task.id}">继续训练</button>` : ''}
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

// 训练任务列表的自动刷新定时器
let trainingTasksRefreshInterval = null;

// 启动训练任务列表的自动刷新
function startTrainingTasksAutoRefresh() {
    // 清除已有定时器
    if (trainingTasksRefreshInterval) {
        clearInterval(trainingTasksRefreshInterval);
    }
    
    // 每10秒自动刷新一次
    trainingTasksRefreshInterval = setInterval(loadTrainingTasks, 10000);
}

// 停止训练任务列表的自动刷新
function stopTrainingTasksAutoRefresh() {
    if (trainingTasksRefreshInterval) {
        clearInterval(trainingTasksRefreshInterval);
        trainingTasksRefreshInterval = null;
    }
}

// 绑定训练页面事件
function bindTrainingEvents() {
    // 启动自动刷新
    startTrainingTasksAutoRefresh();
    
    const addButton = document.getElementById('add-training-btn');
    if (addButton) {
        addButton.addEventListener('click', showAddTrainingModal);
    }

    // 绑定重启TensorBoard按钮事件
    const restartTensorboardBtn = document.getElementById('restart-tensorboard-btn');
    if (restartTensorboardBtn) {
        restartTensorboardBtn.addEventListener('click', function() {
            restartTensorBoard();
        });
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

    // 绑定获取昇腾NPU信息按钮事件
    const getAscendInfoBtn = document.getElementById('get-ascend-info');
    const ascendInfoDiv = document.getElementById('ascend-info');
    const ascendSelect = document.getElementById('ascend-select');
    const ascendMemoryInput = document.getElementById('ascend-memory');
    const ascendMemoryInfoDiv = document.getElementById('ascend-memory-info');
    const validateAscendMemoryBtn = document.getElementById('validate-ascend-memory');
    const ascendValidationResultDiv = document.getElementById('ascend-validation-result');

    if (getAscendInfoBtn) {
        getAscendInfoBtn.addEventListener('click', async function() {
            try {
                // 显示加载中状态
                getAscendInfoBtn.disabled = true;
                getAscendInfoBtn.textContent = '获取中...';

                const response = await fetch(`${API_URL}/training/ascend-info`);
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
        validateAscendMemoryBtn.addEventListener('click', async function() {
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

                const response = await fetch(`${API_URL}/training/validate-ascend-memory`, {
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
    modalSubmit.onclick = submitAddTraining;
}

// 加载数据集选项
function loadDatasetOptions() {
    fetch(`${API_URL}/datasets/`)
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
    fetch(`${API_URL}/models/`)
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
    } else if (deviceTypeSelect.value === 'gpu') {
        // 获取GPU显存和GPU ID
        hardwareConfig.gpu_memory = parseInt(gpuMemoryInput.value);

        // 如果用户选择了特定GPU，添加GPU ID
        const gpuSelect = document.getElementById('gpu-select');
        if (gpuSelect && gpuSelect.value) {
            hardwareConfig.gpu_index = parseInt(gpuSelect.value);
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
                const tbWindow = window.open(data.url, '_blank');

                // 检查窗口是否被阻止
                if (!tbWindow || tbWindow.closed || typeof tbWindow.closed === 'undefined') {
                    // 窗口被阻止，显示提示
                    showModal('TensorBoard打开失败',
                        `<p>浏览器阻止了打开TensorBoard窗口。请允许弹出窗口，或者手动访问以下链接：</p>
                        <p><a href="${data.url}" target="_blank">${data.url}</a></p>
                        <p>如果TensorBoard无法显示数据，请尝试以下操作：</p>
                        <div class="d-flex justify-content-center mt-3">
                            <button id="restart-tensorboard-btn" class="btn btn-warning me-2">重启TensorBoard服务</button>
                            <button id="open-logs-folder-btn" class="btn btn-info">打开日志目录</button>
                        </div>`,
                        function() {
                            // 绑定重启按钮事件
                            document.getElementById('restart-tensorboard-btn').addEventListener('click', function() {
                                restartTensorBoard();
                            });

                            // 绑定打开日志目录按钮事件
                            document.getElementById('open-logs-folder-btn').addEventListener('click', function() {
                                openTensorBoardLogsFolder(taskId);
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
            showModal('TensorBoard打开失败',
                `<p>打开TensorBoard时发生错误: ${error.message}</p>
                <p>请尝试重启TensorBoard服务：</p>
                <button id="restart-tensorboard-btn" class="btn btn-warning">重启TensorBoard服务</button>`,
                function() {
                    // 绑定重启按钮事件
                    document.getElementById('restart-tensorboard-btn').addEventListener('click', function() {
                        restartTensorBoard();
                    });
                }
            );
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

// 显示模态框
function showModal(title, content, callback) {
    // 创建模态框
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
    window.onclick = function(event) {
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
function showToast(message, type = 'info', duration = 3000) {
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
            hideToast(toast);
        }, duration);
    }

    return toast;
}

// 隐藏Toast提示
function hideToast(toast) {
    if (document.body.contains(toast)) {
        document.body.removeChild(toast);
    }
}

// 重启TensorBoard服务
function restartTensorBoard() {
    console.log('Restarting TensorBoard service');

    // 显示加载提示
    const loadingToast = showToast('正在重启TensorBoard服务...', 'info', 10000);

    // 调用重启API
    fetch(`${API_URL}/training/restart-tensorboard`, {
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
        hideToast(loadingToast);

        if (data.success) {
            showToast('TensorBoard服务已重启，请重新打开TensorBoard', 'success', 5000);
        } else {
            showToast('TensorBoard服务重启失败: ' + data.message, 'error', 5000);
        }
    })
    .catch(error => {
        // 隐藏加载提示
        hideToast(loadingToast);

        console.error('Error restarting TensorBoard:', error);
        showToast('重启TensorBoard服务失败: ' + error.message, 'error', 5000);
    });
}

// 打开TensorBoard日志目录
function openTensorBoardLogsFolder(taskId) {
    console.log('Opening TensorBoard logs folder for task:', taskId);

    // 显示加载提示
    const loadingToast = showToast('正在打开日志目录...', 'info', 10000);

    // 调用API获取日志目录路径
    fetch(`${API_URL}/training/${taskId}/logs-folder`)
    .then(response => {
        if (!response.ok) {
            throw new Error('获取日志目录路径失败');
        }
        return response.json();
    })
    .then(data => {
        // 隐藏加载提示
        hideToast(loadingToast);

        if (data.path) {
            // 显示成功提示
            showToast('已打开日志目录', 'success', 3000);
        } else {
            throw new Error('日志目录路径不可用');
        }
    })
    .catch(error => {
        // 隐藏加载提示
        hideToast(loadingToast);

        console.error('Error opening logs folder:', error);
        showToast('打开日志目录失败: ' + error.message, 'error', 5000);
    });
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
    window.onclick = function(event) {
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
                window.onclick = function(event) {
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

// ==================== 验证功能 ====================

// 加载检测表单
function loadDetectionForm() {
    // 加载模型选项
    fetch(`${API_URL}/models/`)
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
        case 'training':
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

// ==================== 在线标注功能 ====================

// 加载标注页面
function loadAnnotationPage() {
    console.log('Loading annotation page...');
    
    // 加载标注项目列表
    loadAnnotationProjects();
    
    // 绑定标注页面事件
    bindAnnotationEvents();
}

// 加载标注项目列表
function loadAnnotationProjects() {
    fetch(`${API_URL}/annotation/projects/`)
        .then(response => response.json())
        .then(projects => {
            const tableBody = document.getElementById('annotation-projects-table-body');
            if (!tableBody) {
                console.error('annotation-projects-table-body element not found');
                return;
            }

            tableBody.innerHTML = '';

            if (projects.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="8" class="text-center">暂无标注项目</td></tr>';
                return;
            }

            projects.forEach(project => {
                const row = document.createElement('tr');
                
                // 获取项目统计信息
                fetch(`${API_URL}/annotation/projects/${project.id}/stats`)
                    .then(response => response.json())
                    .then(stats => {
                        const progressPercentage = stats.progress_percentage || 0;
                        
                        row.innerHTML = `
                            <td>${project.name}</td>
                            <td>${project.description || '-'}</td>
                            <td>${project.classes.length}</td>
                            <td>${stats.total_images || 0}</td>
                            <td>${stats.completed_images || 0}</td>
                            <td>
                                <div class="progress" style="width: 100px;">
                                    <div class="progress-bar" role="progressbar" style="width: ${progressPercentage}%" aria-valuenow="${progressPercentage}" aria-valuemin="0" aria-valuemax="100">
                                        ${Math.round(progressPercentage)}%
                                    </div>
                                </div>
                            </td>
                            <td><span class="badge ${getStatusBadgeClass(project.status)}">${getStatusText(project.status)}</span></td>
                            <td>
                                <div class="btn-group">
                                    <a href="/static/annotation.html?project_id=${project.id}" target="_blank" class="btn btn-sm btn-primary">开始标注</a>
                                    <button class="btn btn-sm btn-info" onclick="scanProjectImages('${project.id}')">扫描图片</button>
                                    <button class="btn btn-sm btn-success" onclick="exportAnnotations('${project.id}')">导出标注</button>
                                    <button class="btn btn-sm btn-warning" onclick="exportToDataset('${project.id}')">导出为数据集</button>
                                    <button class="btn btn-sm btn-danger" onclick="deleteAnnotationProject('${project.id}')">删除</button>
                                </div>
                            </td>
                        `;
                    })
                    .catch(error => {
                        console.error('Error loading project stats:', error);
                        row.innerHTML = `
                            <td>${project.name}</td>
                            <td>${project.description || '-'}</td>
                            <td>${project.classes.length}</td>
                            <td>-</td>
                            <td>-</td>
                            <td>-</td>
                            <td><span class="badge bg-secondary">未知</span></td>
                            <td>
                                <div class="btn-group">
                                    <a href="/static/annotation.html?project_id=${project.id}" target="_blank" class="btn btn-sm btn-primary">开始标注</a>
                                    <button class="btn btn-sm btn-info" onclick="scanProjectImages('${project.id}')">扫描图片</button>
                                    <button class="btn btn-sm btn-success" onclick="exportAnnotations('${project.id}')">导出</button>
                                    <button class="btn btn-sm btn-warning" onclick="exportToDataset('${project.id}')">导出为数据集</button>
                                    <button class="btn btn-sm btn-danger" onclick="deleteAnnotationProject('${project.id}')">删除</button>
                                </div>
                            </td>
                        `;
                    });
                
                tableBody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error loading annotation projects:', error);
            const tableBody = document.getElementById('annotation-projects-table-body');
            if (tableBody) {
                tableBody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">加载标注项目失败</td></tr>';
            }
        });
}

// 绑定标注页面事件
function bindAnnotationEvents() {
    const createProjectBtn = document.getElementById('create-annotation-project-btn');
    if (createProjectBtn) {
        createProjectBtn.addEventListener('click', showCreateAnnotationProjectModal);
    }
    
    const projectSelect = document.getElementById('annotation-project-select');
    if (projectSelect) {
        projectSelect.addEventListener('change', function() {
            if (this.value) {
                loadAnnotationProject(this.value);
            }
        });
    }
}

// 显示创建标注项目模态框
function showCreateAnnotationProjectModal() {
    const modalTitle = document.querySelector('.modal-title');
    const modalBody = document.querySelector('.modal-body');
    const modalSubmit = document.getElementById('modalSubmit');

    modalTitle.textContent = '创建标注项目';

    // 获取模板内容
    const template = document.getElementById('create-annotation-project-template');
    if (!template) {
        console.error('create-annotation-project-template not found');
        return;
    }

    modalBody.innerHTML = template.innerHTML;

    // 加载数据集选项
    loadDatasetOptionsForAnnotation();
    
    // 绑定图片来源选择事件
    bindImageSourceEvents();

    modal.show();

    modalSubmit.onclick = function() {
        submitCreateAnnotationProject();
    };
}

// 绑定图片来源选择事件
function bindImageSourceEvents() {
    const imageSourceRadios = document.querySelectorAll('input[name="image-source"]');
    const datasetContainer = document.getElementById('dataset-source-container');
    const directoryContainer = document.getElementById('directory-source-container');
    const uploadContainer = document.getElementById('upload-source-container');
    
    imageSourceRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            // 隐藏所有容器
            datasetContainer.style.display = 'none';
            directoryContainer.style.display = 'none';
            uploadContainer.style.display = 'none';
            
            // 显示选中的容器
            if (this.value === 'dataset') {
                datasetContainer.style.display = 'block';
            } else if (this.value === 'directory') {
                directoryContainer.style.display = 'block';
                // 绑定目录浏览按钮
                bindDirectoryBrowseButton();
            } else if (this.value === 'upload') {
                uploadContainer.style.display = 'block';
            }
        });
    });
    
    // 默认显示上传容器
    uploadContainer.style.display = 'block';
}

// 绑定目录浏览按钮
function bindDirectoryBrowseButton() {
    const browseBtn = document.getElementById('browse-image-directory-btn');
    const directoryInput = document.getElementById('annotation-image-directory');
    const scanResultDiv = document.getElementById('directory-scan-result');
    const imageCountSpan = document.getElementById('directory-image-count');
    
    if (browseBtn && !browseBtn.hasAttribute('data-bound')) {
        browseBtn.setAttribute('data-bound', 'true');
        browseBtn.addEventListener('click', function() {
            if (window.directoryBrowser) {
                window.directoryBrowser.show(function(selectedPath) {
                    directoryInput.value = selectedPath;
                    
                    // 扫描选中目录的图片
                    fetch(`/api/annotation/scan-directory-images?directory_path=${encodeURIComponent(selectedPath)}`)
                        .then(response => response.json())
                        .then(data => {
                            imageCountSpan.textContent = data.image_count;
                            scanResultDiv.style.display = 'block';
                            
                            if (data.is_valid) {
                                scanResultDiv.querySelector('.alert').className = 'alert alert-success';
                            } else {
                                scanResultDiv.querySelector('.alert').className = 'alert alert-warning';
                            }
                        })
                        .catch(error => {
                            console.error('扫描图片失败:', error);
                            scanResultDiv.style.display = 'none';
                        });
                });
            } else {
                alert('目录浏览器未加载，请刷新页面重试');
            }
        });
    }
}

// 提交创建标注项目
function submitCreateAnnotationProject() {
    const name = document.getElementById('annotation-project-name').value;
    const description = document.getElementById('annotation-project-description').value;
    const classesText = document.getElementById('annotation-classes').value;
    const imageSource = document.querySelector('input[name="image-source"]:checked').value;
    
    if (!name || !classesText) {
        alert('请填写项目名称和类别列表');
        return;
    }
    
    const classes = classesText.split('\n').filter(c => c.trim()).map(c => c.trim());
    
    if (imageSource === 'upload') {
        const zipFile = document.getElementById('annotation-images-zip').files[0];
        if (!zipFile) {
            alert('请选择图片ZIP文件');
            return;
        }
        createProjectWithImageUpload(name, description, classes, zipFile);
    } else {
        createProjectWithExistingImages(name, description, classes, imageSource);
    }
}

// 使用上传图片创建项目
function createProjectWithImageUpload(name, description, classes, zipFile) {
    const progressContainer = document.getElementById('annotation-upload-progress');
    const progressBar = document.getElementById('annotation-progress-bar');
    const statusDiv = document.getElementById('annotation-upload-status');
    const modalSubmit = document.getElementById('modalSubmit');
    
    // 显示进度
    progressContainer.style.display = 'block';
    modalSubmit.disabled = true;
    modalSubmit.textContent = '创建中...';
    
    const formData = new FormData();
    formData.append('name', name);
    formData.append('description', description);
    formData.append('classes', JSON.stringify(classes));
    formData.append('images_zip', zipFile);
    
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_URL}/annotation/projects/upload`, true);
    
    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            progressBar.style.width = percentComplete + '%';
            progressBar.textContent = Math.round(percentComplete) + '%';
            statusDiv.textContent = '上传中...';
        }
    };
    
    xhr.onload = function() {
        if (xhr.status === 200 || xhr.status === 201) {
            statusDiv.textContent = '创建成功！';
            setTimeout(() => {
                modal.hide();
                loadAnnotationProjects();
                alert('标注项目创建成功！');
            }, 1000);
        } else {
            try {
                const response = JSON.parse(xhr.responseText);
                alert('创建失败: ' + (response.detail || '未知错误'));
            } catch (e) {
                alert('创建失败: ' + xhr.statusText);
            }
            modalSubmit.disabled = false;
            modalSubmit.textContent = '确定';
            progressContainer.style.display = 'none';
        }
    };
    
    xhr.onerror = function() {
        alert('上传失败，请检查网络连接');
        modalSubmit.disabled = false;
        modalSubmit.textContent = '确定';
        progressContainer.style.display = 'none';
    };
    
    xhr.send(formData);
}

// 使用现有图片创建项目
function createProjectWithExistingImages(name, description, classes, imageSource) {
    const requestData = {
        name: name,
        description: description,
        classes: classes
    };
    
    let apiEndpoint = `${API_URL}/annotation/projects/`;
    
    if (imageSource === 'dataset') {
        const datasetId = document.getElementById('annotation-dataset-id').value;
        if (!datasetId) {
            alert('请选择数据集');
            return;
        }
        requestData.dataset_id = datasetId;
    } else if (imageSource === 'directory') {
        const imageDirectory = document.getElementById('annotation-image-directory').value;
        if (!imageDirectory) {
            alert('请选择图片目录');
            return;
        }
        requestData.image_directory = imageDirectory;
        apiEndpoint = `${API_URL}/annotation/projects/from-directory`;
    }
    
    fetch(apiEndpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.detail || '创建项目失败'); });
        }
        return response.json();
    })
    .then(data => {
        modal.hide();
        loadAnnotationProjects();
        alert('标注项目创建成功！');
    })
    .catch(error => {
        console.error('Error creating annotation project:', error);
        alert('创建标注项目失败: ' + error.message);
    });
}

// 加载数据集选项用于标注项目
function loadDatasetOptionsForAnnotation() {
    fetch(`${API_URL}/datasets/`)
        .then(response => response.json())
        .then(datasets => {
            const select = document.getElementById('annotation-dataset-id');
            if (!select) return;
            
            // 清空现有选项（保留第一个默认选项）
            while (select.options.length > 1) {
                select.remove(1);
            }
            
            datasets.forEach(dataset => {
                if (dataset.status === 'available') {
                    const option = document.createElement('option');
                    option.value = dataset.id;
                    option.textContent = dataset.name;
                    select.appendChild(option);
                }
            });
            
            // 绑定数据集选择事件
            select.addEventListener('change', function() {
                if (this.value) {
                    // 根据选择的数据集自动填充信息
                    const selectedDataset = datasets.find(d => d.id === this.value);
                    if (selectedDataset) {
                        // 自动填充类别
                        const classesTextarea = document.getElementById('annotation-classes');
                        if (classesTextarea && selectedDataset.classes) {
                            classesTextarea.value = selectedDataset.classes.join('\n');
                        }
                        
                        // 自动填充图片目录
                        const imageDirectoryInput = document.getElementById('annotation-image-directory');
                        if (imageDirectoryInput) {
                            imageDirectoryInput.value = `datasets/${selectedDataset.name}/train/images`;
                        }
                    }
                }
            });
        })
        .catch(error => {
            console.error('Error loading datasets for annotation:', error);
        });
}

// 扫描项目图片
function scanProjectImages(projectId) {
    if (!confirm('确定要扫描项目图片吗？这将重新扫描图片目录并更新图片列表，此操作将清空所有标注请谨慎操作！！。')) {
        return;
    }
    
    fetch(`${API_URL}/annotation/projects/${projectId}/scan`, {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.detail || '扫描失败'); });
        }
        return response.json();
    })
    .then(data => {
        alert(data.message || '图片扫描完成');
        loadAnnotationProjects(); // 刷新项目列表
    })
    .catch(error => {
        console.error('Error scanning project images:', error);
        alert('扫描项目图片失败: ' + error.message);
    });
}

// 导出标注数据
function exportAnnotations(projectId) {
    const exportRequest = {
        format: 'yolo',
        include_images: true,
        split_data: false
    };
    
    fetch(`${API_URL}/annotation/projects/${projectId}/export`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(exportRequest)
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                try {
                    const err = JSON.parse(text);
                    throw new Error(err.detail || '导出失败');
                } catch (e) {
                    throw new Error('导出失败: ' + response.statusText);
                }
            });
        }
        
        // 检查响应类型
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/zip')) {
            // 处理ZIP文件下载
            return response.blob().then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `annotations_project_${projectId}.zip`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                return { message: '标注数据导出成功，文件已下载' };
            });
        } else {
            // 处理JSON响应
            return response.json();
        }
    })
    .then(data => {
        alert(data.message || '标注数据导出成功');
        if (data.export_path) {
            console.log('Export path:', data.export_path);
        }
    })
    .catch(error => {
        console.error('Error exporting annotations:', error);
        alert('导出标注数据失败: ' + error.message);
    });
}

// 删除标注项目
function deleteAnnotationProject(projectId) {
    if (!confirm('确定要删除这个标注项目吗？这将删除所有相关的标注数据。')) {
        return;
    }
    
    fetch(`${API_URL}/annotation/projects/${projectId}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.detail || '删除失败'); });
        }
        return response.json();
    })
    .then(data => {
        alert(data.message || '标注项目删除成功');
        loadAnnotationProjects(); // 刷新项目列表
    })
    .catch(error => {
        console.error('Error deleting annotation project:', error);
        alert('删除标注项目失败: ' + error.message);
    });
}

// 导出为数据集
function exportToDataset(projectId) {
    const datasetName = prompt('请输入数据集名称:');
    if (!datasetName) {
        return;
    }
    
    const datasetDescription = prompt('请输入数据集描述(可选):') || '';
    
    const formData = new FormData();
    formData.append('dataset_name', datasetName);
    formData.append('dataset_description', datasetDescription);
    
    fetch(`${API_URL}/annotation/projects/${projectId}/export-to-dataset`, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.detail || '导出失败'); });
        }
        return response.json();
    })
    .then(data => {
        alert(data.message || '导出为数据集成功');
        console.log('Dataset ID:', data.dataset_id);
    })
    .catch(error => {
        console.error('Error exporting to dataset:', error);
        alert('导出为数据集失败: ' + error.message);
    });
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

// ==================== 视频处理工具 ====================

// 加载视频处理页面
function loadVideoPage() {
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
function bindVideoEvents() {
    console.log('Binding Video Processing events...');

    // 加载覆盖层已完全移除

    // 使用setTimeout确保DOM元素已经加载
    setTimeout(() => {
        console.log('Delayed binding of Video Processing events...');
        bindVideoEventHandlers();
    }, 500);
}

// 实际绑定视频处理事件处理程序
function bindVideoEventHandlers() {
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
        extractFramesForm.addEventListener('submit', function(e) {
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

                fetch(`${API_URL}/video/extract-frames`, {
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
                    
                    // 显示提取进度（暂时关闭）
                    // const progressElement = document.getElementById('extraction-progress');
                    // if (progressElement) progressElement.textContent = `共提取了 ${data.extracted_frames || 0} 帧`;

                    // 显示结果区域
                    // const resultArea = document.getElementById('extract-frames-result');
                    // if (resultArea) resultArea.style.display = 'block';

                    // 显示提取结果
                    // if (data.result) {
                    //     console.log('提取到帧数:', data.result.extracted_frames || 0);
                    //     document.getElementById('extracted-frames-count').textContent = data.result.extracted_frames || 0;
                        
                        // 确保下载按钮可见并启用
                    //     const downloadAllBtn = document.getElementById('download-all-frames');
                    //     if (downloadAllBtn) {
                    //        downloadAllBtn.style.display = 'block';
                    //        downloadAllBtn.disabled = false;
                            
                            // 绑定下载事件
                    //        downloadAllBtn.onclick = function() {
                    //            window.location.href = `${API_URL}/video/download-frames/${data.extraction_id}`;
                    //        };
                    //    }

                        // 显示帧图像
                    //    const framesGallery = document.getElementById('frames-gallery');
                    //    framesGallery.innerHTML = '';

                        // 检查帧数据是否存在
                    //    const frames = data.result.frames || [];

                    //    if (frames.length === 0) {
                    //        framesGallery.innerHTML = '<div class="col-12 text-center"><div class="alert alert-info">未提取到帧</div></div>';
                    //    } else {
                            // 只显示前20帧，避免页面过长
                        //    const framesToShow = frames.slice(0, 20);
                        //    framesToShow.forEach(frame => {
                        //        const col = document.createElement('div');
                        //        col.className = 'col-md-3 mb-3';

                        //        const card = document.createElement('div');
                        //        card.className = 'card';

                        //        const img = document.createElement('img');
                        //        img.className = 'card-img-top';
                        //        img.src = `${API_URL}/video/frames/${data.extraction_id}/${frame}`;
                        //        img.alt = `Frame ${frame}`;

                        //        const cardBody = document.createElement('div');
                        //        cardBody.className = 'card-body';

                        //        const cardText = document.createElement('p');
                        //        cardText.className = 'card-text';
                        //        cardText.textContent = `帧 ${frame}`;

                        //        const downloadBtn = document.createElement('a');
                        //        downloadBtn.className = 'btn btn-sm btn-primary';
                        //        downloadBtn.href = `${API_URL}/video/frames/${data.extraction_id}/${frame}`;
                        //        downloadBtn.download = frame;
                        //        downloadBtn.textContent = '下载';

                        //        cardBody.appendChild(cardText);
                        //        cardBody.appendChild(downloadBtn);
                        //        card.appendChild(img);
                        //        card.appendChild(cardBody);
                        //        col.appendChild(card);
                        //        framesGallery.appendChild(col);
                        //    });

                            // 如果有更多帧，显示提示
                        //    if (frames.length > 20) {
                        //        const moreFrames = document.createElement('div');
                        //        moreFrames.className = 'col-12 text-center mt-3';
                        //        moreFrames.innerHTML = `<div class="alert alert-info">还有 ${frames.length - 20} 帧未显示</div>`;
                        //        framesGallery.appendChild(moreFrames);
                        //    }

                            // 绑定下载所有帧按钮事件
                        //    const downloadAllBtn = document.getElementById('download-all-frames');
                        //    if (downloadAllBtn) {
                        //        downloadAllBtn.style.display = 'block';
                        //        downloadAllBtn.onclick = function() {
                                    // 显示下载中状态
                        //            const originalText = downloadAllBtn.textContent;
                        //            downloadAllBtn.disabled = true;
                        //            downloadAllBtn.textContent = '下载中...';
                                    
                        //            window.open(`${API_URL}/video/download-frames/${data.extraction_id}`, '_blank');
                                    
                                    // 3秒后恢复按钮状态
                        //            setTimeout(() => {
                        //                downloadAllBtn.disabled = false;
                        //                downloadAllBtn.textContent = originalText;
                        //            }, 3000);
                        //        };
                        //    }
                    //    }
                    //} else {
                    //    document.getElementById('extracted-frames-count').textContent = '处理中...';
                    //    document.getElementById('frames-gallery').innerHTML = '<div class="col-12 text-center"><div class="alert alert-info">正在处理中，请稍候...</div></div>';
                //    }
            //    } else {
            //        console.error('提取帧响应数据格式错误:', data);
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
        detectScenesForm.addEventListener('submit', function(e) {
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
            const formData = new FormData(this);

            // 发送请求
            fetch(`${API_URL}/video/detect-scenes`, {
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
                        fetch(`${API_URL}/video/scene-detection-status/${taskId}`)
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
        detectMotionForm.addEventListener('submit', function(e) {
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
            const formData = new FormData(this);

            // 发送请求
            fetch(`${API_URL}/video/detect-motion`, {
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
                        fetch(`${API_URL}/video/motion-detection-status/${taskId}`)
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
                window.loadStreamsList();
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
        fetch(`${API_URL}/models/?type=detection`)
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
                loadStreamsList();
            });
        }
        
        if (manageStreamsBtn) {
            manageStreamsBtn.addEventListener('click', function() {
                showStreamManagementModal();
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

        // 实时检测相关变量
        let isDetecting = false;
        let stream = null;
        let animationFrameId = null;
        let lastFrameTime = 0;
        let fps = 0;
        let detectedObjects = 0;

        // 目标物体监控相关变量
        let targetObjects = [];
        let lastAlertTime = 0;
        let alertCooldown = 3000; // 默认3秒冷却时间
        let alertThreshold = 0.5; // 默认报警置信度阈值
        let visualAlertEnabled = true;
        let soundAlertEnabled = true;
        let isAlertActive = false;

        // 轨迹记录和预测相关变量
        let trajectoryEnabled = false;

        // 监听报警设置变化
        document.getElementById('alert-threshold').addEventListener('input', function() {
            alertThreshold = parseFloat(this.value);
            document.getElementById('alert-threshold-value').textContent = alertThreshold.toFixed(2);
        });

        document.getElementById('alert-cooldown').addEventListener('input', function() {
            alertCooldown = parseInt(this.value) * 1000; // 转换为毫秒
            document.getElementById('alert-cooldown-value').textContent = this.value;
        });

        document.getElementById('visual-alert-check').addEventListener('change', function() {
            visualAlertEnabled = this.checked;
        });

        document.getElementById('sound-alert-check').addEventListener('change', function() {
            soundAlertEnabled = this.checked;
        });

        // 监听轨迹设置变化
        const enableTrajectory = document.getElementById('enable-trajectory');
        const trajectorySettings = document.getElementById('trajectory-settings');

        if (enableTrajectory && trajectorySettings) {
            enableTrajectory.addEventListener('change', function() {
                trajectoryEnabled = this.checked;
                trajectorySettings.style.display = this.checked ? 'block' : 'none';

                // 更新轨迹设置
                if (window.trajectory) {
                    window.trajectory.updateTrajectorySettings({ enabled: trajectoryEnabled });

                    // 如果禁用，清空所有轨迹
                    if (!trajectoryEnabled) {
                        window.trajectory.clearAllTrajectories();
                    }
                }
            });
        }

        // 轨迹长度滑块
        const trajectoryLength = document.getElementById('trajectory-length');
        const trajectoryLengthValue = document.getElementById('trajectory-length-value');

        if (trajectoryLength && trajectoryLengthValue) {
            trajectoryLength.addEventListener('input', function() {
                const maxLength = parseInt(this.value);
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
            predictionSteps.addEventListener('input', function() {
                const steps = parseInt(this.value);
                predictionStepsValue.textContent = steps;

                if (window.trajectory) {
                    window.trajectory.updateTrajectorySettings({ predictionSteps: steps });
                }
            });
        }

        // 显示轨迹线复选框
        const showTrajectoryLine = document.getElementById('show-trajectory-line');
        if (showTrajectoryLine) {
            showTrajectoryLine.addEventListener('change', function() {
                if (window.trajectory) {
                    window.trajectory.updateTrajectorySettings({ showTrajectoryLine: this.checked });
                }
            });
        }

        // 显示预测线复选框
        const showPredictionLine = document.getElementById('show-prediction-line');
        if (showPredictionLine) {
            showPredictionLine.addEventListener('change', function() {
                if (window.trajectory) {
                    window.trajectory.updateTrajectorySettings({ showPredictionLine: this.checked });
                }
            });
        }

        // 添加目标物体按钮事件
        document.getElementById('add-target-btn').addEventListener('click', function() {
            addTargetObject();
        });

        // 目标输入框回车键事件
        document.getElementById('target-objects').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                addTargetObject();
            }
        });

        // 关闭报警按钮事件
        document.getElementById('close-alert-btn').addEventListener('click', function() {
            hideAlert();
        });

        // 清空报警历史按钮事件
        document.getElementById('clear-alerts-btn').addEventListener('click', function() {
            clearAlertHistory();
        });

        // 添加目标物体函数
        function addTargetObject() {
            const input = document.getElementById('target-objects');
            const value = input.value.trim();

            if (!value) return;

            // 分割输入，允许多个目标用逗号分隔
            const newTargets = value.split(',').map(t => t.trim().toLowerCase()).filter(t => t);

            // 添加新目标，去除重复
            newTargets.forEach(target => {
                if (!targetObjects.includes(target)) {
                    targetObjects.push(target);
                }
            });

            // 更新目标列表显示
            updateTargetList();

            // 清空输入框
            input.value = '';
        }

        // 更新目标列表显示
        function updateTargetList() {
            const targetList = document.getElementById('target-list');
            targetList.innerHTML = '';

            if (targetObjects.length === 0) {
                targetList.innerHTML = '<span class="badge bg-secondary">暂无监控目标</span>';
                return;
            }

            targetObjects.forEach(target => {
                const badge = document.createElement('span');
                badge.className = 'badge bg-primary me-2 mb-2';
                badge.innerHTML = `${target} <button type="button" class="btn-close btn-close-white" aria-label="Close" data-target="${target}"></button>`;
                targetList.appendChild(badge);

                // 添加删除按钮事件
                const closeBtn = badge.querySelector('.btn-close');
                closeBtn.addEventListener('click', function() {
                    const targetToRemove = this.getAttribute('data-target');
                    targetObjects = targetObjects.filter(t => t !== targetToRemove);
                    updateTargetList();
                });
            });
        }

        // 检查目标物体函数
        function checkTargetObjects(detections) {
            if (targetObjects.length === 0) return;

            // 检查是否在冷却时间内
            const now = Date.now();
            if (now - lastAlertTime < alertCooldown) return;

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
                const isTargetObject = targetObjects.includes(className) && confidence >= alertThreshold;

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
                triggerAlert(topMatch);

                // 更新最后报警时间
                lastAlertTime = now;
            }
        }

        // 触发报警函数
        function triggerAlert(detection) {
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
            if (visualAlertEnabled) {
                const alertContainer = document.getElementById('alert-container');
                const alertMessage = document.getElementById('alert-message');

                alertMessage.textContent = `检测到 ${className} (置信度: ${(confidence * 100).toFixed(1)}%)`;
                alertContainer.style.display = 'block';

                // 添加闪烁效果
                if (!isAlertActive) {
                    isAlertActive = true;
                    alertContainer.classList.add('alert-flash');
                }
            }

            // 声音报警
            if (soundAlertEnabled && window.alertSoundGenerator) {
                window.alertSoundGenerator.play();
            }

            // 添加到报警历史
            addAlertToHistory(className, confidence);
        }

        // 隐藏报警函数
        function hideAlert() {
            const alertContainer = document.getElementById('alert-container');
            alertContainer.style.display = 'none';
            alertContainer.classList.remove('alert-flash');
            isAlertActive = false;
        }

        // 添加报警到历史记录
        function addAlertToHistory(className, confidence) {
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
        function clearAlertHistory() {
            const alertHistoryTable = document.getElementById('alert-history-table');
            alertHistoryTable.innerHTML = '<tr><td colspan="3" class="text-center">暂无报警记录</td></tr>';

            // 清空统计数据
            if (window.alertStats) {
                window.alertStats.clearAlertRecords();
            }
        }

        // 清除区域按钮事件
        const clearZoneBtn = document.getElementById('clear-zone-btn');
        if (clearZoneBtn) {
            clearZoneBtn.addEventListener('click', function() {
                console.log('main.js: 清除区域按钮被点击');
                if (window.alertZone && window.alertZone.clearAlertZone) {
                    window.alertZone.clearAlertZone();
                } else {
                    console.error('main.js: alertZone或clearAlertZone函数不存在');
                    alert('清除区域失败: 功能不可用');
                }
            });
        }

        // 开始检测按钮事件
        startDetectionBtn.addEventListener('click', function() {
            const modelId = rtModelSelect.value;
            if (!modelId) {
                alert('请选择模型');
                return;
            }

            // 检查是否已经在检测中
            if (isDetecting) return;

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
                startStreamDetection(modelId, streamId);
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
                    stream = mediaStream;
                    videoElement.srcObject = stream;
                    videoElement.style.display = 'block';
                    videoElement.play();

                    // 更新状态
                    document.getElementById('detection-status').innerHTML =
                        `<span class="badge bg-info">摄像头已就绪</span>`;

                    // 设置画布大小
                    videoElement.onloadedmetadata = function() {
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
                                trajectoryEnabled = settings.enabled;

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

                        startRealTimeDetection(modelId);
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
                            stream = mediaStream;
                            videoElement.srcObject = stream;
                            videoElement.style.display = 'block';
                            videoElement.play();

                            // 更新状态
                            document.getElementById('detection-status').innerHTML =
                                `<span class="badge bg-info">默认摄像头已就绪</span>`;

                            // 设置画布大小
                            videoElement.onloadedmetadata = function() {
                                detectionCanvas.width = videoElement.videoWidth;
                                detectionCanvas.height = videoElement.videoHeight;

                                // 初始化报警区域
                                if (window.alertZone) {
                                    window.alertZone.resizeAlertZone(detectionCanvas.width, detectionCanvas.height);
                                    window.alertZone.drawAlertZone();
                                }

                                startRealTimeDetection(modelId);
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
                videoElement.onloadedmetadata = function() {
                    detectionCanvas.width = videoElement.videoWidth;
                    detectionCanvas.height = videoElement.videoHeight;

                    console.log('视频文件元数据加载完成，画布大小:', detectionCanvas.width, detectionCanvas.height);

                    // 初始化报警区域
                    if (window.alertZone) {
                        console.log('初始化报警区域');
                        window.alertZone.resizeAlertZone(detectionCanvas.width, detectionCanvas.height);
                    }

                    startRealTimeDetection(modelId);
                };
            }
        });

        // 停止检测按钮事件
        stopDetectionBtn.addEventListener('click', function() {
            stopRealTimeDetection();
        });

        // 更新检测对象列表
        function updateDetectionTable(detections) {
            const tableBody = document.getElementById('detection-results-table');

            // 清空表格
            tableBody.innerHTML = '';

            if (detections.length === 0) {
                const row = document.createElement('tr');
                const cell = document.createElement('td');
                cell.colSpan = 3;
                cell.className = 'text-center';
                cell.textContent = '暂无检测结果';
                row.appendChild(cell);
                tableBody.appendChild(row);
                return;
            }

            // 添加检测对象
            detections.forEach(detection => {
                const row = document.createElement('tr');

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

                // 类别单元格
                const classCell = document.createElement('td');
                classCell.textContent = className;

                // 置信度单元格
                const confidenceCell = document.createElement('td');
                confidenceCell.textContent = `${(confidence * 100).toFixed(1)}%`;

                // 位置单元格
                const positionCell = document.createElement('td');
                positionCell.textContent = `X: ${Math.round(x)}, Y: ${Math.round(y)}, W: ${Math.round(width)}, H: ${Math.round(height)}`;

                // 添加到行
                row.appendChild(classCell);
                row.appendChild(confidenceCell);
                row.appendChild(positionCell);

                // 添加到表格
                tableBody.appendChild(row);
            });
        }

        // 加载流媒体列表
        window.loadStreamsList = function() {
            const streamSelect = document.getElementById('stream-select');
            if (!streamSelect) return;
            
            // 显示加载状态
            streamSelect.innerHTML = '<option value="">加载中...</option>';
            
            fetch(`${API_URL}/streaming/list`)
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
        function showStreamManagementModal() {
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
                            加载中...
                        </div>
                    </div>
                </div>
            `;
            
            // 绑定事件
            bindStreamManagementEvents();
            
            // 加载流媒体列表
            window.loadStreamsManagementList();
            
            modal.show();
        }
        
        // 绑定流媒体管理事件
        function bindStreamManagementEvents() {
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
                    
                    fetch(`${API_URL}/streaming/test-connection`, {
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
                createStreamForm.addEventListener('submit', function(e) {
                    e.preventDefault();
                    
                    const source = document.getElementById('stream-source').value;
                    const type = document.getElementById('stream-type').value;
                    
                    const formData = new FormData();
                    formData.append('source', source);
                    formData.append('stream_type', type);
                    
                    fetch(`${API_URL}/streaming/create`, {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // 创建成功，启动流媒体
                            return fetch(`${API_URL}/streaming/start/${data.stream_id}`, {
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
                            window.loadStreamsManagementList();
                            window.loadStreamsList();
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
        window.loadStreamsManagementList = function() {
            const streamsList = document.getElementById('streams-list');
            if (!streamsList) return;
            
            fetch(`${API_URL}/streaming/list`)
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
                                                `<button class="btn btn-sm btn-outline-danger ms-2" onclick="stopStream('${streamId}')">\u505c\u6b62</button>` :
                                                `<button class="btn btn-sm btn-outline-success ms-2" onclick="startStream('${streamId}')">\u542f\u52a8</button>`
                                            }
                                            <button class="btn btn-sm btn-outline-secondary ms-1" onclick="deleteStream('${streamId}')">\u5220\u9664</button>
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

        // 开始流媒体检测
        function startStreamDetection(modelId, streamId) {
            isDetecting = true;
            startDetectionBtn.style.display = 'none';
            stopDetectionBtn.style.display = 'inline-block';

            // 更新检测状态
            document.getElementById('detection-status').innerHTML =
                `<span class="badge bg-warning">正在连接流媒体...</span>`;

            // 获取阈值
            const confThreshold = parseFloat(document.getElementById('rt-conf-threshold').value);
            const iouThreshold = parseFloat(document.getElementById('rt-iou-threshold').value);

            // 定义流媒体检测函数
            function detectStreamFrame(timestamp) {
                if (!isDetecting) return;

                // 计算FPS
                if (lastFrameTime) {
                    fps = 1000 / (timestamp - lastFrameTime);
                    fpsCounter.textContent = fps.toFixed(1);
                }
                lastFrameTime = timestamp;

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
                        img.onload = function() {
                            const ctx = detectionCanvas.getContext('2d');
                            detectionCanvas.width = img.width;
                            detectionCanvas.height = img.height;
                            ctx.drawImage(img, 0, 0);
                            
                            // 同时在视频元素上显示（如果需要）
                            if (videoElement) {
                                const videoCtx = videoElement.getContext ? videoElement.getContext('2d') : null;
                                if (videoCtx) {
                                    videoElement.width = img.width;
                                    videoElement.height = img.height;
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
                            detectedObjects = detections.length;
                            objectsCounter.textContent = detectedObjects;

                            // 更新检测状态
                            document.getElementById('detection-status').innerHTML =
                                `<span class="badge bg-success">正在检测</span>`;

                            // 在画布上绘制检测结果
                            drawDetections(detections);

                            // 更新检测结果表格
                            updateDetectionTable(detections);

                            // 处理报警逻辑
                            handleAlerts(detections);
                        }
                    })
                    .catch(error => {
                        console.error('流媒体检测错误:', error);
                        if (isDetecting) {
                            document.getElementById('detection-status').innerHTML =
                                `<span class="badge bg-danger">检测错误</span>`;
                        }
                    });

                // 继续下一帧
                if (isDetecting) {
                    animationFrameId = requestAnimationFrame(detectStreamFrame);
                }
            }

            // 开始检测循环
            animationFrameId = requestAnimationFrame(detectStreamFrame);
        }

        // 开始实时检测
        function startRealTimeDetection(modelId) {
            isDetecting = true;
            startDetectionBtn.style.display = 'none';
            stopDetectionBtn.style.display = 'inline-block';

            // 更新检测状态
            document.getElementById('detection-status').innerHTML =
                `<span class="badge bg-warning">准备中...</span>`;

            // 获取阈值
            const confThreshold = parseFloat(document.getElementById('rt-conf-threshold').value);
            const iouThreshold = parseFloat(document.getElementById('rt-iou-threshold').value);

            // 定义检测函数
            function detectFrame(timestamp) {
                if (!isDetecting) return;

                // 计算FPS
                if (lastFrameTime) {
                    fps = 1000 / (timestamp - lastFrameTime);
                    fpsCounter.textContent = fps.toFixed(1);
                }
                lastFrameTime = timestamp;

                // 绘制当前帧
                const ctx = detectionCanvas.getContext('2d');
                ctx.drawImage(videoElement, 0, 0, detectionCanvas.width, detectionCanvas.height);

                // 获取当前帧数据
                ctx.canvas.toBlob(function(blob) {
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

                    fetch(`${API_URL}/detection/`, {
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
                            fetch(`${API_URL}/detection/${data.id}/result`)
                                .then(response => response.json())
                                .then(resultData => {
                                    console.log('Detection result:', resultData);

                                    if (resultData.status === 'completed' && resultData.results && resultData.results.length > 0) {
                                        // 获取第一个结果的检测内容
                                        const detections = resultData.results[0].detections || [];

                                        // 更新检测到的目标数量
                                        detectedObjects = detections.length;
                                        objectsCounter.textContent = detectedObjects;

                                        // 处理轨迹记录和预测
                                        if (trajectoryEnabled && window.trajectory) {
                                            // 跟踪目标
                                            const trackedObjects = window.trajectory.trackObjects(detections);

                                            // 更新轨迹
                                            window.trajectory.updateTrajectories(trackedObjects);

                                            // 绘制检测框
                                            drawDetections(ctx, trackedObjects);

                                            // 绘制轨迹
                                            window.trajectory.drawTrajectories(ctx);

                                            // 更新检测对象列表
                                            updateDetectionTable(trackedObjects);

                                            // 检查目标物体并触发报警
                                            checkTargetObjects(trackedObjects);
                                        } else {
                                            // 绘制检测框
                                            drawDetections(ctx, detections);

                                            // 更新检测对象列表
                                            updateDetectionTable(detections);

                                            // 检查目标物体并触发报警
                                            checkTargetObjects(detections);
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
                        if (isDetecting) {
                            animationFrameId = requestAnimationFrame(detectFrame);
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
                        if (isDetecting) {
                            animationFrameId = requestAnimationFrame(detectFrame);
                        }
                    });
                }, 'image/jpeg');
            }

            // 绘制检测框
            function drawDetections(ctx, detections) {
                // 清除上一帧的检测框
                ctx.drawImage(videoElement, 0, 0, detectionCanvas.width, detectionCanvas.height);

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
            animationFrameId = requestAnimationFrame(detectFrame);
        }

        // 绘制检测结果
        function drawDetections(detections) {
            const ctx = detectionCanvas.getContext('2d');
            
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
        function updateDetectionTable(detections) {
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
        function handleAlerts(detections) {
            // 这里可以添加报警逻辑，例如检测到特定目标时发出报警
            // 目前保持空实现，可以根据需要扩展
        }

        // 停止实时检测
        function stopRealTimeDetection() {
            isDetecting = false;

            // 更新检测状态
            document.getElementById('detection-status').innerHTML =
                `<span class="badge bg-secondary">已停止</span>`;

            // 取消动画帧
            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }

            // 关闭摄像头
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                stream = null;
            }

            // 重置视频元素
            videoElement.srcObject = null;
            videoElement.src = '';
            videoElement.pause();
            videoElement.load(); // 确保清理流媒体连接

            // 重置按钮状态
            startDetectionBtn.style.display = 'inline-block';
            stopDetectionBtn.style.display = 'none';

            // 清除画布
            const ctx = detectionCanvas.getContext('2d');
            ctx.clearRect(0, 0, detectionCanvas.width, detectionCanvas.height);

            // 重置计数器
            fpsCounter.textContent = '0';
            objectsCounter.textContent = '0';

            // 清空检测对象列表
            const tableBody = document.getElementById('detection-results-table');
            tableBody.innerHTML = '<tr><td colspan="3" class="text-center">暂无检测结果</td></tr>';
        }
    }

    console.log('Video Processing events bound successfully');
}