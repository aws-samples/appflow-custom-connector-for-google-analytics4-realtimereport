import { Stack, StackProps, Duration } from 'aws-cdk-lib'
import { Construct } from 'constructs'
import { aws_lambda as lambda, aws_iam as iam } from 'aws-cdk-lib'
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha'
import { PolicyStatement } from 'aws-cdk-lib/aws-iam'

export class AppFlowCustomConnectorDemoStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props)

    const func = new PythonFunction(this, 'CustomConnectorLambda', {
      runtime: lambda.Runtime.PYTHON_3_9,
      entry: '../lambda',
      timeout: Duration.seconds(29),
      environment: {}
    })

    func.addToRolePolicy(
      new PolicyStatement({
        actions: ['secretsmanager:GetSecretValue'],
        // arn 末尾の '-' の後ろに登録する AppFlow カスタムコネクタのコネクタラベルを付けて権限を絞る
        // `arn:aws:secretsmanager:${this.region}:${this.account}:secret:appflow!${this.account}-カスタムコネクタラベル-*`
        resources: [`arn:aws:secretsmanager:${this.region}:${this.account}:secret:appflow!${this.account}-*`]
      })
    )

    func.addPermission('CustomConnectorPermission', {
      principal: new iam.ServicePrincipal('appflow.amazonaws.com'),
      sourceArn: `arn:aws:appflow:${this.region}:${this.account}:*`
    })
  }
}
