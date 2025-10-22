class AnnotationTool {
    constructor() {
        this.canvas = document.getElementById('annotation-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.currentImage = null;
        this.currentImageData = null;
        this.annotations = [];
        this.isDrawing = false;
        this.isDragging = false;
        this.isResizing = false;
        this.isPanning = false;
        this.isPanReady = false;
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
        // 新增属性：辅助线开关
        this.showGuidelines = false;
        // 新增属性：辅助线颜色
        this.guidelineColor = 'rgba(255, 255, 255, 0.5)';
        // 新增属性：当前选中的标注框
        this.selectedAnnotation = null;
        // 新增属性：鼠标位置
        this.mouseX = 0;
        this.mouseY = 0;
        // 新增属性：拖拽起始位置
        this.dragStartX = 0;
        this.dragStartY = 0;
        // 新增属性：调整大小的控制点
        this.resizeHandle = null;
        // 新增属性：画布偏移量
        this.offsetX = 0;
        this.offsetY = 0;
        // 新增属性：拖动画布的起始位置
        this.panStartX = 0;
        this.panStartY = 0;
        // 新增属性：标记是否刚刚完成绘制（用于防止click事件重新选中）
        this.justFinishedDrawing = false;
        
        // 新增属性：标记是否通过点击选中
        this.selectedByClick = false;
        
        // 新增属性：标记是否刚刚完成拖拽或调整大小操作
        this.justFinishedDragging = false;
        this.justFinishedResizing = false;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadProject();
    }
    
    setupEventListeners() {
        // 画布事件
        this.canvas.addEventListener('mousedown', this.startDrawing.bind(this));
        this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.stopDrawing.bind(this));
        this.canvas.addEventListener('click', this.onCanvasClick.bind(this));
        
        // 鼠标滚轮缩放事件
        this.canvas.addEventListener('wheel', this.handleWheel.bind(this));
        
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
        document.getElementById('delete-image').addEventListener('click', this.deleteCurrentImage.bind(this));
        
        const toggleGuidelinesBtn = document.getElementById('toggle-guidelines');
        if (toggleGuidelinesBtn) {
            toggleGuidelinesBtn.addEventListener('click', this.toggleGuidelines.bind(this));
        }
        
        const filterCompletedBtn = document.getElementById('filter-completed');
        const filterUncompletedBtn = document.getElementById('filter-uncompleted');
        if (filterCompletedBtn) {
            filterCompletedBtn.addEventListener('click', this.toggleCompletedFilter.bind(this));
        }
        if (filterUncompletedBtn) {
            filterUncompletedBtn.addEventListener('click', this.toggleUncompletedFilter.bind(this));
        }
        
        const guidelineColorPicker = document.getElementById('guideline-color');
        if (guidelineColorPicker) {
            guidelineColorPicker.addEventListener('input', (e) => {
                this.guidelineColor = e.target.value;
                this.redraw();
            });
        }
        
        // 键盘快捷键
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
        document.addEventListener('keyup', this.handleKeyUp.bind(this));
        
        // 搜索
        document.getElementById('image-search').addEventListener('input', this.filterImages.bind(this));
    }
    
    // 新增方法：设置辅助线颜色（供annotation-manager.js调用）
    setGuidelineColor(color) {
        this.guidelineColor = color;
        this.redraw();
    }

    onMouseMove(e) {
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY, rawX: mouseX, rawY: mouseY } = this.getCanvasCoordinates(e);
        this.mouseX = mouseX;
        this.mouseY = mouseY;
        
        if (this.isDrawing) {
            this.currentBox = {
                x: Math.min(this.startX, canvasX),
                y: Math.min(this.startY, canvasY),
                width: Math.abs(canvasX - this.startX),
                height: Math.abs(canvasY - this.startY)
            };
            
            this.redraw();
        } else if (this.isDragging && this.selectedAnnotation) {
            // 拖拽标注框
            const deltaX = canvasX - this.dragStartX;
            const deltaY = canvasY - this.dragStartY;
            
            this.selectedAnnotation.x += deltaX;
            this.selectedAnnotation.y += deltaY;
            
            // 更新拖拽起始位置
            this.dragStartX = canvasX;
            this.dragStartY = canvasY;
            
            // 实时更新左侧列表信息
            this.updateAnnotationList();
            this.redraw();
        } else if (this.isResizing && this.selectedAnnotation) {
            // 调整标注框大小
            this.resizeAnnotation(this.selectedAnnotation, this.resizeHandle, canvasX, canvasY);
            
            // 实时更新左侧列表信息
            this.updateAnnotationList();
            this.redraw();
        } else if (this.isPanning) {
            // 拖动画布
            this.offsetX += this.mouseX - this.panStartX;
            this.offsetY += this.mouseY - this.panStartY;
            this.panStartX = this.mouseX;
            this.panStartY = this.mouseY;
            this.redraw();
        }
        
        // 更新鼠标样式
        this.updateCursorStyle(canvasX, canvasY);
        
        // 每次鼠标移动都重绘，以确保辅助线跟随鼠标
        if (this.showGuidelines) {
            this.redraw();
        }
    }
    
    updateCursorStyle(canvasX, canvasY) {
        // 如果正在绘制、拖拽、调整大小或抓手模式，使用特定光标
        if (this.isDrawing || this.isDragging || this.isResizing || this.isPanning) {
            return; // 保持当前操作的光标样式
        }
        
        // 编辑模式下，根据鼠标位置显示不同的光标
        if (this.selectedAnnotation) {
            // 检查是否在调整大小的控制点上
            const handle = this.getResizeHandle(this.selectedAnnotation, canvasX, canvasY);
            if (handle) {
                switch (handle) {
                    case 'right':
                    case 'left':
                        this.canvas.style.cursor = 'ew-resize';
                        return;
                    case 'top':
                    case 'bottom':
                        this.canvas.style.cursor = 'ns-resize';
                        return;
                    case 'top-right':
                    case 'bottom-left':
                        this.canvas.style.cursor = 'ne-resize';
                        return;
                    case 'top-left':
                    case 'bottom-right':
                        this.canvas.style.cursor = 'nw-resize';
                        return;
                }
            }
            
            // 检查是否在标注框内部（用于拖拽）
            if (this.isInAnnotationArea(this.selectedAnnotation, canvasX, canvasY)) {
                this.canvas.style.cursor = 'move';
                return;
            }
            
            // 检查是否在文字标题区域
            if (this.isInTitleArea(this.selectedAnnotation, canvasX, canvasY)) {
                this.canvas.style.cursor = 'pointer';
                return;
            }
        }
        
        // 默认光标（十字标记）
        this.canvas.style.cursor = 'crosshair';
    }

    resizeAnnotation(annotation, handle, canvasX, canvasY) {
        const minWidth = 5;
        const minHeight = 5;
        
        switch (handle) {
            case 'right':
                annotation.width = Math.max(minWidth, canvasX - annotation.x);
                break;
            case 'bottom':
                annotation.height = Math.max(minHeight, canvasY - annotation.y);
                break;
            case 'left':
                const newWidth = Math.max(minWidth, annotation.x + annotation.width - canvasX);
                annotation.x = annotation.x + annotation.width - newWidth;
                annotation.width = newWidth;
                break;
            case 'top':
                const newHeight = Math.max(minHeight, annotation.y + annotation.height - canvasY);
                annotation.y = annotation.y + annotation.height - newHeight;
                annotation.height = newHeight;
                break;
            case 'top-right':
                annotation.width = Math.max(minWidth, canvasX - annotation.x);
                annotation.height = Math.max(minHeight, canvasY - annotation.y);
                break;
            case 'bottom-left':
                const newWidthBL = Math.max(minWidth, annotation.x + annotation.width - canvasX);
                annotation.x = annotation.x + annotation.width - newWidthBL;
                annotation.width = newWidthBL;
                annotation.height = Math.max(minHeight, canvasY - annotation.y);
                break;
            case 'top-left':
                const newWidthTL = Math.max(minWidth, annotation.x + annotation.width - canvasX);
                annotation.x = annotation.x + annotation.width - newWidthTL;
                annotation.width = newWidthTL;
                const newHeightTL = Math.max(minHeight, annotation.y + annotation.height - canvasY);
                annotation.y = annotation.y + annotation.height - newHeightTL;
                annotation.height = newHeightTL;
                break;
            case 'bottom-right':
                annotation.width = Math.max(minWidth, canvasX - annotation.x);
                annotation.height = Math.max(minHeight, canvasY - annotation.y);
                break;
        }
    }
    
    getCanvasCoordinates(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        
        const clickX = (e.clientX - rect.left) * scaleX;
        const clickY = (e.clientY - rect.top) * scaleY;
        
        return {
            x: (clickX - this.offsetX) / this.scale,
            y: (clickY - this.offsetY) / this.scale,
            rawX: clickX,
            rawY: clickY
        };
    }

    isInTitleArea(annotation, canvasX, canvasY, index = -1) {
        const className = this.projectData.classes[annotation.class_id] || `Class ${annotation.class_id}`;
        const label = index >= 0 ? `${index + 1}. ${className}` : className;
        
        // 创建临时canvas测量文字宽度
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        tempCtx.font = '12px Arial';
        const textWidth = tempCtx.measureText(label).width;
        
        // 标题区域：文字位置 + 边距
        const titleLeft = annotation.x + 4;
        const titleRight = annotation.x + textWidth + 8;
        const titleTop = annotation.y - 20;
        const titleBottom = annotation.y - 6;
        
        return canvasX >= titleLeft && canvasX <= titleRight &&
               canvasY >= titleTop && canvasY <= titleBottom;
    }

    isInAnnotationArea(annotation, canvasX, canvasY) {
        return canvasX >= annotation.x && canvasX <= annotation.x + annotation.width &&
               canvasY >= annotation.y && canvasY <= annotation.y + annotation.height;
    }

    setSelectedAnnotation(annotation, byClick = false) {
        this.selectedAnnotation = annotation;
        this.selectedByClick = byClick;
        this.updateAnnotationList(); // 更新标注列表显示
        this.redraw(); // 重新绘制以显示选中状态
    }

    onCanvasClick(e) {
        // 如果正在绘制或处于抓手模式，不处理点击选择
        if (this.isDrawing || this.isPanning || this.isPanReady) return;
        
        // 如果刚刚完成绘制，不处理点击选择（防止重新选中）
        if (this.justFinishedDrawing) {
            this.justFinishedDrawing = false;
            return;
        }
        
        // 如果刚刚完成拖拽或调整大小操作，不处理点击选择（保持选中状态）
        if (this.justFinishedDragging || this.justFinishedResizing) {
            this.justFinishedDragging = false;
            this.justFinishedResizing = false;
            return;
        }
        
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY } = this.getCanvasCoordinates(e);
        
        // 检查是否点击了标注框（使用与startDrawing相同的精确规则）
        let clickedAnnotation = null;
        let clickedIndex = -1;
        
        // 从后往前遍历，确保点击的是最上层的标注框
        for (let i = this.annotations.length - 1; i >= 0; i--) {
            const ann = this.annotations[i];
            
            // 方式1：检查是否点击了标注框左上角的文字标题区域
            if (this.isInTitleArea(ann, canvasX, canvasY, i)) {
                clickedAnnotation = ann;
                clickedIndex = i;
                break;
            }
            
            // 方式2：按住Ctrl键+点击标注框区域
            if (e.ctrlKey && this.isInAnnotationArea(ann, canvasX, canvasY)) {
                clickedAnnotation = ann;
                clickedIndex = i;
                break;
            }
        }
        
        // 更新选中的标注框
        this.setSelectedAnnotation(clickedAnnotation);
        
        // 如果点击了标注框，可以在这里添加其他处理逻辑
        if (clickedAnnotation) {
            console.log('选中标注框:', clickedIndex);
        }
    }
    
    toggleGuidelines() {
        this.showGuidelines = !this.showGuidelines;
        const btn = document.getElementById('toggle-guidelines');
        if (btn) {
            btn.textContent = this.showGuidelines ? '隐藏辅助线' : '显示辅助线';
            btn.className = this.showGuidelines ? 'btn btn-secondary' : 'btn btn-outline-secondary';
        }
        this.redraw();
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
    
    // 删除当前选中的图片
    async deleteCurrentImage() {
        if (!this.currentImageData) return;
        
        if (!confirm(`确定要删除图片 "${this.currentImageData.image_name}" 吗？\n此操作不可恢复！`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/annotation/images/${this.currentImageData.id}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const currentIndex = this.currentImageIndex;
                
                // 从列表中移除
                this.imageList.splice(currentIndex, 1);
                
                if (this.imageList.length > 0) {
                    // 如果删除的是最后一张图片，则加载前一张；否则加载当前索引的图片
                    const nextIndex = currentIndex >= this.imageList.length ? currentIndex - 1 : currentIndex;
                    await this.loadImage(nextIndex);
                } else {
                    // 如果没有图片了，清空当前显示
                    this.currentImage = null;
                    this.currentImageData = null;
                    this.annotations = [];
                    document.getElementById('current-image-name').textContent = '没有图片';
                    this.updateAnnotationList();
                    this.redraw();
                }
                
                this.updateImageList();
                await this.loadProjectStats();
                this.showMessage('图片删除成功', 'success');
            } else {
                this.showMessage('删除失败', 'error');
            }
        } catch (error) {
            console.error('删除图片失败:', error);
            this.showMessage('删除失败: ' + error.message, 'error');
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
        
        // 应用筛选条件
        const filteredImages = this.imageList.filter(imageData => {
            // 如果没有启用任何筛选，则显示所有图片
            if (!this.showCompleted && !this.showUncompleted) {
                return true;
            }
            
            // 如果启用了已完成筛选，则显示已完成的图片
            if (this.showCompleted && imageData.is_completed) {
                return true;
            }
            
            // 如果启用了未完成筛选，则显示未完成的图片
            if (this.showUncompleted && !imageData.is_completed) {
                return true;
            }
            
            // 其他情况不显示
            return false;
        });
        
        // 保存筛选后的图片列表和对应的原始索引
        this.filteredImageList = filteredImages;
        this.filteredImageIndices = filteredImages.map(filteredImg => 
            this.imageList.findIndex(img => img.id === filteredImg.id)
        );
        
        this.filteredImageList.forEach((imageData, index) => {
            const imageItem = document.createElement('div');
            imageItem.className = `annotation-item ${this.filteredImageIndices[index] === this.currentImageIndex ? 'selected' : ''}`;
            imageItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span class="text-truncate">${imageData.image_name}</span>
                    <div>
                        ${imageData.is_completed ? '<i class="fas fa-check text-success"></i>' : ''}
                        <span class="badge bg-info">${imageData.annotations.length}</span>
                    </div>
                </div>
            `;
            imageItem.addEventListener('click', () => this.loadImage(this.filteredImageIndices[index]));
            imageListContainer.appendChild(imageItem);
        });
        
        document.getElementById('total-images').textContent = this.imageList.length;
    }
    
    async loadImage(index) {
        if (index < 0 || index >= this.imageList.length) return;
        
        // 保存上一张图片的数据引用
        const previousImageData = this.currentImageData;
        const previousImageIndex = this.currentImageIndex;
        
        // 更新当前图片索引和数据
        this.currentImageIndex = index;
        this.currentImageData = this.imageList[index];
        
        // 检查并自动标记上一张图片（如果有标注且未完成）
        if (previousImageData && 
            previousImageData.annotations && 
            previousImageData.annotations.length > 0 && 
            !previousImageData.is_completed) {
            // 创建临时函数来标记上一张图片
            const markPreviousCompleted = async () => {
                try {
                    const response = await fetch(`/api/annotation/images/${previousImageData.id}`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            is_completed: true
                        })
                    });
                    
                    if (response.ok) {
                        // 更新本地数据
                        previousImageData.is_completed = true;
                        if (this.imageList && this.imageList[previousImageIndex] !== undefined) {
                            this.imageList[previousImageIndex].is_completed = true;
                        }
                        this.updateImageList();
                        // 更新标注进度
                        await this.loadProjectStats();
                    }
                } catch (error) {
                    console.error('自动标记完成失败:', error);
                }
            };
            
            (async () => {
                await markPreviousCompleted();
            })().catch(err => {
                console.error('执行标记完成过程中出错:', err);
            });
        }
        
        // 更新图片列表选中状态
        this.updateImageListSelection();
        
        // 加载图片
        const img = new Image();
        img.onload = () => {
            this.currentImage = img;
            this.resizeCanvas();
            this.loadAnnotations();
            this.redraw();
            
            document.getElementById('current-image-name').textContent = this.currentImageData.image_name;
            
            // 切换到新图片后立即更新标注进度
            // 改进：添加异步处理和错误捕获
            (async () => {
                try {
                    await this.loadProjectStats();
                } catch (error) {
                    console.error('更新进度失败:', error);
                }
            })();
        };
        
        // 使用API端点获取图片文件
        img.src = `/api/annotation/projects/${this.projectId}/images/${this.currentImageData.id}/file`;
    }
    
    resizeCanvas() {
        if (!this.currentImage) return;
        
        // 获取用户屏幕分辨率和可用空间
        const screenWidth = window.screen.width;
        const screenHeight = window.screen.height;
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        
        // 计算可用空间（考虑页面布局和其他元素）
        // 为侧边栏和其他UI元素预留空间
        const reservedWidth = 300; // 左右两侧面板的宽度
        const reservedHeight = 150; // 顶部工具栏、底部导航等的高度
        
        // 计算最大可用尺寸
        const maxWidth = Math.min(screenWidth * 0.8, windowWidth - reservedWidth, 1600); // 最大不超过1600px
        const maxHeight = Math.min(screenHeight * 0.7, windowHeight - reservedHeight, 1600); // 最大不超过1600px
        
        let { width, height } = this.currentImage;
        
        // 移除可能导致尺寸限制的条件，让画布能更好地适应容器
        // 只在图片尺寸超过最大限制时才进行缩放
        if (width > maxWidth || height > maxHeight) {
            // 保持宽高比
            const aspectRatio = width / height;
            
            if (width > maxWidth) {
                width = maxWidth;
                height = width / aspectRatio;
            }
            
            if (height > maxHeight) {
                height = maxHeight;
                width = height * aspectRatio;
            }
        }
        
        // 设置画布尺寸
        this.canvas.width = width;
        this.canvas.height = height;
        
        // 重置缩放比例和偏移量
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
    }
    
    loadAnnotations() {
        this.annotations = (this.currentImageData.annotations || []).map(ann => ({
            class_id: ann.class_id,
            x: ann.x_center * this.canvas.width - (ann.width * this.canvas.width) / 2,
            y: ann.y_center * this.canvas.height - (ann.height * this.canvas.height) / 2,
            width: ann.width * this.canvas.width,
            height: ann.height * this.canvas.height
        }));
        
        // 清除选中状态
        this.selectedAnnotation = null;
        this.updateAnnotationList();
    }
    
    async saveAnnotation() {
        if (!this.currentImageData) return;
        
        // 转换为YOLO格式（相对于画布尺寸）
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
    
    updateAnnotationList() {
        const annotationList = document.getElementById('annotation-list');
        annotationList.innerHTML = '';
        
        this.annotations.forEach((ann, index) => {
            const className = this.projectData.classes[ann.class_id] || '未知类别';
            const annItem = document.createElement('div');
            annItem.className = `annotation-list-item ${this.selectedAnnotation === ann ? 'selected' : ''}`;
            annItem.innerHTML = `
                <div class="annotation-info">
                    <div><strong>ID:</strong> ${index + 1}</div>
                    <div><strong>类别:</strong> ${className}</div>
                    <div><strong>位置:</strong> (${Math.round(ann.x)}, ${Math.round(ann.y)})</div>
                    <div><strong>尺寸:</strong> ${Math.round(ann.width)} x ${Math.round(ann.height)}</div>
                </div>
                <div class="annotation-actions">
                    <button class="btn btn-sm btn-outline-danger" onclick="annotationTool.removeAnnotation(${index})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            
            // 方式3：点击标注列表项选中对应的标注框
            annItem.addEventListener('click', (e) => {
                // 防止点击删除按钮时触发选中
                if (!e.target.closest('.annotation-actions')) {
                    this.selectedAnnotation = ann;
                    this.updateAnnotationList();
                    this.redraw();
                }
            });
            
            annotationList.appendChild(annItem);
        });
    }
    
    // 重新设计：优化缩放功能，确保标注框位置稳定
    zoom(factor) {
        // 获取鼠标在画布上的位置
        const mouseX = this.mouseX || (this.canvas.width / 2);
        const mouseY = this.mouseY || (this.canvas.height / 2);
        
        // 计算鼠标位置相对于画布的坐标（考虑当前缩放和偏移）
        const canvasX = (mouseX - this.offsetX) / this.scale;
        const canvasY = (mouseY - this.offsetY) / this.scale;
        
        // 更新缩放比例
        const oldScale = this.scale;
        this.scale *= factor;
        
        // 限制缩放范围
        this.scale = Math.max(0.1, Math.min(this.scale, 5));
        
        // 计算新的偏移量，保持鼠标位置不变
        this.offsetX = mouseX - canvasX * this.scale;
        this.offsetY = mouseY - canvasY * this.scale;
        
        // 确保偏移量不会超出画布边界
        this.constrainOffset();
        
        // 重新绘制
        this.redraw();
    }
    
    resetZoom() {
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.redraw();
    }
    
    constrainOffset() {
        const maxOffsetX = Math.max(0, (this.canvas.width * this.scale - this.canvas.width) / 2);
        const maxOffsetY = Math.max(0, (this.canvas.height * this.scale - this.canvas.height) / 2);
        
        this.offsetX = Math.max(-maxOffsetX, Math.min(maxOffsetX, this.offsetX));
        this.offsetY = Math.max(-maxOffsetY, Math.min(maxOffsetY, this.offsetY));
    }
    
    startDrawing(e) {
        // 如果准备好进行抓手模式，开始拖拽
        if (this.isPanReady) {
            this.isPanning = true;
            this.panStartX = this.mouseX;
            this.panStartY = this.mouseY;
            this.canvas.style.cursor = 'grabbing';
            return;
        }
        
        // 使用通用坐标转换方法
        const { x: canvasX, y: canvasY, rawX: startX, rawY: startY } = this.getCanvasCoordinates(e);
        this.startX = startX;
        this.startY = startY;
        
        // 如果有选中的标注框，检查是否点击了控制点
        if (this.selectedAnnotation) {
            const handle = this.getResizeHandle(this.selectedAnnotation, canvasX, canvasY);
            if (handle) {
                // 点击了控制点，开始调整大小
                this.isResizing = true;
                this.resizeHandle = handle;
                return;
            }
            
            // 检查是否点击了标注框内部（用于拖拽）
            if (this.isInAnnotationArea(this.selectedAnnotation, canvasX, canvasY)) {
                // 点击了标注框内部，开始拖拽
                this.isDragging = true;
                this.dragStartX = canvasX;
                this.dragStartY = canvasY;
                return;
            }
        }
        
        // 检查是否点击了标注框顶部的文字标题区域
        let clickedAnnotation = null;
        for (let i = this.annotations.length - 1; i >= 0; i--) {
            const ann = this.annotations[i];
            
            // 方式1：检查是否点击了标注框左上角的文字标题区域
            if (this.isInTitleArea(ann, canvasX, canvasY, i)) {
                clickedAnnotation = ann;
                break;
            }
            
            // 方式2：按住Ctrl键+点击标注框区域
            if (e.ctrlKey && this.isInAnnotationArea(ann, canvasX, canvasY)) {
                clickedAnnotation = ann;
                break;
            }
        }
        
        // 如果通过方式1或方式2点击了标注框，则选中它而不是开始绘制
        if (clickedAnnotation) {
            this.setSelectedAnnotation(clickedAnnotation, true);
            return;
        }
        
        // 否则开始绘制新的标注框（转换为画布坐标）
        this.isDrawing = true;
        this.selectedAnnotation = null; // 取消之前的选中
        this.startX = canvasX;
        this.startY = canvasY;
        this.redraw();
    }
    
    stopDrawing(e) {
        this.justFinishedDrawing = this.isDrawing;
        
        if (this.isDrawing) {
            this.isDrawing = false;
            
            if (this.currentBox && this.currentBox.width > 5 && this.currentBox.height > 5) {
                this.annotations.push({
                    class_id: this.selectedClass,
                    ...this.currentBox
                });
                this.updateAnnotationList();
                this.saveAnnotation();
                this.selectedAnnotation = null;
                this.updateAnnotationList();
            } else {
                this.selectedAnnotation = null;
                this.updateAnnotationList();
            }
            
            this.currentBox = null;
            this.redraw();
        } else if (this.isDragging) {
            this.isDragging = false;
            this.saveAnnotation();
            this.justFinishedDragging = true;
        } else if (this.isResizing) {
            this.isResizing = false;
            this.resizeHandle = null;
            this.saveAnnotation();
            this.justFinishedResizing = true;
        } else if (this.isPanning) {
            this.isPanning = false;
            this.canvas.style.cursor = this.isPanReady ? 'grab' : 'crosshair';
        }
        
        this.selectedByClick = false;
    }
    
    getResizeHandle(annotation, x, y) {
        const handleSize = 8;
        const right = annotation.x + annotation.width;
        const bottom = annotation.y + annotation.height;
        
        // 四个角落控制点（优先级最高）
        // 左上角
        if (x >= annotation.x - handleSize && x <= annotation.x + handleSize &&
            y >= annotation.y - handleSize && y <= annotation.y + handleSize) {
            return 'top-left';
        }
        
        // 右上角
        if (x >= right - handleSize && x <= right + handleSize &&
            y >= annotation.y - handleSize && y <= annotation.y + handleSize) {
            return 'top-right';
        }
        
        // 左下角
        if (x >= annotation.x - handleSize && x <= annotation.x + handleSize &&
            y >= bottom - handleSize && y <= bottom + handleSize) {
            return 'bottom-left';
        }
        
        // 右下角
        if (x >= right - handleSize && x <= right + handleSize &&
            y >= bottom - handleSize && y <= bottom + handleSize) {
            return 'bottom-right';
        }
        
        // 四个边控制点
        // 右侧控制点
        if (x >= right - handleSize && x <= right + handleSize &&
            y >= annotation.y && y <= bottom) {
            return 'right';
        }
        
        // 底部控制点
        if (y >= bottom - handleSize && y <= bottom + handleSize &&
            x >= annotation.x && x <= right) {
            return 'bottom';
        }
        
        // 左侧控制点
        if (x >= annotation.x - handleSize && x <= annotation.x + handleSize &&
            y >= annotation.y && y <= bottom) {
            return 'left';
        }
        
        // 顶部控制点
        if (y >= annotation.y - handleSize && y <= annotation.y + handleSize &&
            x >= annotation.x && x <= right) {
            return 'top';
        }
        
        return null;
    }
    
    redraw() {
        if (!this.currentImage) return;
        
        // 保存当前上下文状态
        this.ctx.save();
        
        // 应用缩放和偏移
        this.ctx.setTransform(1, 0, 0, 1, 0, 0); // 重置变换
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.translate(this.offsetX, this.offsetY);
        this.ctx.scale(this.scale, this.scale);
        
        // 绘制图片
        this.ctx.drawImage(this.currentImage, 0, 0, this.canvas.width, this.canvas.height);
        
        // 绘制辅助线（跟随鼠标移动）
        if (this.showGuidelines) {
            this.drawGuidelines();
        }
        
        // 绘制已有标注
        this.annotations.forEach((ann, index) => {
            const isSelected = this.selectedAnnotation === ann;
            this.drawBox(ann, this.getClassColor(ann.class_id), false, index + 1, isSelected);
        });
        
        // 绘制当前正在绘制的框
        if (this.currentBox) {
            this.drawBox(this.currentBox, this.getClassColor(this.selectedClass), true);
        }
        
        // 恢复上下文状态
        this.ctx.restore();
    }
    
    drawGuidelines() {
        this.ctx.save();
        this.ctx.strokeStyle = this.guidelineColor; // 使用自定义颜色
        this.ctx.lineWidth = 1;
        this.ctx.setLineDash([5, 5]);
        
        // 绘制鼠标位置的垂直线
        if (this.mouseX !== undefined && this.mouseY !== undefined) {
            // 转换鼠标坐标到画布坐标（考虑缩放和偏移）
            const canvasX = (this.mouseX - this.offsetX) / this.scale;
            const canvasY = (this.mouseY - this.offsetY) / this.scale;
            
            // 垂直线（从顶部到底部）
            this.ctx.beginPath();
            this.ctx.moveTo(canvasX, 0);
            this.ctx.lineTo(canvasX, this.canvas.height);
            this.ctx.stroke();
            
            // 水平线（从左侧到右侧）
            this.ctx.beginPath();
            this.ctx.moveTo(0, canvasY);
            this.ctx.lineTo(this.canvas.width, canvasY);
            this.ctx.stroke();
            
            // 显示鼠标坐标
            this.ctx.fillStyle = this.guidelineColor; // 使用自定义颜色
            this.ctx.font = '12px Arial';
            this.ctx.fillText(`(${Math.round(canvasX)}, ${Math.round(canvasY)})`, canvasX + 5, canvasY - 5);
        }
        
        this.ctx.restore();
    }
    
    drawBox(box, color, isDrawing = false, index = null, isSelected = false) {
        // 设置边框颜色
        let borderColor;
        if (isDrawing) {
            borderColor = '#2196F3';
        } else if (isSelected) {
            borderColor = '#44FF44'; // 选中时使用绿色
        } else {
            // 将十六进制颜色转换为 RGBA 格式，设置 50% 透明度
            if (color.startsWith('#')) {
                const r = parseInt(color.substr(1, 2), 16);
                const g = parseInt(color.substr(3, 2), 16);
                const b = parseInt(color.substr(5, 2), 16);
                borderColor = `rgba(${r}, ${g}, ${b}, 0.5)`;
            } else {
                // 如果不是十六进制颜色，使用原来的格式
                borderColor = color + '80';
            }
        }
        
        this.ctx.strokeStyle = borderColor;
        this.ctx.lineWidth = isSelected ? 3 : (isDrawing ? 3 : 2);
        
        // 不填充矩形内部（保持透明）
        // 只绘制边框
        this.ctx.strokeRect(box.x, box.y, box.width, box.height);
        
        // 绘制序号和类别标签
        if (!isDrawing) {
            const className = this.projectData.classes[box.class_id] || '未知';
            let label = className;
            if (index !== null) {
                label = `${index}. ${className}`;
            }
            
            // 标签背景使用半透明颜色
            if (isSelected) {
                this.ctx.fillStyle = 'rgba(68, 255, 68, 0.7)'; // 半透明绿色
            } else {
                // 将颜色转换为半透明格式
                if (color.startsWith('#')) {
                    const r = parseInt(color.substr(1, 2), 16);
                    const g = parseInt(color.substr(3, 2), 16);
                    const b = parseInt(color.substr(5, 2), 16);
                    this.ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.7)`;
                } else {
                    // 如果不是十六进制颜色，使用默认半透明白色背景
                    this.ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
                }
            }
            this.ctx.fillRect(box.x, box.y - 20, this.ctx.measureText(label).width + 10, 20);
            this.ctx.fillStyle = 'white';
            this.ctx.font = '12px Arial';
            this.ctx.fillText(label, box.x + 5, box.y - 5);
        }
        
        // 如果是选中的标注框，绘制控制点
        if (isSelected && !isDrawing) {
            this.drawResizeHandles(box);
        }
    }
    
    drawResizeHandles(box) {
        const handleSize = 6;
        const right = box.x + box.width;
        const bottom = box.y + box.height;
        
        this.ctx.fillStyle = '#44FF44';
        
        // 右侧控制点
        this.ctx.fillRect(right - handleSize/2, box.y + box.height/2 - handleSize/2, handleSize, handleSize);
        
        // 底部控制点
        this.ctx.fillRect(box.x + box.width/2 - handleSize/2, bottom - handleSize/2, handleSize, handleSize);
        
        // 左侧控制点
        this.ctx.fillRect(box.x - handleSize/2, box.y + box.height/2 - handleSize/2, handleSize, handleSize);
        
        // 顶部控制点
        this.ctx.fillRect(box.x + box.width/2 - handleSize/2, box.y - handleSize/2, handleSize, handleSize);
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
                // 同步更新imageList中的状态
                if (this.imageList && this.imageList[this.currentImageIndex]) {
                    this.imageList[this.currentImageIndex].is_completed = true;
                }
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
    

    
    // 处理按键按下事件（整合所有键盘快捷键）
    handleKeyDown(e) {
        // 防止在输入框中触发快捷键
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        // 空格键作为抓手工具准备状态
        if (e.key === ' ') {
            e.preventDefault();
            this.isPanReady = true;
            this.canvas.style.cursor = 'grab';
            return;
        }
        
        // 阻止空格键滚动页面
        if (e.key === ' ') {
            e.preventDefault();
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
            case 'backspace':
                e.preventDefault();
                this.deleteSelectedAnnotation();
                break;
            case 'g':
                e.preventDefault();
                this.toggleGuidelines();
                break;
            case '+':
            case '=':
                e.preventDefault();
                this.zoom(1.2);
                break;
            case '-':
                e.preventDefault();
                this.zoom(0.8);
                break;
            case '0':
                e.preventDefault();
                this.resetZoom();
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
    
    handleKeyUp(e) {
        if (e.key === ' ') {
            this.isPanReady = false;
            this.isPanning = false;
            this.canvas.style.cursor = 'crosshair';
        }
    }
    
    handleWheel(e) {
        e.preventDefault();
        
        // 根据滚轮方向确定缩放因子
        const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
        
        // 调用缩放方法
        this.zoom(zoomFactor);
    }
    

    
    deleteSelectedAnnotation() {
        if (this.selectedAnnotation) {
            const index = this.annotations.indexOf(this.selectedAnnotation);
            if (index > -1) {
                this.annotations.splice(index, 1);
                this.selectedAnnotation = null;
                this.updateAnnotationList();
                this.redraw();
                // 实时保存
                this.saveAnnotation();
            }
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
            const response = await fetch('/api/models/');
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
    
    toggleCompletedFilter() {
        this.showCompleted = !this.showCompleted;
        const btn = document.getElementById('filter-completed');
        if (btn) {
            if (this.showCompleted) {
                btn.classList.remove('btn-outline-success');
                btn.classList.add('btn-success');
            } else {
                btn.classList.remove('btn-success');
                btn.classList.add('btn-outline-success');
            }
        }
        this.updateImageList();
    }
    
    toggleUncompletedFilter() {
        this.showUncompleted = !this.showUncompleted;
        const btn = document.getElementById('filter-uncompleted');
        if (btn) {
            if (this.showUncompleted) {
                btn.classList.remove('btn-outline-warning');
                btn.classList.add('btn-warning');
            } else {
                btn.classList.remove('btn-warning');
                btn.classList.add('btn-outline-warning');
            }
        }
        this.updateImageList();
    }
    
    updateImageListSelection() {
        const imageItems = document.querySelectorAll('#image-list .annotation-item');
        imageItems.forEach((item, index) => {
            // 获取原始索引
            const originalIndex = this.filteredImageIndices[index];
            item.classList.toggle('selected', originalIndex === this.currentImageIndex);
        });
    }
}

// 初始化标注工具
let annotationTool;
document.addEventListener('DOMContentLoaded', () => {
    annotationTool = new AnnotationTool();
});