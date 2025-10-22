// 标注管理器主类
class AnnotationManager {
    constructor() {
        this.currentProject = null;
        this.currentImage = null;
        this.currentImageIndex = 0;
        this.images = [];
        this.classes = [];
        this.currentClassIndex = 0;
        this.annotationHistory = [];
        this.annotationsVisible = true;
        
        this.canvas = null;
        this.shortcuts = null;
        
        this.init();
    }
    
    async init() {
        // 初始化画布
        this.canvas = new AnnotationCanvas('annotationCanvas', 'currentImage');
        
        // 初始化快捷键
        this.shortcuts = new AnnotationShortcuts(this);
        
        // 绑定事件
        this.bindEvents();
        
        // 加载项目列表
        await this.loadProjects();
    }
    
    bindEvents() {
        // 项目选择
        document.getElementById('projectSelect').addEventListener('change', (e) => {
            if (e.target.value) {
                this.loadProject(e.target.value);
            }
        });
        
        // 类别选择
        document.getElementById('classSelect').addEventListener('change', (e) => {
            this.setCurrentClass(parseInt(e.target.value));
        });
        
        // 按钮事件
        document.getElementById('saveBtn').addEventListener('click', () => {
            this.saveCurrentImage();
        });
        
        document.getElementById('exportBtn').addEventListener('click', () => {
            this.showExportModal();
        });
        
        document.getElementById('helpBtn').addEventListener('click', () => {
            const modal = new bootstrap.Modal(document.getElementById('helpModal'));
            modal.show();
        });
        
        // 新增：辅助线切换按钮（使用annotation.js中的功能）
        const toggleGuidelinesBtn = document.getElementById('toggleGuidelinesBtn');
        if (toggleGuidelinesBtn) {
            toggleGuidelinesBtn.addEventListener('click', () => {
                if (window.annotationTool) {
                    window.annotationTool.toggleGuidelines();
                }
            });
        }
        
        // 新增：辅助线颜色选择器（使用annotation.js中的功能）
        const guidelineColorPicker = document.getElementById('guideline-color');
        if (guidelineColorPicker) {
            guidelineColorPicker.addEventListener('input', (e) => {
                if (window.annotationTool) {
                    window.annotationTool.setGuidelineColor(e.target.value);
                }
            });
        }
        
        // 新增：缩放按钮（使用annotation.js中的功能）
        const zoomInBtn = document.getElementById('zoomInBtn');
        const zoomOutBtn = document.getElementById('zoomOutBtn');
        const resetZoomBtn = document.getElementById('resetZoomBtn');
        
        if (zoomInBtn) {
            zoomInBtn.addEventListener('click', () => {
                if (window.annotationTool) {
                    window.annotationTool.zoom(1.2);
                }
            });
        }
        
        if (zoomOutBtn) {
            zoomOutBtn.addEventListener('click', () => {
                if (window.annotationTool) {
                    window.annotationTool.zoom(0.8);
                }
            });
        }
        
        if (resetZoomBtn) {
            resetZoomBtn.addEventListener('click', () => {
                if (window.annotationTool) {
                    window.annotationTool.resetZoom();
                }
            });
        }
        
        // 导出相关事件
        document.getElementById('splitData').addEventListener('change', (e) => {
            document.getElementById('splitOptions').style.display = e.target.checked ? 'block' : 'none';
        });
        
        document.getElementById('confirmExport').addEventListener('click', () => {
            this.exportProject();
        });
    }
    
    // 新增：切换辅助线显示（供AnnotationShortcuts调用）
    toggleGuidelines() {
        if (window.annotationTool) {
            window.annotationTool.toggleGuidelines();
            const btn = document.getElementById('toggleGuidelinesBtn');
            if (btn) {
                // 更新按钮文本和样式
                btn.textContent = window.annotationTool.showGuidelines ? '隐藏辅助线' : '显示辅助线';
                btn.className = window.annotationTool.showGuidelines ? 'btn btn-secondary' : 'btn btn-outline-secondary';
            }
        }
    }
    
    async loadProjects() {
        try {
            const response = await fetch('/api/annotation/projects/');
            const projects = await response.json();
            
            const select = document.getElementById('projectSelect');
            select.innerHTML = '<option value="">选择标注项目</option>';
            
            projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.id;
                option.textContent = project.name;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('加载项目列表失败:', error);
            this.showError('加载项目列表失败');
        }
    }
    
    async loadProject(projectId) {
        try {
            // 加载项目信息
            const projectResponse = await fetch(`/api/annotation/projects/${projectId}`);
            this.currentProject = await projectResponse.json();
            
            // 加载项目图片
            const imagesResponse = await fetch(`/api/annotation/projects/${projectId}/images`);
            this.images = await imagesResponse.json();
            
            // 设置类别
            this.classes = this.currentProject.classes;
            this.updateClassSelect();
            
            // 加载图片列表
            this.updateImageList();
            
            // 加载第一张图片
            if (this.images.length > 0) {
                this.currentImageIndex = 0;
                await this.loadImage(0);
            }
            
            // 更新进度
            await this.updateProgress();
            
            // 更新项目状态显示
            this.updateProjectStatus();
            
            this.updateStatus(`已加载项目: ${this.currentProject.name}`);
        } catch (error) {
            console.error('加载项目失败:', error);
            this.showError('加载项目失败');
        }
    }
    
    // 更新项目状态显示
    updateProjectStatus() {
        if (!this.currentProject) return;
        
        const statusElement = document.getElementById('projectStatus');
        if (!statusElement) return;
        
        // 根据项目完成状态设置状态标签
        let statusClass = 'bg-secondary';
        let statusText = '未开始';
        
        // 检查是否有已完成的图片
        const completedImages = this.images.filter(img => img.is_completed);
        
        if (completedImages.length === this.images.length) {
            statusClass = 'bg-success';
            statusText = '已完成';
        } else if (completedImages.length > 0) {
            statusClass = 'bg-warning';
            statusText = '进行中';
        }
        
        statusElement.className = `badge ${statusClass}`;
        statusElement.textContent = statusText;
    }
    
    updateClassSelect() {
        const select = document.getElementById('classSelect');
        select.innerHTML = '';
        
        this.classes.forEach((className, index) => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = className;
            select.appendChild(option);
        });
        
        if (this.classes.length > 0) {
            select.value = this.currentClassIndex;
        }
    }
    
    updateImageList() {
        const listContainer = document.getElementById('imageList');
        listContainer.innerHTML = '';
        
        this.images.forEach((image, index) => {
            const item = document.createElement('div');
            item.className = 'list-group-item image-list-item d-flex justify-content-between align-items-center';
            item.style.cursor = 'pointer';
            
            const nameSpan = document.createElement('span');
            nameSpan.textContent = image.image_name;
            
            const badgeSpan = document.createElement('span');
            if (image.is_completed) {
                badgeSpan.className = 'badge bg-success';
                badgeSpan.textContent = '已完成';
            } else if (image.annotations && image.annotations.length > 0) {
                badgeSpan.className = 'badge bg-warning';
                badgeSpan.textContent = `部分标注(${image.annotations.length})`;
            } else {
                badgeSpan.className = 'badge bg-secondary';
                badgeSpan.textContent = '未标注';
            }
            
            item.appendChild(nameSpan);
            item.appendChild(badgeSpan);
            
            item.addEventListener('click', () => {
                this.loadImage(index);
            });
            
            listContainer.appendChild(item);
        });
    }
    
    async loadImage(index) {
        if (index < 0 || index >= this.images.length) return;
        
        this.currentImageIndex = index;
        this.currentImage = this.images[index];
        
        // 更新图片列表选中状态
        document.querySelectorAll('.image-list-item').forEach((item, i) => {
            item.classList.toggle('active', i === index);
        });
        
        // 加载图片
        const imagePath = `/static/datasets/${this.currentImage.image_path}`;
        this.canvas.loadImage(imagePath);
        
        // 加载标注
        this.canvas.loadAnnotations(this.currentImage.annotations || []);
        
        this.updateStatus(`图片 ${index + 1}/${this.images.length}: ${this.currentImage.image_name}`);
    }
    
    async saveCurrentImage() {
        if (!this.currentImage) return;
        
        try {
            const annotations = this.canvas.annotations.map(ann => ({
                class_id: ann.class_id,
                x_center: ann.x_center,
                y_center: ann.y_center,
                width: ann.width,
                height: ann.height
            }));
            
            const response = await fetch(`/api/annotation/images/${this.currentImage.id}/annotations`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(annotations)
            });
            
            if (response.ok) {
                const updatedImage = await response.json();
                this.images[this.currentImageIndex] = updatedImage;
                this.currentImage = updatedImage;
                
                this.updateImageList();
                this.updateProgress();
                this.updateStatus('标注已保存');
            } else {
                throw new Error('保存失败');
            }
        } catch (error) {
            console.error('保存标注失败:', error);
            this.showError('保存标注失败');
        }
    }
    
    async updateProgress() {
        if (!this.currentProject) return;
        
        try {
            const response = await fetch(`/api/annotation/projects/${this.currentProject.id}/stats`);
            const stats = await response.json();
            
            const progressBar = document.getElementById('progressBar');
            const progressContainer = document.getElementById('progressContainer');
            const progressText = document.getElementById('progressText');
            
            // 更新进度条宽度和文本
            progressBar.style.width = `${stats.progress_percentage}%`;
            
            // 添加进度文本元素（如果不存在）
            if (!progressText) {
                const textElement = document.createElement('div');
                textElement.id = 'progressText';
                textElement.className = 'progress-text';
                textElement.style.position = 'absolute';
                textElement.style.top = '45%';  // 稍微向上调整位置
                textElement.style.left = '50%';
                textElement.style.transform = 'translate(-50%, -50%)';
                textElement.style.fontWeight = 'bold';
                textElement.style.textShadow = '0 0 2px rgba(0,0,0,0.5)';
                textElement.style.zIndex = '10';
                progressContainer.appendChild(textElement);
            }
            
            // 更新进度文本
            document.getElementById('progressText').textContent = `${stats.progress_percentage}%`;
            
            // 设置进度条容器样式，确保对齐
            if (progressContainer) {
                progressContainer.style.position = 'relative';
                progressContainer.style.margin = '0';
                progressContainer.style.padding = '0';
                progressContainer.style.height = '24px';  // 固定高度
                progressContainer.style.overflow = 'hidden';
            }
            
            // 设置进度条样式
            progressBar.style.display = 'flex';
            progressBar.style.alignItems = 'center';
            progressBar.style.justifyContent = 'center';
            progressBar.style.color = 'white';
            progressBar.style.overflow = 'visible';
            progressBar.style.height = '100%';  // 充满容器高度
        } catch (error) {
            console.error('更新进度失败:', error);
        }
    }
    
    // 快捷键操作方法
    previousImage() {
        if (this.currentImageIndex > 0) {
            this.loadImage(this.currentImageIndex - 1);
        }
    }
    
    nextImage() {
        if (this.currentImageIndex < this.images.length - 1) {
            this.loadImage(this.currentImageIndex + 1);
        }
    }
    
    previousClass() {
        if (this.currentClassIndex > 0) {
            this.setCurrentClass(this.currentClassIndex - 1);
        }
    }
    
    nextClass() {
        if (this.currentClassIndex < this.classes.length - 1) {
            this.setCurrentClass(this.currentClassIndex + 1);
        }
    }
    
    setCurrentClass(classIndex) {
        if (classIndex >= 0 && classIndex < this.classes.length) {
            this.currentClassIndex = classIndex;
            document.getElementById('classSelect').value = classIndex;
            this.canvas.setCurrentClass(classIndex);
            this.updateStatus(`当前类别: ${this.classes[classIndex]}`);
        }
    }
    
    deleteSelectedAnnotation() {
        this.canvas.deleteSelectedAnnotation();
    }
    
    confirmCurrentAnnotation() {
        // 当前实现中，标注在鼠标释放时自动确认
        this.updateStatus('标注已确认');
    }
    
    cancelCurrentOperation() {
        this.canvas.selectedAnnotation = null;
        this.canvas.currentAnnotation = null;
        this.canvas.redraw();
        this.updateStatus('操作已取消');
    }
    
    toggleAnnotationVisibility() {
        this.annotationsVisible = !this.annotationsVisible;
        this.canvas.canvas.style.display = this.annotationsVisible ? 'block' : 'none';
        this.updateStatus(`标注框${this.annotationsVisible ? '显示' : '隐藏'}`);
    }
    
    undo() {
        if (this.canvas.annotations.length > 0) {
            this.canvas.annotations.pop();
            this.canvas.redraw();
            this.canvas.onAnnotationsChanged();
            this.updateStatus('已撤销上一个标注');
        }
    }
    
    fitImageToWindow() {
        this.canvas.resizeCanvas();
        this.updateStatus('已适应窗口大小');
    }
    
    // 工具方法
    getClassName(classId) {
        return this.classes[classId] || `Class ${classId}`;
    }
    
    onAnnotationsChanged(annotations) {
        // 自动保存（可选）
        // this.saveCurrentImage();
    }
    
    showExportModal() {
        if (!this.currentProject) {
            this.showError('请先选择一个项目');
            return;
        }
        
        const modal = new bootstrap.Modal(document.getElementById('exportModal'));
        modal.show();
    }
    
    async exportProject() {
        if (!this.currentProject) return;
        
        try {
            const form = document.getElementById('exportForm');
            const formData = new FormData(form);
            
            const exportData = {
                format: formData.get('format') || 'yolo',
                include_images: formData.has('include_images'),
                split_data: formData.has('split_data'),
                train_ratio: parseFloat(formData.get('train_ratio')) || 0.7,
                val_ratio: parseFloat(formData.get('val_ratio')) || 0.15,
                test_ratio: parseFloat(formData.get('test_ratio')) || 0.15
            };
            
            const response = await fetch(`/api/annotation/projects/${this.currentProject.id}/export`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(exportData)
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.memoryManager.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${this.currentProject.name}_export.zip`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                
                // 延迟释放URL，确保下载完成
                window.memoryManager.setTimeout(() => {
                    window.memoryManager.revokeObjectURL(url);
                }, 2000);
                
                // 关闭模态框
                const modal = bootstrap.Modal.getInstance(document.getElementById('exportModal'));
                modal.hide();
                
                this.updateStatus('导出成功');
            } else {
                throw new Error('导出失败');
            }
        } catch (error) {
            console.error('导出失败:', error);
            this.showError('导出失败');
        }
    }
    
    updateStatus(message) {
        document.getElementById('statusText').textContent = message;
    }
    
    showError(message) {
        alert(message); // 简单的错误提示，可以改进为更好的UI
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.annotationManager = new AnnotationManager();
});