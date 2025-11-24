// 全局变量
const API_URL = '/api';  // API路径
let currentPage = '';
let modal;
let DEBUG_MODE = false;  // 全局DEBUG模式开关
let currentUser = null; // 当前用户信息

// 全局函数：直接加载用户管理页面
window.goToUserManagement = function() {
    console.log('尝试直接进入用户管理页面...');
    if (currentUser && currentUser.role && currentUser.role.toLowerCase() === 'admin') {
        loadPage('user-management');
    } else {
        alert('您需要管理员权限才能访问用户管理功能');
    }
};

// 获取认证令牌
function getAuthToken() {
    const accessToken = localStorage.getItem('access_token');
    const tokenType = localStorage.getItem('token_type') || 'bearer';
    return accessToken ? `${tokenType} ${accessToken}` : null;
}

// 检查是否已登录
function isLoggedIn() {
    const accessToken = localStorage.getItem('access_token');
    return !!accessToken;
}

// 退出登录
function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('token_type');
    // 清除Cookie
    document.cookie = 'access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    document.cookie = 'token_type=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    window.location.href = '/login';
}

// 获取当前用户信息
function getCurrentUser() {
    console.log('获取当前用户信息...');
    authenticatedFetch(`${API_URL}/auth/users/me`)
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('获取用户信息失败');
        })
        .then(user => {
            console.log('用户信息:', user);
            currentUser = user; // 保存当前用户信息
            // 更新页面上的用户名显示
            const usernameElement = document.getElementById('current-username');
            if (usernameElement) {
                usernameElement.textContent = user.username;
            }
            // 打印用户角色信息用于调试
            console.log('当前用户角色:', user.role);
            console.log('角色类型:', typeof user.role);
            
            // 根据后端模型，role字段是字符串类型
            let isAdmin = false;
            if (user.role) {
                isAdmin = user.role.toLowerCase() === 'admin';
            }
            
            console.log('是否管理员:', isAdmin);
            
            // 如果是管理员，显示用户管理菜单项
            if (isAdmin) {
                console.log('用户是管理员，准备显示用户管理菜单项');
                
                // 只保留右侧用户信息旁边的用户管理按钮
                // 方案2: 添加到导航栏右侧的快捷访问按钮
                if (!document.getElementById('admin-user-management-btn')) {
                    // 找到用户下拉菜单区域
                    const userDropdownParent = document.querySelector('.navbar-nav.ms-auto');
                    if (userDropdownParent) {
                        // 创建快捷访问按钮
                        const adminBtnLi = document.createElement('li');
                        adminBtnLi.className = 'nav-item';
                        adminBtnLi.innerHTML = `
                            <button id="admin-user-management-btn" class="nav-link btn btn-sm btn-outline-warning" onclick="loadPage('user-management')">
                                <i class="bi bi-people"></i> 用户管理
                            </button>
                        `;
                        userDropdownParent.insertBefore(adminBtnLi, userDropdownParent.firstChild);
                        console.log('已添加用户管理快捷按钮');
                    } else {
                        // 备用方案：添加到导航栏末尾
                        const navbar = document.querySelector('.navbar');
                        if (navbar) {
                            const adminBtn = document.createElement('button');
                            adminBtn.id = 'admin-user-management-btn';
                            adminBtn.className = 'btn btn-outline-warning me-3';
                            adminBtn.innerHTML = '<i class="bi bi-people"></i> 用户管理';
                            adminBtn.onclick = function() {
                                loadPage('user-management');
                            };
                            navbar.appendChild(adminBtn);
                            console.log('已添加备用用户管理按钮到导航栏');
                        }
                    }
                }
                
                // 方案3: 确保通过window.goToUserManagement函数可以直接访问
                window.goToUserManagement = function() {
                    console.log('直接进入用户管理页面...');
                    loadPage('user-management');
                };
                
                // 方案4: 添加一个全局的用户管理入口提示
                if (!document.getElementById('admin-notice')) {
                    const adminNotice = document.createElement('div');
                    adminNotice.id = 'admin-notice';
                    adminNotice.className = 'admin-notice';
                    adminNotice.style.display = 'none';
                    adminNotice.innerHTML = `
                        <div class="alert alert-info p-2 m-2">
                            <a href="#" onclick="loadPage('user-management'); return false;">管理入口</a>
                        </div>
                    `;
                    document.body.appendChild(adminNotice);
                    console.log('已添加全局用户管理入口提示');
                }
            } else {
                console.log('用户不是管理员，不显示用户管理菜单项');
            }
        })
        .catch(error => {
            console.error('获取用户信息失败:', error);
            // 如果获取失败，可能是会话过期，重定向到登录页面
            if (error.message === 'Not authenticated' || error.message.includes('401')) {
                logout();
            }
        });
}

// 显示修改密码模态框
function showChangePasswordModal() {
    const modalTitle = document.querySelector('#mainModal .modal-title');
    const modalBody = document.querySelector('#mainModal .modal-body');
    const modalSubmit = document.getElementById('modalSubmit');
    
    modalTitle.textContent = '修改密码';
    modalBody.innerHTML = `
        <form id="change-password-form">
            <div class="mb-3">
                <label for="current-password" class="form-label">当前密码</label>
                <input type="password" class="form-control" id="current-password" required>
            </div>
            <div class="mb-3">
                <label for="new-password" class="form-label">新密码</label>
                <input type="password" class="form-control" id="new-password" required minlength="6">
                <div class="form-text">密码长度至少为6个字符</div>
            </div>
            <div class="mb-3">
                <label for="confirm-password" class="form-label">确认新密码</label>
                <input type="password" class="form-control" id="confirm-password" required>
            </div>
        </form>
    `;
    modalSubmit.textContent = '确认修改';
    
    // 绑定提交事件
    modalSubmit.onclick = changePassword;
    
    // 显示模态框
    modal.show();
}

// 修改密码
function changePassword() {
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    // 表单验证
    if (!currentPassword || !newPassword || !confirmPassword) {
        alert('请填写所有字段');
        return;
    }
    
    if (newPassword.length < 6) {
        alert('新密码长度至少为6个字符');
        return;
    }
    
    if (newPassword !== confirmPassword) {
        alert('两次输入的新密码不一致');
        return;
    }
    
    // 构建请求体，使用新的API格式
    const requestBody = {
        current_password: currentPassword,
        new_password: newPassword
    };
    
    // 直接调用新的修改密码API端点
    authenticatedFetch(`${API_URL}/auth/users/me/password`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else if (response.status === 401) {
            throw new Error('当前密码不正确');
        }
        throw new Error('密码修改失败');
    })
    .then(() => {
        alert('密码修改成功，请重新登录');
        modal.hide();
        // 修改成功后强制退出登录
        logout();
    })
    .catch(error => {
        alert('错误: ' + error.message);
        console.error('修改密码失败:', error);
    });
}

// 带认证的fetch请求
function authenticatedFetch(url, options = {}) {
    // 添加认证头
    const headers = options.headers || {};
    const authToken = getAuthToken();
    
    if (authToken) {
        headers['Authorization'] = authToken;
    } else {
        // 没有令牌，重定向到登录页面
        window.location.href = '/login';
        return Promise.reject(new Error('Not authenticated'));
    }
    
    options.headers = headers;
    
    // 添加错误处理，捕获401错误并重定向到登录页面
    return fetch(url, options).then(response => {
        if (response.status === 401) {
            logout();
            throw new Error('Authentication failed');
        }
        return response;
    });
}

// 从localStorage加载DEBUG模式设置
function loadDebugMode() {
    const savedDebugMode = localStorage.getItem('debugMode');
    DEBUG_MODE = savedDebugMode === 'true';
    console.log(`DEBUG模式已${DEBUG_MODE ? '启用' : '禁用'}`);
}

// 保存DEBUG模式设置到localStorage
function saveDebugMode(debugMode) {
    DEBUG_MODE = debugMode;
    localStorage.setItem('debugMode', debugMode);
    console.log(`DEBUG模式已${DEBUG_MODE ? '启用' : '禁用'}`);
}

// 包装console.log，只在DEBUG模式下输出
function log() {
    if (DEBUG_MODE) {
        console.log.apply(console, arguments);
    }
}

// 包装console.error，只在DEBUG模式下输出
function error() {
    if (DEBUG_MODE) {
        console.error.apply(console, arguments);
    }
}

// 包装console.warn，只在DEBUG模式下输出
function warn() {
    if (DEBUG_MODE) {
        console.warn.apply(console, arguments);
    }
}

// 流媒体管理全局函数
window.startStream = function(streamId) {
    authenticatedFetch(`${API_URL}/streaming/start/${streamId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('流媒体启动成功！');
            // 重新加载列表
            if (typeof window.loadStreamsManagementList === 'function') {
                window.loadStreamsManagementList();
            }
            if (typeof window.loadStreamsList === 'function') {
                window.loadStreamsList();
            }
        } else {
            alert('启动失败: ' + (data.message || '未知错误'));
        }
    })
    .catch(error => {
        alert('启动失败: ' + error.message);
    });
};

window.stopStream = function(streamId) {
    authenticatedFetch(`${API_URL}/streaming/stop/${streamId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('流媒体停止成功！');
            // 重新加载列表
            if (typeof window.loadStreamsManagementList === 'function') {
                window.loadStreamsManagementList();
            }
            if (typeof window.loadStreamsList === 'function') {
                window.loadStreamsList();
            }
        } else {
            alert('停止失败: ' + (data.message || '未知错误'));
        }
    })
    .catch(error => {
        alert('停止失败: ' + error.message);
    });
};

window.deleteStream = function(streamId) {
    if (confirm('确定要删除这个流媒体吗？')) {
        // 先停止流媒体
        authenticatedFetch(`${API_URL}/streaming/stop/${streamId}`, {
            method: 'POST'
        })
        .then(() => {
            // 再删除流媒体（如果有删除API的话）
            alert('流媒体已停止！');
            // 重新加载列表
            if (typeof window.loadStreamsManagementList === 'function') {
                window.loadStreamsManagementList();
            }
            if (typeof window.loadStreamsList === 'function') {
                window.loadStreamsList();
            }
        })
        .catch(error => {
            alert('删除失败: ' + error.message);
        });
    }
};

// 测试API端点
function testApiEndpoints() {
    log('Testing API endpoints...');

    // 测试数据集列表API
    authenticatedFetch(`${API_URL}/datasets/`)
        .then(response => {
            log('Datasets API status:', response.status);
            return response.json();
        })
        .then(data => {
            log('Datasets API response:', data);
            if (data.length > 0) {
                log('First dataset structure:', JSON.stringify(data[0], null, 2));
                log('Has train_count:', 'train_count' in data[0]);
                log('Has val_count:', 'val_count' in data[0]);
                log('Has test_count:', 'test_count' in data[0]);
            }
        })
        .catch(error => {
            error('Datasets API error:', error);
        });

    // 测试本地目录API
    authenticatedFetch(`${API_URL}/datasets/local-available`)
        .then(response => {
            log('Local directories API status:', response.status);
            return response.json();
        })
        .then(data => {
            log('Local directories API response:', data);
        })
        .catch(error => {
            error('Local directories API error:', error);
        });
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 加载DEBUG模式设置
    loadDebugMode();
    
    // 如果用户已登录，获取用户信息
    if (isLoggedIn()) {
        getCurrentUser();
        
        // 绑定修改密码按钮事件
        const changePasswordBtn = document.getElementById('change-password-btn');
        if (changePasswordBtn) {
            changePasswordBtn.addEventListener('click', showChangePasswordModal);
        }
        
        // 绑定退出登录按钮事件
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', logout);
        }
    } else {
        // 用户未登录，重定向到登录页面
        window.location.href = '/login';
    }
    
    // 初始化Bootstrap模态框
    try {
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            modal = new bootstrap.Modal(document.getElementById('mainModal'));
            log('Bootstrap模态框初始化成功');
        } else {
            warn('Bootstrap未加载，跳过模态框初始化');
            // 创建一个空对象，避免后续代码出错
            modal = {
                show: function() { warn('模态框功能不可用'); },
                hide: function() { warn('模态框功能不可用'); }
            };
        }
    } catch (error) {
        error('初始化Bootstrap模态框失败:', error);
        // 创建一个空对象，避免后续代码出错
        modal = {
            show: function() { warn('模态框功能不可用'); },
            hide: function() { warn('模态框功能不可用'); }
        };
    }

    // 导航菜单点击事件
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = this.getAttribute('data-page');
            loadPage(page);
        });
    });

    // 测试API端点
    testApiEndpoints();

    // 默认加载数据集页面
    loadPage('datasets');
    
    // 获取后端DEBUG模式状态
    getBackendDebugMode();

    // 已在导航栏中配置为data-page="settings"，由loadPage处理

    // 添加调试代码 - 5秒后检查COCO按钮是否存在并强制绑定事件
    setTimeout(function() {
        log('DEBUG: 检查COCO按钮并强制绑定事件');
        const cocoButton = document.getElementById('import-coco-dataset-btn');
        if (cocoButton) {
            log('DEBUG: 找到COCO按钮:', cocoButton);
            log('DEBUG: COCO按钮当前onclick:', cocoButton.onclick);

            // 直接绑定全局函数
            window.showCocoModal = function() {
                log('DEBUG: 通过全局函数调用showImportCocoDatasetModal');
                showImportCocoDatasetModal();
                return false;
            };

            // 强制重新绑定事件
            cocoButton.onclick = window.showCocoModal;

            // 添加内联事件处理
            cocoButton.setAttribute('onclick', 'return window.showCocoModal();');

            log('DEBUG: COCO按钮事件已强制重新绑定');
        } else {
            error('DEBUG: 5秒后仍未找到COCO按钮');
        }
    }, 5000);
});

// 加载设置页面
function loadSettingsPage() {
    // 设置当前DEBUG模式状态
    const debugModeToggle = document.getElementById('debugModeToggle');
    if (debugModeToggle) {
        debugModeToggle.checked = DEBUG_MODE;
    }
}

// 加载页面内容
function loadPage(page) {
    if (currentPage === page) return;
    
    // 在切换页面之前清理当前页面的资源
    if (currentPage === 'training' && typeof stopTrainingTasksAutoRefresh === 'function') {
        stopTrainingTasksAutoRefresh();
    }
    
    // 清理视频检测页面的资源
    if (currentPage === 'video' && typeof window.videoProcessor !== 'undefined') {
        // 停止任何正在进行的检测
        if (window.videoProcessor.isDetecting) {
            window.videoProcessor.stopRealTimeDetection();
        }
        
        // 清除轮询管理器中的所有轮询
        if (window.PollingManager) {
            window.PollingManager.clearAllPolls();
        }
    }
    
    // 清理流媒体检测资源
    if (currentPage === 'video' && typeof window.streamDetector !== 'undefined') {
        // 停止任何正在进行的流媒体检测
        if (window.streamDetector.isDetecting) {
            window.streamDetector.stopDetection();
        }
    }
    
    currentPage = page;

    // 更新导航菜单激活状态
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('data-page') === page) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // 获取页面模板
    const template = document.getElementById(`${page}-template`);
    if (!template) return;

    // 加载页面内容
    const pageContent = document.getElementById('page-content');
    pageContent.innerHTML = template.innerHTML;

    // 根据页面类型加载数据和绑定事件
    switch (page) {
        case 'datasets':
            // 使用已拆分的模块
            if (typeof window.datasetManager !== 'undefined') {
                window.datasetManager.loadDatasets();
                window.datasetManager.bindDatasetEvents();
            }
            break;
        case 'models':
            // 使用已拆分的模块
            if (typeof window.modelManager !== 'undefined') {
                window.modelManager.loadModels();
                window.modelManager.bindModelEvents();
            }
            break;
        case 'training':
            // 使用已拆分的模块
            if (typeof window.trainingManager !== 'undefined') {
                window.trainingManager.loadTrainingTasks();
                window.trainingManager.bindTrainingEvents();
            }
            break;
        case 'detection':
            // 使用已拆分的模块
            if (typeof window.detectionManager !== 'undefined') {
                window.detectionManager.loadDetectionForm();
                window.detectionManager.bindDetectionEvents();
            }
            break;
        case 'opencv':
            // 使用已拆分的模块
            if (typeof window.opencvTools !== 'undefined') {
                window.opencvTools.loadOpenCVPage();
                window.opencvTools.bindOpenCVEvents();
            }
            break;
        case 'video':
            // 使用已拆分的模块
            if (typeof window.videoProcessor !== 'undefined') {
                window.videoProcessor.loadVideoPage();
                window.videoProcessor.bindVideoEvents();
            }
            break;
        case 'annotation':
            // 使用已拆分的模块
            if (typeof window.onlineAnnotation !== 'undefined') {
                window.onlineAnnotation.loadAnnotationPage();
                window.onlineAnnotation.bindAnnotationEvents();
            }
            break;
        case 'settings':
            loadSettingsPage();
            bindSettingsEvents();
            break;
        case 'user-management':
            // 使用已拆分的模块
            if (typeof window.userManager !== 'undefined') {
                // 使用增强的角色检测逻辑来判断是否是管理员
                let isAdmin = false;
                if (currentUser && currentUser.role) {
                    if (typeof currentUser.role === 'string') {
                        isAdmin = currentUser.role.toLowerCase() === 'admin';
                    } else if (typeof currentUser.role === 'object') {
                        // 如果role是对象，检查它的值
                        if (currentUser.role.value) {
                            isAdmin = currentUser.role.value.toLowerCase() === 'admin';
                        } else if (currentUser.role.name) {
                            isAdmin = currentUser.role.name.toLowerCase() === 'admin';
                        }
                    }
                }
                
                console.log('用户管理页面访问检测 - 是否管理员:', isAdmin);
                
                if (isAdmin) {
                    window.userManager.loadUserManagementPage();
                    window.userManager.bindUserManagementEvents();
                } else {
                    const pageContent = document.getElementById('page-content');
                    pageContent.innerHTML = `
                        <div class="text-center py-5">
                            <h2>权限不足</h2>
                            <p class="lead">只有管理员可以访问用户管理页面</p>
                        </div>
                    `;
                }
            }
            break;
        case 'monitoring':
            // 使用已拆分的模块
            if (typeof window.monitoring !== 'undefined') {
                window.monitoring.initMonitoringPage();
                window.monitoring.bindEventListeners();
            }
            break;
    }
}

// ==================== 设置页面 ====================

// 绑定设置页面事件
function bindSettingsEvents() {
    // 保存设置按钮事件
    const saveBtn = document.getElementById('saveSettingsBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            const debugModeToggle = document.getElementById('debugModeToggle');
            if (debugModeToggle) {
                const newDebugMode = debugModeToggle.checked;
                saveDebugMode(newDebugMode);
                
                // 显示保存成功消息
                showSettingsSaveMessage(`DEBUG模式已${newDebugMode ? '启用' : '禁用'}`);
            }
        });
    }
}

// 显示设置保存消息
function showSettingsSaveMessage(message) {
    const messageElement = document.getElementById('settings-save-message');
    if (messageElement) {
        messageElement.textContent = message;
        messageElement.className = 'mt-2 alert alert-success';
        messageElement.style.display = 'block';
        
        // 3秒后隐藏消息
        setTimeout(function() {
            messageElement.style.display = 'none';
        }, 3000);
    }
}

// 从后端获取DEBUG模式状态
function getBackendDebugMode() {
    if (DEBUG_MODE) {
        authenticatedFetch(`${API_URL}/settings/debug-mode`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    log(`后端DEBUG模式状态: ${data.debug_mode}`);
                }
            })
            .catch(err => {
                error('获取后端DEBUG模式状态失败:', err);
            });
    }
}

// ==================== 全局对象初始化 ====================
// 在DOM加载完成后初始化各个模块的全局实例
document.addEventListener('DOMContentLoaded', function() {
    // 初始化各个模块的全局实例
    window.trainingManager = new TrainingManager();
    window.datasetManager = new DatasetManager();
    window.modelManager = new ModelManager();
    window.userManager = new UserManager();
    window.opencvTools = new OpenCVTools();
    window.videoProcessor = new VideoProcessor();
    window.onlineAnnotation = new OnlineAnnotation();
    window.detectionManager = new DetectionManager();
    window.settingsManager = new SettingsManager();
    window.exportModelsManager = new ExportModelsManager();
});
