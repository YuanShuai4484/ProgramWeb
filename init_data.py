import sqlite3
from datetime import datetime, timedelta
import random

def init_sample_data():
    """初始化示例数据"""
    conn = sqlite3.connect('tools.db')
    
    # 创建表结构
    conn.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL
        )
    ''')
    
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
    
    # 插入分类数据
    categories = [
        ('all', '全部'),
        ('image', '图片工具'),
        ('pdf', 'PDF转换工具'),
        ('entertainment', '生活娱乐工具'),
        ('education', '教育工具')
    ]
    
    for name, display_name in categories:
        conn.execute('INSERT OR IGNORE INTO categories (name, display_name) VALUES (?, ?)', 
                    (name, display_name))
    
    # 插入示例工具数据
    tools_data = [
        # 图片工具
        ('图片压缩器', '快速压缩图片文件大小，支持批量处理，保持高质量输出', 2),
        ('图片格式转换', '支持JPG、PNG、GIF、WebP等多种格式互相转换', 2),
        ('图片水印添加', '为图片批量添加文字或图片水印，保护版权', 2),
        ('图片尺寸调整', '批量调整图片尺寸，支持按比例缩放和自定义尺寸', 2),
        
        # PDF工具
        ('PDF合并工具', '将多个PDF文件合并为一个文件，支持自定义页面顺序', 3),
        ('PDF分割工具', '将大PDF文件按页数或书签分割成多个小文件', 3),
        ('PDF转Word', '高质量PDF转换为可编辑的Word文档', 3),
        ('PDF加密解密', '为PDF文件添加密码保护或移除密码限制', 3),
        
        # 生活娱乐工具
        ('二维码生成器', '快速生成各种类型的二维码，支持文字、链接、WiFi等', 4),
        ('颜色搭配工具', '专业的颜色搭配方案生成器，适用于设计和装修', 4),
        ('随机密码生成', '生成高强度随机密码，可自定义长度和字符类型', 4),
        ('单位换算器', '支持长度、重量、温度、货币等多种单位换算', 4),
        
        # 教育工具
        ('公式编辑器', '在线数学公式编辑器，支持LaTeX语法', 5),
        ('思维导图制作', '简单易用的在线思维导图制作工具', 5),
        ('英语单词记忆', '智能英语单词记忆系统，支持艾宾浩斯遗忘曲线', 5),
        ('代码格式化', '支持多种编程语言的代码格式化和高亮显示', 5),
    ]
    
    # 生成随机发布时间（最近30天内）
    base_date = datetime.now()
    
    for title, description, category_id in tools_data:
        # 随机生成1-30天前的日期
        days_ago = random.randint(1, 30)
        publish_date = (base_date - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        
        conn.execute('''
            INSERT OR IGNORE INTO tools (title, description, category_id, publish_date) 
            VALUES (?, ?, ?, ?)
        ''', (title, description, category_id, publish_date))
    
    conn.commit()
    conn.close()
    print("示例数据初始化完成！")

if __name__ == '__main__':
    init_sample_data()