class AnnotationTool {
    constructor() {
        this.canvas = document.getElementById('annotation-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.currentImage = null;
        this.currentImageData = null;
        this.annotations = [];
        this.isDrawing = false;
        this.startX = 0;
        this.startY = 0;
        this.currentBox = null;
        this.selectedClass = 0;
        this.scale = 1;
        this.projectId = null;
        this.projectData = null;
        this.imageList = [];
        this.currentImageIndex = 0;
        this.isAutoAnnotating = false;
        this.autoAnnotateAbortController = null;
        this.availableModels = [];
        this.selectedModel = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadProject();
    }
    
    setupEventListeners() {
        // 画布事件
        this.canvas.addEventListener('mousedown', this.startDrawing.bind(this));
        this.canvas.addEventListener('mousemove', this.draw.bind(this));
        this.canvas.addEventListener('mouseup', this.stopDrawing.bind(this));
        
        // 按钮事件
        document.getElementById('save-annotation').addEventListener('click', this.saveAnnotation.bind(this));
        document.getElementById('mark-completed').addEventListener('click', this.markCompleted.bind(this));
        document.getElementById('mark-all-completed').addEventListener('click', this.markAllCompleted.bind(this));
        document.getElementById('clear-all').addEventListener('click', this.clearAllAnnotations.bind(this));
        document.getElementById('edit-classes-btn').addEventListener('click', this.showEditProjectClassesModal.bind(this));
        document.getElementById('prev-image').addEventListener('click', this.prevImage.bind(this));
        document.getElementById('next-image').addEventListener('click', this.nextImage.bind(this));
        document.getElementById('zoom-in').addEventListener('click', () => this.zoom(1.2));
        document.getElementById('zoom-out').addEventListener('click', () => this.zoom(0.8));
        document.getElementById('zoom-reset').addEventListener('click', this.resetZoom.bind(this));
        document.getElementById('ai-auto-annotate').addEventListener('click', this.showAutoAnnotateModal.bind(this));
        document.getElementById('stop-auto-annotate').addEventListener('click', this.stopAutoAnnotate.bind(this));
        
        // 键盘快捷键 - 确保事件能够正确捕获
        document.addEventListener('keydown', this.handleKeyboard.bind(this), true);
        // 防止默认行为干扰
        document.addEventListener('keypress', (e) => {
            if (['a', 'd', 'w', 's'].includes(e.key.toLowerCase())) {
                e.preventDefault();
            }
        }, true);
        
        // 搜索
        document.getElementById('image-search').addEventListener('input', this.filterImages.bind(this));
    }
    
    async loadProject() {
        const urlParams = new URLSearchParams(window.location.search);
        this.projectId = urlParams.get('project_id');
        
        if (!this.projectId) {
            alert('未指定项目ID');
            return;
        }
        
        try {
            // 加载项目信息
            const response = await fetch(`/api/annotation/projects/${this.projectId}`);
            this.projectData = await response.json();
            
            this.updateProjectInfo();
            this.loadClasses();
            await this.loadImages();
            await this.loadProjectStats();
            await this.loadAvailableModels();
            
        } catch (error) {
            console.error('加载项目失败:', error);
            alert('加载项目失败');
        }
    }
    
    updateProjectInfo() {
        document.getElementById('project-name').textContent = this.projectData.name;
        document.getElementById('class-count').textContent = this.projectData.classes.length;
    }
    
    loadClasses() {
        const classList = document.getElementById('class-list');
        classList.innerHTML = '';
        
        this.projectData.classes.forEach((className, index) => {
            const classItem = document.createElement('div');
            classItem.className = 'annotation-item';
            classItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span>${className}</span>
                    <span class="badge bg-secondary">${index + 1}</span>
                </div>
            `;
            classItem.addEventListener('click', () => this.selectClass(index, className));
            classList.appendChild(classItem);
        });
        
        // 默认选择第一个类别
        if (this.projectData.classes.length > 0) {
            this.selectClass(0, this.projectData.classes[0]);
        }
    }
    
    selectClass(index, name) {
        this.selectedClass = index;
        document.getElementById('selected-class').textContent = name;
        
        // 更新类别列表的选中状态
        document.querySelectorAll('#class-list .annotation-item').forEach((item, i) => {
            item.classList.toggle('selected', i === index);
        });
    }
    
    async loadImages() {
        try {
            const response = await fetch(`/api/annotation/projects/${this.projectId}/images?limit=10000`);
            this.imageList = await response.json();
            
            this.updateImageList();
            
            if (this.imageList.length > 0) {
                await this.loadImage(0);
            }
            
        } catch (error) {
            console.error('加载图片列表失败:', error);
        }
    }
    
    updateImageList() {
        const imageListContainer = document.getElementById('image-list');
        imageListContainer.innerHTML = '';
        
        this.imageList.forEach((imageData, index) => {
            const imageItem = document.createElement('div');
            imageItem.className = `annotation-item ${index === this.currentImageIndex ? 'selected' : ''}`;
            imageItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span class="text-truncate">${imageData.image_name}</span>
                    <div>
                        ${imageData.is_completed ? '<i class="fas fa-check text-success"></i>' : ''}
                        <span class="badge bg-info">${imageData.annotations.length}</span>
                    </div>
                </div>
            `;
            imageItem.addEventListener('click', () => this.loadImage(index));
            imageListContainer.appendChild(imageItem);
        });
        
        document.getElementById('total-images').textContent = this.imageList.length;
    }
    
    async loadImage(index) {
        if (index < 0 || index >= this.imageList.length) return;
        
        this.currentImageIndex = index;
        this.currentImageData = this.imageList[index];
        
        // 更新图片列表选中状态
        document.querySelectorAll('#image-list .annotation-item').forEach((item, i) => {
            item.classList.toggle('selected', i === index);
        });
        
        // 加载图片
        const img = new Image();
        img.onload = () => {
            this.currentImage = img;
            this.resizeCanvas();
            this.loadAnnotations();
            this.redraw();
            
            document.getElementById('current-image-name').textContent = this.currentImageData.image_name;
        };
        
        // 使用API端点获取图片文件
        img.src = `/api/annotation/projects/${this.projectId}/images/${this.currentImageData.id}/file`;
    }
    
    resizeCanvas() {
        if (!this.currentImage) return;
        
        const maxWidth = 800;
        const maxHeight = 600;
        
        let { width, height } = this.currentImage;
        
        if (width > maxWidth) {
            height = (height * maxWidth) / width;
            width = maxWidth;
        }
        
        if (height > maxHeight) {
            width = (width * maxHeight) / height;
            height = maxHeight;
        }
        
        this.canvas.width = width;
        this.canvas.height = height;
        this.scale = width / this.currentImage.width;
    }
    
    loadAnnotations() {
        this.annotations = this.currentImageData.annotations.map(ann => ({
            class_id: ann.class_id,
            x: ann.x_center * this.canvas.width - (ann.width * this.canvas.width) / 2,
            y: ann.y_center * this.canvas.height - (ann.height * this.canvas.height) / 2,
            width: ann.width * this.canvas.width,
            height: ann.height * this.canvas.height
        }));
        
        this.updateAnnotationList();
    }
    
    updateAnnotationList() {
        const annotationList = document.getElementById('annotation-list');
        annotationList.innerHTML = '';
        
        this.annotations.forEach((ann, index) => {
            const className = this.projectData.classes[ann.class_id] || '未知类别';
            const annItem = document.createElement('div');
            annItem.className = 'annotation-item';
            annItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span>${className}</span>
                    <button class="btn btn-sm btn-outline-danger" onclick="annotationTool.removeAnnotation(${index})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            annotationList.appendChild(annItem);
        });
    }
    
    startDrawing(e) {
        const rect = this.canvas.getBoundingClientRect();
        this.startX = e.clientX - rect.left;
        this.startY = e.clientY - rect.top;
        this.isDrawing = true;
    }
    
    draw(e) {
        if (!this.isDrawing) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;
        
        this.currentBox = {
            x: Math.min(this.startX, currentX),
            y: Math.min(this.startY, currentY),
            width: Math.abs(currentX - this.startX),
            height: Math.abs(currentY - this.startY)
        };
        
        this.redraw();
    }
    
    stopDrawing(e) {
        if (!this.isDrawing) return;
        
        this.isDrawing = false;
        
        if (this.currentBox && this.currentBox.width > 5 && this.currentBox.height > 5) {
            this.annotations.push({
                class_id: this.selectedClass,
                ...this.currentBox
            });
            this.updateAnnotationList();
            // 实时保存
            this.saveAnnotation();
        }
        
        this.currentBox = null;
        this.redraw();
    }
    
    redraw() {
        if (!this.currentImage) return;
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.drawImage(this.currentImage, 0, 0, this.canvas.width, this.canvas.height);
        
        // 绘制已有标注
        this.annotations.forEach((ann, index) => {
            this.drawBox(ann, this.getClassColor(ann.class_id), false);
        });
        
        // 绘制当前正在绘制的框
        if (this.currentBox) {
            this.drawBox(this.currentBox, this.getClassColor(this.selectedClass), true);
        }
    }
    
    drawBox(box, color, isDrawing = false) {
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = isDrawing ? 3 : 2;
        this.ctx.strokeRect(box.x, box.y, box.width, box.height);
        
        // 绘制类别标签
        if (!isDrawing) {
            const className = this.projectData.classes[box.class_id] || '未知';
            this.ctx.fillStyle = color;
            this.ctx.fillRect(box.x, box.y - 20, this.ctx.measureText(className).width + 10, 20);
            this.ctx.fillStyle = 'white';
            this.ctx.font = '12px Arial';
            this.ctx.fillText(className, box.x + 5, box.y - 5);
        }
    }
    
    getClassColor(classId) {
        const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff', '#ffa500', '#800080'];
        return colors[classId % colors.length];
    }
    
    removeAnnotation(index) {
        this.annotations.splice(index, 1);
        this.updateAnnotationList();
        this.redraw();
        // 实时保存
        this.saveAnnotation();
    }
    
    clearAllAnnotations() {
        if (confirm('确定要清除所有标注吗？')) {
            this.annotations = [];
            this.updateAnnotationList();
            this.redraw();
            // 实时保存
            this.saveAnnotation();
        }
    }
    
    async saveAnnotation() {
        if (!this.currentImageData) return;
        
        // 转换为YOLO格式
        const yoloAnnotations = this.annotations.map(ann => ({
            class_id: ann.class_id,
            x_center: (ann.x + ann.width / 2) / this.canvas.width,
            y_center: (ann.y + ann.height / 2) / this.canvas.height,
            width: ann.width / this.canvas.width,
            height: ann.height / this.canvas.height
        }));
        
        try {
            const response = await fetch(`/api/annotation/images/${this.currentImageData.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    annotations: yoloAnnotations
                })
            });
            
            if (response.ok) {
                this.currentImageData.annotations = yoloAnnotations;
                this.updateImageList();
                this.showMessage('标注保存成功', 'success');
            } else {
                this.showMessage('保存失败', 'error');
            }
            
        } catch (error) {
            console.error('保存标注失败:', error);
            this.showMessage('保存失败', 'error');
        }
    }
    
    async markCompleted() {
        if (!this.currentImageData) return;
        
        try {
            const response = await fetch(`/api/annotation/images/${this.currentImageData.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    is_completed: true
                })
            });
            
            if (response.ok) {
                this.currentImageData.is_completed = true;
                this.updateImageList();
                this.showMessage('标记完成成功', 'success');
                await this.loadProjectStats();
            }
            
        } catch (error) {
            console.error('标记完成失败:', error);
        }
    }
    
    async markAllCompleted() {
        // 统计有标注和无标注的图片数量
        const annotatedCount = this.imageList.filter(img => img.annotations && img.annotations.length > 0).length;
        const unannotatedCount = this.imageList.filter(img => !img.annotations || img.annotations.length === 0).length;
        
        const message = `将标记所有 ${this.imageList.length} 张图片为已完成：\n\n` +
                       `有标注的图片：${annotatedCount} 张\n` +
                       `无标注的图片：${unannotatedCount} 张\n\n` +
                       `确定要继续吗？`;
        
        if (!confirm(message)) return;
        
        try {
            const response = await fetch(`/api/annotation/projects/${this.projectId}/mark-all-completed`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                // 更新本地数据
                this.imageList.forEach(img => {
                    img.is_completed = true;
                });
                this.updateImageList();
                await this.loadProjectStats();
                this.showMessage('所有图片已标记为完成', 'success');
            } else {
                this.showMessage('标记失败', 'error');
            }
            
        } catch (error) {
            console.error('一键标记完成失败:', error);
            this.showMessage('标记失败: ' + error.message, 'error');
        }
    }
    
    async loadProjectStats() {
        try {
            const response = await fetch(`/api/annotation/projects/${this.projectId}/stats`);
            const stats = await response.json();
            
            document.getElementById('progress-text').textContent = `${stats.completed_images}/${stats.total_images}`;
            document.getElementById('progress-bar').style.width = `${stats.progress_percentage}%`;
            
        } catch (error) {
            console.error('加载统计信息失败:', error);
        }
    }
    
    prevImage() {
        if (this.currentImageIndex > 0) {
            this.loadImage(this.currentImageIndex - 1);
        }
    }
    
    nextImage() {
        if (this.currentImageIndex < this.imageList.length - 1) {
            this.loadImage(this.currentImageIndex + 1);
        }
    }
    
    zoom(factor) {
        this.scale *= factor;
        this.canvas.style.transform = `scale(${this.scale})`;
    }
    
    resetZoom() {
        this.scale = 1;
        this.canvas.style.transform = 'scale(1)';
    }
    
    handleKeyboard(e) {
        // 防止在输入框中触发快捷键
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        const key = e.key.toLowerCase();
        
        switch(key) {
            case 'a':
            case 'arrowleft':
                e.preventDefault();
                this.prevImage();
                break;
            case 'd':
            case 'arrowright':
                e.preventDefault();
                this.nextImage();
                break;
            case 'w':
                e.preventDefault();
                this.prevClass();
                break;
            case 's':
                if (e.ctrlKey) {
                    e.preventDefault();
                    this.saveAnnotation();
                } else {
                    e.preventDefault();
                    this.nextClass();
                }
                break;
            case 'delete':
                e.preventDefault();
                this.clearAllAnnotations();
                break;
        }
        
        // 数字键选择类别（1-9对应类别0-8）
        const num = parseInt(e.key);
        if (!isNaN(num) && num >= 1 && num <= this.projectData.classes.length && num <= 9) {
            e.preventDefault();
            const classIndex = num - 1;
            this.selectClass(classIndex, this.projectData.classes[classIndex]);
        }
    }
    
    filterImages() {
        const searchTerm = document.getElementById('image-search').value.toLowerCase();
        const imageItems = document.querySelectorAll('#image-list .annotation-item');
        
        imageItems.forEach((item, index) => {
            const imageName = this.imageList[index].image_name.toLowerCase();
            item.style.display = imageName.includes(searchTerm) ? 'block' : 'none';
        });
    }
    
    showMessage(message, type) {
        // 简单的消息提示
        const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        alertDiv.style.top = '20px';
        alertDiv.style.right = '20px';
        alertDiv.style.zIndex = '9999';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alertDiv);
        
        setTimeout(() => {
            alertDiv.remove();
        }, 3000);
    }
    
    // 上一个类别
    prevClass() {
        if (this.projectData.classes.length === 0) return;
        const newIndex = this.selectedClass > 0 ? this.selectedClass - 1 : this.projectData.classes.length - 1;
        this.selectClass(newIndex, this.projectData.classes[newIndex]);
    }
    
    // 下一个类别
    nextClass() {
        if (this.projectData.classes.length === 0) return;
        const newIndex = this.selectedClass < this.projectData.classes.length - 1 ? this.selectedClass + 1 : 0;
        this.selectClass(newIndex, this.projectData.classes[newIndex]);
    }
    
    // 加载可用模型列表
    async loadAvailableModels() {
        try {
            const response = await fetch('/api/models');
            this.availableModels = await response.json();
        } catch (error) {
            console.error('加载模型列表失败:', error);
            this.availableModels = [];
        }
    }
    
    // 显示自动标注模态框
    showAutoAnnotateModal() {
        if (this.availableModels.length === 0) {
            alert('没有可用的模型，请先上传模型文件');
            return;
        }
        
        const modalHtml = `
            <div class="modal fade" id="autoAnnotateModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">AI自动标注</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label for="auto-annotate-model" class="form-label">选择模型</label>
                                <div class="input-group">
                                    <select class="form-select" id="auto-annotate-model" required>
                                        <option value="">请选择模型</option>
                                        ${this.availableModels.map(model => 
                                            `<option value="${model.id}">${model.name} (${model.type})</option>`
                                        ).join('')}
                                    </select>
                                    <button class="btn btn-outline-info" type="button" id="view-model-classes">查看此模型类别</button>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label for="auto-annotate-conf" class="form-label">置信度阈值: <span id="auto-annotate-conf-value">0.25</span></label>
                                <input type="range" class="form-range" id="auto-annotate-conf" min="0.1" max="1.0" step="0.05" value="0.25">
                            </div>
                            <div class="mb-3">
                                <label for="auto-annotate-iou" class="form-label">IoU阈值: <span id="auto-annotate-iou-value">0.45</span></label>
                                <input type="range" class="form-range" id="auto-annotate-iou" min="0.1" max="1.0" step="0.05" value="0.45">
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="auto-annotate-overwrite" checked>
                                <label class="form-check-label" for="auto-annotate-overwrite">
                                    覆盖现有标注
                                </label>
                            </div>
                            <div class="alert alert-info mt-3">
                                <i class="fas fa-info-circle"></i> 系统将使用选定的模型对所有未完成的图片进行自动标注。您可以随时停止并手动调整结果。
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-primary" id="start-auto-annotate">开始标注</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 添加模态框到页面
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        const modal = new bootstrap.Modal(document.getElementById('autoAnnotateModal'));
        
        // 绑定事件
        document.getElementById('auto-annotate-conf').addEventListener('input', (e) => {
            document.getElementById('auto-annotate-conf-value').textContent = e.target.value;
        });
        
        document.getElementById('auto-annotate-iou').addEventListener('input', (e) => {
            document.getElementById('auto-annotate-iou-value').textContent = e.target.value;
        });
        
        document.getElementById('view-model-classes').addEventListener('click', () => {
            const modelId = document.getElementById('auto-annotate-model').value;
            if (modelId) {
                this.showModelClasses(modelId);
            } else {
                alert('请先选择模型');
            }
        });
        
        document.getElementById('start-auto-annotate').addEventListener('click', () => {
            const modelId = document.getElementById('auto-annotate-model').value;
            const confidence = parseFloat(document.getElementById('auto-annotate-conf').value);
            const iou = parseFloat(document.getElementById('auto-annotate-iou').value);
            const overwrite = document.getElementById('auto-annotate-overwrite').checked;
            
            if (!modelId) {
                alert('请选择模型');
                return;
            }
            
            modal.hide();
            this.startAutoAnnotate(modelId, confidence, iou, overwrite);
        });
        
        // 模态框关闭时清理DOM
        document.getElementById('autoAnnotateModal').addEventListener('hidden.bs.modal', () => {
            document.getElementById('autoAnnotateModal').remove();
        });
        
        modal.show();
    }
    
    // 开始自动标注
    async startAutoAnnotate(modelId, confidence, iou, overwrite) {
        this.isAutoAnnotating = true;
        this.autoAnnotateAbortController = new AbortController();
        
        // 更新UI
        document.getElementById('ai-auto-annotate').style.display = 'none';
        document.getElementById('stop-auto-annotate').style.display = 'inline-block';
        
        try {
            // 获取未完成的图片列表
            const uncompletedImages = this.imageList.filter(img => !img.is_completed);
            
            if (uncompletedImages.length === 0) {
                this.showMessage('所有图片已完成标注', 'info');
                this.stopAutoAnnotate();
                return;
            }
            
            this.showMessage(`开始自动标注 ${uncompletedImages.length} 张图片...`, 'info');
            
            for (let i = 0; i < uncompletedImages.length; i++) {
                if (!this.isAutoAnnotating) break;
                
                const imageData = uncompletedImages[i];
                const imageIndex = this.imageList.findIndex(img => img.id === imageData.id);
                
                // 切换到当前图片
                await this.loadImage(imageIndex);
                
                // 调用AI标注API
                await this.annotateImageWithAI(imageData.id, modelId, confidence, iou, overwrite);
                
                // 更新进度
                const progress = Math.round(((i + 1) / uncompletedImages.length) * 100);
                this.showMessage(`标注进度: ${progress}% (${i + 1}/${uncompletedImages.length})`, 'info');
                
                // 等待一小段时间避免过快请求
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            
            if (this.isAutoAnnotating) {
                this.showMessage('自动标注完成', 'success');
            }
            
        } catch (error) {
            console.error('自动标注失败:', error);
            this.showMessage('自动标注失败: ' + error.message, 'error');
        } finally {
            this.stopAutoAnnotate();
        }
    }
    
    // 停止自动标注
    stopAutoAnnotate() {
        this.isAutoAnnotating = false;
        if (this.autoAnnotateAbortController) {
            this.autoAnnotateAbortController.abort();
            this.autoAnnotateAbortController = null;
        }
        
        // 更新UI
        document.getElementById('ai-auto-annotate').style.display = 'inline-block';
        document.getElementById('stop-auto-annotate').style.display = 'none';
    }
    
    // 显示模型类别
    async showModelClasses(modelId) {
        try {
            const response = await fetch(`/api/models/${modelId}/classes`);
            const data = await response.json();
            
            if (data.classes) {
                this.showEditableClassesModal(data.classes);
            }
        } catch (error) {
            console.error('获取模型类别失败:', error);
            alert('获取模型类别失败');
        }
    }
    
    // 显示可编辑类别模态框
    showEditableClassesModal(classes) {
        const modalHtml = `
            <div class="modal fade" id="editClassesModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">模型类别列表</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle"></i> 可以修改类别名称，但不会改变类别顺序
                            </div>
                            <div id="editable-classes-list">
                                ${classes.map((className, index) => `
                                    <div class="mb-2">
                                        <div class="input-group input-group-sm">
                                            <span class="input-group-text">${index}</span>
                                            <input type="text" class="form-control" value="${className}" data-class-index="${index}">
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                            <button type="button" class="btn btn-primary" id="save-model-classes">保存到项目</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('editClassesModal'));
        
        document.getElementById('save-model-classes').addEventListener('click', () => {
            const inputs = document.querySelectorAll('#editable-classes-list input');
            const editedClasses = [];
            inputs.forEach(input => {
                if (input.value.trim()) {
                    editedClasses.push(input.value.trim());
                }
            });
            
            if (editedClasses.length > 0) {
                this.updateProjectClasses(editedClasses);
                modal.hide();
            } else {
                alert('请至少保留一个类别');
            }
        });
        
        document.getElementById('editClassesModal').addEventListener('hidden.bs.modal', () => {
            document.getElementById('editClassesModal').remove();
        });
        
        modal.show();
    }
    
    // 显示编辑项目类别模态框
    showEditProjectClassesModal() {
        const modalHtml = `
            <div class="modal fade" id="editProjectClassesModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">编辑项目类别</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="project-classes-list">
                                ${this.projectData.classes.map((className, index) => `
                                    <div class="mb-2 class-item" data-index="${index}">
                                        <div class="input-group input-group-sm">
                                            <span class="input-group-text">${index + 1}</span>
                                            <input type="text" class="form-control" value="${className}">
                                            <button class="btn btn-outline-danger" type="button" onclick="this.closest('.class-item').remove()">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                            <button class="btn btn-outline-success btn-sm" id="add-class-btn">
                                <i class="fas fa-plus"></i> 添加类别
                            </button>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                            <button type="button" class="btn btn-primary" id="save-project-classes">保存</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('editProjectClassesModal'));
        
        // 添加类别按钮事件
        document.getElementById('add-class-btn').addEventListener('click', () => {
            const container = document.getElementById('project-classes-list');
            const newIndex = container.children.length;
            const newClassHtml = `
                <div class="mb-2 class-item" data-index="${newIndex}">
                    <div class="input-group input-group-sm">
                        <span class="input-group-text">${newIndex + 1}</span>
                        <input type="text" class="form-control" value="新类别${newIndex + 1}" placeholder="输入类别名称">
                        <button class="btn btn-outline-danger" type="button" onclick="this.closest('.class-item').remove()">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', newClassHtml);
        });
        
        // 保存按钮事件
        document.getElementById('save-project-classes').addEventListener('click', () => {
            const inputs = document.querySelectorAll('#project-classes-list input');
            const newClasses = [];
            inputs.forEach(input => {
                if (input.value.trim()) {
                    newClasses.push(input.value.trim());
                }
            });
            
            if (newClasses.length === 0) {
                alert('请至少保留一个类别');
                return;
            }
            
            this.updateProjectClasses(newClasses);
            modal.hide();
        });
        
        document.getElementById('editProjectClassesModal').addEventListener('hidden.bs.modal', () => {
            document.getElementById('editProjectClassesModal').remove();
        });
        
        modal.show();
    }
    
    // 更新项目类别
    async updateProjectClasses(newClasses) {
        try {
            const response = await fetch(`/api/annotation/projects/${this.projectId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    classes: newClasses
                })
            });
            
            if (response.ok) {
                this.projectData.classes = newClasses;
                this.updateProjectInfo();
                this.loadClasses();
                this.showMessage('项目类别已更新', 'success');
            } else {
                const errorData = await response.json();
                this.showMessage('更新失败: ' + (errorData.detail || '未知错误'), 'error');
            }
        } catch (error) {
            console.error('更新项目类别失败:', error);
            this.showMessage('更新失败: ' + error.message, 'error');
        }
    }
    
    // 使用AI模型标注单张图片
    async annotateImageWithAI(imageId, modelId, confidence, iou, overwrite) {
        try {
            const response = await fetch(`/api/annotation/images/${imageId}/auto-annotate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    model_id: modelId,
                    confidence: confidence,
                    iou: iou,
                    overwrite: overwrite
                }),
                signal: this.autoAnnotateAbortController?.signal
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // 更新当前图片的标注数据
            if (this.currentImageData && this.currentImageData.id === imageId) {
                this.currentImageData.annotations = result.annotations;
                this.loadAnnotations();
                this.redraw();
            }
            
            // 更新图片列表中的数据
            const imageIndex = this.imageList.findIndex(img => img.id === imageId);
            if (imageIndex !== -1) {
                this.imageList[imageIndex].annotations = result.annotations;
                this.updateImageList();
            }
            
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('标注被用户取消');
            } else {
                console.error('自动标注失败:', error);
                throw error;
            }
        }
    }
}

// 初始化标注工具
let annotationTool;
document.addEventListener('DOMContentLoaded', () => {
    annotationTool = new AnnotationTool();
});