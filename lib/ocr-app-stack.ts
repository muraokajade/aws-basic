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
    // Lightsail Instanceの設計情報を追加　比較対象
    new lightsail.CfnInstance(this, 'OcrDemoInstance', {
      instanceName: 'ocr-demo-instance',
      availabilityZone: 'ap-northeast-1a',
      blueprintId: 'ubuntu_22_04',
      bundleId: 'nano_3_0',

      // Instanceへ外部から接続するためのport設定
      networking: {
        ports: [
          {
            // SSH接続用
            fromPort: 22,
            toPort: 22,
            protocol: 'tcp',
          },
          {
            // HTTP 公開用
            fromPort: 80,
            toPort: 80,
            protocol: 'tcp',
          }
        ]
      }
    });
    // ============================
    // デプロイするDocker image
    // ============================

    const containerImage = new cdk.CfnParameter(
      this,
      'ContainerImage',
      {
        type: 'String',

        //CDK実験用の公開image
        //後で自作OCR image名を差し替える
        default: 'nginx:latest',

        description:
            'Lightsail Container Serviceで実行するDocker Image',
      }
    );

    // ============================
    // Containerが待ち受けるport
    // ============================
    const containerPort = new cdk.CfnParameter(
      this,
      'ContainerPort',
      {
        type: 'Number',
        // 実験80
        // OCR 8000など
        default: 80,
        description: 'Container内部でアプリが待ち受けるport'
      }
    );

    // ============================
    // Health Check path
    // ============================
    const healthCheckPath = new cdk.CfnParameter(
      this,
      'HealthCheckPath',
      {
        type: 'String',
        // 実験は /
        // OCRでは /health
        default: '/',
        description: 'ヘルスチェック'
      }
    )

    // ============================
    // Lightsail: Container Service
    // ============================
    const containerService =  new lightsail.CfnContainer(
      this,
      'OcrDemoContainerService',
      {
      
      // AWS上のContainer Service名
      serviceName: 'ocr-demo-container-service',
      // Container Serviceの実行サイズ
      power: 'nano',
      // 実行するノード数
      scale: 1,

      // Containerの配置・起動設定
      containerServiceDeployment: {
        containers: [
          {
            containerName: 'ocr-api',
            //実行するDocker image
            image: containerImage.valueAsString,

            // Container内部に渡す環境変数
            environment: [  // containerを起動するときAPP_ENV=demoを渡す。
              {
                variable: 'OPENAI_VISION_MODEL',
                value: 'gpt-4.1-mini'
              },
            ],
            ports: [
              {
                port: containerPort.valueAsString,
                protocol: 'HTTP',
              }
            ],
          },       
        ],
        // インターネットアクセス入口
        publicEndpoint: {
          // アクセスを転送するContainer
          containerName:'ocr-api', //名前で指定

          // アクセスを転送するport
          containerPort: containerPort.valueAsNumber,

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

    // ============================
    // CloudFormation実行後に表示する情報
    // ============================
    new cdk.CfnOutput(this, 'ContainerServiceName', {
      description: 'Container Serviceの公開URL',
      value: containerService.serviceName,
    });

    new cdk.CfnOutput(this, 'ContainerServiceUrl', {
      description: 'Coontainer Serviceの公開Url',
      value: containerService.attrUrl,
    })

  }
}
