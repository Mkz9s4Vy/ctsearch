import configparser
import subprocess
import os


def read_config(config_path):
    """
    读取配置文件并返回定时时间。

    :param config_file: 配置文件的路径
    :return: 定时时间（秒）
    """
    config = configparser.ConfigParser()
    config.read(config_path)
    return int(config['scheduler']['interval'])


def add_cron_job(cron_command):
    """
    添加一个新的 crontab 任务。

    :param cron_command: 要添加的 crontab 命令，例如 "*/5 * * * * /usr/bin/python3 /path/to/script.py"
    """
    # 使用 crontab -l 获取当前的 crontab 任务
    current_crontab = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    
    # 将新的任务添加到当前的 crontab 任务中
    new_crontab = current_crontab.stdout + cron_command + "\n"
    
    # 使用 crontab - 将新的 crontab 任务写入
    subprocess.run(['crontab', '-'], input=new_crontab, text=True)


def generate_cron_command(interval, script_path):
    """
    生成 crontab 命令。

    :param interval: 定时时间（秒）
    :param script_path: 要运行的脚本路径
    :return: crontab 命令
    """
    minutes = interval // 60
    cron_command = f"*/{minutes} * * * * /usr/bin/python3 {script_path}"
    return cron_command


def main():
    script_path = script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "data/config.ini")

    # 读取配置文件中的定时时间
    interval = read_config(config_path)
    
    # 生成 crontab 命令
    cron_command = generate_cron_command(interval, script_path)
    
    # 添加 crontab 任务
    add_cron_job(cron_command)


if __name__ == "__main__":
    main()
