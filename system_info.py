#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台系统信息采集脚本
- 自动识别Windows/Linux（针对Debian内核6.12.18-trim做兼容）
- 采集 CPU、内存、存储、网络等信息（不采集风扇、内存温度与硬盘温度）
- 尽量使用标准库/psutil

运行：
  Windows: .venv\Scripts\python.exe system_info.py
  Linux  : python3 system_info.py
"""

import argparse
import json
import os
import platform
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

# Windows 平台可选依赖
try:
    import wmi  # type: ignore
except Exception:
    wmi = None  # 非Windows或未安装时安全降级


# ======================= 通用工具函数 =======================

def bytes_to_gb(b: float) -> float:
    """将字节转换为GB并保留两位小数。"""
    return round(b / (1024 ** 3), 2)


# ======================= CPU 信息 =======================

def get_cpu_usage() -> float:
    """获取CPU当前占用率（百分比）。"""
    try:
        return float(psutil.cpu_percent(interval=1))
    except Exception:
        return 0.0


def get_cpu_temperature() -> Optional[float]:
    """获取CPU温度（摄氏度）。不同平台采用不同策略，获取失败返回None。"""
    system = platform.system()
    # Linux 优先使用 psutil.sensors_temperatures
    if system == 'Linux':
        try:
            temps = psutil.sensors_temperatures(fahrenheit=False) or {}
            # 常见键：coretemp/k10temp/zenpower
            for key in ('coretemp', 'k10temp', 'zenpower', 'cpu-thermal'):
                if key in temps and temps[key]:
                    vals = [s.current for s in temps[key] if getattr(s, 'current', None) is not None]
                    if vals:
                        return float(max(vals))
            # 退化至 /sys/class/thermal
            base = '/sys/class/thermal'
            if os.path.isdir(base):
                res = []
                for name in os.listdir(base):
                    if not name.startswith('thermal_zone'):
                        continue
                    tpath = os.path.join(base, name, 'temp')
                    if os.path.isfile(tpath):
                        try:
                            val = int(open(tpath).read().strip())
                            # 常见以毫度C表示
                            if val > 1000:
                                res.append(val / 1000.0)
                            else:
                                res.append(float(val))
                        except Exception:
                            pass
                if res:
                    return float(max(res))
        except Exception:
            pass
        return None

    # Windows 尝试 WMI（MSAcpi_ThermalZoneTemperature），注意可能是主板而非核心温度
    if system == 'Windows' and wmi is not None:
        try:
            c = wmi.WMI(namespace='root\\WMI')
            sensors = c.MSAcpi_ThermalZoneTemperature()
            vals = []
            for s in sensors:
                # 温度单位为0.1K，需要转换摄氏度：C = (K/10) - 273.15
                if hasattr(s, 'CurrentTemperature'):
                    celsius = s.CurrentTemperature / 10.0 - 273.15
                    vals.append(celsius)
            if vals:
                return float(max(vals))
        except Exception:
            pass
        # 尝试 OpenHardwareMonitor WMI（如果用户已运行该工具）
        try:
            c = wmi.WMI(namespace='root\\OpenHardwareMonitor')
            for sensor in getattr(c, 'Sensor', lambda: [])():
                if getattr(sensor, 'SensorType', '') == 'Temperature' and 'cpu' in sensor.Name.lower():
                    return float(sensor.Value)
        except Exception:
            pass
        return None

    return None


# ======================= 内存信息 =======================

def get_memory_usage() -> Dict[str, float]:
    """获取内存使用信息（已用/总量，GB）。"""
    try:
        vm = psutil.virtual_memory()
        return {
            'used_gb': bytes_to_gb(vm.total - vm.available),
            'total_gb': bytes_to_gb(vm.total),
        }
    except Exception:
        return {'used_gb': 0.0, 'total_gb': 0.0}

# 已删除 get_memory_temperature（不再采集内存温度）


# ======================= 存储信息 =======================

def _linux_list_block_devices() -> List[str]:
    """Linux 获取物理块设备列表（如 sda、nvme0n1、vda）。"""
    res = []
    base = '/sys/block'
    if os.path.isdir(base):
        for name in os.listdir(base):
            if re.match(r'^(sd[a-z]+|nvme\d+n\d+|vd[a-z]+)$', name):
                res.append(name)
    return res


def _linux_disk_size_bytes(dev: str) -> Optional[int]:
    """Linux 通过 /sys/block/<dev>/size 读取总字节数。"""
    p = f'/sys/block/{dev}/size'
    try:
        sectors = int(open(p).read().strip())
        return sectors * 512
    except Exception:
        return None


def _linux_disk_partitions_map() -> Dict[str, List[str]]:
    """构建物理盘到分区设备路径的映射，例如 {'sda': ['/dev/sda1', ...]}。"""
    mapping: Dict[str, List[str]] = {}
    for part in psutil.disk_partitions(all=False):
        dev = part.device  # 如 /dev/sda1
        mountpoint = part.mountpoint  # 挂载点
        
        # 处理标准分区格式 /dev/sda1
        m = re.match(r'/dev/([a-z]+)\d+$', dev)
        if not m:
            # 处理 nvme0n1p1
            m = re.match(r'/dev/(nvme\d+n\d+)p\d+$', dev)
        if not m:
            # 处理整个磁盘作为分区的情况 /dev/sda
            m = re.match(r'/dev/([a-z]+)$', dev)
        if not m:
            # 处理 nvme0n1 整盘
            m = re.match(r'/dev/(nvme\d+n\d+)$', dev)
        
        if m:
            root = m.group(1)
            mapping.setdefault(root, []).append(mountpoint)  # 使用挂载点而不是设备路径
    return mapping

# 已删除 _linux_disk_temperature（不再采集硬盘温度）


def get_storage_info() -> Dict[str, Any]:
    """获取存储信息：硬盘数量、每个硬盘的容量（已用/总、GB）。"""
    system = platform.system()
    result: Dict[str, Any] = {
        'disk_count': 0,
        'disks': [],
    }

    if system == 'Linux':
        # 直接遍历已挂载的分区，而不是物理硬盘设备
        processed_mountpoints = set()
        
        for part in psutil.disk_partitions(all=False):
            mountpoint = part.mountpoint
            device = part.device
            
            # 跳过已处理的挂载点
            if mountpoint in processed_mountpoints:
                continue
                
            # 跳过特殊文件系统
            if part.fstype in ['tmpfs', 'devtmpfs', 'sysfs', 'proc', 'devpts']:
                continue
                
            try:
                usage = psutil.disk_usage(mountpoint)
                
                # 为不同挂载点设置合适的显示名称
                if mountpoint == '/':
                    display_name = '系统盘 (/)'
                elif mountpoint == '/vol1':
                    display_name = '/vol1 (应用存储)'
                elif mountpoint.startswith('/vol'):
                    display_name = f'{mountpoint} (存储卷)'
                else:
                    display_name = f'{mountpoint} ({device})'
                
                result['disks'].append({
                    'name': display_name,
                    'used_gb': bytes_to_gb(usage.used),
                    'total_gb': bytes_to_gb(usage.total),
                })
                
                processed_mountpoints.add(mountpoint)
                
            except Exception as e:
                # print(f"获取 {mountpoint} 使用量失败: {e}")
                pass
        result['disk_count'] = len(result['disks'])
        return result

    if system == 'Windows' and wmi is not None:
        try:
            c = wmi.WMI()
            # 通过关联链路汇总每个物理盘上的分区占用
            for disk in c.Win32_DiskDrive():
                total_b = int(getattr(disk, 'Size', 0) or 0)
                used_b = 0
                try:
                    for part in disk.associators("Win32_DiskDriveToDiskPartition"):
                        for ld in part.associators("Win32_LogicalDiskToPartition"):
                            mount = ld.DeviceID + "\\"  # 如 C:\
                            try:
                                u = psutil.disk_usage(mount)
                                used_b += u.used
                            except Exception:
                                pass
                except Exception:
                    pass
                result['disks'].append({
                    'name': f"{disk.Model}",
                    'used_gb': bytes_to_gb(used_b),
                    'total_gb': bytes_to_gb(total_b),
                })
            result['disk_count'] = len(result['disks'])
            return result
        except Exception:
            pass

    # 兜底：按挂载点统计（不区分物理盘）
    mounts = []
    seen = set()
    for p in psutil.disk_partitions(all=False):
        if p.mountpoint in seen:
            continue
        seen.add(p.mountpoint)
        try:
            u = psutil.disk_usage(p.mountpoint)
            mounts.append({
                'name': p.device,
                'used_gb': bytes_to_gb(u.used),
                'total_gb': bytes_to_gb(u.total),
            })
        except Exception:
            pass
    result['disks'] = mounts
    result['disk_count'] = len(mounts)
    return result


# ======================= 网络信息 =======================

def get_ip_interfaces() -> List[Tuple[str, str]]:
    """获取所有具有IPv4地址的网卡及其IP。屏蔽以 br- 开头的 bridge 网卡（如 Docker 的 br-f86755ba2795）。"""
    import socket
    res: List[Tuple[str, str]] = []
    addrs = psutil.net_if_addrs()
    AF_LINK = getattr(psutil, 'AF_LINK', None)
    for name, arr in addrs.items():
        # 屏蔽 bridge 网卡（如 Docker 的 br-xxxxxxxxxxxx）
        if name.startswith('br-'):
            continue
        for a in arr:
            fam = getattr(a, 'family', None)
            if AF_LINK is not None and fam == AF_LINK:
                continue
            if fam == socket.AF_INET:
                res.append((name, a.address))
    return res


def get_network_rate(sample_seconds: float = 1.0) -> Dict[str, float]:
    """采样一段时间，估算总上行/下行速率（Mbps）。"""
    try:
        c1 = psutil.net_io_counters()
        time.sleep(sample_seconds)
        c2 = psutil.net_io_counters()
        up_bps = (c2.bytes_sent - c1.bytes_sent) * 8.0 / sample_seconds
        down_bps = (c2.bytes_recv - c1.bytes_recv) * 8.0 / sample_seconds
        return {
            'up_mbps': round(up_bps / 1_000_000, 3),
            'down_mbps': round(down_bps / 1_000_000, 3),
        }
    except Exception:
        return {'up_mbps': 0.0, 'down_mbps': 0.0}

# 已删除风扇信息相关代码（get_fans_info）


# ======================= 主流程 =======================

def is_debian_kernel_special() -> bool:
    """是否为需要特别兼容的Debian内核版本 6.12.18-trim。"""
    try:
        return platform.system() == 'Linux' and platform.release().strip() == '6.12.18-trim'
    except Exception:
        return False


def collect_system_info() -> Dict[str, Any]:
    """汇总采集所有信息，返回结构化字典。"""
    info: Dict[str, Any] = {
        'os': platform.system(),
        'os_release': platform.release(),
        'os_version': platform.version(),
        'debian_kernel_6_12_18_trim': is_debian_kernel_special(),
    }

    # CPU
    info['cpu'] = {
        'usage_percent': get_cpu_usage(),
        'temperature_c': get_cpu_temperature(),
    }

    # Memory
    mem = get_memory_usage()
    info['memory'] = mem

    # Storage
    info['storage'] = get_storage_info()

    # Network
    info['network'] = {
        'interfaces': [{'name': n, 'ip': ip} for n, ip in get_ip_interfaces()],
        **get_network_rate(1.0),
    }

    return info


# 新增：FastAPI 与 CORS、Uvicorn（仅在 --serve 模式下使用）
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


# ======================= 图片文件扫描 =======================

def get_image_files() -> Dict[str, List[str]]:
    """扫描image目录中的所有图片文件
    
    Returns:
        Dict: 包含图片文件列表的字典
    """
    try:
        # 获取当前脚本所在目录
        script_dir = Path(__file__).parent.absolute()
        image_dir = script_dir / "image"
        
        # 支持的图片格式
        image_extensions = {'.gif', '.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        
        image_files = []
        
        if image_dir.exists() and image_dir.is_dir():
            for file_path in image_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                    image_files.append(file_path.name)
        
        # 按文件名排序
        image_files.sort()
        
        return {
            "files": image_files,
            "count": len(image_files),
            "directory": str(image_dir)
        }
        
    except Exception as e:
        return {
            "files": [],
            "count": 0,
            "error": str(e),
            "directory": ""
        }


# ======================= HTTP 服务（FastAPI） =======================

def create_app() -> FastAPI:
    """创建 FastAPI 应用并注册路由。
    - 提供 GET /system-info 端点，返回 collect_system_info() 的结果
    - 默认开启 CORS 以便前后端跨域访问（生产可按需收敛域名）
    """
    app = FastAPI(title="NAS Monitor Python Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/system-info")
    def system_info_endpoint():
        return collect_system_info()
    
    @app.get("/image-files")
    def image_files_endpoint():
        """获取image目录中的所有图片文件列表"""
        return get_image_files()

    return app


def serve_api(host: str = "0.0.0.0", port: int = 8000) -> None:
    """启动 Uvicorn 服务，运行 FastAPI 应用。"""
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


def main() -> None:
    """主函数：采集信息并以JSON形式输出（CLI 模式）。"""
    data = collect_system_info()
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        # 在 Windows 下确保 stdout 使用 UTF-8，避免中文网卡名乱码
        import sys
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # 新增：解析命令行参数，支持 --serve 模式
    parser = argparse.ArgumentParser(description="NAS Monitor system_info 服务/脚本")
    parser.add_argument("--serve", action="store_true", help="以 HTTP API 模式提供 /system-info")
    parser.add_argument("--host", default=os.environ.get("PY_HOST", "0.0.0.0"), help="HTTP 监听地址，默认 0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PY_PORT", "8000")), help="HTTP 监听端口，默认 8000")
    args = parser.parse_args()

    if args.serve:
        serve_api(args.host, args.port)
    else:
        main()