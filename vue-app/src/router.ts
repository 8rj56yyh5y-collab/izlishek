import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory('/app/'),
  routes: [
    { path: '/', component: () => import('./pages/OverviewPage.vue'), meta: { title: 'Огляд' } },
    { path: '/reconcile', component: () => import('./pages/ReconcilePage.vue'), meta: { title: 'Звірка' } },
    { path: '/shipments', component: () => import('./pages/ShipmentsPage.vue'), meta: { title: 'Відвантаження' } },
    { path: '/receivers/:name', component: () => import('./pages/ReceiverPage.vue'), props: true, meta: { title: 'Приймальник' } },
    { path: '/directory', component: () => import('./pages/DirectoryPage.vue'), meta: { title: 'Довідники' } },
  ],
})
