import subprocess
import os
import configparser


# 获取当前脚本文件的目录
script_dir = os.path.dirname(os.path.abspath(__file__))


# 定义任务的详细信息
task_name = "RunMyExeEvery30Minutes"
exe_name = "indexer.exe"  # 假设 .exe 文件名为 program.exe
exe_path = os.path.join(script_dir, exe_name)
task_schedule = "MINUTE"


"""读取配置文件并返回interval值"""
config_path = os.path.join(script_dir, "data/config.ini")
config = configparser.ConfigParser()
config.read(config_path)
task_interval = config.getint('scheduler', 'interval')
print(task_interval)


# 构建 schtasks 命令
schtasks_command = [
    "schtasks",
    "/Create",
    "/TN", task_name,
    "/TR", exe_path,
    "/SC", task_schedule,
    "/MO", task_interval,
    "/F"  # 强制创建任务，如果任务已存在则覆盖
]

# 运行 schtasks 命令
try:
    subprocess.run(schtasks_command, check=True)
    print(f"任务 '{task_name}' 已成功创建。")
except subprocess.CalledProcessError as e:
    print(f"创建任务时出错: {e}")
