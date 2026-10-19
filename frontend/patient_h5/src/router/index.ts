import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue') },
    { path: '/', name: 'home', component: () => import('@/views/Home.vue') },
    { path: '/chat', name: 'chat', component: () => import('@/views/Chat.vue') },
    { path: '/result', name: 'result', component: () => import('@/views/TriageResult.vue') },
    { path: '/emr', name: 'emr', component: () => import('@/views/Emr.vue') },
    {
      path: '/appointment',
      name: 'appointment',
      component: () => import('@/views/Appointment.vue'),
    },
  ],
})

router.beforeEach((to) => {
  const authed = Boolean(getToken())
  if (to.path !== '/login' && !authed) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && authed) return '/'
  return true
})

export default router
