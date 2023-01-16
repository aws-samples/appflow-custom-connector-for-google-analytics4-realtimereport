# デプロイ手順

本サンプルをデプロイする手順を説明します。

## CDK スタックのデプロイ

### 事前準備

- Docker
- [AWS CLI のインストール](https://docs.aws.amazon.com/ja_jp/cli/latest/userguide/install-cliv2.html) および [認証情報の設定](https://docs.aws.amazon.com/ja_jp/cli/latest/userguide/cli-configure-files.html)
- [Node.js LTS](https://nodejs.org/en/) のインストール

### AWS Cloud9 環境の簡易構築

Cloud9 からのデプロイを想定し、その環境構築を行います。ご自身の環境で CDK をデプロイできる場合はこの手順は不要です。

1. AWS CloudShell を起動して下記コマンドを実行

```sh
git clone https://github.com/aws-samples/cloud9-setup-for-prototyping
cd cloud9-setup-for-prototyping

## Cloud9 環境 "cloud9-for-prototyping" を構築
./bin/bootstrap
```

2. AWS Cloud9 に移動して `cloud9-for-prototyping` を起動
3. `File` から `Upload Local Files` を押下
4. サンプルのソース zip ファイルを `Drag & drop file here ` に投下
5. `unzip` コマンドを実行してディレクトリを移動

```sh
Admin:~/environment $ unzip your_prototype.zip
Admin:~/environment $ cd your_prototype/
```

**NOTE:** 上記方法で構築した Cloud9 環境の場合、事前準備に記載した Docker, AWS CLI, Node.js は導入済みのため不要です

### 1. CDK のセットアップ

CDK のセットアップをします。
この作業は、利用している AWS アカウントにおいて、デプロイ先となるリージョンで初めて CDK を利用する際に必要になります。以下のコマンドを実行して下さい。

```bash
npx cdk bootstrap
```

### 2. CDK スタックのデプロイ

本サンプルではカスタムコネクタ用の Lambda を CDK でデプロイするので、当該ディレクトリに移動してスタックをデプロイします。

```bash
cd provisioning
npx cdk deploy --all
```

**NOTE:** 本サンプルを誤って本番環境にデプロイしないよう十分にご注意ください

次に[AppFlow カスタムコネクタの設定](#appflow-カスタムコネクタの設定)に進んでください。

### Clean up

デプロイされた AWS リソースが不要になった場合、下記のコマンドですべて削除することができます。

```bash
npx cdk destroy --all
```

## AppFlow カスタムコネクタの設定

### 1. Lambda 関数のデプロイ

カスタムコネクタとして使用する Lambda 関数をデプロイする。本サンプルでは上記 [CDK スタックのデプロイ](#cdk-スタックのデプロイ)で完了済みです。

### 2. カスタムコネクタの登録

デプロイした Lambda 関数を AppFlow コンソールから「カスタムコネクタ」として登録します。

1. AppFlow コンソールのサイドバーの「コネクタ」を選択する。
2. 「新しいコネクタを登録」をクリックし、Lambda 関数を選択し、任意のコネクタラベルを指定して登録する。

![コネクタ](/docs/img/AppFlow-Connector.gif)

### 3. 接続の作成

作成したカスタムコネクタの「接続」を作成します。

1. AppFlow コンソールのサイドバーの「接続」を選択する。
2. 登録したカスタムコネクタをコネクタとして選択し、「接続を作成」をクリックし、認証情報（Private Key, Client Email, GA4 Property ID など）を入力する。ここでは、Google Cloud のサービスアカウントを認証情報として使用するため、公式ドキュメントなどを参考に鍵情報を事前に取得しておく。

![接続](/docs/img/AppFlow-Connection.gif)

### 4. フローの作成

登録したコネクタ、接続を用いて「フロー」を作成し、送信するフィールドなどを指定します。

1. AppFlow コンソールのサイドバーの「フロー」を選択する。
2. 「フローを作成」をクリックし、「手順 1 フローの詳細を指定」でフロー名など設定する。
3. 「手順 2 フローを設定」で、送信元に登録したカスタムコネクタとその接続を指定し、送信先として任意のサービスを指定する。また、フロートリガーでスケジュールを設定できる。
4. 「手順 3 データフィールドマッピング」で送信したいフィールドをマッピングします。
5. 「手順 4 フィルターを追加する」でのフィルターの設定には対応していません。必要な場合は、フィルター機能の追加実装が必要です。

![フロー](/docs/img/AppFlow-Flow.gif)

次に[動作確認手順](/docs/OPERATION.md)を参照しながら検証に進んでください。

# システムツリー

下記は本システムを構成する重要なファイルの抜粋です。

```
├── lambda (Backend, Lambda)
│   ├── custom_connector_sdk
│   └── index.py
└── provisioning (Infrastructure as Code, CDK)
    ├── bin
    │   └── provisioning.ts
    ├── cdk.json
    └── stacks
        └── appflow-customconnector-demo-stack.ts
```
