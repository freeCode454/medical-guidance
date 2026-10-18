import { createRouter, createWebHistory } from 'vue-router'
import { getToken, getTokenRole } from '@/api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue') },
    { path: '/', redirect: () => (getTokenRole() === 'KB_ADMIN' ? '/kb' : '/users') },
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
  if (to.name === 'login') return true
  if (!getToken()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  const allowed = to.meta.roles as string[] | undefined
  const role = getTokenRole()
  if (allowed && role && !allowed.includes(role)) {
    return role === 'KB_ADMIN' ? '/kb' : '/users'
  }
  return true
})

export default router
