// 全局函数用于处理模块收起展开
function toggleSubmodules(element) {
    const parentLi = element.closest('li.module-item');
    const submodulesContainer = parentLi.querySelector('.submodules-container');
    const icon = element.querySelector('i.bi');
    
    if (submodulesContainer) {
        if (submodulesContainer.style.display === 'none' || submodulesContainer.style.display === '') {
            submodulesContainer.style.display = 'block';
            if (icon) {
                icon.className = 'bi bi-chevron-down';
            }
        } else {
            submodulesContainer.style.display = 'none';
            if (icon) {
                icon.className = 'bi bi-chevron-right';
            }
        }
    }
}

// 模型管理模块
class ModelManager {
    constructor() {
        // 模型管理相关属性
    }

    // 加载模型列表
    loadModels() {
        authenticatedFetch(`${API_URL}/models/`)
            .then(response => response.json())
            .then(models => {
                const tableBody = document.getElementById('models-table-body');
                
                // 检查元素是否存在，避免在不相关页面调用时出错
                if (!tableBody) {
                    console.log('模型表格元素不存在，跳过更新');
                    return;
                }
                
                tableBody.innerHTML = '';

                if (models.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="7" class="text-center">暂无模型</td></tr>';
                    return;
                }

                models.forEach(model => {
                    const row = document.createElement('tr');
                    // 直接使用模型名称
                    const displayName = model.name || `${model.type} (自定义模型)`;
                    
                    // 区分YOLOE模型类型
                    let modelTypeDisplay = model.type;
                    if (model.type && model.type.toLowerCase().includes('yoloe')) {
                        // 根据模型名称或路径判断YOLOE模型类型
                        const modelNameLower = (model.name || '').toLowerCase();
                        const modelPathLower = (model.path || '').toLowerCase();
                        
                        if (modelNameLower.includes('prompt') || modelPathLower.includes('prompt') || 
                            modelNameLower.includes('text') || modelPathLower.includes('text') ||
                            modelNameLower.includes('vision') || modelPathLower.includes('vision')) {
                            modelTypeDisplay = 'YOLOE (文本/视觉提示模型)';
                        } else {
                            modelTypeDisplay = 'YOLOE (无提示词模型)';
                        }
                    }

                    row.innerHTML = `
                        <td>${displayName}</td>
                        <td>${model.description || '-'}</td>
                        <td>${modelTypeDisplay}</td>
                        <td>${this.getTaskText(model.task)}</td>
                        <td>${this.getSourceText(model.source)}</td>
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
                                <button class="btn btn-sm btn-info view-model-structure" data-id="${model.id}" title="查看模型结构">
                                    <i class="bi bi-diagram-3"></i> 结构
                                </button>
                                <button class="btn btn-sm btn-warning release-model" data-id="${model.id}" title="释放模型以便删除">
                                    <i class="bi bi-unlink"></i> 释放
                                </button>
                                <button class="btn btn-sm btn-danger delete-model" data-id="${model.id}">删除</button>
                            </div>
                        </td>
                    `;
                    tableBody.appendChild(row);
                });

                // 绑定删除按钮事件
                document.querySelectorAll('.delete-model').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const modelId = e.target.getAttribute('data-id');
                        this.deleteModel(modelId);
                    });
                });

                // 绑定释放模型按钮事件
                document.querySelectorAll('.release-model').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const modelId = e.target.getAttribute('data-id');
                        this.releaseModel(modelId);
                    });
                });

                // 绑定PT模型下载按钮事件
                document.querySelectorAll('.download-model-pt').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const modelId = e.target.getAttribute('data-id');
                        const downloadUrl = `${API_URL}/models/${modelId}/download/pt`;
                        console.log('PT模型下载URL:', downloadUrl);
                        window.location.href = downloadUrl;
                    });
                });

                // 绑定ONNX模型下载按钮事件
                document.querySelectorAll('.download-model-onnx').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const modelId = e.target.getAttribute('data-id');
                        const downloadUrl = `${API_URL}/models/${modelId}/download/onnx`;
                        console.log('ONNX模型下载URL:', downloadUrl);
                        // 显示加载指示器
                        e.target.innerHTML = '<i class="bi bi-arrow-clockwise spinner-border spinner-border-sm"></i> 转换中...';
                        e.target.disabled = true;
                        
                        // 开始下载
                        window.location.href = downloadUrl;
                        
                        // 设置一个超时，恢复按钮状态（即使下载中断）
                        setTimeout(() => {
                            e.target.innerHTML = '<i class="bi bi-exchange"></i> ONNX';
                            e.target.disabled = false;
                        }, 30000); // 30秒超时
                    });
                });

                // 绑定模型结构查看按钮事件
                document.querySelectorAll('.view-model-structure').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const modelId = e.target.getAttribute('data-id');
                        this.viewModelStructure(modelId);
                    });
                });
            })
            .catch(error => {
                console.error('Error loading models:', error);
                // 只在模型页面显示错误提示
                if (document.getElementById('models-table-body')) {
                    alert('加载模型失败');
                }
            });
    }

    // 绑定模型页面事件
    bindModelEvents() {
        const addButton = document.getElementById('add-model-btn');
        if (addButton) {
            addButton.addEventListener('click', () => this.showAddModelModal());
        }
        
        const loadDefaultModelsButton = document.getElementById('load-default-models-btn');
        if (loadDefaultModelsButton) {
            loadDefaultModelsButton.addEventListener('click', () => this.loadDefaultModels());
        }
    }

    // 加载预置模型
    loadDefaultModels() {
        if (confirm('确定要加载预置模型吗？这将会导入models目录和项目根目录下的.pt模型文件到系统中。\n注意：已存在的模型将被跳过。')) {
            // 显示加载中提示
            this.showLoadingOverlay('正在加载预置模型，请稍候...');
            
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
                this.hideLoadingOverlay();
                
                // 显示成功消息
                if (data.success) {
                    const message = `加载预置模型成功！\n共找到 ${data.total} 个模型文件，导入了 ${data.imported} 个新模型。`;
                    alert(message);
                    // 重新加载模型列表
                    this.loadModels();
                } else {
                    alert('加载预置模型失败：' + (data.message || '未知错误'));
                }
            })
            .catch(error => {
                // 隐藏加载中提示
                this.hideLoadingOverlay();
                alert('加载预置模型失败：' + error.message);
            });
        }
    }

    // 显示加载中覆盖层
    showLoadingOverlay(message) {
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
    hideLoadingOverlay() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }

    // 显示添加模型模态框
    showAddModelModal() {
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
        modalSubmit.onclick = () => this.submitAddModel();
    }

    // 提交添加模型表单
    submitAddModel() {
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
        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progressBarInner.style.width = percentComplete + '%';
                progressBarInner.textContent = Math.round(percentComplete) + '%';
            }
        };

        // 上传完成事件
        xhr.onload = () => {
            if (xhr.status === 200 || xhr.status === 201) {
                // 重置按钮状态
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = '确定';
                }
                modal.hide();
                this.loadModels();
            } else {
                // 重置按钮状态
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = '确定';
                }
                
                // 尝试解析错误响应
                try {
                    const response = JSON.parse(xhr.responseText);
                    alert('上传模型失败: ' + (response.detail || response.message || xhr.statusText));
                } catch (e) {
                    // 如果无法解析JSON，显示原始错误文本
                    alert('上传模型失败: ' + (xhr.statusText || '未知错误'));
                }
            }
        };

        // 上传错误事件
        xhr.onerror = () => {
            // 重置按钮状态
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = '确定';
            }
            
            // 尝试从响应中获取错误信息
            if (xhr.responseText) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    alert('上传模型失败: ' + (response.detail || response.message || '网络错误'));
                } catch (e) {
                    alert('上传模型失败: 网络错误或服务器无响应');
                }
            } else {
                alert('上传模型失败: 网络错误或服务器无响应');
            }
        };

        // 设置超时处理
        setTimeout(() => {
            if (submitButton && submitButton.disabled) {
                submitButton.disabled = false;
                submitButton.textContent = '确定';
                alert('上传操作超时，请刷新页面后重试');
            }
        }, 600000); // 10分钟超时

        // 发送请求
        xhr.send(formData);
    }

    // 释放模型
    releaseModel(modelId) {
        if (!confirm('确定要释放这个模型吗？这将解除模型与所有检测任务的关联，使其可以被删除。')) {
            return;
        }

        // 显示加载中提示
        const originalText = this.innerHTML;
        this.innerHTML = '<i class="bi bi-arrow-clockwise spinner-border spinner-border-sm"></i> 处理中...';
        this.disabled = true;
        const self = this;

        authenticatedFetch(`${API_URL}/tools/release-model`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ model_id: modelId })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || '释放模型失败');
                });
            }
            return response.json();
        })
        .then(data => {
            // 恢复按钮状态
            self.innerHTML = originalText;
            self.disabled = false;
            
            if (data.success) {
                alert('模型释放成功！现在可以删除该模型了。');
            } else {
                alert('释放模型失败：' + (data.message || '未知错误'));
            }
        })
        .catch(error => {
            // 恢复按钮状态
            self.innerHTML = originalText;
            self.disabled = false;
            alert('释放模型失败：' + error.message);
        });
    }

    // 删除模型
    deleteModel(modelId) {
        // 创建删除确认对话框
        const modalHtml = `
            <div class="modal fade" id="deleteModelModal" tabindex="-1" aria-labelledby="deleteModelModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="deleteModelModalLabel">删除模型确认</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p class="mb-4">慎重！若使用是预加载模型，将删除原始文件！</p>
                            <div class="mb-4">
                                <h6>删除选项：</h6>
                                <div class="form-check">
                                    <input class="form-check-input" type="radio" name="deleteOption" id="deleteOnlyList" value="only_list" checked>
                                    <label class="form-check-label" for="deleteOnlyList">
                                        仅从清单移除（保留模型文件）
                                    </label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="radio" name="deleteOption" id="deleteWithFile" value="with_file">
                                    <label class="form-check-label" for="deleteWithFile">
                                        从清单移除并删除模型文件
                                    </label>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-danger" id="confirmDeleteBtn">确认删除</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 添加模态框到页面
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('deleteModelModal'));
        modal.show();

        // 绑定确认删除按钮事件
        document.getElementById('confirmDeleteBtn').addEventListener('click', () => {
            // 获取选中的删除选项
            const deleteOption = document.querySelector('input[name="deleteOption"]:checked').value;
            const deleteFile = deleteOption === 'with_file';

            // 隐藏模态框
            modal.hide();

            // 执行删除操作
            authenticatedFetch(`${API_URL}/models/${modelId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ delete_file: deleteFile })
            })
                .then(response => {
                    if (response.ok) {
                        this.loadModels();
                        return;
                    }

                    // 处理错误响应
                    return response.json().then(data => {
                        throw new Error(data.detail || '删除模型失败');
                    });
                })
                .catch(error => {
                    if (DEBUG_MODE) {
                        console.error('Error deleting model:', error);
                    }

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
        });

        // 模态框关闭时清理DOM
        document.getElementById('deleteModelModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }

    // 查看模型结构
    viewModelStructure(modelId) {
        // 检查modelId是否有效
        if (!modelId || modelId === 'null' || modelId === 'undefined') {
            alert('模型ID无效，无法查看模型结构');
            return;
        }
        
        // 显示加载中提示
        this.showLoadingOverlay('正在加载模型结构，请稍候...');

        authenticatedFetch(`${API_URL}/models/${modelId}/structure`)
            .then(response => response.json())
            .then(data => {
                // 隐藏加载中提示
                this.hideLoadingOverlay();

                if (data.success) {
                    // 将modelId传递给showModelStructureModal函数
                    data.model_id = modelId;  // 确保modelId在data对象中
                    this.showModelStructureModal(data);
                } else {
                    alert('获取模型结构失败：' + (data.detail || '未知错误'));
                }
            })
            .catch(error => {
                // 隐藏加载中提示
                this.hideLoadingOverlay();
                console.error('Error getting model structure:', error);
                alert('获取模型结构失败：' + error.message);
            });
    }

    // 显示模型结构模态框
    showModelStructureModal(data) {
        // 创建模态框HTML
        const modalHtml = `
        <div class="modal fade" id="modelStructureModal" data-model-id="${data.model_id}" tabindex="-1" aria-labelledby="modelStructureModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="modelStructureModalLabel">模型结构 - ${data.model_name}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-12">
                                <div class="card mb-3">
                                    <div class="card-header">
                                        <div class="row">
                                            <div class="col-md-8">
                                                <h6>模型信息</h6>
                                                <p class="mb-0">
                                                    <strong>模型类型:</strong> ${data.model_type} | 
                                                    <strong>总参数量:</strong> ${data.structure.total_params.toLocaleString()} | 
                                                    <strong>可剪枝模块数:</strong> ${data.structure.prunable_modules.length}
                                                </p>
                                                <p class="mb-0">
                                                    <strong>总模块数:</strong> ${data.structure.total_modules} | 
                                                    <strong>预估内存使用:</strong> ${(data.structure.analysis?.memory_usage || 0).toFixed(2)} MB
                                                </p>
                                            </div>
                                            <div class="col-md-4">
                                                <div class="input-group">
                                                    <input type="text" class="form-control" id="search-module-input" placeholder="搜索层...">
                                                    <button class="btn btn-outline-secondary" type="button" id="search-module-btn">搜索</button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="card">
                                    <div class="card-header d-flex justify-content-between align-items-center">
                                        <h6>剪枝操作</h6>
                                        <div class="d-flex align-items-center">
                                            <div class="form-check me-3">
                                                <input class="form-check-input" type="checkbox" id="disable-prune-control">
                                                <label class="form-check-label small" for="disable-prune-control">
                                                    关闭剪枝控制
                                                </label>
                                            </div>
                                            <button id="select-all-prunable" class="btn btn-sm btn-outline-primary">全选可剪枝模块</button>
                                        </div>
                                    </div>
                                    <div class="card-body">
                                        <div class="row mb-3">
                                            <div class="col-md-6">
                                                <label class="form-label">新模型名称</label>
                                                <input type="text" class="form-control" id="new-model-name-prune" value="${data.model_name}_pruned">
                                            </div>
                                            <div class="col-md-6">
                                                <label class="form-label">剪枝比例</label>
                                                <input type="range" class="form-range" id="prune-ratio-slider" min="0.1" max="0.9" step="0.05" value="0.5">
                                                <div class="d-flex justify-content-between">
                                                    <span>10%</span>
                                                    <span id="prune-ratio-value">50%</span>
                                                    <span>90%</span>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="row mb-3">
                                            <div class="col-md-6">
<label class="form-label">剪枝类型 <i class="bi bi-question-circle" data-bs-toggle="tooltip" data-bs-placement="top" title="非结构化剪枝: 移除单个权重连接，保留模型结构，通常移除权重较小的连接。注意：非结构化剪枝不会减少模型大小，也不会加速推理（除非使用特殊硬件支持）。\n结构化剪枝: 移除整个结构单元（如通道、滤波器），改变模型结构，通常可加速推理。"></i></label>
                                                <select class="form-select" id="prune-type-select">
                                                    <option value="unstructured" selected>非结构化剪枝</option>
                                                    <option value="structured">结构化剪枝</option>
                                                </select>
                                            </div>
                                            <div class="col-md-6">
                                                <label class="form-label">剪枝方法 <i class="bi bi-question-circle" data-bs-toggle="tooltip" data-bs-placement="top" title="L1范数剪枝: 基于权重L1范数的非结构化剪枝方法，优先移除权重较小的连接。依赖图: 使用依赖图进行结构化剪枝，按用户选择的层和比例进行剪枝。"></i></label>
                                                <select class="form-select" id="prune-method-select">
                                                    <option value="l1_unstructured" selected>L1范数剪枝</option>
                                                    <option value="dependency">依赖图</option>
                                                </select>
                                            </div>
                                        </div>
                                        <div class="row">
                                            <div class="col-md-12">
                                                <label class="form-label">操作</label>
                                                <div class="d-grid gap-2">
                                                    <button id="prune-model-btn" class="btn btn-warning">执行剪枝并保存</button>
                                                    <button id="analyze-model-btn" class="btn btn-info">模型分析</button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <hr>
                                
                                <h6>模型结构 <span class="badge bg-secondary" id="module-count">共 ${data.structure.total_modules || data.structure.modules.length} 层</span></h6>
                                <div id="model-structure-tree">
                                    ${this.renderModuleTree(data.structure.modules, 0, data.structure.prunable_modules)}
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    </div>
                </div>
            </div>
        </div>`;

        // 添加模态框到页面
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // 显示模态框
        const modalElement = document.getElementById('modelStructureModal');
        const modal = new bootstrap.Modal(modalElement);
        modal.show();

        // 绑定搜索功能
        const searchBtn = document.getElementById('search-module-btn');
        const searchInput = document.getElementById('search-module-input');
        if (searchBtn && searchInput) {
            searchBtn.addEventListener('click', () => {
                this.searchModules(searchInput.value);
            });
            
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.searchModules(searchInput.value);
                }
            });
        }

        // 绑定全选按钮
        const selectAllBtn = document.getElementById('select-all-prunable');
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => {
                this.selectAllPrunableModules();
            });
        }
        
        // 绑定“关闭剪枝控制”复选框事件
        const disableControlCheckbox = document.getElementById('disable-prune-control');
        if (disableControlCheckbox) {
            const self = this; // 保存当前实例的引用
            disableControlCheckbox.addEventListener('change', () => {
                // 重新渲染模块树以反映新的可剪枝状态
                const structureData = data.structure;
                const treeContainer = document.getElementById('model-structure-tree');
                if (treeContainer) {
                    treeContainer.innerHTML = self.renderModuleTree(structureData.modules, 0, structureData.prunable_modules);
                }
            });
        }

        // 绑定剪枝按钮事件
        const pruneBtn = document.getElementById('prune-model-btn');
        if (pruneBtn) {
            pruneBtn.addEventListener('click', () => {
                const pruneMethodSelect = document.getElementById('prune-method-select');
                const selectedMethod = pruneMethodSelect ? pruneMethodSelect.value : 'l1_unstructured';
                
                // 执行统一的模型剪枝
                this.performModelPruning(data.model_name);
            });
        }
        
        // 绑定模型分析按钮事件
        const analyzeBtn = document.getElementById('analyze-model-btn');
        if (analyzeBtn) {
            analyzeBtn.addEventListener('click', () => {
                this.analyzeModel(data.model_id);
            });
        }
        

        


        // 绑定剪枝比例滑块事件
        const pruneRatioSlider = document.getElementById('prune-ratio-slider');
        const pruneRatioValue = document.getElementById('prune-ratio-value');
        if (pruneRatioSlider && pruneRatioValue) {
            pruneRatioSlider.addEventListener('input', () => {
                const ratio = parseFloat(pruneRatioSlider.value);
                pruneRatioValue.textContent = Math.round(ratio * 100) + '%';
            });
        }
        
        // 绑定剪枝类型变化事件，动态更新可用的剪枝方法和模块树
        const pruneTypeSelect = document.getElementById('prune-type-select');
        const pruneMethodSelect = document.getElementById('prune-method-select');
        if (pruneTypeSelect && pruneMethodSelect) {
            const self = this; // 保存当前实例的引用
            pruneTypeSelect.addEventListener('change', function() {
                const selectedType = this.value;
                // 清空当前选项
                pruneMethodSelect.innerHTML = '';
                
                if (selectedType === 'unstructured') {
                    // 非结构化剪枝方法 - 仅保留L1范数
                    pruneMethodSelect.innerHTML = `
                        <option value="l1_unstructured" selected>L1范数剪枝</option>
                    `;
                } else if (selectedType === 'structured') {
                    // 结构化剪枝方法 - 只保留依赖图选项
                    pruneMethodSelect.innerHTML = `
                        <option value="dependency" selected>依赖图</option>
                    `;
                }
                
                // 重新渲染模块树以反映新的可剪枝状态
                const structureData = data.structure;
                const treeContainer = document.getElementById('model-structure-tree');
                if (treeContainer) {
                    treeContainer.innerHTML = self.renderModuleTree(structureData.modules, 0, structureData.prunable_modules);
                }
                
                // 更新工具提示 - 先销毁现有的工具提示以防止内存泄漏
                var existingTooltips = [].slice.call(modalElement.querySelectorAll('[data-bs-toggle="tooltip"]'));
                existingTooltips.forEach(function(tooltipEl) {
                    var tooltipInstance = bootstrap.Tooltip.getInstance(tooltipEl);
                    if (tooltipInstance) {
                        tooltipInstance.dispose();
                    }
                });
                
                // 重新创建工具提示
                var tooltipTriggerList = [].slice.call(modalElement.querySelectorAll('[data-bs-toggle="tooltip"]'));
                var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
                    return new bootstrap.Tooltip(tooltipTriggerEl);
                });
            });
        }
        
        // 初始化工具提示 - 先销毁可能存在的工具提示以防止内存泄漏
        var existingTooltips = [].slice.call(modalElement.querySelectorAll('[data-bs-toggle="tooltip"]'));
        existingTooltips.forEach(function(tooltipEl) {
            var tooltipInstance = bootstrap.Tooltip.getInstance(tooltipEl);
            if (tooltipInstance) {
                tooltipInstance.dispose();
            }
        });
        
        // 重新创建工具提示
        var tooltipTriggerList = [].slice.call(modalElement.querySelectorAll('[data-bs-toggle="tooltip"]'));
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });

        // 模态框关闭时清理
        modalElement.addEventListener('hidden.bs.modal', function () {
            // 隐藏所有工具提示
            tooltipList.forEach(function(tooltip) {
                tooltip.dispose();
            });
            modalElement.remove();
        });
    }

    // 渲染模块树
    renderModuleTree(modules, depth, prunableModules) {
        if (!modules || modules.length === 0) return '';

        const indent = '&nbsp;'.repeat(depth * 4);
        let html = '<ul class="list-unstyled module-tree" style="margin-left: ' + (depth * 20) + 'px;">';

        modules.forEach(module => {
            // 检查是否启用了“关闭剪枝控制”
            const disableControlCheckbox = document.getElementById('disable-prune-control');
            const isControlDisabled = disableControlCheckbox ? disableControlCheckbox.checked : false;
            
            // 检查当前是否选择了结构化剪枝
            const pruneTypeSelect = document.getElementById('prune-type-select');
            const pruneMethodSelect = document.getElementById('prune-method-select');
            const isStructuredPrune = pruneTypeSelect && pruneTypeSelect.value === 'structured';
            
            // 检查是否选择了依赖图剪枝方法
            const isDependencyPrune = isStructuredPrune && pruneMethodSelect && pruneMethodSelect.value === 'dependency';
            
            // 对于依赖图剪枝，使用更严格的判断逻辑，仅标记真正可剪枝的模块
            let isPrunable;
            if (isStructuredPrune && isDependencyPrune) {
                // 依赖图方法：只有在prunableModules列表中的模块才是可剪枝的
                // 同时排除检测头等绝对不能剪枝的层
                const isCriticalLayer = module.name.toLowerCase().includes('detect') || 
                                      module.name.toLowerCase().includes('segment') || 
                                      module.name.toLowerCase().includes('pose') ||
                                      module.name.toLowerCase().includes('dfl') ||
                                      module.name.toLowerCase().includes('cls') ||
                                      module.name.toLowerCase().includes('reg');
                isPrunable = isControlDisabled ? true : (prunableModules.includes(module.name) && !isCriticalLayer);
            } else if (isStructuredPrune) {
                // 对于其他结构化剪枝方法，我们放宽条件，显示更多潜在可剪枝的层
                // 主要是Conv2d层（除了某些特殊层如Detect等）
                const isConvLayer = module.type.includes('Conv') && !module.name.toLowerCase().includes('detect') && 
                                  !module.name.toLowerCase().includes('segment') && !module.name.toLowerCase().includes('pose');
                isPrunable = isControlDisabled ? true : (prunableModules.includes(module.name) || isConvLayer);
            } else {
                // 对于非结构化剪枝，保持原有逻辑
                isPrunable = isControlDisabled ? true : prunableModules.includes(module.name);
            }
            
            const prunableCheckbox = isPrunable ? 
                `<div class="form-check form-check-inline">
                    <input class="form-check-input module-checkbox" type="checkbox" value="${module.name}" id="module_${module.name.replace(/\./g, '_')}" data-prunable="true">
                    <label class="form-check-label" for="module_${module.name.replace(/\./g, '_')}">
                        <span class="badge bg-warning">可剪枝</span>
                    </label>
                </div>` : 
                `<span class="badge bg-secondary">不可剪枝</span>`;
            
            const hasSubmodules = module.submodules && module.submodules.length > 0;
            
            html += `<li class="module-item" data-module-name="${module.name}" style="margin-bottom: 5px;">
                <div class="d-flex justify-content-between align-items-center module-header p-2 border rounded" style="background-color: #f8f9fa; cursor: pointer;" onclick="toggleSubmodules(this)">
                    <div>
                        <span><strong>${module.name}</strong> (${module.type})</span>
                        <small class="text-muted"> - 参数: ${module.params.toLocaleString()}</small>
                        ${hasSubmodules ? '<i class="bi bi-chevron-down" style="margin-left: 5px;"></i>' : ''}
                    </div>
                    <div>
                        ${prunableCheckbox}
                    </div>
                </div>`;
            
            if (hasSubmodules) {
                html += `<div class="submodules-container" style="display: block;">${this.renderModuleTree(module.submodules, depth + 1, prunableModules)}</div>`;
            } else {
                html += '<div class="submodules-container" style="display: none;"></div>';
            }
            
            html += '</li>';
        });

        html += '</ul>';
        return html;
    }

    // 搜索模块
    searchModules(searchTerm) {
        if (!searchTerm.trim()) {
            // 显示所有模块
            document.querySelectorAll('.module-item').forEach(item => {
                item.style.display = '';
                // 同时显示所有子模块
                const subModules = item.querySelectorAll('.module-item');
                subModules.forEach(subItem => {
                    subItem.style.display = '';
                });
            });
            return;
        }

        // 首先隐藏所有模块
        document.querySelectorAll('.module-item').forEach(item => {
            item.style.display = 'none';
        });

        // 查找匹配的模块并显示它们及其父级
        const allModules = document.querySelectorAll('.module-item');
        allModules.forEach(item => {
            const moduleName = item.getAttribute('data-module-name');
            if (moduleName && moduleName.toLowerCase().includes(searchTerm.toLowerCase())) {
                // 显示匹配的模块
                item.style.display = '';
                
                // 显示所有父级模块（展开层级）
                let parentElement = item.parentElement;
                while (parentElement && parentElement !== document.body) {
                    if (parentElement.classList.contains('module-tree')) {
                        // 显示这个树的直接父级li元素
                        const parentLi = parentElement.closest('.module-item');
                        if (parentLi) {
                            parentLi.style.display = '';
                        }
                    }
                    parentElement = parentElement.parentElement;
                }
                
                // 显示所有子模块
                const subModules = item.querySelectorAll('.module-item');
                subModules.forEach(subItem => {
                    subItem.style.display = '';
                });
            }
        });
    }

    // 全选可剪枝模块
    selectAllPrunableModules() {
        // 检查是否启用了“关闭剪枝控制”
        const disableControlCheckbox = document.getElementById('disable-prune-control');
        const isControlDisabled = disableControlCheckbox ? disableControlCheckbox.checked : false;
        
        if (isControlDisabled) {
            // 如果关闭了剪枝控制，则选择所有模块
            document.querySelectorAll('.module-checkbox').forEach(checkbox => {
                checkbox.checked = true;
            });
        } else {
            // 否则只选择标记为可剪枝的模块
            document.querySelectorAll('.module-checkbox[data-prunable="true"]').forEach(checkbox => {
                checkbox.checked = true;
            });
        }
    }


    // 统一的模型剪枝函数
    performModelPruning(modelName) {
        // 从模态框获取模型ID，而不是依赖全局变量
        const modal = document.getElementById('modelStructureModal');
        const modelId = modal ? modal.dataset.modelId : null;
            
        if (!modelId || modelId === 'null' || modelId === 'undefined') {
            alert('模型ID无效，无法执行剪枝操作');
            return;
        }
            
        // 检查是否启用了“关闭剪枝控制”
        const disableControlCheckbox = document.getElementById('disable-prune-control');
        const isControlDisabled = disableControlCheckbox ? disableControlCheckbox.checked : false;
            
        // 获取剪枝参数
        const pruneTypeSelect = document.getElementById('prune-type-select');
        const pruneMethodSelect = document.getElementById('prune-method-select');
        const pruneRatioSlider = document.getElementById('prune-ratio-slider');
        const newModelNameInput = document.getElementById('new-model-name-prune');
                    
        const pruneType = pruneTypeSelect ? pruneTypeSelect.value : 'unstructured';
        // 如果是结构化剪枝且未选择具体方法，则默认为依赖图方法
        const pruneMethod = pruneMethodSelect ? 
            (pruneType === 'structured' && !pruneMethodSelect.value ? 'dependency' : pruneMethodSelect.value) : 
            (pruneType === 'structured' ? 'dependency' : 'l1_unstructured');
        const pruneRatio = pruneRatioSlider ? parseFloat(pruneRatioSlider.value) : 0.5;
        const newModelName = newModelNameInput ? newModelNameInput.value : '';
        
        // 验证剪枝比例是否合理
        if (pruneRatio < 0.1 || pruneRatio > 0.9) {
            alert('剪枝比例应在0.1-0.9之间（10%-90%）');
            return;
        }
        
        // 获取选中的模块
        const selectedModules = [];
            
        // 获取用户选择的模块
        if (isControlDisabled) {
            // 如果关闭了剪枝控制，则可以选择所有模块
            document.querySelectorAll('.module-checkbox:checked').forEach(checkbox => {
                selectedModules.push(checkbox.value);
            });
        } else {
            // 否则只获取标记为可剪枝的选中模块
            document.querySelectorAll('.module-checkbox[data-prunable="true"]:checked').forEach(checkbox => {
                selectedModules.push(checkbox.value);
            });
        }
            
        if (selectedModules.length === 0) {
            alert('请至少选择一个模块进行剪枝');
            return;
        }
        
        if (!confirm(`确定要对模型进行剪枝吗？将剪枝 ${selectedModules.length} 个模块`)) {
            return;
        }
    
        if (!newModelName.trim()) {
            alert('请输入新模型名称');
            return;
        }
    
        // 显示加载中提示
        this.showLoadingOverlay('正在执行模型剪枝，请稍候...');
        
        // 需要在剪枝操作开始时禁用按钮，防止重复提交
        const pruneBtn = document.getElementById('prune-model-btn');
        if (pruneBtn) {
            pruneBtn.disabled = true;
            pruneBtn.innerHTML = '<i class="bi bi-arrow-clockwise spinner-border spinner-border-sm"></i> 剪枝中...';
        }
    
        authenticatedFetch(`${API_URL}/models/${modelId}/prune`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                modules_to_prune: selectedModules,
                prune_type: pruneType,
                prune_method: pruneMethod,
                prune_ratio: pruneRatio,
                new_model_name: newModelName || `${modelName}_pruned`
            })
        })
        .then(response => {
            // 剪枝完成后恢复按钮状态
            if (pruneBtn) {
                pruneBtn.disabled = false;
                pruneBtn.innerHTML = '执行剪枝并保存';
            }
            
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.detail || '剪枝请求失败');
                });
            }
            return response.json();
        })
        .then(data => {
            // 隐藏加载中提示
            this.hideLoadingOverlay();
    
            if (data.success) {
                // 根据剪枝类型显示不同的提示信息
                let successMessage = '模型剪枝成功！';
                                
                if (pruneTypeSelect && pruneTypeSelect.value) {
                    const pruneType = pruneTypeSelect.value;
                    if (pruneType === 'unstructured') {
                        successMessage += '\n⚠️ 注意：非结构化剪枝仅将权重置零，不会减少模型大小，也不会加速推理（除非使用专门的稀疏推理引擎）';
                    } else {
                        successMessage += '\n✅ 结构化剪枝可能提升推理速度';
                    }
                } else {
                    successMessage += '\n⚠️ 无法确定剪枝类型';
                }
                                
                // 显示剪枝详细结果
                if (data.pruning_details) {
                    const details = data.pruning_details;
                    successMessage += `\n\n剪枝详细结果：
- 总共处理层: ${details.summary.total_selected}
- 成功剪枝: ${details.summary.successfully_pruned} 层
- 剪枝失败: ${details.summary.failed_attempts} 层`;
                    
                    // 显示成功剪枝的层
                    if (details.successful_modules && details.successful_modules.length > 0) {
                        successMessage += `\n\n✅ 成功剪枝的层 (${details.successful_modules.length}):`;
                        details.successful_modules.forEach(layer => {
                            successMessage += `\n  - ${layer}`;
                        });
                    }
                    
                    // 显示失败的层
                    if (details.failed_modules && details.failed_modules.length > 0) {
                        successMessage += `\n\n❌ 剪枝失败的层 (${details.failed_modules.length}):`;
                        details.failed_modules.forEach(layer => {
                            successMessage += `\n  - ${layer}`;
                        });
                    }
                }
                
                alert(successMessage);
                            
                // 关闭所有模态框
                document.querySelectorAll('.modal').forEach(modal => {
                    const bsModal = bootstrap.Modal.getInstance(modal);
                    if (bsModal) {
                        bsModal.hide();
                    }
                });
                // 刷新模型列表
                this.loadModels();
            } else {
                alert('模型剪枝失败：' + (data.detail || '未知错误')); 
            }
        })
        .catch(error => {
            // 剪枝完成后恢复按钮状态
            if (pruneBtn) {
                pruneBtn.disabled = false;
                pruneBtn.innerHTML = '执行剪枝并保存';
            }
            
            // 隐藏加载中提示
            this.hideLoadingOverlay();
            console.error('Error pruning model:', error);
            
            // 增强错误处理
            if (error.message.includes('所选模块均不可剪枝')) {
                alert('模型剪枝失败：' + error.message + '\n提示：请检查您选择的模块是否支持当前剪枝类型，或者尝试启用“关闭剪枝控制”选项。');
            } else {
                alert('模型剪枝失败：' + error.message);
            }
        });
    }

    

    // 获取任务类型文本
    getTaskText(task) {
        switch (task) {
            case 'detect':
                return '目标检测';
            case 'segment':
                return '实例分割';
            case 'pose':
                return '关键点/姿态估计';
            case 'obb':
                return '旋转框检测';
            case 'detection':
                return '目标检测';
            case 'segmentation':
                return '实例分割';
            case 'keypoints':
                return '关键点/姿态估计';
            default:
                return task;
        }
    }

    // 获取来源文本
    getSourceText(source) {
        switch (source) {
            case 'upload':
                return '上传';
            case 'training':
                return '训练';
            default:
                return source;
        }
    }
    
    

    
    // 模型分析
    analyzeModel(modelId) {
        // 检查modelId是否有效
        if (!modelId || modelId === 'null' || modelId === 'undefined') {
            alert('模型ID无效，无法执行模型分析');
            return;
        }

        // 显示加载中提示
        this.showLoadingOverlay('正在分析模型，请稍候...');

        authenticatedFetch(`${API_URL}/models/${modelId}/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                include_flops: true,
                include_memory: true,
                include_bottleneck: true,
                hardware_target: 'auto'
            })
        })
        .then(response => response.json())
        .then(data => {
            // 隐藏加载中提示
            this.hideLoadingOverlay();

            if (data.analysis) {
                this.showAnalysisResults(data);
            } else {
                alert('模型分析失败：' + (data.detail || '未知错误'));
            }
        })
        .catch(error => {
            // 隐藏加载中提示
            this.hideLoadingOverlay();
            console.error('Error analyzing model:', error);
            alert('模型分析失败：' + error.message);
        });
    }
    
    // 显示分析结果
    showAnalysisResults(data) {
        // 创建分析结果模态框HTML
        const modalHtml = `
        <div class="modal fade" id="analysisResultsModal" tabindex="-1" aria-labelledby="analysisResultsModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="analysisResultsModalLabel">模型分析结果 - ${data.model_name}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-12">
                                <div class="card mb-3">
                                    <div class="card-header">
                                        <h6>模型分析概览</h6>
                                    </div>
                                    <div class="card-body">
                                        <div class="row">
                                            <div class="col-md-6">
                                                <div class="card bg-light">
                                                    <div class="card-body text-center">
                                                        <h5 class="card-title">总参数量</h5>
                                                        <p class="card-text display-6">${data.analysis.memory_usage?.total_params.toLocaleString() || 0}</p>
                                                    </div>
                                                </div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="card bg-light">
                                                    <div class="card-body text-center">
                                                        <h5 class="card-title">预估内存</h5>
                                                        <p class="card-text display-6">${(data.analysis.memory_usage?.estimated_memory_mb || 0).toFixed(2)} MB</p>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="card mb-3">
                                    <div class="card-header">
                                        <h6>参数分布分析</h6>
                                    </div>
                                    <div class="card-body">
                                        <div class="table-responsive">
                                            <table class="table table-striped">
                                                <thead>
                                                    <tr>
                                                        <th>层名称</th>
                                                        <th>层类型</th>
                                                        <th>参数量</th>
                                                        <th>占比(%)</th>
                                                    </tr>
                                                </thead>
                                                <tbody id="param-distribution-body">
                                                    ${this.renderParamDistribution(data.analysis.param_distribution)}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="card">
                                    <div class="card-header">
                                        <h6>瓶颈层分析</h6>
                                    </div>
                                    <div class="card-body">
                                        <div class="table-responsive">
                                            <table class="table table-striped">
                                                <thead>
                                                    <tr>
                                                        <th>层名称</th>
                                                        <th>层类型</th>
                                                        <th>参数量</th>
                                                    </tr>
                                                </thead>
                                                <tbody id="bottleneck-layers-body">
                                                    ${this.renderBottleneckLayers(data.analysis.bottleneck_layers)}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    </div>
                </div>
            </div>
        </div>`;

        // 添加模态框到页面
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // 显示模态框
        const modalElement = document.getElementById('analysisResultsModal');
        const modal = new bootstrap.Modal(modalElement);
        modal.show();

        // 模态框关闭时清理
        modalElement.addEventListener('hidden.bs.modal', function () {
            modalElement.remove();
        });
    }
    
    // 渲染参数分布表格
    renderParamDistribution(paramDist) {
        if (!paramDist || paramDist.length === 0) {
            return '<tr><td colspan="4" class="text-center">暂无参数分布数据</td></tr>';
        }
        
        let html = '';
        paramDist.forEach(item => {
            html += `
            <tr>
                <td>${item.name}</td>
                <td>${item.type}</td>
                <td>${item.params.toLocaleString()}</td>
                <td>${item.percentage}%</td>
            </tr>`;
        });
        
        return html;
    }
    
    // 渲染瓶颈层表格
    renderBottleneckLayers(bottleneckLayers) {
        if (!bottleneckLayers || bottleneckLayers.length === 0) {
            return '<tr><td colspan="3" class="text-center">暂无瓶颈层</td></tr>';
        }
        
        let html = '';
        bottleneckLayers.forEach(item => {
            html += `
            <tr>
                <td>${item.name}</td>
                <td>${item.type}</td>
                <td>${item.params.toLocaleString()}</td>
            </tr>`;
        });
        
        return html;
    }
    
    // 更新模块树以适应结构化剪枝显示
    updateModuleTreeForStructuredPruning() {
        // 获取当前的结构化数据
        const treeContainer = document.getElementById('model-structure-tree');
        if (!treeContainer) return;
        
        // 重新获取模型结构信息并重新渲染树
        // 由于我们无法直接访问原始数据，这里只是视觉上提示用户
        // 实际的分析将在后端进行
        console.log('准备进行结构化剪枝分析，将显示更广泛的可剪枝层');
    }
    

}

// 创建全局实例
window.modelManager = new ModelManager();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModelManager;
}