import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: { title: '数据总览' }
  },
  {
    path: '/search',
    name: 'search',
    component: () => import('../views/SearchView.vue'),
    meta: { title: '高级检索' }
  },
  {
    path: '/graph',
    name: 'graph',
    component: () => import('../views/GraphView.vue'),
    meta: { title: '图谱探索' }
  },
  {
    path: '/recommend',
    name: 'recommend',
    component: () => import('../views/RecommendView.vue'),
    meta: { title: '智能推荐' }
  },
  {
    path: '/analysis',
    name: 'analysis',
    component: () => import('../views/AnalysisView.vue'),
    meta: { title: '统计分析' }
  },
  {
    path: '/qa',
    name: 'qa',
    component: () => import('../views/QaView.vue'),
    meta: { title: '智能问答' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.afterEach(to => {
  document.title = `${to.meta.title || '首页'}｜云访古建`
})

export default router