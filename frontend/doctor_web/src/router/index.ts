import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue') },
    { path: '/', name: 'encounters', component: () => import('@/views/Encounters.vue') },
    { path: '/session/:id', name: 'session', component: () => import('@/views/SessionDetail.vue') },
    { path: '/takeover', name: 'takeover', component: () => import('@/views/TakeoverQueue.vue') },
  ],
})

router.beforeEach((to) => {
  if (to.name !== 'login' && !getToken()) return '/login'
  return true
})

export default router
