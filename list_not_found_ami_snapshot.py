"""AMIに関連付けられていないSnapShotをリストする"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from time import struct_time


####################
# グローバル定数定義 #
####################
try:
    DIRECTORY_NAME = "list_not_found_ami_snapshot"
    DIRECTORY_PATH = Path(__file__).parent / DIRECTORY_NAME
    DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
    BOTO3_CONFIG = Config(
        retries={"max_attempts": 30, "mode": "standard"},
        read_timeout=900,
        connect_timeout=900,
        region_name="ap-northeast-1",
    )
    JST = ZoneInfo("Asia/Tokyo")
    CURRENT_DATE = datetime.now(JST).strftime("%Y-%m-%d")
    LOG_FILE = f"{DIRECTORY_PATH}/{CURRENT_DATE}.log"
    EXPORT_FILE_NAME = f"{DIRECTORY_PATH}/unassociated_snapshots.txt"
    ACCOUNT_ID = "123456789012"
except Exception as e:
    msg = "グローバル定数定義エラー"
    raise Exception(msg) from e


#############
# ロガー設定 #
#############
try:

    def custom_time(*_args: tuple[Any, ...]) -> struct_time:
        """ログのタイムゾーンをJSTに設定するための関数"""
        return datetime.now(JST).timetuple()

    log_level = logging.DEBUG
    log_format = "[%(asctime)s.%(msecs)03d JST] [%(levelname)s] [%(lineno)d行目] [関数名: %(funcName)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(log_format, datefmt=date_format)
    formatter.converter = custom_time
    # ログ出力設定
    stdout_handler = logging.StreamHandler(sys.stdout)  # ログ標準出力
    stdout_handler.setLevel(log_level)
    file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    file_handler.setLevel(log_level)  # ログファイル出力
    # ログハンドラ設定
    stdout_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    logger = logging.getLogger("custom_logger")
    logger.addHandler(stdout_handler)
    logger.addHandler(file_handler)
    logger.setLevel(log_level)
except Exception as e:
    msg = "ロガー設定エラー"
    raise Exception(msg) from e


###########
# 処理開始 #
###########
def list_snapshot(ec2_client: boto3.client) -> set[str]:
    """SnapShotIDをsetで一覧取得する関数"""
    snapshots_set: set[str] = set()
    paginator = ec2_client.get_paginator("describe_snapshots")
    response_iterator = paginator.paginate(OwnerIds=[ACCOUNT_ID])
    for page in response_iterator:
        for snapshot in page["Snapshots"]:
            snapshot_description = snapshot.get("Description", "")
            # AMIから作成されたSnapShotのみ取得
            # ※AMIから作成されたSnapShotの「説明」には、「Created by CreateImage ~」という文言が記載されている
            if "Created by CreateImage" in snapshot_description:
                snapshot_id = snapshot.get("SnapshotId", "")
                snapshots_set.add(snapshot_id)
    logger.debug("SnapShotIDの一覧: %s", snapshots_set)
    return snapshots_set


def list_ami(ec2_client: boto3.client) -> set[str]:
    """AMIのSnapShotIDをsetで一覧取得する関数"""
    amis_set: set[str] = set()
    paginator = ec2_client.get_paginator("describe_images")
    response_iterator = paginator.paginate(Owners=[ACCOUNT_ID])
    for page in response_iterator:
        for ami in page["Images"]:
            for block in ami.get("BlockDeviceMappings", []):
                ebs = block.get("Ebs", {})
                snapshot_id = ebs.get("SnapshotId", "")
                amis_set.add(snapshot_id)
    logger.debug("AMIに関連付けられたSnapShotIDの一覧: %s", amis_set)
    return amis_set


def grant_tag(ec2_client: boto3.client, snapshot_ids: list[str]) -> None:
    """SnapShotにタグを付与する関数"""
    ec2_client.create_tags(
        Resources=snapshot_ids,
        Tags=[{"Key": "NotAttachedAMI", "Value": "True"}],
    )


def export_text(unassociated_snapshots: set[str]) -> None:
    """setの結果をテキストファイルに出力する関数"""
    export_path = Path(EXPORT_FILE_NAME)
    with export_path.open("w", encoding="utf-8") as file:
        for snapshot_id in unassociated_snapshots:
            file.write(f"{snapshot_id}\n")


def main(ec2_client: boto3.client) -> set[str]:
    """メイン関数"""
    # 1. AMIから作成されたSnapShotを取得
    # 2. すでにAMIは削除されていて、AMIに関連付けられていないSnapShotを取得
    try:
        snapshots_set = list_snapshot(ec2_client)
        amis_set = list_ami(ec2_client)
        unassociated_snapshots = snapshots_set - amis_set
        logger.debug("AMIに関連付けられていないSnapShotIDの一覧: %s", unassociated_snapshots)
        if unassociated_snapshots:
            grant_tag(ec2_client, list(unassociated_snapshots))
            export_text(unassociated_snapshots)
        else:
            logger.debug("AMIに関連付けられていないSnapShotはありません。")
    except Exception as e:
        msg = "メイン関数エラー"
        raise Exception(msg) from e
    return unassociated_snapshots


if __name__ == "__main__":
    ec2_client = boto3.client("ec2", config=BOTO3_CONFIG)
    main(ec2_client)
