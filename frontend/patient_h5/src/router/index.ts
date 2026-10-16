import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/Home.vue') },
    { path: '/chat', name: 'chat', component: () => import('@/views/Chat.vue') },
    { path: '/result', name: 'result', component: () => import('@/views/TriageResult.vue') },
    { path: '/emr', name: 'emr', component: () => import('@/views/Emr.vue') },
  ],
})

export default router
