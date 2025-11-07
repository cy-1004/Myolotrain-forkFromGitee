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

                    row.innerHTML = `
                        <td>${displayName}</td>
                        <td>${model.description || '-'}</td>
                        <td>${model.type}</td>
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
                alert('上传模型失败: ' + xhr.statusText);
            }
        };

        // 上传错误事件
        xhr.onerror = () => {
            // 重置按钮状态
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.textContent = '确定';
            }
            alert('上传模型失败');
        };

        // 设置超时处理
        setTimeout(() => {
            if (submitButton && submitButton.disabled) {
                submitButton.disabled = false;
                submitButton.textContent = '确定';
                alert('上传操作超时，请刷新页面后重试');
            }
        }, 60000); // 60秒超时

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
        if (!confirm('确定要删除这个模型吗？此操作不可恢复。')) {
            return;
        }

        authenticatedFetch(`${API_URL}/models/${modelId}`, {
            method: 'DELETE'
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
    }

    // 获取任务类型文本
    getTaskText(task) {
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
}

// 创建全局实例
window.modelManager = new ModelManager();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ModelManager;
}