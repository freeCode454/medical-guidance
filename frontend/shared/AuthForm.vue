<script lang="ts">
import { defineComponent, type PropType } from 'vue'

type Portal = 'AUTO' | 'PATIENT' | 'DOCTOR' | 'ADMIN'
type Mode = 'login' | 'register'

interface AuthPayload {
  mode: Mode
  portal: Portal
  account: string
  password: string
  name: string
}

export default defineComponent({
  name: 'AuthForm',
  props: {
    portal: { type: String as PropType<Portal>, default: 'AUTO' },
    allowRegister: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    error: { type: String, default: '' },
    demoAccount: { type: String, default: '' },
    demoPassword: { type: String, default: '' },
  },
  emits: {
    submit: (_payload: AuthPayload) => true,
  },
  data() {
    return {
      mode: 'login' as Mode,
      account: '',
      name: '',
      password: '',
      confirm: '',
      showPassword: false,
      agree: false,
      localError: '',
    }
  },
  computed: {
    portalLabel(): string {
      if (this.portal === 'PATIENT') return '患者'
      if (this.portal === 'DOCTOR') return '医生'
      if (this.portal === 'ADMIN') return '管理员'
      return '统一'
    },
    heading(): string {
      if (this.mode === 'register') return '注册患者账号'
      return '登录'
    },
    subheading(): string {
      if (this.portal === 'AUTO') {
        return this.mode === 'login'
          ? '输入账号和密码，系统自动识别患者 / 医生 / 管理员并进入对应页面'
          : '注册患者账号；医生和管理员账号由机构开通，不能自助注册'
      }
      if (this.portal === 'PATIENT') {
        return this.mode === 'login'
          ? '登录后查看问诊记录、既往病历与预约挂号'
          : '创建患者账号，注册后自动登录'
      }
      if (this.portal === 'DOCTOR') return '使用院内医生账号登录工作台'
      return '使用机构管理员或知识库管理员账号登录'
    },
  },
  watch: {
    error(value: string) {
      if (value) this.localError = value
    },
  },
  methods: {
    switchMode(next: Mode) {
      this.mode = next
      this.localError = ''
      this.confirm = ''
    },
    submit() {
      this.localError = ''
      const acc = this.account.trim()
      if (acc.length < 4) {
        this.localError = '账号至少 4 位'
        return
      }
      if (this.password.length < 8) {
        this.localError = '密码至少 8 位'
        return
      }
      if (!/^[A-Za-z0-9_]+$/.test(acc) && this.mode === 'register') {
        this.localError = '账号仅支持字母、数字和下划线'
        return
      }
      if (this.mode === 'register') {
        if (this.name.trim().length < 2) {
          this.localError = '请输入至少 2 个字的患者姓名'
          return
        }
        if (this.password !== this.confirm) {
          this.localError = '两次输入的密码不一致'
          return
        }
        if (!this.agree) {
          this.localError = '请先阅读并同意服务条款与隐私政策'
          return
        }
      }
      this.$emit('submit', {
        mode: this.mode,
        portal: this.portal,
        account: acc,
        password: this.password,
        name: this.name.trim(),
      })
    },
    fillDemo() {
      if (!this.demoAccount) return
      this.account = this.demoAccount
      this.password = this.demoPassword
    },
  },
})
</script>

<template>
  <div class="auth-form">
    <div class="auth-eyebrow">
      <span class="auth-mark" aria-hidden="true">诊</span>
      <span>{{ portalLabel }}入口</span>
    </div>

    <div v-if="allowRegister" class="auth-tabs" role="tablist" aria-label="登录或注册">
      <button
        type="button"
        role="tab"
        :aria-selected="mode === 'login'"
        :class="{ active: mode === 'login' }"
        @click="switchMode('login')"
      >
        登录
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="mode === 'register'"
        :class="{ active: mode === 'register' }"
        @click="switchMode('register')"
      >
        注册
      </button>
    </div>

    <h2>{{ heading }}{{ portalLabel === '患者' ? '患者账号' : '' }}</h2>
    <p class="auth-sub">{{ subheading }}</p>

    <div v-if="localError" class="auth-error" role="alert">{{ localError }}</div>

    <form novalidate @submit.prevent="submit">
      <label v-if="mode === 'register'" class="auth-field">
        <span>姓名</span>
        <input
          v-model="name"
          type="text"
          autocomplete="name"
          placeholder="请输入患者姓名"
          maxlength="32"
        />
      </label>

      <label class="auth-field">
        <span>账号</span>
        <input
          v-model="account"
          type="text"
          autocomplete="username"
          placeholder="请输入登录账号"
          inputmode="text"
        />
      </label>

      <label class="auth-field">
        <span>密码</span>
        <div class="password-wrap">
          <input
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            :autocomplete="mode === 'register' ? 'new-password' : 'current-password'"
            placeholder="至少 8 位"
          />
          <button
            type="button"
            class="eye"
            :aria-label="showPassword ? '隐藏密码' : '显示密码'"
            @click="showPassword = !showPassword"
          >
            {{ showPassword ? '隐藏' : '显示' }}
          </button>
        </div>
      </label>

      <label v-if="mode === 'register'" class="auth-field">
        <span>确认密码</span>
        <input v-model="confirm" type="password" autocomplete="new-password" placeholder="再次输入密码" />
      </label>

      <label v-if="mode === 'register'" class="auth-agree">
        <input v-model="agree" type="checkbox" />
        <span>我已阅读并同意服务条款与隐私政策，授权系统在本次问诊中使用我的健康信息</span>
      </label>

      <button class="auth-submit" type="submit" :disabled="loading">
        {{ loading ? '处理中…' : mode === 'login' ? '登录' : '注册并登录' }}
      </button>
    </form>

    <button
      v-if="mode === 'login' && demoAccount"
      type="button"
      class="auth-demo"
      @click="fillDemo"
    >
      演示账号 {{ demoAccount }} / {{ demoPassword }} · 点此填入
    </button>

    <p v-if="!allowRegister" class="auth-hint">院内账号由机构管理员开通，不支持自助注册。</p>
    <p v-else class="auth-hint">注册只创建患者账号；医生与管理员请直接使用已开通账号登录。</p>
  </div>
</template>

<style scoped>
.auth-form {
  width: 100%;
  max-width: 370px;
  margin: 0 auto;
  color: var(--c-ink, #22302e);
  font-family: var(--font-body, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif);
}

.auth-eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--c-accent-text, #a55726);
}

.auth-mark {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--c-primary, #17504e);
  color: #f3dcc8;
  font-family: var(--font-display, serif);
  font-size: 13px;
}

.auth-tabs {
  display: flex;
  gap: 4px;
  margin: 22px 0 4px;
  padding: 3px;
  border-radius: 10px;
  background: var(--c-surface-soft, #faf6ee);
  border: 1px solid var(--c-line, #e7dfd2);
}

.auth-tabs button {
  flex: 1;
  border: 0;
  border-radius: 8px;
  padding: 8px 0;
  background: transparent;
  color: var(--c-muted, #66716b);
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
}

.auth-tabs button.active {
  background: var(--c-surface, #fffdfa);
  color: var(--c-primary, #17504e);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(34, 48, 46, 0.08);
}

h2 {
  margin: 24px 0 0;
  font-family: var(--font-display, 'Songti SC', serif);
  font-size: 28px;
  color: var(--c-primary, #17504e);
  line-height: 1.3;
}

.auth-sub {
  margin: 7px 0 0;
  color: var(--c-muted, #66716b);
  font-size: 12.5px;
  line-height: 1.65;
}

.auth-error {
  margin-top: 16px;
  padding: 9px 12px;
  border: 1px solid rgba(180, 67, 47, 0.24);
  border-radius: 9px;
  background: rgba(180, 67, 47, 0.07);
  color: #b4432f;
  font-size: 12.5px;
}

.auth-field {
  display: block;
  margin-top: 17px;
}

.auth-field > span {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--c-muted, #66716b);
}

.auth-field input {
  width: 100%;
  height: 45px;
  box-sizing: border-box;
  padding: 0 13px;
  border: 1px solid var(--c-line, #e7dfd2);
  border-radius: 9px;
  background: var(--c-surface, #fffdfa);
  color: var(--c-ink, #22302e);
  font-family: inherit;
  font-size: 14px;
  outline: none;
}

.auth-field input:focus {
  border-color: var(--c-primary, #17504e);
  box-shadow: 0 0 0 3px rgba(23, 80, 78, 0.08);
}

.password-wrap {
  position: relative;
}

.password-wrap input {
  padding-right: 52px;
}

.eye {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  color: var(--c-muted, #66716b);
  font-size: 11px;
  padding: 6px;
  cursor: pointer;
}

.auth-agree {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-top: 15px;
  font-size: 11px;
  line-height: 1.65;
  color: var(--c-muted, #66716b);
}

.auth-agree input {
  margin-top: 2px;
  accent-color: var(--c-primary, #17504e);
}

.auth-submit {
  width: 100%;
  height: 47px;
  margin-top: 20px;
  border: 0;
  border-radius: 10px;
  background: var(--c-primary, #17504e);
  color: #fff;
  font-family: inherit;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
}

.auth-submit:disabled {
  opacity: 0.65;
  cursor: wait;
}

.auth-demo {
  width: 100%;
  margin-top: 12px;
  padding: 8px 10px;
  border: 1px dashed var(--c-line, #e7dfd2);
  border-radius: 9px;
  background: transparent;
  color: var(--c-muted, #66716b);
  font-family: inherit;
  font-size: 11.5px;
  cursor: pointer;
}

.auth-hint {
  margin: 16px 0 0;
  text-align: center;
  color: var(--c-faint, #8a938d);
  font-size: 11px;
  line-height: 1.65;
}
</style>
