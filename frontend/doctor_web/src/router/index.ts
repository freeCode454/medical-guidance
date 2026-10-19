import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/api/client'

const LOGIN_URL = 'http://127.0.0.1:5173/login'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/auth-callback',
      name: 'auth-callback',
      component: () => import('@/views/AuthCallback.vue'),
    },
    { path: '/', name: 'encounters', component: () => import('@/views/Encounters.vue') },
    { path: '/session/:id', name: 'session', component: () => import('@/views/SessionDetail.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  // 统一登录页在患者端 5173；这里不再保留第二套登录页
  if (to.name === 'auth-callback') return true
  if (!getToken()) {
    const next = encodeURIComponent(window.location.href)
    window.location.replace(`${LOGIN_URL}?redirect=${next}`)
    return false
  }
  return true
})

export default router
