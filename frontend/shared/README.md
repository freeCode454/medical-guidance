# 单入口登录/注册

全项目只有 **一个** 登录/注册页面：

```text
http://127.0.0.1:5173/login
```

账号密码由后端 `/api/v1/auth/login` 判断角色：

| 角色 | 跳转 |
|---|---|
| `PATIENT` | 患者端 `/` |
| `DOCTOR` | 医生端 `5174/auth-callback` |
| `ORG_ADMIN` / `KB_ADMIN` | 管理后台 `5175/auth-callback` |

医生端和管理后台不再有登录页，未登录时直接跳 `5173/login`。
登录成功后的令牌通过 URL fragment 交给目标端，目标端写入自己的 localStorage 后进入工作台。

`AuthForm.vue` 是唯一表单源文件；修改后同步到患者端：

```powershell
powershell -ExecutionPolicy Bypass -File frontend/shared/sync-auth-form.ps1
```
