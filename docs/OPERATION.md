# 動作確認手順

本サンプルの動作確認手順を説明します。

## AppFlow の動作確認

作成したフローの詳細画面の「実行履歴」タブから実行時刻やレコード数などを確認できます。

## 送信されたデータの確認

データの中身の確認は送信先のサービスに応じて、実施します。ここでは S3 と Redshift の場合を説明します。

### 送信先が S3 の場合のデータの確認

送信先を S3 として場合は Athena でクエリをかけることにより、データを確認できます。

1. Athena のクエリエディタから下記のクエリを参考に AppFlow の宛先の S3 バケットのテーブルを作成します（LOCATION の S3 のバケット名やパスは適宜修正してください）。また、GUI でテーブルとビューから作成することも可能です。

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS `default`.`appflow-custom-connector-table` (
  `DateTime` string,
  `RequestDateTime` string,
  `Country` string,
  `City` string,
  `ScreenPageViews` int,
  `ActiveUsers` int
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
  'ignore.malformed.json' = 'FALSE',
  'dots.in.keys' = 'FALSE',
  'case.insensitive' = 'TRUE',
  'mapping' = 'TRUE'
)
STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat' OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION 's3://<bucket-name>/<path>/'
TBLPROPERTIES ('classification' = 'json');
```

2. 作成したテーブルの右のメニューから「テーブルをプレビュー」をクリックし、データを確認します。

![Athena クエリエディタ](/docs/img/Athena-QueryEditor.png)

## 送信先が Redshift の場合のデータの確認

1. Redshift のコンソールから当該クラスターを選択し、クエリエディタを開きます。
2. 当該テーブルに Select table することで確認できます。

![Redshift クエリエディタ](/docs/img/Redshift-QueryEditor.png)
