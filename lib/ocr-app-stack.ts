import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs';
import * as lightsail from 'aws-cdk-lib/aws-lightsail';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

export class OcrAppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    //このStackをCDKの仕組みの中に登録します


    // new lightsail.CfnInstance(...) オブジェクト、AWS上の本物のInstanceではない
    //     ↓
    // CDKコード上に
    // Lightsail Instanceの設計情報を追加
    new lightsail.CfnInstance(this, 'OcrDemoInstance', {
      instanceName: 'ocr-demo-instance',
      availabilityZone: 'ap-northeast-1a',
      blueprintId: 'ubuntu_22_04',
      bundleId: 'nano_3_0',
    });
    // Container Service方式
    // Lightsail上に
    // Container Serviceという実行基盤を1つ定義
    new lightsail.CfnContainer(this, 'OcrDemoContainerService',{
      serviceName: 'ocr-demo-container-service',
      power: 'nano',
      scale: 1,

      containerServiceDeployment: {
        containers: [
          {
            containerName: 'demo-web',
            image: 'nginx:latest',

            environment: [  // containerを起動するときAPP_ENV=demoを渡す。
              {
                variable: 'APP_ENV',
                value: 'demo'
              }
            ],
            ports: [
              {
                port: '80',
                protocol: 'HTTP',
              }
            ],
          },       
        ],
        publicEndpoint: {
          containerName:'demo-web', //名前で指定
          containerPort: 80,

          healthCheckConfig: {
            path: '/',
            intervalSeconds: 10,
            timeoutSeconds: 2,
            healthyThreshold: 2,
            unhealthyThreshold: 2,
            successCodes: '200-399',
          }
        }
      }
    });

  }
}
