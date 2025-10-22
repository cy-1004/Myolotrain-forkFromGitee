// 标注画布管理类
class AnnotationCanvas {
    constructor(canvasId, imageId) {
        this.canvas = document.getElementById(canvasId);
        this.image = document.getElementById(imageId);
        this.ctx = this.canvas.getContext('2d');
        
        this.annotations = [];
        this.currentAnnotation = null;
        this.selectedAnnotation = null;
        this.isDrawing = false;
        this.startPoint = null;
        this.currentClass = 0;
        // 缩放相关
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        // 鼠标位置
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        
        this.colors = [
            '#FF4444', '#44FF44', '#4444FF', '#FFFF44', 
            '#FF44FF', '#44FFFF', '#FF8844', '#88FF44'
        ];
        
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // 鼠标事件
        this.canvas.addEventListener('mousedown', this.onMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.onMouseUp.bind(this));
        this.canvas.addEventListener('click', this.onClick.bind(this));
        
        // 图片加载事件
        this.image.addEventListener('load', this.onImageLoad.bind(this));
        
        // 窗口大小变化
        window.addEventListener('resize', this.resizeCanvas.bind(this));
    }
    
    // 修改：优化resizeCanvas函数
    resizeCanvas() {
        if (!this.image.complete) return;
        
        const container = this.canvas.parentElement;
        const containerRect = container.getBoundingClientRect();
        
        // 计算图片显示尺寸
        const imageAspect = this.image.naturalWidth / this.image.naturalHeight;
        const containerAspect = containerRect.width / containerRect.height;
        
        let displayWidth, displayHeight;
        if (imageAspect > containerAspect) {
            displayWidth = Math.min(containerRect.width - 20, this.image.naturalWidth);
            displayHeight = displayWidth / imageAspect;
        } else {
            displayHeight = Math.min(containerRect.height - 20, this.image.naturalHeight);
            displayWidth = displayHeight * imageAspect;
        }
        
        // 设置画布尺寸
        this.canvas.width = displayWidth;
        this.canvas.height = displayHeight;
        
        // 保持缩放比例不变
        this.redraw();
    }
    
    onImageLoad() {
        this.resizeCanvas();
        this.redraw();
    }
    
    // 修改：优化绘制函数
    redraw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // 绘制图片
        if (this.image.complete) {
            this.ctx.drawImage(this.image, 0, 0, this.canvas.width, this.canvas.height);
        }
        
        // 绘制现有标注框
        this.annotations.forEach((annotation, index) => {
            this.drawAnnotation(annotation, annotation === this.selectedAnnotation, index + 1);
        });
        
        // 绘制正在绘制的标注框
        if (this.currentAnnotation) {
            this.drawCurrentAnnotation(this.currentAnnotation);
        }
    }
    
    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // 转换为画布坐标（考虑缩放和偏移）
        const canvasX = (x - this.offsetX) / this.scale;
        const canvasY = (y - this.offsetY) / this.scale;
        
        // 检查是否点击了现有标注框
        const clickedAnnotation = this.getAnnotationAt(canvasX, canvasY);
        if (clickedAnnotation) {
            this.selectedAnnotation = clickedAnnotation;
            this.redraw();
            return;
        }
        
        // 开始绘制新的标注框
        this.isDrawing = true;
        this.startPoint = { x: canvasX, y: canvasY };
        this.selectedAnnotation = null;
        this.redraw();
    }
    
    onMouseMove(e) {
        if (!this.isDrawing) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // 转换为画布坐标（考虑缩放和偏移）
        const canvasX = (x - this.offsetX) / this.scale;
        const canvasY = (y - this.offsetY) / this.scale;
        
        this.currentAnnotation = {
            x: Math.min(this.startPoint.x, canvasX),
            y: Math.min(this.startPoint.y, canvasY),
            width: Math.abs(canvasX - this.startPoint.x),
            height: Math.abs(canvasY - this.startPoint.y),
            class_id: this.currentClass
        };
        
        this.redraw();
    }
    
    onMouseUp(e) {
        if (!this.isDrawing) return;
        
        this.isDrawing = false;
        
        if (this.currentAnnotation && 
            this.currentAnnotation.width > 10 && 
            this.currentAnnotation.height > 10) {
            
            // 转换为YOLO格式
            const yoloAnnotation = this.canvasToYolo(this.currentAnnotation);
            this.annotations.push(yoloAnnotation);
            
            // 触发保存事件
            this.onAnnotationsChanged();
        }
        
        this.currentAnnotation = null;
        this.redraw();
    }
    
    onClick(e) {
        // 处理点击选择
        if (!this.isDrawing) {
            const rect = this.canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            // 转换为画布坐标（考虑缩放和偏移）
            const canvasX = (x - this.offsetX) / this.scale;
            const canvasY = (y - this.offsetY) / this.scale;
            
            const clickedAnnotation = this.getAnnotationAt(canvasX, canvasY);
            this.selectedAnnotation = clickedAnnotation;
            this.redraw();
        }
    }
    
    getAnnotationAt(x, y) {
        for (let i = this.annotations.length - 1; i >= 0; i--) {
            const ann = this.yoloToCanvas(this.annotations[i]);
            if (x >= ann.x && x <= ann.x + ann.width &&
                y >= ann.y && y <= ann.y + ann.height) {
                return this.annotations[i];
            }
        }
        return null;
    }
    
    canvasToYolo(canvasAnnotation) {
        const x_center = (canvasAnnotation.x + canvasAnnotation.width / 2) / this.canvas.width;
        const y_center = (canvasAnnotation.y + canvasAnnotation.height / 2) / this.canvas.height;
        const width = canvasAnnotation.width / this.canvas.width;
        const height = canvasAnnotation.height / this.canvas.height;
        
        return {
            class_id: canvasAnnotation.class_id,
            x_center: Math.max(0, Math.min(1, x_center)),
            y_center: Math.max(0, Math.min(1, y_center)),
            width: Math.max(0, Math.min(1, width)),
            height: Math.max(0, Math.min(1, height))
        };
    }
    
    yoloToCanvas(yoloAnnotation) {
        const x_center = yoloAnnotation.x_center * this.canvas.width;
        const y_center = yoloAnnotation.y_center * this.canvas.height;
        const width = yoloAnnotation.width * this.canvas.width;
        const height = yoloAnnotation.height * this.canvas.height;
        
        return {
            x: x_center - width / 2,
            y: y_center - height / 2,
            width: width,
            height: height,
            class_id: yoloAnnotation.class_id
        };
    }
    
    // 修改：drawAnnotation函数，添加序号参数
    drawAnnotation(yoloAnnotation, isSelected = false, index = null) {
        const canvasAnnotation = this.yoloToCanvas(yoloAnnotation);
        const color = this.colors[yoloAnnotation.class_id % this.colors.length];
        
        // 设置半透明边框颜色 (使用 RGBA 格式更精确地控制透明度)
        let transparentColor;
        if (isSelected) {
            transparentColor = '#44FF44';
        } else {
            // 将十六进制颜色转换为 RGBA 格式，设置 50% 透明度
            if (color.startsWith('#')) {
                const r = parseInt(color.substr(1, 2), 16);
                const g = parseInt(color.substr(3, 2), 16);
                const b = parseInt(color.substr(5, 2), 16);
                transparentColor = `rgba(${r}, ${g}, ${b}, 0.5)`;
            } else {
                // 如果不是十六进制颜色，使用原来的格式
                transparentColor = color + '80';
            }
        }
        
        this.ctx.strokeStyle = transparentColor;
        this.ctx.lineWidth = isSelected ? 3 : 2;

        // 绘制边框
        this.ctx.strokeRect(canvasAnnotation.x, canvasAnnotation.y, canvasAnnotation.width, canvasAnnotation.height);
        
        // 绘制序号和类别标签
        const className = window.annotationManager?.getClassName(yoloAnnotation.class_id) || `Class ${yoloAnnotation.class_id}`;
        let label = className;
        if (index !== null) {
            label = `${index}. ${className}`;
        }
        
        this.ctx.fillStyle = isSelected ? '#44FF44' : color;
        this.ctx.font = '12px Arial';
        
        const textWidth = this.ctx.measureText(label).width;
        this.ctx.fillRect(canvasAnnotation.x, canvasAnnotation.y - 20, textWidth + 8, 18);
        
        this.ctx.fillStyle = 'white';
        this.ctx.fillText(label, canvasAnnotation.x + 4, canvasAnnotation.y - 6);
    }
    
    // 修改：drawCurrentAnnotation函数
    drawCurrentAnnotation(canvasAnnotation) {
        this.ctx.strokeStyle = '#2196F3';
        this.ctx.lineWidth = 2;
        this.ctx.setLineDash([5, 5]);

        // 绘制边框
        this.ctx.strokeRect(canvasAnnotation.x, canvasAnnotation.y, canvasAnnotation.width, canvasAnnotation.height);
        
        this.ctx.setLineDash([]);
    }
    
    loadImage(imageSrc) {
        this.image.src = imageSrc;
        this.annotations = [];
        this.selectedAnnotation = null;
        this.currentAnnotation = null;
    }
    
    loadAnnotations(annotations) {
        this.annotations = annotations || [];
        this.selectedAnnotation = null;
        this.redraw();
    }
    
    deleteSelectedAnnotation() {
        if (this.selectedAnnotation) {
            const index = this.annotations.indexOf(this.selectedAnnotation);
            if (index > -1) {
                this.annotations.splice(index, 1);
                this.selectedAnnotation = null;
                this.redraw();
                this.onAnnotationsChanged();
            }
        }
    }
    
    setCurrentClass(classId) {
        this.currentClass = classId;
    }
    
    // 修改：优化缩放功能
    zoom(factor) {
        // 获取鼠标在画布上的位置
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = (event?.clientX || rect.width / 2) - rect.left;
        const mouseY = (event?.clientY || rect.height / 2) - rect.top;
        
        // 计算鼠标位置相对于画布的坐标（考虑当前缩放和偏移）
        const canvasX = (mouseX - this.offsetX) / this.scale;
        const canvasY = (mouseY - this.offsetY) / this.scale;
        
        // 更新缩放比例
        this.scale *= factor;
        
        // 限制缩放范围
        this.scale = Math.max(0.1, Math.min(this.scale, 5));
        
        // 计算新的偏移量，保持鼠标位置不变
        this.offsetX = mouseX - canvasX * this.scale;
        this.offsetY = mouseY - canvasY * this.scale;
        
        // 重新绘制
        this.redraw();
    }
    
    resetZoom() {
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.redraw();
    }
    
    onAnnotationsChanged() {
        // 触发标注变化事件
        if (window.annotationManager) {
            window.annotationManager.onAnnotationsChanged(this.annotations);
        }
    }
}

// 导出到全局
window.AnnotationCanvas = AnnotationCanvas;