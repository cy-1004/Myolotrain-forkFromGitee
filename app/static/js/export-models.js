// 导出模型功能模块
class ExportModelsManager {
    constructor() {
        // 导出模型相关属性
        this.initModalEventListeners();
    }

    // 初始化模态框事件监听器
    initModalEventListeners() {
        // 获取模态框元素
        const modalElement = document.getElementById('mainModal');
        if (modalElement) {
            // 监听模态框隐藏事件
            modalElement.addEventListener('hidden.bs.modal', (event) => {
                // 模态框关闭时恢复确定按钮的显示
                const modalSubmit = document.getElementById('modalSubmit');
                if (modalSubmit) {
                    modalSubmit.style.display = 'inline-block';
                }
            });
        }
    }

    // 导出模型
    exportModels(taskId) {
        // 获取任务信息
        authenticatedFetch(`${API_URL}/training/${taskId}`)
            .then(response => response.json())
            .then(task => {
                // 显示导出模型模态框
                this.showExportModelsModal(taskId, task);
            })
            .catch(error => {
                console.error('Error fetching task info:', error);
                alert('获取任务信息失败');
            });
    }

    // 显示导出模型模态框
    showExportModelsModal(taskId, task) {
        const modalTitle = document.querySelector('.modal-title');
        const modalBody = document.querySelector('.modal-body');
        const modalSubmit = document.getElementById('modalSubmit');

        modalTitle.textContent = '导出模型';

        // 隐藏确定按钮，因为导出模型页面不需要
        modalSubmit.style.display = 'none';

        // 获取模板内容
        const template = document.getElementById('export-models-template');
        if (template) {
            modalBody.innerHTML = template.innerHTML;
            
            // 设置任务ID
            const downloadBestBtn = modalBody.querySelector('.download-best');
            const uploadBestBtn = modalBody.querySelector('.upload-best-to-models');
            const downloadLastBtn = modalBody.querySelector('.download-last');
            const uploadLastBtn = modalBody.querySelector('.upload-last-to-models');
            
            if (downloadBestBtn) downloadBestBtn.setAttribute('data-task-id', taskId);
            if (uploadBestBtn) uploadBestBtn.setAttribute('data-task-id', taskId);
            if (downloadLastBtn) downloadLastBtn.setAttribute('data-task-id', taskId);
            if (uploadLastBtn) uploadLastBtn.setAttribute('data-task-id', taskId);
        } else {
            // 如果模板不存在，创建默认内容
            modalBody.innerHTML = `
                <div class="container-fluid">
                    <div class="row">
                        <div class="col-12">
                            <p>请选择要导出的模型文件：</p>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <div class="card">
                                <div class="card-header">
                                    <h6>最佳模型 (best.pt)</h6>
                                </div>
                                <div class="card-body">
                                    <p>训练过程中表现最好的模型权重</p>
                                    <div class="d-grid gap-2">
                                        <button class="btn btn-primary download-best" data-task-id="${taskId}">
                                            <i class="bi bi-download"></i> 下载到本地
                                        </button>
                                        <button class="btn btn-success upload-best-to-models" data-task-id="${taskId}">
                                            <i class="bi bi-cloud-upload"></i> 上传到模型管理
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6 mb-3">
                            <div class="card">
                                <div class="card-header">
                                    <h6>最后模型 (last.pt)</h6>
                                </div>
                                <div class="card-body">
                                    <p>训练完成时的最后一个模型权重</p>
                                    <div class="d-grid gap-2">
                                        <button class="btn btn-primary download-last" data-task-id="${taskId}">
                                            <i class="bi bi-download"></i> 下载到本地
                                        </button>
                                        <button class="btn btn-success upload-last-to-models" data-task-id="${taskId}">
                                            <i class="bi bi-cloud-upload"></i> 上传到模型管理
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        // 显示模态框
        const modalElement = document.getElementById('mainModal');
        const modal = new bootstrap.Modal(modalElement);
        modal.show();

        // 绑定下载和上传按钮事件
        setTimeout(() => {
            // 下载最佳模型
            const downloadBestBtn = document.querySelector('.download-best');
            if (downloadBestBtn) {
                downloadBestBtn.addEventListener('click', (e) => {
                    const taskId = e.target.getAttribute('data-task-id') || e.target.closest('button').getAttribute('data-task-id');
                    this.downloadModel(taskId, 'best');
                });
            }

            // 上传最佳模型到模型管理
            const uploadBestBtn = document.querySelector('.upload-best-to-models');
            if (uploadBestBtn) {
                uploadBestBtn.addEventListener('click', (e) => {
                    const taskId = e.target.getAttribute('data-task-id') || e.target.closest('button').getAttribute('data-task-id');
                    this.uploadModelToModels(taskId, 'best');
                });
            }

            // 下载最后模型
            const downloadLastBtn = document.querySelector('.download-last');
            if (downloadLastBtn) {
                downloadLastBtn.addEventListener('click', (e) => {
                    const taskId = e.target.getAttribute('data-task-id') || e.target.closest('button').getAttribute('data-task-id');
                    this.downloadModel(taskId, 'last');
                });
            }

            // 上传最后模型到模型管理
            const uploadLastBtn = document.querySelector('.upload-last-to-models');
            if (uploadLastBtn) {
                uploadLastBtn.addEventListener('click', (e) => {
                    const taskId = e.target.getAttribute('data-task-id') || e.target.closest('button').getAttribute('data-task-id');
                    this.uploadModelToModels(taskId, 'last');
                });
            }
        }, 100);
    }

    // 下载模型
    downloadModel(taskId, modelType) {
        const modelName = modelType === 'best' ? 'best.pt' : 'last.pt';
        const downloadUrl = `${API_URL}/training/${taskId}/download-model/${modelType}`;
        
        // 创建一个隐藏的a标签用于下载
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `${modelName}`;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    // 上传模型到模型管理
    uploadModelToModels(taskId, modelType) {
        const modelName = modelType === 'best' ? 'best.pt' : 'last.pt';
        
        // 显示确认对话框
        if (!confirm(`确定要将${modelType === 'best' ? '最佳模型' : '最后模型'}上传到模型管理吗？`)) {
            return;
        }

        // 显示加载提示
        const loadingToast = this.showToast(`正在上传${modelType === 'best' ? '最佳模型' : '最后模型'}...`, 'info', 0);

        // 发送上传请求
        authenticatedFetch(`${API_URL}/training/${taskId}/upload-model/${modelType}`, {
            method: 'POST'
        })
        .then(response => {
            // 隐藏加载提示
            this.hideToast(loadingToast);

            if (response.ok) {
                return response.json();
            } else {
                return response.json().then(data => {
                    throw new Error(data.detail || `上传${modelType === 'best' ? '最佳模型' : '最后模型'}失败`);
                });
            }
        })
        .then(result => {
            this.showToast(`模型已成功上传到模型管理`, 'success', 3000);
            console.log('Upload result:', result);
        })
        .catch(error => {
            // 隐藏加载提示
            this.hideToast(loadingToast);
            console.error(`Error uploading ${modelType} model:`, error);
            this.showToast(`上传失败: ${error.message}`, 'error', 5000);
        });
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
window.exportModelsManager = new ExportModelsManager();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ExportModelsManager;
}