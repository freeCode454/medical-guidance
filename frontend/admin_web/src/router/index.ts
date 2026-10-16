import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue') },
    { path: '/', redirect: '/users' },
    { path: '/users', name: 'users', component: () => import('@/views/Users.vue') },
    { path: '/depts', name: 'depts', component: () => import('@/views/Depts.vue') },
    { path: '/kb', name: 'kb', component: () => import('@/views/KbEntries.vue') },
    { path: '/audit', name: 'audit', component: () => import('@/views/AuditLogs.vue') },
    { path: '/settings', name: 'settings', component: () => import('@/views/Settings.vue') },
  ],
})

router.beforeEach((to) => {
  if (to.name !== 'login' && !getToken()) return '/login'
  return true
})

export default router
