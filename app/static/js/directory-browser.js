/**
 * 目录浏览器组件
 * 用于浏览和选择本地目录
 */
class DirectoryBrowser {
    constructor() {
        this.currentPath = '';
        this.selectedPath = '';
        this.onSelectCallback = null;
        this.modal = null;
        this.init();
    }

    init() {
        this.createModal();
    }

    createModal() {
        // 创建模态框HTML
        const modalHtml = `
            <div class="modal fade" id="directoryBrowserModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">选择目录</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <nav aria-label="breadcrumb">
                                    <ol class="breadcrumb" id="directory-breadcrumb">
                                        <li class="breadcrumb-item active">加载中...</li>
                                    </ol>
                                </nav>
                            </div>
                            
                            <div class="mb-3">
                                <div class="input-group">
                                    <input type="text" class="form-control" id="current-path-input" readonly>
                                    <button class="btn btn-outline-secondary" type="button" id="scan-images-btn">
                                        <i class="bi bi-search"></i> 扫描图片
                                    </button>
                                </div>
                            </div>

                            <div id="image-scan-result" class="alert alert-info" style="display: none;">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <strong>扫描结果：</strong> 
                                        找到 <span id="scanned-image-count">0</span> 张图片
                                    </div>
                                    <div>
                                        <small class="text-muted">支持格式：jpg, jpeg, png, bmp, webp, tiff, tif</small>
                                    </div>
                                </div>
                                <div class="mt-2" id="sample-images-container" style="display: none;">
                                    <small class="text-muted">示例图片：</small>
                                    <div id="sample-images-list" class="mt-1"></div>
                                </div>
                            </div>

                            <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                                <table class="table table-hover">
                                    <thead class="table-light sticky-top">
                                        <tr>
                                            <th width="50"><i class="bi bi-folder"></i></th>
                                            <th>名称</th>
                                            <th width="100">操作</th>
                                        </tr>
                                    </thead>
                                    <tbody id="directory-list">
                                        <tr>
                                            <td colspan="3" class="text-center">加载中...</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-primary" id="select-directory-btn" disabled>选择此目录</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 添加到页面
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // 获取模态框元素
        this.modal = new bootstrap.Modal(document.getElementById('directoryBrowserModal'));
        
        // 绑定事件
        this.bindEvents();
    }

    bindEvents() {
        // 扫描图片按钮
        document.getElementById('scan-images-btn').addEventListener('click', () => {
            this.scanImages();
        });

        // 选择目录按钮
        document.getElementById('select-directory-btn').addEventListener('click', () => {
            this.selectDirectory();
        });

        // 模态框显示时加载根目录
        document.getElementById('directoryBrowserModal').addEventListener('shown.bs.modal', () => {
            this.loadDirectory();
        });
    }

    async loadDirectory(path = '') {
        try {
            const response = await fetch(`/api/annotation/browse-directories?path=${encodeURIComponent(path)}`);
            const data = await response.json();

            this.currentPath = data.current_path;
            document.getElementById('current-path-input').value = this.currentPath;

            // 更新面包屑导航
            this.updateBreadcrumb();

            // 更新目录列表
            this.updateDirectoryList(data.items);

            // 更新选择按钮状态
            this.updateSelectButton();

        } catch (error) {
            console.error('加载目录失败:', error);
            this.showError('加载目录失败: ' + error.message);
        }
    }

    updateBreadcrumb() {
        const breadcrumb = document.getElementById('directory-breadcrumb');
        breadcrumb.innerHTML = '';

        if (!this.currentPath) {
            breadcrumb.innerHTML = '<li class="breadcrumb-item active">根目录</li>';
            return;
        }

        // 添加根目录链接
        const rootItem = document.createElement('li');
        rootItem.className = 'breadcrumb-item';
        rootItem.innerHTML = '<a href="#" data-path="">根目录</a>';
        rootItem.querySelector('a').addEventListener('click', (e) => {
            e.preventDefault();
            this.loadDirectory('');
        });
        breadcrumb.appendChild(rootItem);

        // 分割路径并创建面包屑
        const pathParts = this.currentPath.split(/[/\\]/).filter(part => part);
        let currentPath = '';

        pathParts.forEach((part, index) => {
            currentPath += (currentPath ? '/' : '') + part;
            const item = document.createElement('li');
            
            if (index === pathParts.length - 1) {
                // 最后一个是当前目录
                item.className = 'breadcrumb-item active';
                item.textContent = part;
            } else {
                // 其他的是链接
                item.className = 'breadcrumb-item';
                const link = document.createElement('a');
                link.href = '#';
                link.textContent = part;
                link.dataset.path = currentPath;
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.loadDirectory(e.target.dataset.path);
                });
                item.appendChild(link);
            }
            
            breadcrumb.appendChild(item);
        });
    }

    updateDirectoryList(items) {
        const tbody = document.getElementById('directory-list');
        tbody.innerHTML = '';

        if (items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">此目录为空</td></tr>';
            return;
        }

        items.forEach(item => {
            const row = document.createElement('tr');
            row.className = 'directory-item';
            row.dataset.path = item.path;
            
            let icon = '';
            if (item.type === 'parent') {
                icon = '<i class="bi bi-arrow-up-circle text-primary"></i>';
            } else if (item.type === 'drive') {
                icon = '<i class="bi bi-device-hdd text-warning"></i>';
            } else {
                icon = '<i class="bi bi-folder text-primary"></i>';
            }

            row.innerHTML = `
                <td>${icon}</td>
                <td>
                    <a href="#" class="text-decoration-none directory-link" data-path="${item.path}">
                        ${item.name}
                    </a>
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-primary select-btn" data-path="${item.path}">
                        选择
                    </button>
                </td>
            `;

            // 绑定点击事件
            const link = row.querySelector('.directory-link');
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.loadDirectory(item.path);
            });

            const selectBtn = row.querySelector('.select-btn');
            selectBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.selectedPath = item.path;
                this.updateSelectButton();
                // 高亮选中的行
                document.querySelectorAll('.directory-item').forEach(r => r.classList.remove('table-active'));
                row.classList.add('table-active');
            });

            tbody.appendChild(row);
        });
    }

    updateSelectButton() {
        const selectBtn = document.getElementById('select-directory-btn');
        if (this.currentPath || this.selectedPath) {
            selectBtn.disabled = false;
            selectBtn.textContent = `选择: ${this.selectedPath || this.currentPath}`;
        } else {
            selectBtn.disabled = true;
            selectBtn.textContent = '选择此目录';
        }
    }

    async scanImages() {
        const pathToScan = this.selectedPath || this.currentPath;
        if (!pathToScan) {
            this.showError('请先选择一个目录');
            return;
        }

        try {
            const response = await fetch(`/api/annotation/scan-directory-images?directory_path=${encodeURIComponent(pathToScan)}`);
            const data = await response.json();

            const resultDiv = document.getElementById('image-scan-result');
            const countSpan = document.getElementById('scanned-image-count');
            const sampleContainer = document.getElementById('sample-images-container');
            const sampleList = document.getElementById('sample-images-list');

            countSpan.textContent = data.image_count;
            resultDiv.style.display = 'block';

            if (data.sample_images && data.sample_images.length > 0) {
                sampleContainer.style.display = 'block';
                sampleList.innerHTML = data.sample_images.map(img => 
                    `<span class="badge bg-light text-dark me-1">${img.name}</span>`
                ).join('');
            } else {
                sampleContainer.style.display = 'none';
            }

            // 更新结果样式
            if (data.is_valid) {
                resultDiv.className = 'alert alert-success';
            } else {
                resultDiv.className = 'alert alert-warning';
            }

        } catch (error) {
            console.error('扫描图片失败:', error);
            this.showError('扫描图片失败: ' + error.message);
        }
    }

    selectDirectory() {
        const pathToSelect = this.selectedPath || this.currentPath;
        if (pathToSelect && this.onSelectCallback) {
            this.onSelectCallback(pathToSelect);
        }
        this.modal.hide();
    }

    showError(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const modalBody = document.querySelector('#directoryBrowserModal .modal-body');
        modalBody.insertBefore(alertDiv, modalBody.firstChild);
    }

    // 公共方法：显示目录选择器
    show(callback) {
        this.onSelectCallback = callback;
        this.selectedPath = '';
        this.modal.show();
    }
}

// 创建全局实例
window.directoryBrowser = new DirectoryBrowser();