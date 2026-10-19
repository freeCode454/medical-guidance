<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { useSessionStore } from '@/stores/session'
import {
  bookAppointment,
  cancelAppointment,
  getAppointmentSlots,
  listAppointments,
  type AppointmentDay,
  type AppointmentDoctor,
  type AppointmentItem,
  type AppointmentSlot,
} from '@/api/patient'
import MiniNav from '@/components/MiniNav.vue'

const route = useRoute()
const store = useSessionStore()

const deptCode = String(route.query.dept || '')
const sessionId = String(route.query.sessionId || store.sessionId || '')

const loading = ref(true)
const error = ref('')
const slots = ref<AppointmentDay[]>([])
const deptName = ref('')
const activeDate = ref(0)
const appointments = ref<AppointmentItem[]>([])
const selected = ref<{ doctor: AppointmentDoctor; slot: AppointmentSlot } | null>(null)
const booking = ref(false)

const activeDay = computed(() => slots.value[activeDate.value] ?? null)
const experts = computed(
  () => activeDay.value?.doctors.filter((d) => d.is_expert) ?? [],
)
const others = computed(
  () => activeDay.value?.doctors.filter((d) => !d.is_expert) ?? [],
)

function dateLabel(value: string) {
  const [, m, d] = value.split('-')
  return `${Number(m)}月${Number(d)}日`
}

function initial(name: string) {
  return name.slice(0, 1)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    if (!store.patientId) await store.ensureAuth()
    const [data, mine] = await Promise.all([
      getAppointmentSlots(deptCode),
      listAppointments(),
    ])
    deptName.value = data.dept_name
    slots.value = data.dates
    appointments.value = mine.items
    activeDate.value = 0
  } catch (e) {
    error.value = (e as Error).message || '号源加载失败'
  } finally {
    loading.value = false
  }
}

function selectSlot(doctor: AppointmentDoctor, slot: AppointmentSlot) {
  if (!slot.available) return
  selected.value = { doctor, slot }
}

function isSelected(doctor: AppointmentDoctor, slot: AppointmentSlot) {
  return (
    selected.value?.doctor.doctor_id === doctor.doctor_id &&
    selected.value?.slot.time_slot === slot.time_slot
  )
}

async function confirm() {
  if (!selected.value || !activeDay.value) return
  booking.value = true
  try {
    const result = await bookAppointment({
      session_id: sessionId || null,
      dept_code: deptCode,
      doctor_id: selected.value.doctor.doctor_id,
      schedule_date: activeDay.value.date,
      time_slot: selected.value.slot.time_slot,
    })
    showToast(`预约成功：${result.schedule_date} ${result.time_slot}`)
    selected.value = null
    await load()
  } catch (e) {
    showToast((e as Error).message || '预约失败')
  } finally {
    booking.value = false
  }
}

async function cancel(item: AppointmentItem) {
  try {
    await showConfirmDialog({
      title: '取消预约',
      message: `取消 ${item.schedule_date} ${item.time_slot} 与 ${item.doctor_name} 的预约？`,
      confirmButtonText: '确认取消',
      cancelButtonText: '保留',
    })
  } catch {
    return
  }
  try {
    await cancelAppointment(item.appointment_id)
    showToast('已取消预约')
    await load()
  } catch (e) {
    showToast((e as Error).message || '取消失败')
  }
}

onMounted(load)
</script>

<template>
  <main class="appointment-page">
    <MiniNav :title="deptName || '预约挂号'" back />

    <div v-if="loading" class="state">正在加载全部号源…</div>
    <div v-else-if="error" class="state state--error">
      <p>{{ error }}</p>
      <button class="ghost" type="button" @click="load">重试</button>
    </div>

    <template v-else>
      <section class="date-strip" aria-label="选择日期">
        <button
          v-for="(day, index) in slots"
          :key="day.date"
          type="button"
          class="date"
          :class="{ active: index === activeDate }"
          @click="activeDate = index; selected = null"
        >
          <em>{{ day.weekday }}</em>
          <b>{{ dateLabel(day.date) }}</b>
        </button>
      </section>

      <section v-if="experts.length" class="doctor-group">
        <h2 class="group-title">专家门诊</h2>
        <article v-for="doctor in experts" :key="doctor.doctor_id" class="doctor">
          <header class="doctor-head">
            <span class="avatar">{{ initial(doctor.doctor_name) }}</span>
            <div class="doctor-name">
              <b>{{ doctor.doctor_name }}</b>
              <span class="title">{{ doctor.title }}</span>
            </div>
            <span class="expert-tag">专家</span>
          </header>
          <div class="slot-grid">
            <button
              v-for="slot in doctor.slots"
              :key="slot.time_slot"
              type="button"
              class="slot"
              :class="{ selected: isSelected(doctor, slot) }"
              :disabled="!slot.available"
              @click="selectSlot(doctor, slot)"
            >
              <b>{{ slot.time_slot }}</b>
              <em>{{ slot.available ? `余 ${slot.remaining}` : '约满' }}</em>
            </button>
          </div>
        </article>
      </section>

      <section v-if="others.length" class="doctor-group">
        <h2 class="group-title">普通门诊</h2>
        <article v-for="doctor in others" :key="doctor.doctor_id" class="doctor">
          <header class="doctor-head">
            <span class="avatar">{{ initial(doctor.doctor_name) }}</span>
            <div class="doctor-name">
              <b>{{ doctor.doctor_name }}</b>
              <span class="title">{{ doctor.title }}</span>
            </div>
          </header>
          <div class="slot-grid">
            <button
              v-for="slot in doctor.slots"
              :key="slot.time_slot"
              type="button"
              class="slot"
              :class="{ selected: isSelected(doctor, slot) }"
              :disabled="!slot.available"
              @click="selectSlot(doctor, slot)"
            >
              <b>{{ slot.time_slot }}</b>
              <em>{{ slot.available ? `余 ${slot.remaining}` : '约满' }}</em>
            </button>
          </div>
        </article>
      </section>

      <section v-if="appointments.length" class="mine">
        <h2 class="group-title">我的预约</h2>
        <article v-for="item in appointments" :key="item.appointment_id" class="mine-item">
          <div class="mine-main">
            <b>{{ item.dept_name }} · {{ item.doctor_name }}</b>
            <span>{{ item.schedule_date }} {{ item.time_slot }} · {{ item.doctor_title }}</span>
            <em>{{ item.appointment_no }}</em>
          </div>
          <div class="mine-side">
            <span class="status" :class="{ off: item.status !== 'BOOKED' }">{{ item.status_label }}</span>
            <button v-if="item.can_cancel" class="link" type="button" @click="cancel(item)">取消</button>
          </div>
        </article>
      </section>
    </template>

    <footer v-if="selected" class="confirm-bar">
      <div class="confirm-summary">
        <b>{{ selected.doctor.doctor_name }} · {{ selected.slot.time_slot }}</b>
        <span>{{ activeDay?.date }} · {{ selected.doctor.title }}</span>
      </div>
      <button class="confirm-btn" type="button" :disabled="booking" @click="confirm">
        {{ booking ? '预约中…' : '确认预约' }}
      </button>
    </footer>
  </main>
</template>

<style scoped>
.appointment-page {
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  max-width: 560px;
  margin: 0 auto;
  padding: 0 14px calc(120px + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

.head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
}

.back {
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

.back svg {
  width: 17px;
  height: 17px;
}

.eyebrow {
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--c-accent-text);
}

.head h1 {
  margin-top: 3px;
  font-size: 28px;
  line-height: 1.25;
}

.state {
  padding: 80px 12px;
  text-align: center;
  color: var(--c-muted);
  font-size: 13px;
}

.state--error p {
  margin-bottom: 16px;
  color: var(--c-danger);
}

.ghost {
  border: 1px solid var(--c-line);
  border-radius: 999px;
  padding: 9px 18px;
  background: transparent;
  color: var(--c-primary);
}

.date-strip {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 8px;
  margin-top: 12px;
  margin-bottom: 18px;
  scrollbar-width: none;
}

.date {
  flex: none;
  width: 66px;
  padding: 10px 0;
  border: 1px solid var(--c-line);
  border-radius: 14px;
  background: var(--c-surface);
  color: var(--c-muted);
  display: flex;
  flex-direction: column;
  gap: 3px;
  cursor: pointer;
}

.date em {
  font-style: normal;
  font-size: 10.5px;
}

.date b {
  font-family: var(--font-display);
  font-size: 13px;
  color: var(--c-ink);
}

.date.active {
  background: var(--c-primary);
  border-color: var(--c-primary);
  box-shadow: var(--shadow-accent);
}

.date.active em,
.date.active b {
  color: #fff;
}

.doctor-group {
  margin-bottom: 18px;
}

.group-title {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--c-muted);
  margin-bottom: 8px;
}

.doctor {
  background: var(--c-surface);
  border: 1px solid var(--c-line);
  border-radius: 18px;
  padding: 14px;
  margin-bottom: 10px;
  box-shadow: var(--shadow-xs);
}

.doctor-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.avatar {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--c-primary-soft);
  border: 1px solid var(--c-primary-line);
  color: var(--c-primary);
  font-family: var(--font-display);
  font-size: 15px;
}

.doctor-name {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex: 1;
}

.doctor-name b {
  font-size: 14px;
}

.doctor-name span {
  font-size: 11.5px;
  color: var(--c-muted);
}

.expert-tag {
  padding: 2px 7px;
  border-radius: 5px;
  background: var(--c-accent-soft);
  color: var(--c-accent-text);
  font-size: 10.5px;
}

.slot-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
}

.slot {
  padding: 7px 2px;
  border: 1px solid var(--c-line-soft);
  border-radius: 9px;
  background: var(--c-surface-soft);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  cursor: pointer;
}

.slot b {
  font-size: 10.5px;
  color: var(--c-ink);
  font-weight: 500;
}

.slot em {
  font-style: normal;
  font-size: 9.5px;
  color: var(--c-muted);
}

.slot.selected {
  background: var(--c-primary);
  border-color: var(--c-primary);
}

.slot.selected b,
.slot.selected em {
  color: #fff;
}

.slot:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.mine {
  margin-top: 8px;
}

.mine-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--c-line);
  border-radius: 14px;
  background: var(--c-surface);
  margin-bottom: 8px;
}

.mine-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.mine-main b {
  font-size: 13px;
}

.mine-main span {
  font-size: 11.5px;
  color: var(--c-muted);
}

.mine-main em {
  font-style: normal;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--c-faint);
}

.mine-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  flex: none;
}

.status {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--c-primary-soft);
  color: var(--c-primary);
  font-size: 10.5px;
}

.status.off {
  background: var(--c-surface-soft);
  color: var(--c-faint);
}

.link {
  border: 0;
  background: transparent;
  color: var(--c-danger);
  font-size: 11.5px;
  padding: 0;
  cursor: pointer;
}

.confirm-bar {
  position: fixed;
  left: 50%;
  bottom: 0;
  transform: translateX(-50%);
  width: 100%;
  max-width: 560px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px calc(12px + env(safe-area-inset-bottom));
  box-sizing: border-box;
  background: rgba(255, 253, 250, 0.94);
  backdrop-filter: blur(10px);
  border-top: 1px solid var(--c-line);
}

.confirm-summary {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.confirm-summary b {
  font-size: 13px;
  color: var(--c-ink);
}

.confirm-summary span {
  font-size: 11px;
  color: var(--c-muted);
}

.confirm-btn {
  flex: none;
  border: 0;
  border-radius: 999px;
  padding: 12px 22px;
  background: var(--c-accent);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  box-shadow: var(--shadow-accent);
  cursor: pointer;
}

.confirm-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}
</style>
