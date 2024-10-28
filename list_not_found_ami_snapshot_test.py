"""AMIとSnapShotを作成するテストコード"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from moto import mock_aws
from zoneinfo import ZoneInfo

from list_not_found_ami_snapshot import main

if TYPE_CHECKING:
    from time import struct_time


####################
# グローバル定数定義 #
####################
try:
    BOTO3_CONFIG = Config(
        retries={"max_attempts": 30, "mode": "standard"},
        read_timeout=900,
        connect_timeout=900,
        region_name="ap-northeast-1",
    )
    JST = ZoneInfo("Asia/Tokyo")
    AMI_ID = "ami-03f584e50b2d32776"
    ACCOUNT_ID = "123456789012"
    # mock内におけるアカウントIDを設定
    os.environ["MOTO_ACCOUNT_ID"] = ACCOUNT_ID
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
    # ログハンドラ設定
    stdout_handler.setFormatter(formatter)
    test_logger = logging.getLogger("test_logger")
    test_logger.addHandler(stdout_handler)
    test_logger.setLevel(log_level)
except Exception as e:
    msg = "ロガー設定エラー"
    raise Exception(msg) from e


###########
# 処理開始 #
###########
# clientの作成はmock内で行う
@mock_aws
def test_create_instance(ec2_client: boto3.client) -> str:
    """EC2インスタンスを作成する関数"""
    response = ec2_client.run_instances(
        ImageId=AMI_ID,
        MaxCount=1,
        MinCount=1,
        Monitoring={
            "Enabled": False,
        },
    )
    instance_id = response["Instances"][0]["InstanceId"]
    test_logger.debug("instance_id: %s", instance_id)
    return instance_id


@mock_aws
def test_wait_instance_running(ec2_client: boto3.client, instance_id: str) -> None:
    """EC2インスタンスが起動するまで待機する関数"""
    waiter = ec2_client.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])
    response = ec2_client.describe_instances(InstanceIds=[instance_id])
    state = response["Reservations"][0]["Instances"][0]["State"]["Name"]
    test_logger.debug("instance_state: %s", state)


@mock_aws
def test_create_image(ec2_client: boto3.client, instance_id: str, ami_name: str) -> str:
    """AMIを作成する関数"""
    response = ec2_client.create_image(
        InstanceId=instance_id,
        Name=ami_name,
    )
    ami_id = response["ImageId"]
    test_logger.debug("ami_name: %s, ami_id: %s", ami_name, ami_id)
    return ami_id


@mock_aws
def test_wait_image_available(ec2_client: boto3.client, ami_id: str) -> None:
    """AMIが利用可能になるまで待機する関数"""
    waiter = ec2_client.get_waiter("image_available")
    waiter.wait(ImageIds=[ami_id])
    response = ec2_client.describe_images(ImageIds=[ami_id])
    state = response["Images"][0]["State"]
    test_logger.debug("ami_id: %s, ami_state: %s", ami_id, state)


@mock_aws
def test_delete_image(ec2_client: boto3.client, ami_id: str) -> None:
    """AMIを削除する関数"""
    ec2_client.deregister_image(ImageId=ami_id)
    test_logger.debug("ami_id: %s deleted", ami_id)


@mock_aws
def test_describe_snapshot_tag(ec2_client: boto3.client, snapshot_ids: list[str]) -> None:
    """SnapShotのタグを取得する関数"""
    response = ec2_client.describe_snapshots(SnapshotIds=snapshot_ids)
    for snapshot in response["Snapshots"]:
        test_logger.debug("snapshot_id: %s, tag: %s", snapshot["SnapshotId"], snapshot["Tags"])


@mock_aws
def test_main() -> None:
    """テスト用のmain関数"""
    # 事前処理
    ec2_client = boto3.client("ec2", config=BOTO3_CONFIG)
    instance_id = test_create_instance(ec2_client)
    test_wait_instance_running(ec2_client, instance_id)
    ami_id_1 = test_create_image(ec2_client, instance_id, "test-ami-1")
    ami_id_2 = test_create_image(ec2_client, instance_id, "test-ami-2")
    ami_id_3 = test_create_image(ec2_client, instance_id, "test-ami-3")
    test_wait_image_available(ec2_client, ami_id_1)
    test_wait_image_available(ec2_client, ami_id_2)
    test_wait_image_available(ec2_client, ami_id_3)
    test_delete_image(ec2_client, ami_id_2)
    # メイン処理
    unassociated_snapshots = main(ec2_client)
    # 事後処理
    test_describe_snapshot_tag(ec2_client, list(unassociated_snapshots))


if __name__ == "__main__":
    test_main()
