# AppFlow Custom Connector for Google Analytics 4 (GA4)

## 概要

本サンプルは Google Analytics 4 (GA4) からニアリアルタイムでデータを送信する AppFlow カスタムコネクタです。日次でのデータ取得については、ネイティブに[サポートしている Google Analytics 4 コネクタ](https://docs.aws.amazon.com/appflow/latest/userguide/connectors-google-analytics-4.html)の活用も併せて検討ください。また、Custom Connector SDK を用いた実装についてはこちらの[解説ブログ](https://aws.amazon.com/jp/builders-flash/202302/appflow-custom-connecter-saas-data)も併せてご参照ください。

## 目次

- [デプロイ手順](/docs/DEPLOYMENT.md)
- [動作確認手順](/docs/OPERATION.md)
- [カスタムコネクタについて](#カスタムコネクタ)

## カスタムコネクタ

Custom Connector SDK の仕様について説明します。本サンプルでは [Amazon AppFlow Custom Connector SDK for Python](https://github.com/awslabs/aws-appflow-custom-connector-python) を使用しています。
カスタムコネクタを利用するにはこちらの SDK を用いて、カスタムコネクタ用の Lambda を実装しデプロイする必要があります。そして、デプロイした Lambda 関数を AppFlow コンソールからカスタムコネクタとして登録し、利用することができます。

### カスタムコネクタ用 Lambda 関数

以下の 3 つの Class と各 Class 内で決まった関数を実装し、各関数のレスポンスは AppFlow の決まった形で返す必要があります。[各関数の詳細](#各関数の詳細)は後述します。

- ConfigurationHandler
  - validate_connector_runtime_settings
  - validate_credentials
  - describe_connector_configuration
- RecordHandler
  - retrieve_data
  - write_data
  - query_data
- MetadataHandler
  - list_entities
  - describe_entity

#### 注意事項

- Lambda 関数に以下のリソースベースポリシーを付与する必要があります。

```json
{
  "Version": "2012-10-17",
  "Id": "default",
  "Statement": [
    {
      "Sid": "<任意の名前>",
      "Effect": "Allow",
      "Principal": {
        "Service": "appflow.amazonaws.com"
      },
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:<リージョン名>:<アカウントID>:function:<Lambda関数名>",
      "Condition": {
        "ArnLike": {
          "AWS:SourceArn": "arn:aws:appflow:<リージョン名>:<アカウントID>:*"
        }
      }
    }
  ]
}
```

- フロー実行時以外（カスタムコネクタ登録時、フロー作成時など）でも Lambda 関数は実行されるので CloudWatch Logs を参照してデバッグ可能です。
- カスタムコネクタとして Lambda 関数を登録した後且つ、フロー作成の完了前に Lambda 関数を更新した場合はカスタムコネクタの登録からやり直す必要があります。また、フロー作成まで完了すると Lambda の更新はフローに即時反映されるため、再登録は不要です。

### 各関数の詳細

#### describe_connector_configuration

- カスタムコネクタ登録時に呼び出され、連携元システムへの認証方法の定義を返す
- 選択可能な認証方式
  - OAuth2
  - BASIC
  - API キー
  - カスタム認証

#### list_entities

- フロー作成時に呼び出され、スキーマ定義 (Entity) のリストを返す
- Entity
  - サポートする API 毎に定義する
    - RunRealtimeReport API の例
      - ```python
        run_realtime_report_entity = context.Entity(
          entity_identifier="RunRealtimeReportEntity",
          label="RunRealtimeReportEntity",
          has_nested_entities=False,
          description="RunRealtimeReportEntity",
        )
        ```
    - `has_nested_entities` はサブオブジェクトの有無
- 返り値の `entities` に `Entity` のリストを渡す

#### describe_entity

- フロー作成のデータフィールドマッピングで呼び出され、フィールドの定義を返す
- 返り値の `entity_definition`
  - entity は `list_entities` の `entities` の当該 `Entity` と同値
  - `fields` は当該 `Entity` のフィールド定義のリスト
    - `field_name`, `data_type`, `read_properties` などを設定
    - `data_time` フィールドの例
      - ```python
        date_time_field = context.FieldDefinition(
            field_name="DateTime",
            data_type=fields.FieldDataType.String,
            data_type_label="string",
            label="DateTime",
            description="DateTime",
            default_value="1970-01-01 00:00:00",
            is_primary_key=True,
            # データの送信元に指定する場合に設定するフィールドの型定義
            read_properties=fields.ReadOperationProperty(
                # データ取得時にフィルタとして指定できる項目かどうか
                is_queryable=True,
                # データ取得時に表示されるかどうか
                is_retrievable=True,
                # null 値を許容するかどうか
                is_nullable=False,
                # Date か DateTime 型かどうか
                is_timestamp_field_for_incremental_queries=False,
            ),
            # データの送信先に指定する場合に設定するフィールドの型定義
            write_properties=None,
        )
        ```

#### query_data

- フロー実行時に呼び出され、フローで定義されたフィールドを取得する
- 返り値の `records` に渡す配列は以下の形式の JSON オブジェクトの文字列の配列
  - ```python
    record_list = [
      '{"field-name-1": 1, "field-name-2": 2, "field-name-3": 3}',
      '{"field-name-1": 4, "field-name-2": 5, "field-name-3": 6}',
    ]
    ```
    - `field-name-*` は各フィールドの `describe_entity` の `field_name` と一致させる
    - 送信データの `field` を `field-name-1` に指定した場合、S3 に格納されるのは以下のデータ
      - ```
        {"field-name-1":1}
        {"field-name-1":4}
        ```

## 本カスタムコネクタの注意事項

本カスタムコネクタは runRealtimeReport API により GA4 のデータを取得し、それによりいくつかの制約があるため注意事項として説明します。runRealtimeReport API の詳細については GA4 のドキュメントを正式な情報とするのでそちらを参照いただき、本セクションの内容は参考情報としていただければと思います。

### 相対的な日時の取得制限による日時データの誤差

日時データは相対値で返されるため (datetime ではなく minutesAgo) 、この相対値とローカルの現在日時から実際の日時データに近い値を取得し `DateTime` としています。

### 最大取得行数の制限

取得する行数には 100,000 件の制限があり、dimensions の値を増やすと取得する行数が大幅に増加します。このため、訪問者が多く dimensions も多い場合、この制限に達してしまい正確なデータが取得できない可能性があります。ページネーションなどはサポートされておらず、制限に達する場合は指定する dimensions を減らす必要があります。

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
