#!/bin/bash
# NAS监控系统启动脚本 - 虚拟环境版本
# 功能：在虚拟环境中启动Python API后端服务器和HTML静态文件服务器

# 设置脚本目录为工作目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== NAS监控系统启动脚本（虚拟环境版本） ==="
echo "工作目录: $SCRIPT_DIR"

# 读取配置文件
CONFIG_FILE="$SCRIPT_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "错误: 配置文件config.json不存在"
    exit 1
fi

# 从JSON配置文件读取端口
FRONTEND_PORT=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['frontend_port'])" 2>/dev/null)
BACKEND_PORT=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['backend_port'])" 2>/dev/null)

if [ -z "$FRONTEND_PORT" ] || [ -z "$BACKEND_PORT" ]; then
    echo "错误: 无法从config.json读取端口配置"
    exit 1
fi

echo "配置端口 - 前端: $FRONTEND_PORT, 后端: $BACKEND_PORT"

# 虚拟环境目录
VENV_DIR="$SCRIPT_DIR/venv"

# 检查虚拟环境是否存在
if [ ! -d "$VENV_DIR" ]; then
    echo "虚拟环境不存在，正在创建..."
    
    # 检查Python是否安装
    if ! which python3 >/dev/null 2>&1 && ! python3 --version >/dev/null 2>&1; then
        echo "错误: 未找到python3，请先安装Python 3"
        echo "请尝试: sudo apt update && sudo apt install python3 python3-venv python3-pip"
        exit 1
    fi
    
    echo "找到Python: $(python3 --version)"
    
    # 创建虚拟环境
    python3 -m venv "$VENV_DIR" || {
        echo "错误: 创建虚拟环境失败"
        exit 1
    }
    
    echo "虚拟环境创建成功: $VENV_DIR"
fi

# 激活虚拟环境
echo "激活虚拟环境..."
. "$VENV_DIR/bin/activate" || {
    echo "错误: 激活虚拟环境失败"
    exit 1
}

echo "当前Python路径: $(which python)"
echo "当前Python版本: $(python --version)"

# 检查必要文件是否存在
if [ ! -f "system_info.py" ]; then
    echo "错误: 未找到system_info.py文件"
    exit 1
fi

if [ ! -f "index.html" ]; then
    echo "错误: 未找到index.html文件"
    exit 1
fi

# 检查并安装Python依赖
echo "检查Python依赖..."
if ! python -c "import psutil, fastapi, uvicorn" 2>/dev/null; then
    echo "安装Python依赖包..."
    pip install psutil fastapi uvicorn || {
        echo "错误: 依赖安装失败，请检查网络连接"
        exit 1
    }
else
    echo "依赖包已安装"
fi

# 创建日志目录
mkdir -p logs

# 定义清理函数
cleanup() {
    echo "\n正在停止服务器..."
    
    # 停止API服务器
    if [ ! -z "$API_PID" ]; then
        kill $API_PID 2>/dev/null
        sleep 1
        # 如果进程仍在运行，强制终止
        if kill -0 $API_PID 2>/dev/null; then
            kill -9 $API_PID 2>/dev/null
        fi
        echo "已停止API服务器 (PID: $API_PID)"
    fi
    
    # 停止HTTP服务器
    if [ ! -z "$HTTP_PID" ]; then
        kill $HTTP_PID 2>/dev/null
        sleep 1
        # 如果进程仍在运行，强制终止
        if kill -0 $HTTP_PID 2>/dev/null; then
            kill -9 $HTTP_PID 2>/dev/null
        fi
        echo "已停止HTTP服务器 (PID: $HTTP_PID)"
    fi
    
    # 额外检查：杀死可能残留的Python HTTP服务器进程
    pkill -f "python.*http.server.*$FRONTEND_PORT" 2>/dev/null || true
    
    echo "退出虚拟环境"
    if command -v deactivate >/dev/null 2>&1; then
        deactivate 2>/dev/null
    fi
    echo "服务器已停止"
    exit 0
}

# 设置信号处理
trap cleanup INT TERM

# 检查端口是否被占用的函数
check_port() {
    local port=$1
    if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
        return 0  # 端口被占用
    else
        return 1  # 端口可用
    fi
}

# 清理可能残留的进程
echo "清理可能残留的进程..."
pkill -f "python.*system_info.py.*--serve" 2>/dev/null || true
pkill -f "python.*http.server.*$FRONTEND_PORT" 2>/dev/null || true
sleep 1

echo "启动服务器..."

# 检查API端口
if check_port $BACKEND_PORT; then
    echo "警告: 端口$BACKEND_PORT被占用，尝试清理..."
    pkill -f "python.*system_info.py.*--serve" 2>/dev/null || true
    sleep 2
    if check_port $BACKEND_PORT; then
        echo "错误: 端口$BACKEND_PORT仍被占用，请手动检查"
        exit 1
    fi
fi

# 启动Python API后端服务器
echo "启动Python API服务器 (端口$BACKEND_PORT)..."
python system_info.py --serve --port $BACKEND_PORT > logs/api_server.log 2>&1 &
API_PID=$!
echo "API服务器已启动 (PID: $API_PID)"

# 等待API服务器启动
sleep 3

# 检查API服务器是否正常启动
if ! kill -0 $API_PID 2>/dev/null; then
    echo "错误: API服务器启动失败，请检查logs/api_server.log"
    exit 1
fi

# 检查HTTP端口
if check_port $FRONTEND_PORT; then
    echo "警告: 端口$FRONTEND_PORT被占用，尝试清理..."
    pkill -f "python.*http.server.*$FRONTEND_PORT" 2>/dev/null || true
    sleep 2
    if check_port $FRONTEND_PORT; then
        echo "错误: 端口$FRONTEND_PORT仍被占用，请手动检查"
        cleanup
        exit 1
    fi
fi

# 启动HTTP静态文件服务器
echo "启动HTTP静态文件服务器 (端口$FRONTEND_PORT)..."
python -m http.server $FRONTEND_PORT > logs/http_server.log 2>&1 &
HTTP_PID=$!
echo "HTTP服务器已启动 (PID: $HTTP_PID)"

# 等待HTTP服务器启动
sleep 3

# 检查HTTP服务器是否正常启动
if ! kill -0 $HTTP_PID 2>/dev/null; then
    echo "错误: HTTP服务器启动失败，请检查logs/http_server.log"
    cleanup
    exit 1
fi

echo "\n=== 服务器启动成功 ==="
echo "虚拟环境: $VENV_DIR"
echo "前端页面: http://localhost:$FRONTEND_PORT"
echo "API接口: http://localhost:$BACKEND_PORT/system-info"
echo "图片文件接口: http://localhost:$BACKEND_PORT/image-files"
echo "日志文件: logs/api_server.log, logs/http_server.log"
echo "\n按 Ctrl+C 停止服务器"

# 保持脚本运行，等待用户中断
while true; do
    # 检查进程是否还在运行
    if ! kill -0 $API_PID 2>/dev/null; then
        echo "警告: API服务器进程已停止"
        break
    fi
    if ! kill -0 $HTTP_PID 2>/dev/null; then
        echo "警告: HTTP服务器进程已停止"
        break
    fi
    sleep 5
done

cleanup