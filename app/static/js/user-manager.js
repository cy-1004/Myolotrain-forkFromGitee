// 用户管理模块
class UserManager {
    constructor() {
        // 排序状态变量
        this.currentSortField = '';
        this.currentSortDirection = 'asc';
    }

    // 加载用户管理页面
    loadUserManagementPage() {
        console.log('加载用户管理页面...');
        // 加载用户列表
        this.loadUsersList();
    }

    // 绑定用户管理页面事件
    bindUserManagementEvents() {
        console.log('绑定用户管理页面事件...');
        // 添加用户按钮事件
        const addUserBtn = document.getElementById('add-user-btn');
        if (addUserBtn) {
            addUserBtn.addEventListener('click', () => this.showAddUserModal());
        }
        
        // 绑定排序事件
        const sortableHeaders = document.querySelectorAll('th.sortable');
        sortableHeaders.forEach(header => {
            header.addEventListener('click', (e) => {
                const sortField = e.target.getAttribute('data-sort-field');
                
                // 如果点击的是当前排序字段，则切换排序方向
                if (this.currentSortField === sortField) {
                    this.currentSortDirection = this.currentSortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    // 否则设置新的排序字段和默认排序方向
                    this.currentSortField = sortField;
                    this.currentSortDirection = 'asc';
                }
                
                // 更新排序图标
                this.updateSortIcons();
                
                // 重新加载排序后的用户列表
                this.loadUsersList();
            });
        });
        
        // 初始化排序图标
        this.updateSortIcons();
    }

    // 更新排序图标
    updateSortIcons() {
        const sortableHeaders = document.querySelectorAll('th.sortable');
        sortableHeaders.forEach(header => {
            const icon = header.querySelector('i');
            const sortField = header.getAttribute('data-sort-field');
            
            // 重置所有图标
            icon.className = 'bi bi-sort';
            
            // 设置当前排序字段的图标
            if (this.currentSortField === sortField) {
                icon.className = this.currentSortDirection === 'asc' ? 'bi bi-sort-up' : 'bi bi-sort-down';
            }
        });
    }

    // 加载用户列表
    loadUsersList() {
        console.log('加载用户列表...');
        authenticatedFetch(`${API_URL}/auth/users`)
            .then(response => {
                if (response.ok) {
                    return response.json();
                }
                throw new Error('获取用户列表失败');
            })
            .then(users => {
                console.log('用户列表:', users);
                const tableBody = document.getElementById('users-table-body');
                if (!tableBody) return;
                
                tableBody.innerHTML = '';
                
                if (users.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="7" class="text-center">暂无用户</td></tr>';
                    return;
                }
                
                // 应用排序
                if (this.currentSortField) {
                    users.sort((a, b) => {
                        let valueA = a[this.currentSortField];
                        let valueB = b[this.currentSortField];
                        
                        // 处理日期类型
                        if (this.currentSortField === 'created_at' || this.currentSortField === 'last_login') {
                            valueA = valueA ? new Date(valueA) : new Date(0);
                            valueB = valueB ? new Date(valueB) : new Date(0);
                        }
                        
                        // 处理布尔类型
                        if (this.currentSortField === 'is_active') {
                            valueA = valueA ? 1 : 0;
                            valueB = valueB ? 1 : 0;
                        }
                        
                        // 处理空值
                        if (valueA === null || valueA === undefined) valueA = '';
                        if (valueB === null || valueB === undefined) valueB = '';
                        
                        // 字符串转小写进行比较
                        if (typeof valueA === 'string') valueA = valueA.toLowerCase();
                        if (typeof valueB === 'string') valueB = valueB.toLowerCase();
                        
                        if (valueA < valueB) return this.currentSortDirection === 'asc' ? -1 : 1;
                        if (valueA > valueB) return this.currentSortDirection === 'asc' ? 1 : -1;
                        return 0;
                    });
                }
                
                users.forEach(user => {
                    const row = document.createElement('tr');
                    const isCurrentUser = currentUser && user.id === currentUser.id;
                    
                    // 确保用户ID是字符串格式，以兼容UUID
                    const userIdStr = String(user.id);
                    
                    row.innerHTML = `
                        <td>${userIdStr}</td>
                        <td>${user.username}</td>
                        <td>${user.role}</td>
                        <td>${user.is_active ? '<span class="badge bg-success">活跃</span>' : '<span class="badge bg-danger">禁用</span>'}</td>
                        <td>${new Date(user.created_at).toLocaleString()}</td>
                        <td>${user.last_login ? new Date(user.last_login).toLocaleString() : '-'}</td>
                        <td>
                            <button class="btn btn-primary btn-sm me-1" onclick="userManager.showEditUserModal('${userIdStr}')" ${isCurrentUser ? 'disabled title="不可编辑当前用户"' : ''}>
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="userManager.confirmDeleteUser('${userIdStr}')" ${isCurrentUser ? 'disabled title="不可删除当前用户"' : ''}>
                                <i class="bi bi-trash"></i>
                            </button>
                        </td>
                    `;
                    
                    tableBody.appendChild(row);
                });
            })
            .catch(error => {
                console.error('获取用户列表失败:', error);
                alert('获取用户列表失败: ' + error.message);
            });
    }

    // 显示添加用户模态框
    showAddUserModal() {
        const modalTitle = document.querySelector('#mainModal .modal-title');
        const modalBody = document.querySelector('#mainModal .modal-body');
        const modalSubmit = document.getElementById('modalSubmit');
        
        modalTitle.textContent = '添加用户';
        modalBody.innerHTML = `
            <form id="add-user-form">
                <div class="mb-3">
                    <label for="add-username" class="form-label">用户名</label>
                    <input type="text" class="form-control" id="add-username" required minlength="3">
                </div>
                <div class="mb-3">
                    <label for="add-password" class="form-label">密码</label>
                    <input type="password" class="form-control" id="add-password" required minlength="6">
                    <div class="form-text">密码长度至少为6个字符</div>
                </div>
                <div class="mb-3">
                    <label for="add-confirm-password" class="form-label">确认密码</label>
                    <input type="password" class="form-control" id="add-confirm-password" required>
                </div>
                <div class="mb-3">
                    <label for="add-role" class="form-label">角色</label>
                    <select class="form-control" id="add-role">
                        <option value="operator">普通用户</option>
                        <option value="admin">管理员</option>
                    </select>
                </div>
            </form>
        `;
        modalSubmit.textContent = '添加用户';
        
        // 绑定提交事件
        modalSubmit.onclick = () => this.addUser();
        
        // 显示模态框
        modal.show();
    }

    // 添加用户
    addUser() {
        const username = document.getElementById('add-username').value;
        const password = document.getElementById('add-password').value;
        const confirmPassword = document.getElementById('add-confirm-password').value;
        const role = document.getElementById('add-role').value;
        
        // 表单验证
        if (!username || !password || !confirmPassword) {
            alert('请填写所有字段');
            return;
        }
        
        if (username.length < 3) {
            alert('用户名长度至少为3个字符');
            return;
        }
        
        if (password.length < 6) {
            alert('密码长度至少为6个字符');
            return;
        }
        
        if (password !== confirmPassword) {
            alert('两次输入的密码不一致');
            return;
        }
        
        // 构建请求体
        const requestBody = {
            username: username,
            password: password,
            confirm_password: confirmPassword,
            role: role
        };
        
        // 调用添加用户API
        authenticatedFetch(`${API_URL}/auth/users/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('添加用户失败');
        })
        .then(() => {
            alert('用户添加成功');
            modal.hide();
            // 重新加载用户列表
            this.loadUsersList();
        })
        .catch(error => {
            alert('错误: ' + error.message);
            console.error('添加用户失败:', error);
        });
    }

    // 显示编辑用户模态框
    showEditUserModal(userId) {
        // 先获取用户信息
        console.log('获取用户信息，ID:', userId);
        authenticatedFetch(`${API_URL}/auth/users/${String(userId)}`)
            .then(response => {
                console.log('获取用户信息响应状态:', response.status);
                if (response.ok) {
                    return response.json();
                }
                throw new Error('获取用户信息失败，状态码: ' + response.status);
            })
            .then(user => {
                const modalTitle = document.querySelector('#mainModal .modal-title');
                const modalBody = document.querySelector('#mainModal .modal-body');
                const modalSubmit = document.getElementById('modalSubmit');
                
                modalTitle.textContent = '编辑用户';
                modalBody.innerHTML = `
                    <form id="edit-user-form">
                        <input type="hidden" id="edit-user-id" value="${user.id}">
                        <div class="mb-3">
                            <label for="edit-username" class="form-label">用户名</label>
                            <input type="text" class="form-control" id="edit-username" value="${user.username}" required minlength="3">
                        </div>
                        <div class="mb-3">
                            <label for="edit-password" class="form-label">密码（留空表示不修改）</label>
                            <input type="password" class="form-control" id="edit-password" minlength="6">
                        </div>
                        <div class="mb-3">
                            <label for="edit-confirm-password" class="form-label">确认密码（留空表示不修改）</label>
                            <input type="password" class="form-control" id="edit-confirm-password">
                        </div>
                        <div class="mb-3">
                            <label for="edit-role" class="form-label">角色</label>
                            <select class="form-control" id="edit-role">
                                <option value="operator" ${user.role === 'operator' ? 'selected' : ''}>普通用户</option>
                                <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>管理员</option>
                            </select>
                        </div>
                        <div class="mb-3 form-check">
                            <input type="checkbox" class="form-check-input" id="edit-is-active" ${user.is_active ? 'checked' : ''}>
                            <label class="form-check-label" for="edit-is-active">是否活跃</label>
                        </div>
                    </form>
                `;
                modalSubmit.textContent = '保存修改';
                
                // 绑定提交事件
                modalSubmit.onclick = () => this.updateUser();
                
                // 显示模态框
                modal.show();
            })
            .catch(error => {
                alert('错误: ' + error.message);
                console.error('获取用户信息失败:', error);
            });
    }

    // 更新用户
    updateUser() {
        const userId = document.getElementById('edit-user-id').value;
        const username = document.getElementById('edit-username').value;
        const password = document.getElementById('edit-password').value;
        const confirmPassword = document.getElementById('edit-confirm-password').value;
        const role = document.getElementById('edit-role').value;
        const isActive = document.getElementById('edit-is-active').checked;
        
        // 表单验证
        if (!username) {
            alert('请填写用户名');
            return;
        }
        
        if (username.length < 3) {
            alert('用户名长度至少为3个字符');
            return;
        }
        
        if (password || confirmPassword) {
            if (password !== confirmPassword) {
                alert('两次输入的密码不一致');
                return;
            }
            if (password.length < 6) {
                alert('密码长度至少为6个字符');
                return;
            }
        }
        
        // 构建请求体
        const requestBody = {
            username: username,
            role: role,
            is_active: isActive
        };
        
        // 如果填写了密码，则添加密码字段
        if (password) {
            requestBody.password = password;
        }
        
        // 调用更新用户API
        console.log('更新用户信息，ID:', userId);
        authenticatedFetch(`${API_URL}/auth/users/${String(userId)}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('更新用户失败');
        })
        .then(() => {
            alert('用户更新成功');
            modal.hide();
            // 重新加载用户列表
            this.loadUsersList();
        })
        .catch(error => {
            alert('错误: ' + error.message);
            console.error('更新用户失败:', error);
        });
    }

    // 确认删除用户
    confirmDeleteUser(userId) {
        if (confirm('确定要删除这个用户吗？')) {
            // 调用删除用户API
            authenticatedFetch(`${API_URL}/auth/users/${String(userId)}`, {
                method: 'DELETE'
            })
            .then(response => {
                if (response.ok) {
                    alert('用户删除成功');
                    // 重新加载用户列表
                    this.loadUsersList();
                } else {
                    throw new Error('删除用户失败');
                }
            })
            .catch(error => {
                alert('错误: ' + error.message);
                console.error('删除用户失败:', error);
            });
        }
    }
}

// 创建全局实例
window.userManager = new UserManager();

// 全局暴露函数，以便在HTML中直接调用
window.showAddUserModal = () => userManager.showAddUserModal();
window.showEditUserModal = (userId) => userManager.showEditUserModal(userId);
window.confirmDeleteUser = (userId) => userManager.confirmDeleteUser(userId);

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UserManager;
}