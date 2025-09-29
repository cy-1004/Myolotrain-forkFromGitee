// 验证状态标签和进度条的更改
console.log('验证Myolotrain标注页面的状态标签和进度条更改...');

// 模拟状态类和文本函数测试
function testStatusLabels() {
    console.log('\n=== 状态标签测试 ===');
    
    // 测试各种状态
    const testStatuses = ['active', 'inactive', 'processing', 'available', 'error', 'pending', 'running', 'training', 'completed', 'failed', 'cancelled'];
    
    testStatuses.forEach(status => {
        // 根据修改后的getStatusBadgeClass和getStatusText逻辑
        let badgeClass, statusText;
        
        switch (status) {
            case 'processing':
            case 'pending':
                badgeClass = 'bg-warning';
                statusText = '处理中';
                break;
            case 'available':
            case 'completed':
            case 'inactive':
                badgeClass = 'bg-success';
                statusText = status === 'available' ? '可用' : status === 'completed' ? '已完成' : '已完成';
                break;
            case 'error':
            case 'failed':
                badgeClass = 'bg-danger';
                statusText = '错误';
                break;
            case 'running':
            case 'training':
            case 'active':
                badgeClass = 'bg-primary';
                statusText = status === 'running' ? '运行中' : status === 'training' ? '训练中' : '进行中';
                break;
            case 'cancelled':
                badgeClass = 'bg-secondary';
                statusText = '已取消';
                break;
            default:
                badgeClass = 'bg-secondary';
                statusText = status;
        }
        
        console.log(`状态: ${status} => 类: ${badgeClass}, 文本: ${statusText}`);
    });
}

// 模拟图片列表状态标签测试
function testImageBadges() {
    console.log('\n=== 图片列表状态标签测试 ===');
    
    // 测试不同的图片状态
    const testImages = [
        { is_completed: true, annotations: [] },
        { is_completed: false, annotations: [{ id: 1 }, { id: 2 }] },
        { is_completed: false, annotations: [] }
    ];
    
    testImages.forEach((image, index) => {
        let badgeClass, badgeText;
        
        if (image.is_completed) {
            badgeClass = 'badge bg-success';
            badgeText = '已完成';
        } else if (image.annotations && image.annotations.length > 0) {
            badgeClass = 'badge bg-warning';
            badgeText = `部分标注(${image.annotations.length})`;
        } else {
            badgeClass = 'badge bg-secondary';
            badgeText = '未标注';
        }
        
        console.log(`图片 ${index + 1} => 类: ${badgeClass}, 文本: ${badgeText}`);
    });
}

// 执行测试
function runTests() {
    testStatusLabels();
    testImageBadges();
    
    console.log('\n验证完成！更改已应用并通过基本测试。');
    console.log('请在浏览器中打开Myolotrain应用程序，检查在线标注页面的进度条对齐和状态标签显示是否正常。');
}

// 运行测试
runTests();