## 概要

AMIに関連付けられていないSnapShotを取得し、そのSnapShotにタグを付与する

## インストール

- boto3
- moto

https://aws.amazon.com/jp/sdk-for-python/<br>
https://docs.getmoto.org/en/latest/docs/getting_started.html

## 事前準備

以下のコードに記載されている `ACCOUNT_ID` を環境に合わせて設定する

- list_not_found_ami_snapshot.py
- list_not_found_ami_snapshot_text.py


## 使い方


```bash
python list_not_found_ami_snapshot.py
```

## ローカルテスト

```bash
python list_not_found_ami_snapshot_test.py
```
