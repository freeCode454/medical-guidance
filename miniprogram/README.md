# MedicalGuidance 微信小程序（原生骨架）

患者端小程序：首页主诉 → 对话追问 → 分诊结果/预问诊病历。直接调用现有后端 REST API，不依赖 H5/web-view。

## 打开方式

1. 微信开发者工具 → 新建项目 → 小程序；
2. 目录选择本目录 `D:\AIProject\MedicalGuidance\miniprogram`；
3. AppID 填自己的小程序 AppID；没有就选“测试号”；
4. 后端服务选择“不使用云服务”；
5. 模板选“JavaScript - 基础模板”也可以，本项目已自带页面。

## 本地调试

1. 后端启动：

```powershell
cd backend
python -m app
```

2. 开发者工具右上角：**详情 → 本地设置**，勾选：

> 不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书

3. `config.js` 默认：

```js
BASE_URL: 'http://127.0.0.1:8000/api/v1'
```

模拟器可以直接访问本机后端。

## 真机调试

手机和电脑连同一 Wi-Fi，把 `config.js` 改成电脑局域网 IP：

```js
BASE_URL: 'http://192.168.20.24:8000/api/v1'
```

后端必须监听局域网：

```powershell
$env:HOST='0.0.0.0'
python -m app
```

同时放行 Windows 防火墙 8000 端口。真机调试仍然受微信域名校验影响，正式环境请使用 HTTPS 域名。

## 正式环境

- `config.js`：`https://api.example.com/api/v1`
- 微信公众平台 → 开发设置 → request 合法域名：`https://api.example.com`
- socket 合法域名：`wss://api.example.com`（当前页面用轮询，暂未建立 WS）
- 域名需备案、HTTPS、有效证书

## 当前实现范围

- 匿名设备身份：`utils/auth.js`，64 位随机 device_id，token 存 `wx.setStorageSync`；
- 首页：主诉、性别、年龄；
- 对话：REST 轮询消息，2.5 秒一次；
- 结果：分诊建议、风险提示、SOAP 病历摘要；
- 没有微信登录、订阅消息、语音输入、图片上传。

## 文件结构

```text
miniprogram/
├── app.js / app.json / app.wxss
├── config.js
├── utils/
│   ├── api.js      # wx.request 封装
│   └── auth.js     # 匿名设备 + token
└── pages/
    ├── home/       # 主诉输入
    ├── chat/       # 多轮对话
    └── result/     # 分诊结果 + 病历
```
