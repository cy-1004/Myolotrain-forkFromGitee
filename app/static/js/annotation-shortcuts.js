// 快捷键处理类
class AnnotationShortcuts {
    constructor(annotationManager) {
        this.annotationManager = annotationManager;
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        document.addEventListener('keydown', this.onKeyDown.bind(this));
        
        // 阻止某些默认行为
        document.addEventListener('keydown', (e) => {
            // 阻止空格键滚动页面
            if (e.code === 'Space') {
                e.preventDefault();
            }
            
            // 阻止F键的默认行为
            if (e.code === 'KeyF' && !e.ctrlKey) {
                e.preventDefault();
            }
        });
    }
    
    onKeyDown(e) {
        // 如果焦点在输入框中，不处理快捷键
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        switch (e.code) {
            case 'KeyA':
            case 'ArrowLeft':
                e.preventDefault();
                this.annotationManager.previousImage();
                break;
                
            case 'KeyD':
            case 'ArrowRight':
                e.preventDefault();
                this.annotationManager.nextImage();
                break;
                
            case 'KeyW':
            case 'ArrowUp':
                e.preventDefault();
                this.annotationManager.previousClass();
                break;
                
            case 'KeyS':
            case 'ArrowDown':
                e.preventDefault();
                this.annotationManager.nextClass();
                break;
                
            case 'Delete':
            case 'Backspace':
                e.preventDefault();
                this.annotationManager.deleteSelectedAnnotation();
                break;
                
            case 'Enter':
                e.preventDefault();
                this.annotationManager.confirmCurrentAnnotation();
                break;
                
            case 'Escape':
                e.preventDefault();
                this.annotationManager.cancelCurrentOperation();
                break;
                
            case 'Space':
                e.preventDefault();
                this.annotationManager.toggleAnnotationVisibility();
                break;
                
            case 'KeyZ':
                if (e.ctrlKey) {
                    e.preventDefault();
                    this.annotationManager.undo();
                }
                break;
                
            case 'KeyS':
                if (e.ctrlKey) {
                    e.preventDefault();
                    this.annotationManager.saveCurrentImage();
                }
                break;
                
            case 'KeyF':
                if (!e.ctrlKey) {
                    e.preventDefault();
                    this.annotationManager.fitImageToWindow();
                }
                break;
                
            // 新增：辅助线切换快捷键 (G键)
            case 'KeyG':
                e.preventDefault();
                this.annotationManager.toggleGuidelines();
                break;
                
            // 新增：缩放快捷键
            case 'Equal': // +键
            case 'NumpadAdd':
                e.preventDefault();
                if (this.annotationManager.canvas) {
                    this.annotationManager.canvas.zoom(1.2);
                }
                break;
                
            case 'Minus': // -键
            case 'NumpadSubtract':
                e.preventDefault();
                if (this.annotationManager.canvas) {
                    this.annotationManager.canvas.zoom(0.8);
                }
                break;
                
            case 'Digit0': // 0键重置缩放
            case 'Numpad0':
                e.preventDefault();
                if (this.annotationManager.canvas) {
                    this.annotationManager.canvas.resetZoom();
                }
                break;
                
            // 数字键快速选择类别
            case 'Digit1':
            case 'Digit2':
            case 'Digit3':
            case 'Digit4':
            case 'Digit5':
            case 'Digit6':
            case 'Digit7':
            case 'Digit8':
            case 'Digit9':
                e.preventDefault();
                const classIndex = parseInt(e.code.replace('Digit', '')) - 1;
                this.annotationManager.setCurrentClass(classIndex);
                break;
        }
    }
}

// 导出到全局
window.AnnotationShortcuts = AnnotationShortcuts;