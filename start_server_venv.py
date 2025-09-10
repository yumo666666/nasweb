#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAS监控系统启动脚本 - 虚拟环境版本
功能：在虚拟环境中启动Python API后端服务器和HTML静态文件服务器
适用于Linux/Windows系统

使用方法：
  python3 start_server_venv.py
  或
  python start_server_venv.py
"""

import os
import sys
import time
import signal
import subprocess
import threading
import venv
from pathlib import Path


class VenvServerManager:
    """虚拟环境服务器管理类"""
    
    def __init__(self):
        self.api_process = None
        self.http_process = None
        self.script_dir = Path(__file__).parent.absolute()
        self.logs_dir = self.script_dir / "logs"
        self.venv_dir = self.script_dir / "venv"
        self.venv_python = None
        
    def setup_logging(self):
        """创建日志目录"""
        self.logs_dir.mkdir(exist_ok=True)
        print(f"日志目录: {self.logs_dir}")
        
    def create_virtual_environment(self):
        """创建虚拟环境"""
        if self.venv_dir.exists():
            print(f"虚拟环境已存在: {self.venv_dir}")
        else:
            print(f"正在创建虚拟环境: {self.venv_dir}")
            try:
                venv.create(self.venv_dir, with_pip=True)
                print("虚拟环境创建成功")
            except Exception as e:
                print(f"错误: 创建虚拟环境失败 - {e}")
                sys.exit(1)
                
        # 设置虚拟环境Python路径
        if os.name == 'nt':  # Windows
            self.venv_python = self.venv_dir / "Scripts" / "python.exe"
        else:  # Linux/macOS
            self.venv_python = self.venv_dir / "bin" / "python"
            
        if not self.venv_python.exists():
            print(f"错误: 虚拟环境Python不存在: {self.venv_python}")
            sys.exit(1)
            
        print(f"虚拟环境Python: {self.venv_python}")
        
    def install_dependencies(self):
        """在虚拟环境中安装依赖包"""
        print("检查并安装Python依赖包...")
        
        # 检查依赖是否已安装
        try:
            result = subprocess.run(
                [str(self.venv_python), "-c", "import psutil, fastapi, uvicorn"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("依赖包已安装")
                return
        except Exception:
            pass
            
        # 安装依赖包
        print("正在安装依赖包...")
        try:
            # 获取pip路径
            if os.name == 'nt':  # Windows
                pip_path = self.venv_dir / "Scripts" / "pip.exe"
            else:  # Linux/macOS
                pip_path = self.venv_dir / "bin" / "pip"
                
            subprocess.run(
                [str(pip_path), "install", "psutil", "fastapi", "uvicorn"],
                check=True,
                cwd=self.script_dir
            )
            print("依赖包安装成功")
        except subprocess.CalledProcessError as e:
            print(f"错误: 依赖包安装失败 - {e}")
            sys.exit(1)
        
    def check_dependencies(self):
        """检查依赖文件"""
        print("检查依赖文件...")
        
        # 检查必要文件
        required_files = ["system_info.py", "index.html"]
        for file in required_files:
            if not (self.script_dir / file).exists():
                print(f"错误: 未找到{file}文件")
                sys.exit(1)
                
    def start_api_server(self):
        """启动API服务器"""
        print("启动Python API服务器 (端口8001)...")
        
        api_log = self.logs_dir / "api_server.log"
        with open(api_log, "w", encoding="utf-8") as log_file:
            self.api_process = subprocess.Popen(
                [str(self.venv_python), "system_info.py", "--serve", "--port", "8001"],
                cwd=self.script_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True
            )
            
        print(f"API服务器已启动 (PID: {self.api_process.pid})")
        return self.api_process
        
    def start_http_server(self):
        """启动HTTP静态文件服务器"""
        print("启动HTTP静态文件服务器 (端口8000)...")
        
        http_log = self.logs_dir / "http_server.log"
        with open(http_log, "w", encoding="utf-8") as log_file:
            self.http_process = subprocess.Popen(
                [str(self.venv_python), "-m", "http.server", "8000"],
                cwd=self.script_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True
            )
            
        print(f"HTTP服务器已启动 (PID: {self.http_process.pid})")
        return self.http_process
        
    def check_server_health(self):
        """检查服务器健康状态"""
        time.sleep(3)  # 等待服务器启动
        
        # 检查API服务器
        if self.api_process.poll() is not None:
            print("错误: API服务器启动失败，请检查logs/api_server.log")
            return False
            
        # 检查HTTP服务器
        if self.http_process.poll() is not None:
            print("错误: HTTP服务器启动失败，请检查logs/http_server.log")
            return False
            
        return True
        
    def monitor_servers(self):
        """监控服务器状态"""
        while True:
            time.sleep(5)
            
            # 检查API服务器
            if self.api_process.poll() is not None:
                print("警告: API服务器进程已停止")
                break
                
            # 检查HTTP服务器
            if self.http_process.poll() is not None:
                print("警告: HTTP服务器进程已停止")
                break
                
    def cleanup(self):
        """清理资源"""
        print("\n正在停止服务器...")
        
        if self.api_process:
            try:
                self.api_process.terminate()
                self.api_process.wait(timeout=5)
                print(f"已停止API服务器 (PID: {self.api_process.pid})")
            except subprocess.TimeoutExpired:
                self.api_process.kill()
                print(f"强制停止API服务器 (PID: {self.api_process.pid})")
            except Exception as e:
                print(f"停止API服务器时出错: {e}")
                
        if self.http_process:
            try:
                self.http_process.terminate()
                self.http_process.wait(timeout=5)
                print(f"已停止HTTP服务器 (PID: {self.http_process.pid})")
            except subprocess.TimeoutExpired:
                self.http_process.kill()
                print(f"强制停止HTTP服务器 (PID: {self.http_process.pid})")
            except Exception as e:
                print(f"停止HTTP服务器时出错: {e}")
                
        print("服务器已停止")
        
    def signal_handler(self, signum, frame):
        """信号处理函数"""
        print(f"\n收到信号 {signum}，正在关闭服务器...")
        self.cleanup()
        sys.exit(0)
        
    def run(self):
        """运行服务器管理器"""
        print("=== NAS监控系统启动脚本（虚拟环境版本） ===")
        print(f"工作目录: {self.script_dir}")
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, self.signal_handler)
            
        try:
            # 初始化
            self.setup_logging()
            self.create_virtual_environment()
            self.install_dependencies()
            self.check_dependencies()
            
            # 启动服务器
            self.start_api_server()
            self.start_http_server()
            
            # 检查服务器健康状态
            if not self.check_server_health():
                self.cleanup()
                sys.exit(1)
                
            print("\n=== 服务器启动成功 ===")
            print(f"虚拟环境: {self.venv_dir}")
            print("前端页面: http://localhost:8000")
            print("API接口: http://localhost:8001/system-info")
            print("日志文件: logs/api_server.log, logs/http_server.log")
            print("\n按 Ctrl+C 停止服务器")
            
            # 监控服务器
            self.monitor_servers()
            
        except KeyboardInterrupt:
            print("\n用户中断")
        except Exception as e:
            print(f"\n运行时错误: {e}")
        finally:
            self.cleanup()


def main():
    """主函数"""
    manager = VenvServerManager()
    manager.run()


if __name__ == "__main__":
    main()