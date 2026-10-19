import { createRouter, createWebHistory } from 'vue-router'
import { getToken, getTokenRole } from '@/api/client'

const LOGIN_URL = 'http://127.0.0.1:5173/login'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/auth-callback',
      name: 'auth-callback',
      component: () => import('@/views/AuthCallback.vue'),
    },
    { path: '/', redirect: () => (getTokenRole() === 'KB_ADMIN' ? '/kb' : '/users') },
    {
      path: '/patients',
      name: 'patients',
      component: () => import('@/views/Patients.vue'),
      meta: { roles: ['ORG_ADMIN'] },
    },
    {
      path: '/users',
      name: 'users',
      component: () => import('@/views/Users.vue'),
      meta: { roles: ['ORG_ADMIN'] },
    },
    {
      path: '/depts',
      name: 'depts',
      component: () => import('@/views/Depts.vue'),
      meta: { roles: ['ORG_ADMIN'] },
    },
    {
      path: '/kb',
      name: 'kb',
      component: () => import('@/views/KbEntries.vue'),
      meta: { roles: ['ORG_ADMIN', 'KB_ADMIN'] },
    },
    {
      path: '/kg',
      name: 'kg',
      component: () => import('@/views/KnowledgeGraph.vue'),
      meta: { roles: ['ORG_ADMIN', 'KB_ADMIN'] },
    },
    {
      path: '/audit',
      name: 'audit',
      component: () => import('@/views/AuditLogs.vue'),
      meta: { roles: ['ORG_ADMIN', 'KB_ADMIN'] },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/Settings.vue'),
      meta: { roles: ['ORG_ADMIN'] },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  if (to.name === 'auth-callback') return true
  if (!getToken()) {
    const next = encodeURIComponent(window.location.href)
    window.location.replace(`${LOGIN_URL}?redirect=${next}`)
    return false
  }
  const allowed = to.meta.roles as string[] | undefined
  const role = getTokenRole()
  if (allowed && role && !allowed.includes(role)) {
    return role === 'KB_ADMIN' ? '/kb' : '/users'
  }
  return true
})

export default router
