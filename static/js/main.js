// 全局变量
let currentCategoryId = '0'; // 默认显示全部
let categories = [];
let tools = [];
let currentPage = 1;
let totalPages = 1;
let totalTools = 0;
let currentSearch = '';
const perPage = 10;

// DOM元素
const categoryList = document.getElementById('categoryList');
const toolsGrid = document.getElementById('toolsGrid');
const loading = document.getElementById('loading');
const emptyState = document.getElementById('emptyState');
const currentCategoryElement = document.getElementById('currentCategory');
const toolsCountElement = document.getElementById('toolsCount');
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const clearBtn = document.getElementById('clearBtn');
const paginationContainer = document.getElementById('paginationContainer');
const paginationInfo = document.getElementById('paginationInfo');
const paginationNumbers = document.getElementById('paginationNumbers');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initApp();
});

// 初始化应用
async function initApp() {
    try {
        showLoading();
        await loadCategories();
        await loadTools();
        initSearchEvents();
        hideLoading();
    } catch (error) {
        console.error('初始化失败:', error);
        hideLoading();
        showError('加载失败，请刷新页面重试');
    }
}

// 初始化搜索事件
function initSearchEvents() {
    // 创建防抖搜索函数
    const debouncedSearch = debounce((value) => {
        if (currentSearch !== value) {
            currentSearch = value;
            currentPage = 1;
            loadTools();
        }
    }, 300);
    
    // 搜索按钮点击事件
    searchBtn.addEventListener('click', handleSearch);
    
    // 搜索框回车事件
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            handleSearch();
        }
    });
    
    // 搜索框输入事件（实时搜索）
    searchInput.addEventListener('input', function() {
        const value = this.value.trim();
        
        // 显示/隐藏清除按钮
        if (value) {
            clearBtn.style.display = 'flex';
        } else {
            clearBtn.style.display = 'none';
        }
        
        // 使用防抖搜索
        debouncedSearch(value);
    });
    
    // 清除按钮点击事件
    clearBtn.addEventListener('click', function() {
        searchInput.value = '';
        currentSearch = '';
        currentPage = 1;
        clearBtn.style.display = 'none';
        loadTools();
    });
}

// 加载分类数据
async function loadCategories() {
    try {
        const response = await fetch('/api/categories');
        if (!response.ok) {
            throw new Error('获取分类失败');
        }
        
        categories = await response.json();
        renderCategories();
    } catch (error) {
        console.error('加载分类失败:', error);
        throw error;
    }
}

// 渲染分类列表
function renderCategories() {
    // 添加"全部"选项
    const allCategory = {
        id: 0,
        name: 'all',
        display_name: '全部'
    };
    
    const allCategories = [allCategory, ...categories.filter(cat => cat.name !== 'all')];
    
    categoryList.innerHTML = allCategories.map(category => `
        <li class="category-item">
            <a href="#" 
               class="category-link ${category.id == currentCategoryId ? 'active' : ''}" 
               data-category-id="${category.id}"
               data-category-name="${category.display_name}">
                ${category.display_name}
            </a>
        </li>
    `).join('');
    
    // 绑定分类点击事件
    categoryList.addEventListener('click', handleCategoryClick);
}

// 处理搜索事件
function handleSearch() {
    const value = searchInput.value.trim();
    if (currentSearch !== value) {
        currentSearch = value;
        currentPage = 1;
        loadTools();
    }
}

// 处理分类点击事件
function handleCategoryClick(event) {
    event.preventDefault();
    
    const link = event.target.closest('.category-link');
    if (!link) return;
    
    const categoryId = link.dataset.categoryId;
    const categoryName = link.dataset.categoryName;
    
    if (categoryId === currentCategoryId) return;
    
    // 更新当前分类
    currentCategoryId = categoryId;
    
    // 重置分页
    currentPage = 1;
    
    // 更新UI状态
    updateCategoryActiveState(link);
    updateCurrentCategoryDisplay(categoryName);
    
    // 加载对应分类的工具
    loadTools();
}

// 更新分类激活状态
function updateCategoryActiveState(activeLink) {
    // 移除所有激活状态
    categoryList.querySelectorAll('.category-link').forEach(link => {
        link.classList.remove('active');
    });
    
    // 添加当前激活状态
    activeLink.classList.add('active');
}

// 更新当前分类显示
function updateCurrentCategoryDisplay(categoryName) {
    currentCategoryElement.textContent = categoryName + '工具';
}

// 加载工具数据
async function loadTools() {
    try {
        showLoading();
        
        // 构建URL参数
        const params = new URLSearchParams();
        
        if (currentCategoryId !== '0') {
            params.append('category_id', currentCategoryId);
        }
        
        if (currentSearch) {
            params.append('search', currentSearch);
        }
        
        params.append('page', currentPage);
        params.append('per_page', perPage);
        
        const url = `/api/tools?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error('获取工具失败');
        }
        
        const data = await response.json();
        tools = data.tools;
        
        // 更新分页信息
        totalTools = data.pagination.total;
        totalPages = data.pagination.pages;
        currentPage = data.pagination.page;
        
        renderTools();
        renderPagination();
        hideLoading();
    } catch (error) {
        console.error('加载工具失败:', error);
        hideLoading();
        showError('加载工具失败，请重试');
    }
}

// 渲染工具列表
function renderTools() {
    // 更新工具数量
    toolsCountElement.textContent = totalTools;
    
    if (tools.length === 0) {
        showEmptyState();
        hidePagination();
        return;
    }
    
    hideEmptyState();
    
    toolsGrid.innerHTML = tools.map(tool => `
        <div class="tool-card" data-tool-id="${tool.id}" data-source-type="${tool.source_type || 'preset'}" data-url="${tool.url}">
            <h3 class="tool-title">${escapeHtml(tool.name)}</h3>
            <p class="tool-description">${escapeHtml(tool.description)}</p>
            <div class="tool-meta">
                <span class="tool-category">${escapeHtml(tool.category_name)}</span>
                <span class="tool-date">${formatDate(tool.publish_date)}</span>
            </div>
        </div>
    `).join('');
    
    // 绑定工具卡片点击事件
    bindToolCardEvents();
}

// 渲染分页组件
function renderPagination() {
    if (totalPages <= 1) {
        hidePagination();
        return;
    }
    
    showPagination();
    
    // 更新分页信息
    const start = (currentPage - 1) * perPage + 1;
    const end = Math.min(currentPage * perPage, totalTools);
    paginationInfo.textContent = `显示第 ${start}-${end} 项，共 ${totalTools} 项`;
    
    // 更新上一页/下一页按钮状态
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
    
    // 渲染页码按钮
    renderPageNumbers();
    
    // 绑定分页事件
    bindPaginationEvents();
}

// 渲染页码按钮
function renderPageNumbers() {
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    // 调整起始页
    if (endPage - startPage + 1 < maxVisiblePages) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    let pageNumbers = [];
    
    // 添加第一页
    if (startPage > 1) {
        pageNumbers.push(`<button class="pagination-number" data-page="1">1</button>`);
        if (startPage > 2) {
            pageNumbers.push(`<span class="pagination-ellipsis">...</span>`);
        }
    }
    
    // 添加中间页码
    for (let i = startPage; i <= endPage; i++) {
        const isActive = i === currentPage ? 'active' : '';
        pageNumbers.push(`<button class="pagination-number ${isActive}" data-page="${i}">${i}</button>`);
    }
    
    // 添加最后一页
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            pageNumbers.push(`<span class="pagination-ellipsis">...</span>`);
        }
        pageNumbers.push(`<button class="pagination-number" data-page="${totalPages}">${totalPages}</button>`);
    }
    
    paginationNumbers.innerHTML = pageNumbers.join('');
}

// 绑定分页事件
function bindPaginationEvents() {
    // 上一页按钮
    prevBtn.onclick = () => {
        if (currentPage > 1) {
            currentPage--;
            loadTools();
        }
    };
    
    // 下一页按钮
    nextBtn.onclick = () => {
        if (currentPage < totalPages) {
            currentPage++;
            loadTools();
        }
    };
    
    // 页码按钮
    paginationNumbers.querySelectorAll('.pagination-number').forEach(btn => {
        btn.onclick = () => {
            const page = parseInt(btn.dataset.page);
            if (page !== currentPage) {
                currentPage = page;
                loadTools();
            }
        };
    });
}

// 绑定工具卡片事件
function bindToolCardEvents() {
    toolsGrid.querySelectorAll('.tool-card').forEach(card => {
        card.addEventListener('click', function() {
            const toolId = this.dataset.toolId;
            handleToolClick(toolId);
        });
    });
}

// 处理工具点击事件
function handleToolClick(toolId) {
    const tool = tools.find(t => t.id == toolId);
    if (tool) {
        if (tool.source_type === 'uploaded') {
            // 上传组件：跳转到本地路径
            window.open(`/${tool.url}`, '_blank');
        } else {
            // 预设工具：显示提示信息
            alert(`${tool.name}\n\n${tool.description}\n\n这是一个示例工具，暂无实际功能。`);
        }
    }
}

// 显示加载状态
function showLoading() {
    loading.style.visibility = 'visible';
    loading.style.opacity = '1';
    toolsGrid.style.visibility = 'hidden';
    toolsGrid.style.opacity = '0';
    emptyState.style.visibility = 'hidden';
    emptyState.style.opacity = '0';
}

// 隐藏加载状态
function hideLoading() {
    loading.style.visibility = 'hidden';
    loading.style.opacity = '0';
    toolsGrid.style.visibility = 'visible';
    toolsGrid.style.opacity = '1';
}

// 显示空状态
function showEmptyState() {
    toolsGrid.style.visibility = 'hidden';
    toolsGrid.style.opacity = '0';
    emptyState.style.visibility = 'visible';
    emptyState.style.opacity = '1';
}

// 隐藏空状态
function hideEmptyState() {
    emptyState.style.visibility = 'hidden';
    emptyState.style.opacity = '0';
}

// 显示分页组件
function showPagination() {
    paginationContainer.style.display = 'flex';
}

// 隐藏分页组件
function hidePagination() {
    paginationContainer.style.display = 'none';
}

// 显示错误信息
function showError(message) {
    toolsGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #e53e3e;">
            <h3>⚠️ ${message}</h3>
        </div>
    `;
}

// HTML转义函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 格式化日期
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 1) {
        return '昨天';
    } else if (diffDays < 7) {
        return `${diffDays}天前`;
    } else if (diffDays < 30) {
        const weeks = Math.floor(diffDays / 7);
        return `${weeks}周前`;
    } else {
        return date.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 搜索功能（预留）
function searchTools(keyword) {
    if (!keyword.trim()) {
        renderTools();
        return;
    }
    
    const filteredTools = tools.filter(tool => 
        tool.title.toLowerCase().includes(keyword.toLowerCase()) ||
        tool.description.toLowerCase().includes(keyword.toLowerCase())
    );
    
    // 临时更新工具列表
    const originalTools = tools;
    tools = filteredTools;
    renderTools();
    tools = originalTools;
}