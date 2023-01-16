import * as cdk from 'aws-cdk-lib'
import { AppFlowCustomConnectorDemoStack } from '../stacks/appflow-customconnector-demo-stack'

const app = new cdk.App()

new AppFlowCustomConnectorDemoStack(app, 'AppFlowCustomConnectorDemoStack', {
  env: {
    region: 'us-east-1'
  }
})
