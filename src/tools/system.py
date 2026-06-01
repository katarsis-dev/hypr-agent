"""System info tool — CPU, RAM, disk, processes."""

from __future__ import annotations

import os
import platform
from typing import Any


class SystemTool:
    name = "system_info"
    description = "Get system information: CPU, RAM, disk usage, running processes, or OS details."
    input_schema = '{"query": "cpu|ram|disk|processes|os|all"}'

    async def execute(self, **kwargs: Any) -> str:
        query = kwargs.get("query") or kwargs.get("input", "all")
        query = query.lower().strip()

        parts: list[str] = []

        if query in ("cpu", "all"):
            parts.append(self._cpu_info())
        if query in ("ram", "memory", "all"):
            parts.append(self._ram_info())
        if query in ("disk", "storage", "all"):
            parts.append(self._disk_info())
        if query in ("processes", "procs", "all"):
            parts.append(self._processes())
        if query in ("os", "system", "all"):
            parts.append(self._os_info())

        if not parts:
            return f"Unknown query '{query}'. Use: cpu, ram, disk, processes, os, all"

        return "\n\n".join(parts)

    def _cpu_info(self) -> str:
        try:
            with open("/proc/cpuinfo") as f:
                cpuinfo = f.read()
            model = ""
            cores = 0
            for line in cpuinfo.split("\n"):
                if "model name" in line and not model:
                    model = line.split(":")[1].strip()
                if "processor" in line:
                    cores += 1

            # Load average
            load = os.getloadavg()
            return (
                f"CPU: {model}\n"
                f"Cores/Threads: {cores}\n"
                f"Load average (1/5/15 min): {load[0]:.2f} / {load[1]:.2f} / {load[2]:.2f}"
            )
        except Exception as e:
            return f"CPU info unavailable: {e}"

    def _ram_info(self) -> str:
        try:
            with open("/proc/meminfo") as f:
                meminfo = f.read()
            mem: dict[str, int] = {}
            for line in meminfo.split("\n"):
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    mem[key] = int(parts[1])  # in kB

            total = mem.get("MemTotal", 0) / 1024 / 1024
            available = mem.get("MemAvailable", 0) / 1024 / 1024
            used = total - available
            return (
                f"RAM: {used:.1f} GB used / {total:.1f} GB total "
                f"({available:.1f} GB available)"
            )
        except Exception as e:
            return f"RAM info unavailable: {e}"

    def _disk_info(self) -> str:
        try:
            stat = os.statvfs("/")
            total = stat.f_blocks * stat.f_frsize / (1024**3)
            free = stat.f_bavail * stat.f_frsize / (1024**3)
            used = total - free
            return f"Disk (/): {used:.1f} GB used / {total:.1f} GB total ({free:.1f} GB free)"
        except Exception as e:
            return f"Disk info unavailable: {e}"

    def _processes(self) -> str:
        try:
            # Use ps to get top processes by CPU
            result = os.popen("ps aux --sort=-%cpu | head -11").read()
            return f"Top processes by CPU:\n{result}"
        except Exception as e:
            return f"Process info unavailable: {e}"

    def _os_info(self) -> str:
        return (
            f"OS: {platform.system()} {platform.release()}\n"
            f"Distribution: {platform.freedesktop_os_release().get('PRETTY_NAME', 'unknown') if hasattr(platform, 'freedesktop_os_release') else platform.platform()}\n"
            f"Hostname: {platform.node()}\n"
            f"Python: {platform.python_version()}\n"
            f"Architecture: {platform.machine()}"
        )
