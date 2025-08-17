from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, send_from_directory
import sqlite3
import os
import re
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 数据库配置
DATABASE = 'tools.db'

# 文件上传配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'html'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 确保上传目录存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_path_name(path_name):
    """验证路径名称：只能包含字母和数字"""
    return bool(re.match(r'^[a-zA-Z0-9]+$', path_name))

def is_path_unique(path_name):
    """检查路径名称是否唯一"""
    conn = get_db_connection()
    result = conn.execute('SELECT id FROM uploaded_components WHERE path_name = ?', (path_name,)).fetchone()
    conn.close()
    return result is None

def init_db():
    """初始化数据库"""
    conn = get_db_connection()
    
    # 创建分类表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL
        )
    ''')
    
    # 创建工具表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            publish_date TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    
    # 创建上传组件表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS uploaded_components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            path_name TEXT NOT NULL UNIQUE,
            file_name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            upload_date TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/categories')
def get_categories():
    """获取所有分类"""
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories ORDER BY id').fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in categories])

@app.route('/api/tools')
def get_tools():
    """获取工具列表（包含预设工具和上传组件），支持分页和搜索"""
    category_id = request.args.get('category_id')
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    
    conn = get_db_connection()
    
    # 构建基础查询条件
    where_conditions = []
    params = []
    
    if category_id and category_id != '0':  # 0表示全部
        where_conditions.append('category_id = ?')
        params.append(category_id)
    
    # 构建搜索条件
    search_condition = ''
    if search:
        search_condition = ' AND (name LIKE ? OR description LIKE ?)'
        search_params = [f'%{search}%', f'%{search}%']
    
    # 获取预设工具
    tools_query = '''
        SELECT t.id, t.title as name, t.description, '#' as url, t.category_id, t.publish_date, c.display_name as category_name, 'preset' as source_type
        FROM tools t 
        JOIN categories c ON t.category_id = c.id 
    '''
    
    if where_conditions:
        tools_query += ' WHERE ' + ' AND '.join(where_conditions)
    
    if search:
        if where_conditions:
            tools_query += search_condition
        else:
            tools_query += ' WHERE (t.title LIKE ? OR t.description LIKE ?)'
        params.extend(search_params)
    
    tools = conn.execute(tools_query, params).fetchall()
    
    # 获取上传组件
    uploaded_query = '''
        SELECT uc.id, uc.title as name, uc.title as description, uc.path_name as url, uc.category_id, uc.upload_date as publish_date, c.display_name as category_name, 'uploaded' as source_type
        FROM uploaded_components uc 
        JOIN categories c ON uc.category_id = c.id 
    '''
    
    uploaded_params = []
    if category_id and category_id != '0':
        uploaded_query += ' WHERE uc.category_id = ?'
        uploaded_params.append(category_id)
    
    if search:
        if uploaded_params:
            uploaded_query += ' AND (uc.title LIKE ? OR uc.title LIKE ?)'
        else:
            uploaded_query += ' WHERE (uc.title LIKE ? OR uc.title LIKE ?)'
        uploaded_params.extend([f'%{search}%', f'%{search}%'])
    
    uploaded = conn.execute(uploaded_query, uploaded_params).fetchall()
    
    # 合并两个结果集
    all_tools = [dict(row) for row in tools] + [dict(row) for row in uploaded]
    
    # 按发布日期排序
    all_tools.sort(key=lambda x: x['publish_date'], reverse=True)
    
    # 计算分页
    total = len(all_tools)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_tools = all_tools[start:end]
    
    conn.close()
    
    return jsonify({
        'tools': paginated_tools,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'has_prev': page > 1,
            'has_next': page * per_page < total
        }
    })

@app.route('/upload')
def upload_page():
    """上传管理页面"""
    return render_template('upload.html')

@app.route('/api/upload', methods=['POST'])
def upload_component():
    """处理组件上传"""
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '请选择文件'}), 400
        
        file = request.files['file']
        title = request.form.get('title', '').strip()
        path_name = request.form.get('path_name', '').strip()
        category_id = request.form.get('category_id')
        
        # 验证输入
        if not title:
            return jsonify({'success': False, 'message': '请输入标题'}), 400
        
        if not path_name:
            return jsonify({'success': False, 'message': '请输入路径名称'}), 400
        
        if not validate_path_name(path_name):
            return jsonify({'success': False, 'message': '路径名称只能包含字母和数字'}), 400
        
        if not is_path_unique(path_name):
            return jsonify({'success': False, 'message': '路径名称已存在，请使用其他名称'}), 400
        
        if not category_id or category_id == '0':
            return jsonify({'success': False, 'message': '请选择分类'}), 400
        
        if file.filename == '':
            return jsonify({'success': False, 'message': '请选择文件'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': '只允许上传HTML文件'}), 400
        
        # 保存文件
        filename = secure_filename(f"{path_name}.html")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # 保存到数据库
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO uploaded_components (title, path_name, file_name, category_id, upload_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, path_name, filename, category_id, datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': '上传成功！',
            'access_url': f'/{path_name}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'上传失败：{str(e)}'}), 500

@app.route('/<path_name>')
def serve_component(path_name):
    """访问上传的组件"""
    # 验证路径名称格式
    if not validate_path_name(path_name):
        return "无效的路径名称", 404
    
    # 查询数据库
    conn = get_db_connection()
    component = conn.execute(
        'SELECT * FROM uploaded_components WHERE path_name = ?', 
        (path_name,)
    ).fetchone()
    conn.close()
    
    if not component:
        return "组件不存在", 404
    
    # 返回HTML文件
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], component['file_name'])
    except FileNotFoundError:
        return "文件不存在", 404

@app.route('/api/uploaded-components')
def get_uploaded_components():
    """获取上传组件列表"""
    sort_by = request.args.get('sort', 'upload_date')  # 默认按上传时间排序
    order = request.args.get('order', 'desc')  # 默认降序
    
    # 验证排序参数
    valid_sorts = ['upload_date', 'title']
    valid_orders = ['asc', 'desc']
    
    if sort_by not in valid_sorts:
        sort_by = 'upload_date'
    if order not in valid_orders:
        order = 'desc'
    
    conn = get_db_connection()
    query = f'''
        SELECT uc.*, c.display_name as category_name 
        FROM uploaded_components uc 
        JOIN categories c ON uc.category_id = c.id 
        ORDER BY uc.{sort_by} {order.upper()}
    '''
    
    components = conn.execute(query).fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in components])

@app.route('/api/uploaded-components/<int:component_id>', methods=['DELETE'])
def delete_uploaded_component(component_id):
    """删除上传的组件"""
    try:
        conn = get_db_connection()
        
        # 先查询组件信息
        component = conn.execute(
            'SELECT * FROM uploaded_components WHERE id = ?', 
            (component_id,)
        ).fetchone()
        
        if not component:
            conn.close()
            return jsonify({'success': False, 'message': '组件不存在'}), 404
        
        # 删除数据库记录
        conn.execute('DELETE FROM uploaded_components WHERE id = ?', (component_id,))
        conn.commit()
        conn.close()
        
        # 删除文件
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], component['file_name'])
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return jsonify({
            'success': True, 
            'message': f'组件 "{component["title"]}" 删除成功！'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败：{str(e)}'}), 500

# 分类管理API
@app.route('/api/categories', methods=['POST'])
def create_category():
    """创建新分类"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        display_name = data.get('display_name', '').strip()
        
        if not name or not display_name:
            return jsonify({'success': False, 'message': '分类名称和显示名称不能为空'}), 400
        
        # 验证名称格式（只能包含字母、数字和下划线）
        if not re.match(r'^[a-zA-Z0-9_]+$', name):
            return jsonify({'success': False, 'message': '分类名称只能包含字母、数字和下划线'}), 400
        
        conn = get_db_connection()
        
        # 检查名称是否已存在
        existing = conn.execute('SELECT id FROM categories WHERE name = ?', (name,)).fetchone()
        if existing:
            conn.close()
            return jsonify({'success': False, 'message': '分类名称已存在'}), 400
        
        # 插入新分类
        cursor = conn.execute('INSERT INTO categories (name, display_name) VALUES (?, ?)', (name, display_name))
        category_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': '分类创建成功',
            'category': {'id': category_id, 'name': name, 'display_name': display_name}
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建失败：{str(e)}'}), 500

@app.route('/api/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    """更新分类"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        display_name = data.get('display_name', '').strip()
        
        if not name or not display_name:
            return jsonify({'success': False, 'message': '分类名称和显示名称不能为空'}), 400
        
        # 验证名称格式
        if not re.match(r'^[a-zA-Z0-9_]+$', name):
            return jsonify({'success': False, 'message': '分类名称只能包含字母、数字和下划线'}), 400
        
        conn = get_db_connection()
        
        # 检查分类是否存在
        category = conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,)).fetchone()
        if not category:
            conn.close()
            return jsonify({'success': False, 'message': '分类不存在'}), 404
        
        # 检查新名称是否与其他分类冲突
        existing = conn.execute('SELECT id FROM categories WHERE name = ? AND id != ?', (name, category_id)).fetchone()
        if existing:
            conn.close()
            return jsonify({'success': False, 'message': '分类名称已存在'}), 400
        
        # 更新分类
        conn.execute('UPDATE categories SET name = ?, display_name = ? WHERE id = ?', (name, display_name, category_id))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': '分类更新成功',
            'category': {'id': category_id, 'name': name, 'display_name': display_name}
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败：{str(e)}'}), 500

@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """删除分类"""
    try:
        conn = get_db_connection()
        
        # 检查分类是否存在
        category = conn.execute('SELECT * FROM categories WHERE id = ?', (category_id,)).fetchone()
        if not category:
            conn.close()
            return jsonify({'success': False, 'message': '分类不存在'}), 404
        
        # 检查是否有工具使用此分类
        tools_count = conn.execute('SELECT COUNT(*) as count FROM tools WHERE category_id = ?', (category_id,)).fetchone()['count']
        uploaded_count = conn.execute('SELECT COUNT(*) as count FROM uploaded_components WHERE category_id = ?', (category_id,)).fetchone()['count']
        
        if tools_count > 0 or uploaded_count > 0:
            conn.close()
            return jsonify({'success': False, 'message': f'无法删除分类，还有 {tools_count + uploaded_count} 个工具使用此分类'}), 400
        
        # 删除分类
        conn.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'分类 "{category["display_name"]}" 删除成功！'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败：{str(e)}'}), 500

# 预设工具管理API
@app.route('/api/preset-tools', methods=['GET'])
def get_preset_tools():
    """获取预设工具列表"""
    try:
        sort_by = request.args.get('sort', 'publish_date')
        category_id = request.args.get('category_id')
        
        conn = get_db_connection()
        
        if category_id and category_id != '0':
            tools = conn.execute('''
                SELECT t.*, c.display_name as category_name 
                FROM tools t 
                JOIN categories c ON t.category_id = c.id 
                WHERE t.category_id = ?
                ORDER BY {} DESC
            '''.format('t.' + sort_by), (category_id,)).fetchall()
        else:
            tools = conn.execute('''
                SELECT t.*, c.display_name as category_name 
                FROM tools t 
                JOIN categories c ON t.category_id = c.id 
                ORDER BY {} DESC
            '''.format('t.' + sort_by)).fetchall()
        
        conn.close()
        return jsonify([dict(row) for row in tools])
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取失败：{str(e)}'}), 500

@app.route('/api/preset-tools', methods=['POST'])
def create_preset_tool():
    """创建新的预设工具"""
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        category_id = data.get('category_id')
        
        if not title or not description:
            return jsonify({'success': False, 'message': '标题和描述不能为空'}), 400
        
        if not category_id or category_id == '0':
            return jsonify({'success': False, 'message': '请选择分类'}), 400
        
        conn = get_db_connection()
        
        # 检查分类是否存在
        category = conn.execute('SELECT id FROM categories WHERE id = ?', (category_id,)).fetchone()
        if not category:
            conn.close()
            return jsonify({'success': False, 'message': '分类不存在'}), 400
        
        # 插入新工具
        publish_date = datetime.now().strftime('%Y-%m-%d')
        cursor = conn.execute('''
            INSERT INTO tools (title, description, category_id, publish_date) 
            VALUES (?, ?, ?, ?)
        ''', (title, description, category_id, publish_date))
        
        tool_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': '工具创建成功',
            'tool': {
                'id': tool_id, 
                'title': title, 
                'description': description, 
                'category_id': category_id,
                'publish_date': publish_date
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建失败：{str(e)}'}), 500

@app.route('/api/preset-tools/<int:tool_id>', methods=['PUT'])
def update_preset_tool(tool_id):
    """更新预设工具"""
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        category_id = data.get('category_id')
        
        if not title or not description:
            return jsonify({'success': False, 'message': '标题和描述不能为空'}), 400
        
        if not category_id or category_id == '0':
            return jsonify({'success': False, 'message': '请选择分类'}), 400
        
        conn = get_db_connection()
        
        # 检查工具是否存在
        tool = conn.execute('SELECT * FROM tools WHERE id = ?', (tool_id,)).fetchone()
        if not tool:
            conn.close()
            return jsonify({'success': False, 'message': '工具不存在'}), 404
        
        # 检查分类是否存在
        category = conn.execute('SELECT id FROM categories WHERE id = ?', (category_id,)).fetchone()
        if not category:
            conn.close()
            return jsonify({'success': False, 'message': '分类不存在'}), 400
        
        # 更新工具
        conn.execute('''
            UPDATE tools SET title = ?, description = ?, category_id = ? 
            WHERE id = ?
        ''', (title, description, category_id, tool_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': '工具更新成功',
            'tool': {
                'id': tool_id, 
                'title': title, 
                'description': description, 
                'category_id': category_id
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败：{str(e)}'}), 500

@app.route('/api/preset-tools/<int:tool_id>', methods=['DELETE'])
def delete_preset_tool(tool_id):
    """删除预设工具"""
    try:
        conn = get_db_connection()
        
        # 检查工具是否存在
        tool = conn.execute('SELECT * FROM tools WHERE id = ?', (tool_id,)).fetchone()
        if not tool:
            conn.close()
            return jsonify({'success': False, 'message': '工具不存在'}), 404
        
        # 删除工具
        conn.execute('DELETE FROM tools WHERE id = ?', (tool_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'工具 "{tool["title"]}" 删除成功！'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败：{str(e)}'}), 500

if __name__ == '__main__':
    # 初始化数据库
    if not os.path.exists(DATABASE):
        init_db()
        print("数据库初始化完成")
    
    app.run(debug=True, host='0.0.0.0', port=5000)