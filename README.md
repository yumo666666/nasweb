# NAS监控系统

一个实时显示系统信息的Web监控面板，支持CPU、内存、硬盘、网络等信息的实时监控。

## 功能特性

- 🖥️ **实时系统监控**: CPU使用率、温度、内存使用情况
- 💾 **存储监控**: 硬盘使用率、容量信息、多硬盘支持
- 🌐 **网络监控**: 实时网络速度、IP地址管理
- 🎨 **主题切换**: 支持明暗主题切换
- ⚡ **高频更新**: 0.5秒更新频率，实时响应
- 📱 **响应式设计**: 适配不同屏幕尺寸

## 系统要求

- Python 3.7+
- Linux/Windows系统
- 依赖包：`psutil`, `fastapi`, `uvicorn`

## 快速开始

### 方法一：使用Python启动脚本（推荐）

```bash
# 安装依赖
pip install psutil fastapi uvicorn

# 启动服务器
python start_server_venv.py
```

### 方法二：使用Linux Shell脚本

```bash
# 给脚本执行权限
chmod +x start_server_venv.sh

# 启动服务器
./start_server_venv.sh
```

### 方法三：手动启动

```bash
# 终端1：启动API服务器
python system_info.py --serve --port 8001

# 终端2：启动HTTP服务器
python -m http.server 8000
```

## 访问地址

启动成功后，在浏览器中访问：

- **前端页面**: http://localhost:8000
- **API接口**: http://localhost:8001/system-info

## 文件结构

```
web/
├── index.html              # 前端页面
├── system_info.py          # 后端API服务器
├── start_server.py         # Python启动脚本（跨平台）
├── start_server.sh         # Linux Shell启动脚本
├── README.md               # 说明文档
└── logs/                   # 日志目录（自动创建）
    ├── api_server.log      # API服务器日志
    └── http_server.log     # HTTP服务器日志
```

## 使用说明

1. **启动服务器**: 使用上述任一方法启动服务器
2. **访问页面**: 打开浏览器访问 http://localhost:8000
3. **实时监控**: 页面每0.5秒自动更新系统信息
4. **主题切换**: 点击左上角按钮切换明暗主题
5. **IP选择**: 右上角可选择不同网络接口的IP地址
6. **停止服务器**: 按 `Ctrl+C` 停止服务器

## 故障排除

### 端口被占用

如果遇到端口被占用的错误，可以：

1. 检查端口使用情况：
   ```bash
   # Linux
   netstat -tulpn | grep :8000
   netstat -tulpn | grep :8001
   
   # Windows
   netstat -ano | findstr :8000
   netstat -ano | findstr :8001
   ```

2. 修改端口（在脚本中修改端口号）

### 依赖安装失败

```bash
# 使用国内镜像源
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple psutil fastapi uvicorn

# 或使用conda
conda install psutil
pip install fastapi uvicorn
```

### 权限问题（Linux）

```bash
# 给脚本执行权限
chmod +x start_server_venv.sh

# 如果需要监控某些系统信息，可能需要sudo权限
sudo python start_server_venv.py
```

## 开发说明

- **前端**: 纯HTML/CSS/JavaScript，无需构建工具
- **后端**: Python FastAPI，提供RESTful API
- **数据获取**: 使用psutil库获取系统信息
- **更新频率**: 可在index.html中修改定时器间隔

## 许可证

本项目采用MIT许可证。
