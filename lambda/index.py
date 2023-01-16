import datetime
import json
import logging

import boto3
import custom_connector_sdk.connector.auth as auth
import custom_connector_sdk.connector.configuration as config
import custom_connector_sdk.connector.context as context
import custom_connector_sdk.connector.fields as fields
import custom_connector_sdk.connector.settings as settings
import custom_connector_sdk.lambda_handler.requests as requests
import custom_connector_sdk.lambda_handler.responses as responses
from custom_connector_sdk.lambda_handler.handlers import (
    ConfigurationHandler,
    MetadataHandler,
    RecordHandler,
)
from custom_connector_sdk.lambda_handler.lambda_handler import (
    BaseLambdaConnectorHandler,
)
from custom_connector_sdk.lambda_handler.responses import ErrorCode, ErrorDetails
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    Dimension,
    Metric,
    OrderBy,
    RunRealtimeReportRequest,
)
from google.oauth2 import service_account

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

# カスタムコネクタの情報
CONNECTOR_OWNER = "DemoOwner"
CONNECTOR_NAME = "GA4Connector"
CONNECTOR_VERSION = "1.0"

# GA4 への接続情報のキー名（変更不要）
PROPERTY_ID_KEY = "propertyId"
PRIVATE_KEY_KEY = "privateKey"
CLIENT_EMAIL_KEY = "clientEmail"

# スキーマ定義（API 毎に定義）
# 今回は RunRealtimeReport API のみサポートするのでそのエンティティを定義
run_realtime_report_entity = context.Entity(
    entity_identifier="RunRealtimeReportEntity",
    label="RunRealtimeReportEntity",
    has_nested_entities=False,
    description="RunRealtimeReportEntity",
)


class ConnectorDemoConfigurationHandler(ConfigurationHandler):
    def validate_connector_runtime_settings(
        self, request: requests.ValidateConnectorRuntimeSettingsRequest
    ) -> responses.ValidateConnectorRuntimeSettingsResponse:
        print("ConfigurationHandler::validate_connector_runtime_settings")
        return responses.ValidateConnectorRuntimeSettingsResponse(is_success=True)

    def validate_credentials(
        self, request: requests.ValidateCredentialsRequest
    ) -> responses.ValidateCredentialsResponse:
        print("ConfigurationHandler::validate_credentials")
        return responses.ValidateCredentialsResponse(is_success=True)

    # このメソッドが CustomConnector 登録時に呼び出される
    # 実装内容は連携先システムへの認証方法の定義
    def describe_connector_configuration(
        self, request: requests.DescribeConnectorConfigurationRequest
    ) -> responses.DescribeConnectorConfigurationResponse:
        print("ConfigurationHandler::describe_connector_configuration")

        # コネクタの認証方法の設定
        # 今回は GA4 Data API を叩く際に GCP のサービスアカウントを使用するため Custom Auth を設定
        authentication_config = auth.AuthenticationConfig(
            is_custom_auth_supported=True,
            custom_auth_config=[
                auth.CustomAuthConfig(
                    authentication_type="CUSTOM",
                    auth_parameters=[
                        auth.AuthParameter(
                            key=PRIVATE_KEY_KEY,
                            required=True,
                            label="Private Key",
                            description="GCP サービスアカウントの private_key を入力（スペースは \\s に置換）",
                            sensitive_field=True,
                            connector_supplied_values=None,
                        ),
                        auth.AuthParameter(
                            key=CLIENT_EMAIL_KEY,
                            required=True,
                            label="Client Email",
                            description="xxxxxx@xxxx.iam.gserviceaccount.com",
                            sensitive_field=False,
                            connector_supplied_values=None,
                        ),
                    ],
                )
            ],
        )

        property_id_setting = settings.ConnectorRuntimeSetting(
            key=PROPERTY_ID_KEY,
            data_type=settings.ConnectorRuntimeSettingDataType.String,
            required=True,
            label="GA4 Property ID",
            description="GA4 Property ID",
            scope=settings.ConnectorRuntimeSettingScope.CONNECTOR_PROFILE,
        )

        return responses.DescribeConnectorConfigurationResponse(
            is_success=True,
            # カスタムコネクタの所有者
            connector_owner=CONNECTOR_OWNER,
            # カスタムコネクタ名
            connector_name=CONNECTOR_NAME,
            # 認証設定
            authentication_config=authentication_config,
            # このカスタムコネクタのバージョン
            connector_version=CONNECTOR_VERSION,
            # サポートしている GA4 Data API のバージョン
            supported_api_versions=["GoogleAnalyticsDataAPIv1"],
            # カスタムコネクタのモードを設定
            # このカスタムコネクタは送信元にのみ指定できるため, ConnectorModes.SOURCE のみ設定
            connector_modes=[config.ConnectorModes.SOURCE],
            # コネクタの runtime の設定
            # 今回は GA4 のプロパティ ID を設定
            connector_runtime_setting=[property_id_setting],
        )


class ConnectorDemoRecordHandler(RecordHandler):
    def retrieve_data(
        self, request: requests.RetrieveDataRequest
    ) -> responses.RetrieveDataResponse:
        print("RecordHandler::retrieve_data")
        record_list = []
        return responses.RetrieveDataResponse(is_success=True, records=record_list)

    def write_data(
        self, request: requests.WriteDataRequest
    ) -> responses.WriteDataResponse:
        print("RecordHandler::write_data")
        write_record_results = []

        return responses.WriteDataResponse(
            is_success=True, write_record_results=write_record_results
        )

    def query_data(
        self, request: requests.QueryDataRequest
    ) -> responses.QueryDataResponse:
        print("RecordHandler::query_data")

        # コネクタの runtime に GA4 のプロパティ ID が設定されているか検証
        if PROPERTY_ID_KEY not in request.connector_context.connector_runtime_settings:
            error_message = f"{PROPERTY_ID_KEY} should be provided as runtime setting"
            LOGGER.error(f"QueryData request failed with entity: {error_message}")
            return responses.QueryDataResponse(
                is_success=False,
                error_details=ErrorDetails(
                    error_code=ErrorCode.InvalidArgument,
                    error_message=error_message,
                ),
            )

        # 有効なエンティティか検証（ここでは RunRealtimeReportEntity かどうか検証）
        entity_id = request.connector_context.entity_definition.entity.entity_identifier
        if entity_id != run_realtime_report_entity.entity_identifier:
            error_message = f"{entity_id} is not valid entity"
            LOGGER.error(f"QueryData request failed with entity: {error_message}")
            return responses.QueryDataResponse(
                is_success=False,
                error_details=ErrorDetails(
                    error_code=ErrorCode.InvalidArgument,
                    error_message=error_message,
                ),
            )

        # AppFlow の接続作成時に設定した認証情報を Secrets Manager から取得
        secrets = boto3.client("secretsmanager").get_secret_value(
            SecretId=request.connector_context.credentials.secret_arn
        )
        secret_string = json.loads(secrets["SecretString"])

        credentials = service_account.Credentials.from_service_account_info(
            {
                "private_key": secret_string[PRIVATE_KEY_KEY]
                .replace("\\s", " ")
                .replace("\\n", "\n"),
                "client_email": secret_string[CLIENT_EMAIL_KEY],
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )

        # GA4 Data API を叩く
        client = BetaAnalyticsDataClient(credentials=credentials)

        req = RunRealtimeReportRequest(
            property=f"properties/{request.connector_context.connector_runtime_settings[PROPERTY_ID_KEY]}",
            # 分析項目の指定
            dimensions=[
                Dimension(name="minutesAgo"),
                Dimension(name="country"),
                Dimension(name="city"),
            ],
            # 集計項目の指定
            metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers")],
            # 順序の指定
            order_bys=[
                OrderBy(
                    dimension=OrderBy.DimensionOrderBy(dimension_name="minutesAgo"),
                    desc=False,
                )
            ],
            # 取得する行数 (最大100,000)
            limit=100000,
        )

        res = client.run_realtime_report(req)

        # 秒を切り捨てた現在時刻を取得
        now_floor_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:00")
        now = datetime.datetime.strptime(now_floor_str, "%Y-%m-%d %H:%M:%S")

        # JSON オブジェクトの文字列の配列
        # RunRealtimeReport のエンティティでマッピングしたデータフィールドだけ送信される
        # record_list = [
        #     '{"DateTime": "2022-01-01 00:00:00", "RequestDateTime": "2022-01-01 00:00:00", "ScreenPageViews": 1}',
        #     '{"DateTime": "2022-01-01 00:01:00", "RequestDateTime": "2022-01-01 00:01:00", "ScreenPageViews": 2}',
        # ]
        record_list = []

        for row in res.rows:
            # イベント発生日時の絶対値をイベント発生日時の相対値 (dimensions.minutesAgo) から割り出す
            time = now - datetime.timedelta(minutes=int(row.dimension_values[0].value))

            record_list.append(
                json.dumps(
                    {
                        # レポートをリクエストした時間
                        # * DIMENSION が同じで METRIC が異なるデータは RequestDateTime が新しい方が正確なデータ
                        "RequestDateTime": now.strftime("%Y-%m-%d %H:%M:00"),
                        # [DIMENSION]: イベントの発生日時
                        "DateTime": time.strftime("%Y-%m-%d %H:%M:00"),
                        # [DIMENSION]: イベントを発生させた訪問者の国名
                        "Country": row.dimension_values[1].value,
                        # [DIMENSION]: イベントを発生させた訪問者の町名
                        "City": row.dimension_values[2].value,
                        # [METRIC]: dimensions に対応する訪問者がページを開いた回数
                        "ScreenPageViews": row.metric_values[0].value,
                        # [METRIC]: dimensions に対応するアクティブな訪問者の数
                        "ActiveUsers": row.metric_values[1].value,
                    }
                )
            )

        return responses.QueryDataResponse(is_success=True, records=record_list)


class ConnectorDemoMetadataHandler(MetadataHandler):
    # フロー作成時に呼び出され、スキーマ定義のリストを返す
    def list_entities(
        self, request: requests.ListEntitiesRequest
    ) -> responses.ListEntitiesResponse:
        print("MetadataHandler::list_entities")

        # フロー作成時のスキーマ定義
        # 今回は RunRealtimeReport API のみサポートしているため 1 つのエンティティを設定
        entity_list = [run_realtime_report_entity]

        return responses.ListEntitiesResponse(is_success=True, entities=entity_list)

    # フロー作成のデータフィールドマッピングで呼び出され、フィールドの定義を返す
    def describe_entity(
        self, request: requests.DescribeEntityRequest
    ) -> responses.DescribeEntityResponse:
        print("MetadataHandler::describe_entity")

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

        request_date_time_field = context.FieldDefinition(
            field_name="RequestDateTime",
            data_type=fields.FieldDataType.String,
            data_type_label="string",
            label="RequestDateTime",
            description="RequestDateTime",
            default_value="1970-01-01 00:00:00",
            is_primary_key=False,
            read_properties=fields.ReadOperationProperty(
                is_queryable=True,
                is_retrievable=True,
                is_nullable=False,
                is_timestamp_field_for_incremental_queries=False,
            ),
            write_properties=None,
        )

        country_field = context.FieldDefinition(
            field_name="Country",
            data_type=fields.FieldDataType.String,
            data_type_label="string",
            label="Country",
            description="Country",
            default_value="Country",
            is_primary_key=False,
            read_properties=fields.ReadOperationProperty(
                is_queryable=True,
                is_retrievable=True,
                is_nullable=False,
                is_timestamp_field_for_incremental_queries=False,
            ),
            write_properties=None,
        )

        city_field = context.FieldDefinition(
            field_name="City",
            data_type=fields.FieldDataType.String,
            data_type_label="string",
            label="City",
            description="City",
            default_value="City",
            is_primary_key=False,
            read_properties=fields.ReadOperationProperty(
                is_queryable=True,
                is_retrievable=True,
                is_nullable=False,
                is_timestamp_field_for_incremental_queries=False,
            ),
            write_properties=None,
        )

        screen_page_views_field = context.FieldDefinition(
            field_name="ScreenPageViews",
            data_type=fields.FieldDataType.Integer,
            data_type_label="int",
            label="ScreenPageViews",
            description="ScreenPageViews",
            default_value="0",
            is_primary_key=False,
            read_properties=fields.ReadOperationProperty(
                is_queryable=True,
                is_retrievable=True,
                is_nullable=False,
                is_timestamp_field_for_incremental_queries=False,
            ),
            write_properties=None,
        )

        active_users_field = context.FieldDefinition(
            field_name="ActiveUsers",
            data_type=fields.FieldDataType.Integer,
            data_type_label="int",
            label="ActiveUsers",
            description="ActiveUsers",
            default_value="0",
            is_primary_key=False,
            read_properties=fields.ReadOperationProperty(
                is_queryable=True,
                is_retrievable=True,
                is_nullable=False,
                is_timestamp_field_for_incremental_queries=False,
            ),
            write_properties=None,
        )

        # 今回は RunRealtimeReport API の DataTime, RequestDatetime, ScreenPageViews を fields に設定
        entity_definition = context.EntityDefinition(
            entity=run_realtime_report_entity,
            fields=[
                date_time_field,
                request_date_time_field,
                country_field,
                city_field,
                screen_page_views_field,
                active_users_field,
            ],
        )

        return responses.DescribeEntityResponse(
            is_success=True, entity_definition=entity_definition
        )


class ConnectorDemoLambdaHandler(BaseLambdaConnectorHandler):
    def __init__(self):
        super().__init__(
            ConnectorDemoMetadataHandler(),
            ConnectorDemoRecordHandler(),
            ConnectorDemoConfigurationHandler(),
        )


def handler(event, context):
    return ConnectorDemoLambdaHandler().lambda_handler(event, context)
