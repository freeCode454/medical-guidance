<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useSessionStore } from '@/stores/session'
import MiniNav from '@/components/MiniNav.vue'
import MiniTabBar from '@/components/MiniTabBar.vue'
import {
  getProfile,
  listAppointments,
  listMedicalRecords,
  type AppointmentItem,
  type MedicalRecord,
  type PatientProfile,
} from '@/api/patient'

const router = useRouter()
const store = useSessionStore()
const loading = ref(true)
const error = ref('')
const profile = ref<PatientProfile | null>(null)
const appointments = ref<AppointmentItem[]>([])
const records = ref<MedicalRecord[]>([])

const initial = computed(() => (profile.value?.account || '患').slice(0, 1))

function fmtDate(value: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value.slice(0, 10)
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`
}

function fmtDateTime(value: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return `${fmtDate(value)} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    store.hydrateAuth()
    if (!store.patientId) {
      router.replace('/login')
      return
    }
    const [p, a, r] = await Promise.all([
      getProfile(),
      listAppointments(),
      listMedicalRecords(20),
    ])
    profile.value = p
    appointments.value = a.items
    records.value = r.items
  } catch (e) {
    error.value = (e as Error).message || '加载个人信息失败'
  } finally {
    loading.value = false
  }
}

function viewRecord(item: MedicalRecord) {
  store.sessionId = item.session_id
  router.push('/emr')
}

function logout() {
  store.logout()
  router.replace('/login')
}

onMounted(load)
</script>

<template>
  <main class="profile-page">
    <MiniNav title="我的" back>
      <template #right>
        <button class="logout" type="button" @click="logout">退出</button>
      </template>
    </MiniNav>

    <div v-if="loading" class="state">正在加载个人信息…</div>
    <div v-else-if="error" class="state state--error">
      <p>{{ error }}</p>
      <button class="ghost" type="button" @click="load">重试</button>
    </div>

    <template v-else-if="profile">
      <section class="profile-card">
        <div class="identity">
          <span class="avatar">{{ initial }}</span>
          <div class="identity__text">
            <b>{{ profile.account }}</b>
            <span>{{ profile.patient_no || profile.patient_id }}</span>
          </div>
        </div>
        <div class="facts">
          <div class="fact">
            <span>性别</span>
            <b>{{ profile.gender_label }}</b>
          </div>
          <div class="fact">
            <span>年龄</span>
            <b>{{ profile.age != null ? `${profile.age} 岁` : '未填写' }}</b>
          </div>
          <div class="fact">
            <span>建档时间</span>
            <b>{{ fmtDate(profile.created_at) }}</b>
          </div>
          <div class="fact">
            <span>最近登录</span>
            <b>{{ fmtDateTime(profile.last_login_time) }}</b>
          </div>
        </div>
      </section>

      <section class="stats">
        <div class="stat"><b>{{ profile.session_count }}</b><span>问诊</span></div>
        <div class="stat"><b>{{ profile.appointment_count }}</b><span>预约</span></div>
        <div class="stat"><b>{{ profile.record_count }}</b><span>病历</span></div>
      </section>

      <section class="block">
        <div class="block-head">
          <h2>挂号记录</h2>
          <span>{{ appointments.length }} 条</span>
        </div>
        <div v-if="!appointments.length" class="empty">还没有预约记录</div>
        <article v-for="item in appointments" :key="item.appointment_id" class="appointment">
          <div class="appointment__main">
            <b>{{ item.dept_name }} · {{ item.doctor_name }}</b>
            <span>{{ fmtDate(item.schedule_date) }} {{ item.time_slot }}</span>
            <em>{{ item.appointment_no }}</em>
          </div>
          <span class="badge" :class="{ 'badge--off': item.status !== 'BOOKED' }">
            {{ item.status_label }}
          </span>
        </article>
      </section>

      <section class="block">
        <div class="block-head">
          <h2>历史病历</h2>
          <span>{{ records.length }} 份</span>
        </div>
        <div v-if="!records.length" class="empty">还没有生成过预问诊病历</div>
        <article
          v-for="item in records"
          :key="item.record_id"
          class="record"
          role="button"
          tabindex="0"
          @click="viewRecord(item)"
          @keyup.enter="viewRecord(item)"
        >
          <div class="record__top">
            <b>{{ item.dept_name || '预问诊' }}</b>
            <span>{{ fmtDate(item.visit_time) }}</span>
          </div>
          <p class="record__complaint">{{ item.chief_complaint || '未记录主诉' }}</p>
          <p class="record__summary">{{ item.summary }}</p>
          <span class="record__link">查看病历 →</span>
        </article>
      </section>
    </template>

    <MiniTabBar />
  </main>
</template>

<style scoped>
.profile-page {
  width: 100%;
  max-width: 640px;
  margin: 0 auto;
  padding: 0 14px calc(76px + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

.profile-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
}

.icon-btn {
  width: 34px;
  height: 34px;
  flex: none;
  display: grid;
  place-items: center;
  border: 1px solid var(--c-line);
  border-radius: 10px;
  background: var(--c-surface);
  color: var(--c-primary);
  cursor: pointer;
}

.icon-btn svg {
  width: 17px;
  height: 17px;
}

.profile-head > div {
  flex: 1;
}

.eyebrow {
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--c-accent-text);
}

.profile-head h1 {
  margin-top: 2px;
  font-family: var(--font-display);
  font-size: 28px;
  color: var(--c-primary);
}

.logout {
  border: 1px solid var(--c-line);
  border-radius: 999px;
  padding: 7px 12px;
  background: var(--c-surface);
  color: var(--c-muted);
  font-size: 11.5px;
  cursor: pointer;
}

.state {
  padding: 70px 12px;
  text-align: center;
  color: var(--c-muted);
  font-size: 13px;
}

.state--error p {
  margin-bottom: 14px;
  color: var(--c-danger);
}

.ghost {
  border: 1px solid var(--c-line);
  border-radius: 999px;
  padding: 8px 18px;
  background: transparent;
  color: var(--c-primary);
}

.profile-card {
  margin-top: 12px;
  padding: 18px;
  border: 1px solid var(--c-line);
  border-radius: 18px;
  background: var(--c-surface);
  box-shadow: var(--shadow-sm);
}

.identity {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar {
  width: 46px;
  height: 46px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 14px;
  background: var(--c-primary);
  color: #f3dcc8;
  font-family: var(--font-display);
  font-size: 20px;
}

.identity__text {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.identity__text b {
  font-size: 17px;
  color: var(--c-ink);
}

.identity__text span {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--c-faint);
}

.facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 16px;
  margin-top: 18px;
}

.fact {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.fact span {
  font-size: 10.5px;
  color: var(--c-faint);
}

.fact b {
  font-size: 13px;
  font-weight: 500;
  color: var(--c-ink);
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 12px;
}

.stat {
  padding: 14px 10px;
  border-radius: 14px;
  background: var(--c-surface-soft);
  text-align: center;
}

.stat b {
  display: block;
  font-family: var(--font-display);
  font-size: 22px;
  color: var(--c-primary);
}

.stat span {
  font-size: 10.5px;
  color: var(--c-muted);
}

.block {
  margin-top: 22px;
}

.block-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 9px;
}

.block-head h2 {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  color: var(--c-ink);
}

.block-head span {
  font-size: 10.5px;
  color: var(--c-faint);
}

.empty {
  padding: 24px 12px;
  border-radius: 14px;
  background: var(--c-surface-soft);
  text-align: center;
  color: var(--c-faint);
  font-size: 12px;
}

.appointment {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--c-surface-soft);
  margin-bottom: 8px;
}

.appointment__main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.appointment__main b {
  font-size: 13px;
  color: var(--c-ink);
}

.appointment__main span {
  font-size: 11.5px;
  color: var(--c-muted);
}

.appointment__main em {
  font-style: normal;
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--c-faint);
}

.badge {
  flex: none;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 10.5px;
}

.badge--off {
  background: var(--c-surface-soft);
  color: var(--c-faint);
}

.record {
  padding: 13px 14px;
  border-radius: 14px;
  background: var(--c-surface-soft);
  margin-bottom: 8px;
  cursor: pointer;
}

.record__top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.record__top b {
  font-size: 13px;
  color: var(--c-ink);
}

.record__top span {
  font-size: 10.5px;
  color: var(--c-faint);
}

.record__complaint {
  margin-top: 5px;
  font-size: 12px;
  color: var(--c-ink-soft);
}

.record__summary {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.65;
  color: var(--c-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.record__link {
  display: inline-block;
  margin-top: 6px;
  font-size: 10.5px;
  color: var(--c-primary);
  text-decoration: none;
}
</style>
