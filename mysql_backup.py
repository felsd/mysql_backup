import glob
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime
from os.path import basename
from pathlib import Path
from zipfile import ZipFile

from paramiko import AutoAddPolicy, SSHClient
from scp import SCPClient

import settings


def init_logger():
    logger = logging.getLogger("mysql_backup")
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    logger_formatter = logging.Formatter(
        "[%(levelname)s] [%(asctime)s] %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
    )
    console_handler.setFormatter(logger_formatter)
    logger.addHandler(console_handler)
    return logger


def test_ssh_connection():
    client = SSHClient()
    try:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(AutoAddPolicy())
        client.connect(
            settings.SSH_HOST,
            port=settings.SSH_PORT,
            username=settings.SSH_USER,
            key_filename=settings.SSH_KEY,
            look_for_keys=True,
            timeout=5000,
        )
    except Exception as e:
        logger.error("SSH connection failed! Exiting.", exc_info=e)
        os._exit(1)
    finally:
        client.close()


def backup_database_to_temp_dir(db_name):
    logger.info(f"Creating backup of database '{db}'...")
    cmd = (
        f"mysqldump -h{settings.MYSQL_HOST} -P{settings.MYSQL_PORT} "
        f"-u{settings.MYSQL_USER} -p{settings.MYSQL_PASS} "
        f"{db_name} > {os.path.join(temp_dir, db_name)}.sql"
    )
    try:
        subprocess.check_call(cmd, shell=True)
    except Exception:
        logger.error(f"Backing up '{db_name}' failed!")


def zip_databases_to_ldest():
    dt = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = os.path.join(settings.LOCAL_DESTINATION, f"mysql_backup_{dt}.zip")
    logger.info(f"Zipping databases to {filename}")
    with ZipFile(filename, "w") as zf:
        for f in os.listdir(temp_dir):
            if f.endswith(".sql"):
                fp = os.path.join(temp_dir, f)
                zf.write(fp, os.path.basename(fp))


def cleanup_ldest():
    counter = 0
    files = list(
        sorted(
            Path(settings.LOCAL_DESTINATION).iterdir(),
            key=os.path.getmtime,
            reverse=True,
        )
    )
    for f in files:
        if str(f).endswith(".zip"):
            counter += 1
            if counter > settings.ROLLING:
                logger.info(f"Deleting old backup {f}")
                os.remove(f)


def sync_ssh():
    logger.info("Uploading backups to SSH destination")
    files = glob.glob(os.path.join(settings.LOCAL_DESTINATION, "*.zip"))
    client = SSHClient()
    scp = None
    try:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(AutoAddPolicy())
        client.connect(
            settings.SSH_HOST,
            port=settings.SSH_PORT,
            username=settings.SSH_USER,
            key_filename=settings.SSH_KEY,
            look_for_keys=True,
            timeout=5000,
        )
        stdin, stdout, stderr = client.exec_command(
            f"mkdir -p {settings.SSH_DESTINATION}"
        )
        if stdout.channel.recv_exit_status():
            raise Exception("mkdir -p failed")
        scp = SCPClient(client.get_transport())
        for file in files:
            scp.put(file, remote_path=settings.SSH_DESTINATION)
        logger.info("Cleaning up remote directory")
        stdin, stdout, stderr = client.exec_command(
            f"ls {settings.SSH_DESTINATION}/*.zip"
        )
        if stdout.channel.recv_exit_status():
            raise Exception("Failed to list remote directory")
        basenames = [basename(x) for x in files]
        for rfile in stdout:
            rfile = rfile.strip()
            if basename(rfile) not in basenames:
                logger.info(f"Deleting old remote backup {rfile}")
                client.exec_command(f"rm {rfile}")
    except Exception as e:
        logger.error("SSH syncing failed! Exiting.", exc_info=e)
        os._exit(1)
    finally:
        client.close()
        if scp:
            scp.close()


if __name__ == "__main__":
    temp_dir = f"/tmp/mysqlbkp/{time.time()}"
    os.makedirs(temp_dir)
    logger = init_logger()
    logger.info(f"Starting MySQL backup {settings.VERSION}")
    logger.info(f"Databases: {settings.DATABASES}")
    logger.info(f"Local destination: {settings.LOCAL_DESTINATION}")
    logger.info(f"SSH destination: {settings.SSH_DESTINATION}")
    logger.info(f"Temporary dir: {temp_dir}")
    if settings.SSH_BACKUP:
        test_ssh_connection()
    if not os.path.exists(settings.LOCAL_DESTINATION):
        os.makedirs(settings.LOCAL_DESTINATION)
    for db in settings.DATABASES:
        backup_database_to_temp_dir(db)
    zip_databases_to_ldest()
    cleanup_ldest()
    logger.info("Deleting temporary dir")
    shutil.rmtree(temp_dir)
    if settings.SSH_BACKUP:
        sync_ssh()
    logger.info("Done")
