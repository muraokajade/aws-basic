# CDK ≒ CloudFormation 対応解説

CDKで書いたTypeScriptコードは `cdk synth` すると CloudFormation テンプレート（JSON）に変換される。
以下では「CDKのこの記述 ≒ CloudFormationのこの部分」を1対1で対応づける。

---

## 全体構造の対応

```text
CDK (TypeScript)                    ≒  CloudFormation (JSON)
──────────────────────────────────────────────────────────────
new cdk.CfnParameter(...)           ≒  "Parameters": { ... }
new lightsail.CfnContainer(...)     ≒  "Resources": { "Type": "AWS::Lightsail::Container", ... }
new cdk.CfnOutput(...)              ≒  "Outputs": { ... }
（明示的な記述なし）                  ≒  "Conditions", "Rules", "CDKMetadata"（自動生成）
```

---

## 1. Parameters（パラメータ）

### CDK

```typescript
const containerImage = new cdk.CfnParameter(this, "ContainerImage", {
  type: "String",
  default: "nginx:latest",
  description: "Lightsail Container Serviceで実行するDocker Image",
});
```

### ≒ CloudFormation

```json
"Parameters": {
  "ContainerImage": {
    "Type": "String",
    "Default": "nginx:latest",
    "Description": "Lightsail Container Serviceで実行するDocker Image"
  }
}
```

### 対応ルール

```text
第2引数 "ContainerImage"     ≒  パラメータのキー名（論理ID）
type: "String"               ≒  "Type": "String"
default: "nginx:latest"      ≒  "Default": "nginx:latest"
description: "..."           ≒  "Description": "..."
```

他の2つも同じパターン:

```text
new CfnParameter(this, "ContainerPort", { type: "Number", default: 80, ... })
≒ "ContainerPort": { "Type": "Number", "Default": 80, ... }

new CfnParameter(this, "HealthCheckPath", { type: "String", default: "/", ... })
≒ "HealthCheckPath": { "Type": "String", "Default": "/", ... }
```

---

## 2. パラメータの「参照」

CDKで定義したパラメータを別の場所で使うとき、CloudFormationでは `Ref` に変換される。

```text
CDK                                  ≒  CloudFormation
──────────────────────────────────────────────────────────────
containerImage.valueAsString         ≒  { "Ref": "ContainerImage" }
containerPort.valueAsString          ≒  { "Ref": "ContainerPort" }
containerPort.valueAsNumber          ≒  { "Ref": "ContainerPort" }
healthCheckPath.valueAsString        ≒  { "Ref": "HealthCheckPath" }
```

`valueAsString` も `valueAsNumber` も、CloudFormation上では同じ `{ "Ref": "..." }` になる。
違いはCDK側のTypeScript型チェック用。

---

## 3. Resources（リソース）

### CDK

```typescript
const containerService = new lightsail.CfnContainer(
  this,
  "OcrDemoContainerService",    // ← 論理ID
  {
    serviceName: "ocr-demo-container-service",
    power: "nano",
    scale: 1,
    containerServiceDeployment: { ... }
  }
);
```

### ≒ CloudFormation

```json
"Resources": {
  "OcrDemoContainerService": {
    "Type": "AWS::Lightsail::Container",
    "Properties": {
      "ServiceName": "ocr-demo-container-service",
      "Power": "nano",
      "Scale": 1,
      "ContainerServiceDeployment": { ... }
    }
  }
}
```

### 対応ルール

```text
lightsail.CfnContainer              ≒  "Type": "AWS::Lightsail::Container"
第2引数 "OcrDemoContainerService"   ≒  リソースのキー名（論理ID）
{ serviceName: "..." }              ≒  "Properties": { "ServiceName": "..." }
```

### プロパティ名の変換（camelCase → PascalCase）

```text
CDK (camelCase)                      ≒  CloudFormation (PascalCase)
──────────────────────────────────────────────────────────────
serviceName                          ≒  ServiceName
power                                ≒  Power
scale                                ≒  Scale
containerServiceDeployment           ≒  ContainerServiceDeployment
containerName                        ≒  ContainerName
healthCheckConfig                    ≒  HealthCheckConfig
intervalSeconds                      ≒  IntervalSeconds
successCodes                         ≒  SuccessCodes
```

CDKが自動でPascalCaseに変換してくれる。

---

## 4. Deployment部分（ネスト構造）

### CDK

```typescript
containerServiceDeployment: {
  containers: [{
    containerName: "ocr-api",
    image: containerImage.valueAsString,      // ← Ref に変換
    environment: [{
      variable: "OPENAI_VISION_MODEL",
      value: "gpt-4.1-mini",
    }],
    ports: [{
      port: containerPort.valueAsString,      // ← Ref に変換
      protocol: "HTTP",
    }],
  }],
  publicEndpoint: {
    containerName: "ocr-api",
    containerPort: containerPort.valueAsNumber,  // ← Ref に変換
    healthCheckConfig: {
      path: healthCheckPath.valueAsString,       // ← Ref に変換
      intervalSeconds: 10,
      timeoutSeconds: 2,
      healthyThreshold: 2,
      unhealthyThreshold: 2,
      successCodes: "200-399",
    }
  }
}
```

### ≒ CloudFormation

```json
"ContainerServiceDeployment": {
  "Containers": [{
    "ContainerName": "ocr-api",
    "Image": { "Ref": "ContainerImage" },
    "Environment": [{
      "Variable": "OPENAI_VISION_MODEL",
      "Value": "gpt-4.1-mini"
    }],
    "Ports": [{
      "Port": { "Ref": "ContainerPort" },
      "Protocol": "HTTP"
    }]
  }],
  "PublicEndpoint": {
    "ContainerName": "ocr-api",
    "ContainerPort": { "Ref": "ContainerPort" },
    "HealthCheckConfig": {
      "Path": { "Ref": "HealthCheckPath" },
      "IntervalSeconds": 10,
      "TimeoutSeconds": 2,
      "HealthyThreshold": 2,
      "UnhealthyThreshold": 2,
      "SuccessCodes": "200-399"
    }
  }
}
```

### まとめ

```text
固定文字列 "ocr-api"                 ≒  そのまま "ocr-api"
固定数値 10                          ≒  そのまま 10
param.valueAsString                  ≒  { "Ref": "パラメータ名" }
ネスト構造                           ≒  同じ構造でキー名がPascalCaseになるだけ
```

---

## 5. Outputs（出力）

### CDK

```typescript
new cdk.CfnOutput(this, "ContainerServiceName", {
  description: "Container Serviceの公開URL",
  value: containerService.serviceName,
});

new cdk.CfnOutput(this, "ContainerServiceUrl", {
  description: "Coontainer Serviceの公開Url",
  value: containerService.attrUrl,
});
```

### ≒ CloudFormation

```json
"Outputs": {
  "ContainerServiceName": {
    "Description": "Container Serviceの公開URL",
    "Value": "ocr-demo-container-service"
  },
  "ContainerServiceUrl": {
    "Description": "Coontainer Serviceの公開Url",
    "Value": { "Fn::GetAtt": ["OcrDemoContainerService", "Url"] }
  }
}
```

### 対応ルール

```text
containerService.serviceName         ≒  "ocr-demo-container-service"（固定文字列としてインライン展開）
containerService.attrUrl             ≒  { "Fn::GetAtt": ["OcrDemoContainerService", "Url"] }
```

**なぜ違うのか:**

- `.serviceName` → CDKがビルド時に解決できる（自分で設定した固定値だから）→ 文字列として埋め込み
- `.attrUrl` → デプロイ後にAWSが生成する値（事前に分からない）→ `Fn::GetAtt` で実行時に取得

```text
CDK attr〇〇 プロパティ               ≒  { "Fn::GetAtt": ["論理ID", "〇〇"] }
```

---

## 6. CDKが自動生成する部分

CDKコードに**書いていない**のに、CloudFormationテンプレートに出現するもの:

| CloudFormation側 | 内容 | なぜ存在するか |
|:---|:---|:---|
| `"BootstrapVersion"` (Parameters) | CDK Bootstrap バージョン確認用 | CDKデプロイ基盤のバージョン管理 |
| `"CDKMetadata"` (Resources) | CDK利用状況の匿名統計 | AWS側のCDK改善用データ |
| `"CDKMetadataAvailable"` (Conditions) | リージョン判定 | メタデータ送信可能リージョンかの判定 |
| `"CheckBootstrapVersion"` (Rules) | Bootstrap v6以上を強制 | 古いBootstrapでのデプロイを防止 |

**これらは開発者が意識する必要はない。CDKフレームワークが勝手に追加する。**

---

## 7. 全体まとめ図

```text
┌─────────────────────────────────┐
│  CDK TypeScript                  │
├─────────────────────────────────┤
│                                  │
│  CfnParameter("ContainerImage")  │──────→  Parameters.ContainerImage
│  CfnParameter("ContainerPort")   │──────→  Parameters.ContainerPort
│  CfnParameter("HealthCheckPath") │──────→  Parameters.HealthCheckPath
│                                  │
│  CfnContainer("OcrDemo...")      │──────→  Resources.OcrDemoContainerService
│    ├ serviceName: "..."          │           ├ ServiceName: "..."
│    ├ image: param.valueAsString  │           ├ Image: { Ref: "..." }
│    └ attrUrl                     │           └ Fn::GetAtt で参照可能
│                                  │
│  CfnOutput("ContainerService..") │──────→  Outputs.ContainerServiceName
│  CfnOutput("ContainerService..") │──────→  Outputs.ContainerServiceUrl
│                                  │
│  （記述なし）                     │──────→  Conditions, Rules, CDKMetadata
│                                  │
└─────────────────────────────────┘
           cdk synth
              ↓
┌─────────────────────────────────┐
│  CloudFormation JSON             │
│  (cdk.out/OcrAppStack.template)  │
└─────────────────────────────────┘
```

---

## 8. 覚えておくべき変換パターン（3つだけ）

| CDKで書くこと | CloudFormationで出てくるもの | 意味 |
|:---|:---|:---|
| `param.valueAsString` | `{ "Ref": "パラメータ名" }` | デプロイ時にユーザーが指定する値を参照 |
| `resource.attrXxx` | `{ "Fn::GetAtt": ["論理ID", "Xxx"] }` | デプロイ後にAWSが生成する値を参照 |
| `プロパティ: "固定値"` | `"プロパティ(PascalCase)": "固定値"` | そのまま埋め込み（キー名だけ大文字に変わる） |

これだけ覚えれば、CDKとCloudFormationの対応関係は読める。
