import os
import configparser

def setup_cron():
    # 脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 定义 Whoosh 索引存储的目录
    config_path = os.path.join(script_dir, "data/config.ini")
    # 读取配置文件
    config = configparser.ConfigParser()
    config.read(config_path)
    interval = config.getint('scheduler', 'interval')
    print(interval)

    # 创建日志文件
    log_file_path = os.path.join(script_dir, "data/cron.log")
    if not os.path.exists(log_file_path):
        with open(log_file_path, 'w') as log_file:
            log_file.write('Cron log file created.\n')

    # 创建 cron 任务
    cron_job = f"*/{interval} * * * * python indexer.py >> {log_file_path} 2>&1\n"
    print(cron_job)


    # 写入 cron 任务
    try:
        with open('/etc/cron.d/indexer_cron', 'w') as cron_file:
            cron_file.write(cron_job)
        log_file.write(cron_job)
    except Exception as e:
        log_file.write("Set indexer cron job failed")

    # 确保 cron 任务文件有正确的权限
    try:
        os.chmod('/etc/cron.d/indexer_cron', 0o644)
        log_file.write("Cron job file permissions set.")
    except Exception as e:
        log_file.write(f"Failed to set cron job file permissions: {e}")
        return

if __name__ == "__main__":
    setup_cron()
