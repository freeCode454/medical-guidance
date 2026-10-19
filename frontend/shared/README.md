# 共用登录/注册界面

`AuthForm.vue` 是三端共用的登录/注册表单（患者端显示注册，医生/管理端只显示登录）。
各前端构建时使用各自 `src/components/AuthForm.vue` 的副本，避免 Vite 跨项目引用导致
`vue-tsc` 无法推导模板类型。

修改 `frontend/shared/AuthForm.vue` 后执行：

```powershell
powershell -ExecutionPolicy Bypass -File frontend/shared/sync-auth-form.ps1
```

脚本会把同一份表单同步到：

- `frontend/patient_h5/src/components/AuthForm.vue`
- `frontend/doctor_web/src/components/AuthForm.vue`
- `frontend/admin_web/src/components/AuthForm.vue`
