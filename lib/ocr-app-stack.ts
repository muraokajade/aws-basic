import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs';
import * as lightsail from 'aws-cdk-lib/aws-lightsail';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

export class OcrAppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

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
            path: healthCheckPath.valueAsString,
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
    // CloudFormationの実行結果として表示したい情報を登録する。
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
