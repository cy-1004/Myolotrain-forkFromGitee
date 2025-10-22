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
        
        // 将快捷键处理委托给annotation.js中的handleKeyDown方法
        // 这里只保留annotation-manager.js特有的功能
        switch (e.code) {
            // 调用annotation.js中的功能
            case 'KeyA':
            case 'ArrowLeft':
                e.preventDefault();
                if (window.annotationTool) {
                    window.annotationTool.prevImage();
                }
                break;
                
            case 'KeyD':
            case 'ArrowRight':
                e.preventDefault();
                if (window.annotationTool) {
                    window.annotationTool.nextImage();
                }
                break;
                
            case 'KeyW':
            case 'ArrowUp':
                e.preventDefault();
                if (window.annotationTool) {
                    window.annotationTool.prevClass();
                }
                break;
                
            case 'KeyS':
            case 'ArrowDown':
                e.preventDefault();
                if (window.annotationTool) {
                    window.annotationTool.nextClass();
                }
                break;
                
            case 'Delete':
            case 'Backspace':
                e.preventDefault();
                if (window.annotationTool) {
                    window.annotationTool.deleteSelectedAnnotation();
                }
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
                    if (window.annotationTool) {
                        window.annotationTool.saveAnnotation();
                    }
                }
                break;
                
            // annotation-manager.js特有的 fitImageToWindow 功能
            case 'KeyF':
                if (!e.ctrlKey) {
                    e.preventDefault();
                    this.annotationManager.fitImageToWindow();
                }
                break;
                
            // 调用annotation.js中的功能
            case 'KeyG':
                e.preventDefault();
                if (window.annotationTool) {
                    window.annotationTool.toggleGuidelines();
                }
                break;
                
            // 调用annotation.js中的功能
            case 'Equal': // +键
            case 'NumpadAdd':
                e.preventDefault();
                if (window.annotationTool) {
                    window.annotationTool.zoom(1.2);
                }
                break;
                
            case 'Minus': // -键
            case 'NumpadSubtract':
                e.preventDefault();
                if (window.annotationTool) {
                    window.annotationTool.zoom(0.8);
                }
                break;
                
            case 'Digit0': // 0键重置缩放
            case 'Numpad0':
                e.preventDefault();
                if (window.annotationTool) {
                    window.annotationTool.resetZoom();
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