<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import {
  Network,
  Landmark,
  GitBranch,
  MapPinned,
  Sparkles,
  Search,
  Share2,
  MessageCircle,
  ArrowRight,
  DatabaseZap
} from 'lucide-vue-next'
import { getOverviewAnalysis, getPeriodAnalysis, getStats } from '../api'

const router = useRouter()
const loading = ref(true)
const errorMessage = ref('')
const chartRef = ref(null)
let chartInstance = null

const stats = ref({
  node_count: null,
  relationship_count: null,
  building_count: null,
  province_count: null,
  period_count: null,
  recommendation_count: null
})

const numberText = value =>
  value === null || value === undefined
    ? '—'
    : new Intl.NumberFormat('zh-CN').format(value)

// 底部两个可视化表格的聚合数据：省级行政区与建筑类型的古建筑数量排行
const overview = ref({ provinces: [], types: [] })

const rankWidth = (count, list) =>
  `${Math.round((count / (list[0]?.count || 1)) * 100)}%`

const statCards = computed(() => [
  {
    label: '知识节点',
    value: numberText(stats.value.node_count),
    unit: '个',
    icon: Network,
    tone: 'green'
  },
  {
    label: '关联关系',
    value: numberText(stats.value.relationship_count),
    unit: '条',
    icon: GitBranch,
    tone: 'red'
  },
  {
    label: '古建筑实体',
    value: numberText(stats.value.building_count),
    unit: '座',
    icon: Landmark,
    tone: 'gold'
  },
  {
    label: '覆盖省份',
    value: numberText(stats.value.province_count),
    unit: '个',
    icon: MapPinned,
    tone: 'blue'
  },
  {
    label: '历史时期',
    value: numberText(stats.value.period_count),
    unit: '类',
    icon: DatabaseZap,
    tone: 'purple'
  },
  {
    label: '推荐关系',
    value: numberText(stats.value.recommendation_count),
    unit: '条',
    icon: Sparkles,
    tone: 'orange'
  }
])

const functions = [
  {
    title: '高级组合检索',
    description: '按照省份、时代、建筑类型和保护级别进行多条件检索。',
    path: '/search',
    icon: Search,
    tag: 'Cypher动态查询'
  },
  {
    title: '交互式图谱探索',
    description: '从任意古建筑出发，查看地点、时代、类型及旅游推荐关系。',
    path: '/graph',
    icon: Share2,
    tag: 'ECharts关系图'
  },
  {
    title: '可解释智能推荐',
    description: '综合同省份、同历史时期及图结构特征生成旅游推荐。',
    path: '/recommend',
    icon: Sparkles,
    tag: '知识推理'
  },
  {
    title: '自然语言问答',
    description: '使用自然语言查询古建筑知识，并返回答案与图谱证据。',
    path: '/qa',
    icon: MessageCircle,
    tag: '意图识别'
  }
]

function normalizePeriods(data) {
  const rows = Array.isArray(data)
    ? data
    : data?.items || data?.data || data?.periods || []

  return rows
    .map(item => ({
      name: item.period || item.era || item.name || item.历史时期,
      value:
        item.count ??
        item.building_count ??
        item.value ??
        item.古建筑数量 ??
        0
    }))
    .filter(item => item.name && Number(item.value) > 0)
    .slice(0, 12)
}

function drawChart(rows) {
  if (!chartRef.value || !rows.length) return

  chartInstance?.dispose()
  chartInstance = echarts.init(chartRef.value)

  chartInstance.setOption({
    animationDuration: 900,
    grid: {
      left: 48,
      right: 22,
      top: 36,
      bottom: 56
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(24, 55, 49, 0.94)',
      borderWidth: 0,
      textStyle: { color: '#fff' }
    },
    xAxis: {
      type: 'category',
      data: rows.map(item => item.name),
      axisLabel: {
        color: '#6b7d75',
        interval: 0,
        rotate: rows.length > 8 ? 28 : 0
      },
      axisLine: { lineStyle: { color: '#cfc8b7' } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '古建筑数量',
      nameTextStyle: { color: '#7b877f' },
      axisLabel: { color: '#7b877f' },
      splitLine: {
        lineStyle: {
          color: 'rgba(35, 70, 61, 0.08)',
          type: 'dashed'
        }
      }
    },
    series: [
      {
        type: 'bar',
        data: rows.map(item => item.value),
        barMaxWidth: 35,
        itemStyle: {
          borderRadius: [6, 6, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#b5483d' },
            { offset: 1, color: '#d3a65a' }
          ])
        }
      }
    ]
  })
}

function resizeChart() {
  chartInstance?.resize()
}

onMounted(async () => {
  try {
    const [statsResult, periodResult, overviewResult] = await Promise.all([
      getStats(),
      getPeriodAnalysis(),
      getOverviewAnalysis()
    ])

    stats.value = {
      ...stats.value,
      ...statsResult
    }

    overview.value = {
      provinces: Array.isArray(overviewResult?.provinces)
        ? overviewResult.provinces
        : [],
      types: Array.isArray(overviewResult?.types) ? overviewResult.types : []
    }

    await nextTick()
    drawChart(normalizePeriods(periodResult))
  } catch (error) {
    errorMessage.value = '数据加载失败，请检查FastAPI和Neo4j是否已启动。'
    console.error(error)
  } finally {
    loading.value = false
  }

  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chartInstance?.dispose()
})
</script>

<template>
  <section class="home-page">
    <div class="hero panel">
      <div class="hero-copy">
        <img
          src="../assets/title.png"
          alt="云访古建"
          class="hero-title-img"
        />
        <p>
          系统融合实体抽取、关系抽取、Neo4j图存储、知识推理与可视化技术，
          为中华古建筑提供检索、探索、分析、推荐和问答服务。
        </p>

        <div class="hero-actions">
          <button class="primary-button" @click="router.push('/graph')">
            探索知识图谱
          </button>

          <button class="secondary-button" @click="router.push('/recommend')">
            获取旅游推荐
          </button>
        </div>

        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>
      </div>

     <div class="hero-visual">
  <div class="cloud-pattern cloud-left"></div>
  <div class="cloud-pattern cloud-right"></div>

  <img
    src="../assets/ancient-buildings-hero.png"
    alt=""
    class="hero-building-image"
  />

  <div class="hero-visual-card">
    <div class="eyebrow">DIGITAL HERITAGE · KNOWLEDGE GRAPH</div>
    <h2>
      一图识古建
      <span>智游山河间</span>
    </h2>
  </div>

  <div class="hero-seal">云访<br />古建</div>
</div>
    </div>

    <div class="section-heading">
      <div>
        <span>REAL-TIME GRAPH DATA</span>
        <h3>知识图谱数据概览</h3>
      </div>
      <p>{{ loading ? '正在从Neo4j读取数据…' : '数据由FastAPI实时查询Neo4j获得' }}</p>
    </div>

    <div class="stats-grid">
      <article
        v-for="card in statCards"
        :key="card.label"
        class="stat-card panel"
        :class="card.tone"
      >
        <div class="stat-icon">
          <component :is="card.icon" :size="23" />
        </div>
        <div>
          <p>{{ card.label }}</p>
          <strong>{{ card.value }}</strong>
          <small>{{ card.unit }}</small>
        </div>
      </article>
    </div>

    <div class="content-grid">
      <section class="period-panel panel">
        <div class="panel-heading">
          <div>
            <span>DYNASTY DISTRIBUTION</span>
            <h3>古建筑历史时期分布</h3>
          </div>
          <button @click="router.push('/analysis')">
            查看完整分析
            <ArrowRight :size="15" />
          </button>
        </div>

        <div ref="chartRef" class="period-chart"></div>
      </section>

      <section class="feature-panel panel">
        <div class="panel-heading">
          <div>
            <span>CORE CAPABILITIES</span>
            <h3>核心应用能力</h3>
          </div>
        </div>

        <div class="feature-list">
          <button
            v-for="item in functions"
            :key="item.path"
            class="feature-item"
            @click="router.push(item.path)"
          >
            <span class="feature-icon">
              <component :is="item.icon" :size="20" />
            </span>

            <span class="feature-copy">
              <strong>{{ item.title }}</strong>
              <small>{{ item.description }}</small>
            </span>

            <span class="feature-tag">{{ item.tag }}</span>
            <ArrowRight class="feature-arrow" :size="17" />
          </button>
        </div>
      </section>
    </div>

    <section class="rank-grid">
      <article class="rank-panel panel">
        <div class="panel-heading">
          <div>
            <span>REGIONAL RANKING</span>
            <h3>古建筑省级分布排行</h3>
          </div>
          <MapPinned :size="20" />
        </div>

        <div class="rank-list">
          <div
            v-for="(item, index) in overview.provinces.slice(0, 10)"
            :key="item.name"
            class="rank-row"
          >
            <span class="rank-no">{{ String(index + 1).padStart(2, '0') }}</span>
            <strong :title="item.name">{{ item.name }}</strong>
            <div class="rank-track">
              <i
                :style="{ width: rankWidth(item.count, overview.provinces) }"
              ></i>
            </div>
            <b>{{ item.count }}</b>
          </div>

          <p v-if="!overview.provinces.length" class="rank-empty">
            {{ loading ? '正在统计…' : '暂未统计到省级行政区数据' }}
          </p>
        </div>
      </article>

      <article class="rank-panel panel">
        <div class="panel-heading">
          <div>
            <span>BUILDING TYPE</span>
            <h3>古建筑类型分布</h3>
          </div>
          <Landmark :size="20" />
        </div>

        <div class="rank-list">
          <div
            v-for="(item, index) in overview.types.slice(0, 10)"
            :key="item.name"
            class="rank-row"
          >
            <span class="rank-no">{{ String(index + 1).padStart(2, '0') }}</span>
            <strong :title="item.name">{{ item.name }}</strong>
            <div class="rank-track">
              <i :style="{ width: rankWidth(item.count, overview.types) }"></i>
            </div>
            <b>{{ item.count }}</b>
          </div>

          <p v-if="!overview.types.length" class="rank-empty">
            {{ loading ? '正在统计…' : '暂未统计到建筑类型数据' }}
          </p>
        </div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.hero {
  position: relative;
  display: grid;
  min-height: 330px;
  grid-template-columns: 1.08fr 0.92fr;
  overflow: hidden;
  border-color: rgba(197, 154, 74, 0.3);
  background:
    linear-gradient(105deg, rgba(251, 248, 239, 0.98) 0 53%, rgba(226, 232, 220, 0.92)),
    #f7f3e9;
}

.hero::before {
  position: absolute;
  top: 0;
  left: 0;
  width: 7px;
  height: 100%;
  background: linear-gradient(#9d382f, #c48e47);
  content: "";
}

.hero-copy {
  position: relative;
  z-index: 3;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 22px 28px 40px 50px;
}

/* 左上角书法标题：multiply 混合让白底融入暖色面板，只留墨色笔触 */
.hero-title-img {
  width: min(440px, 92%);
  margin-bottom: 16px;
  mix-blend-mode: multiply;
}

/* 右侧视觉区上的标题卡 */
.hero-visual-card {
  position: absolute;
  top: 24px;
  left: 24px;
  z-index: 4;
  max-width: 78%;
  padding: 14px 20px 16px;
  border: 1px solid rgba(197, 154, 74, 0.45);
  border-radius: 14px;
  background: rgba(252, 247, 236, 0.82);
  backdrop-filter: blur(6px);
  box-shadow: 0 10px 26px rgba(73, 49, 29, 0.14);
}

.hero-visual-card h2 {
  margin: 8px 0 0;
  font-size: 31px;
}

.hero-visual-card h2 span {
  font-size: 23px;
}

.eyebrow,
.section-heading span,
.panel-heading span {
  color: #a27e3d;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
}

.hero h2 {
  margin: 12px 0 16px;
  color: #173e36;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 40px;
  line-height: 1.3;
  letter-spacing: 3px;
}

.hero h2 span {
  display: block;
  color: #a43f35;
  font-size: 30px;
}

.hero p {
  max-width: 660px;
  margin: 0;
  color: #65756e;
  font-size: 14px;
  line-height: 1.9;
}

.hero-actions {
  display: flex;
  gap: 12px;
  margin-top: 25px;
}

.hero-actions button {
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-message {
  margin-top: 16px;
  color: #a74438;
  font-size: 13px;
}

.hero-visual {
  position: relative;
  min-height: 330px;
  overflow: hidden;
  background:
    radial-gradient(circle at 75% 24%, rgba(201, 154, 73, 0.25), transparent 20%),
    linear-gradient(155deg, rgba(30, 75, 66, 0.04), rgba(30, 75, 66, 0.16));
}

.hero-visual {
  position: relative;
  min-height: 330px;
  overflow: hidden;
  background:
    radial-gradient(circle at 82% 18%, rgba(190, 74, 57, 0.2), transparent 14%),
    linear-gradient(155deg, #eee9da 0%, #dfe8dd 48%, #c9d8cf 100%);
}

.hero-visual::before {
  position: absolute;
  inset: 0;
  background:
    repeating-linear-gradient(
      90deg,
      transparent 0 34px,
      rgba(33, 77, 69, 0.025) 35px
    );
  content: "";
}

.hero-visual::after {
  position: absolute;
  top: 35px;
  right: 72px;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: rgba(177, 63, 51, 0.78);
  box-shadow:
    0 0 0 16px rgba(177, 63, 51, 0.06),
    0 0 50px rgba(177, 63, 51, 0.1);
  content: "";
}

.hero-building-image {
  position: absolute;
  z-index: 2;
  right: -15px;
  bottom: -3px;
  width: 108%;
  max-width: none;
  filter:
    drop-shadow(0 15px 16px rgba(31, 60, 52, 0.17))
    saturate(0.92);
}

.cloud-pattern {
  position: absolute;
  z-index: 1;
  width: 130px;
  height: 45px;
  border: 2px solid rgba(191, 148, 69, 0.24);
  border-right-color: transparent;
  border-bottom-color: transparent;
  border-radius: 50%;
}

.cloud-left {
  top: 38px;
  left: 28px;
}

.cloud-right {
  right: 18px;
  bottom: 38px;
  transform: rotate(180deg);
}

.hero-seal {
  position: absolute;
  z-index: 4;
  right: 22px;
  bottom: 20px;
  padding: 7px 8px;
  border: 2px solid rgba(158, 55, 47, 0.75);
  color: #9e372f;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 13px;
  line-height: 1.15;
  background: rgba(247, 238, 218, 0.72);
}

.hero::after {
  position: absolute;
  z-index: 5;
  right: 0;
  bottom: 0;
  left: 0;
  height: 7px;
  background:
    repeating-linear-gradient(
      90deg,
      #a83f34 0 18px,
      #c99b49 18px 36px,
      #1e5147 36px 54px
    );
  opacity: 0.72;
  content: "";
}
.hero-seal {
  position: absolute;
  right: 30px;
  bottom: 24px;
  padding: 7px 8px;
  border: 2px solid rgba(158, 55, 47, 0.7);
  color: #9e372f;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 13px;
  line-height: 1.15;
}

.section-heading,
.panel-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}

.section-heading h3,
.panel-heading h3 {
  margin: 5px 0 0;
  color: #1c453d;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 22px;
  letter-spacing: 1px;
}

.section-heading p {
  margin: 0;
  color: #7a8981;
  font-size: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 14px;
}

.stat-card {
  display: flex;
  min-height: 110px;
  align-items: center;
  gap: 14px;
  padding: 20px 16px;
  transition: 0.25s ease;
}



.stat-card {
  position: relative;
  overflow: hidden;
}

.stat-card:hover {
  transform: translateY(-4px);
}

.stat-icon {
  display: grid;
  width: 43px;
  height: 43px;
  flex: 0 0 43px;
  place-items: center;
  border-radius: 12px;
  color: white;
}

.stat-card p {
  margin: 0 0 5px;
  color: #76847d;
  font-size: 12px;
}

.stat-card strong {
  color: #263d36;
  font-family: Georgia, serif;
  font-size: 25px;
}

.stat-card small {
  margin-left: 4px;
  color: #8b958f;
}

.green .stat-icon { background: #2b6b5f; }
.red .stat-icon { background: #a84438; }
.gold .stat-icon { background: #ba873b; }
.blue .stat-icon { background: #477188; }
.purple .stat-icon { background: #77617c; }
.orange .stat-icon { background: #b7693e; }

.content-grid {
  display: grid;
  grid-template-columns: 1.16fr 0.84fr;
  gap: 18px;
}

.period-panel,
.feature-panel,
.rank-panel {
  padding: 23px;
}

.panel-heading button {
  display: flex;
  align-items: center;
  gap: 5px;
  border: 0;
  color: #9c4035;
  background: transparent;
  font-size: 12px;
}

.period-chart {
  width: 100%;
  height: 340px;
  margin-top: 12px;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin-top: 20px;
}

.feature-item {
  display: grid;
  grid-template-columns: 42px 1fr auto 20px;
  align-items: center;
  gap: 11px;
  width: 100%;
  padding: 13px;
  border: 1px solid rgba(36, 74, 65, 0.1);
  border-radius: 11px;
  text-align: left;
  background: rgba(249, 247, 240, 0.75);
  transition: 0.22s ease;
}

.feature-item:hover {
  border-color: rgba(169, 63, 52, 0.25);
  background: #fffdf8;
  transform: translateX(3px);
}

.feature-icon {
  display: grid;
  width: 39px;
  height: 39px;
  place-items: center;
  border-radius: 10px;
  color: #f3dfae;
  background: #214e45;
}

.feature-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.feature-copy strong {
  color: #26483f;
  font-size: 14px;
}

.feature-copy small {
  overflow: hidden;
  color: #7a8881;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feature-tag {
  padding: 5px 8px;
  border-radius: 20px;
  color: #9a4338;
  background: rgba(169, 63, 52, 0.08);
  font-size: 10px;
}

.feature-arrow {
  color: #9a8a68;
}

/* ===== 宫廷红金主题二次美化 ===== */

.home-page {
  position: relative;
  isolation: isolate;
}

/* 页面宣纸底纹与云气纹样 */
.home-page::before {
  position: fixed;
  z-index: -1;
  inset: 82px 0 0;
  pointer-events: none;
  background:
    radial-gradient(
      ellipse at 8% 18%,
      transparent 0 48px,
      rgba(178, 118, 69, 0.07) 49px 51px,
      transparent 52px
    ),
    radial-gradient(
      ellipse at 94% 42%,
      transparent 0 65px,
      rgba(35, 79, 70, 0.06) 66px 68px,
      transparent 69px
    ),
    repeating-linear-gradient(
      0deg,
      rgba(120, 91, 50, 0.018) 0 1px,
      transparent 1px 7px
    );
  content: "";
}

/* 主卡片取消外框 */
.hero {
  border: none !important;
  border-radius: 20px;
  background:
    linear-gradient(
      105deg,
      rgba(252, 246, 232, 0.98) 0 53%,
      rgba(232, 224, 201, 0.93) 53% 100%
    );
  box-shadow:
    0 22px 55px rgba(73, 49, 29, 0.12),
    0 4px 12px rgba(73, 49, 29, 0.06);
}

/* 去掉左侧竖线和底部彩色边框 */
.hero::before,
.hero::after {
  content: "";
  position: absolute;
  right: 18px;
  bottom: 0;
  width: 58%;
  height: 82%;
  background: url("../assets/hero-palace-watermark.png")
    right bottom / contain no-repeat;
  opacity: 0.14;
  pointer-events: none;
  z-index: 0;
}

.hero > * {
  position: relative;
  z-index: 1;
}

/* 去掉太阳 */
.hero-visual::after {
  display: none !important;
}

/* 主视觉增加柔和山水晕染 */
.hero-visual {
  border: none;
  background:
    radial-gradient(
      ellipse at 70% 88%,
      rgba(39, 88, 76, 0.18),
      transparent 48%
    ),
    linear-gradient(
      155deg,
      #f2ead8 0%,
      #e1e9dc 48%,
      #cbd9ce 100%
    );
}

/* 云纹弱化，避免抢建筑插画 */
.cloud-pattern {
  opacity: 0.6;
  border-color: rgba(176, 126, 59, 0.22);
  border-right-color: transparent;
  border-bottom-color: transparent;
}

/* 按钮改成宫廷牌匾造型 */
.hero-actions button {
  position: relative;
  min-width: 166px;
  justify-content: center;
  overflow: hidden;
  border: none;
  border-radius: 4px;
  clip-path: polygon(
    7px 0,
    calc(100% - 7px) 0,
    100% 7px,
    100% calc(100% - 7px),
    calc(100% - 7px) 100%,
    7px 100%,
    0 calc(100% - 7px),
    0 7px
  );
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 17px;
  letter-spacing: 1px;
}

.hero-actions button::before {
  position: absolute;
  inset: 4px;
  border: 1px solid rgba(255, 235, 188, 0.34);
  pointer-events: none;
  content: "";
}

.primary-button {
  color: #fff8e8;
  background:
    linear-gradient(135deg, #8f2f28, #bd4b3c 55%, #96352d);
  box-shadow: 0 10px 24px rgba(142, 46, 39, 0.24);
}

.secondary-button {
  color: #6f3b24;
  background:
    linear-gradient(135deg, #efd29a, #d5a75f);
  box-shadow: 0 10px 24px rgba(167, 117, 54, 0.2);
}

.hero-actions button:hover {
  filter: brightness(1.06);
  transform: translateY(-2px);
}

/* 数据卡片取消普通边框，加入屋檐与窗棂暗纹 */
.stat-card {
  position: relative;
  min-height: 126px;
  overflow: visible;
  border: none !important;
  border-radius: 7px 7px 15px 15px;
  background:
    linear-gradient(
      90deg,
      transparent 0 48%,
      rgba(155, 90, 46, 0.025) 48% 52%,
      transparent 52%
    ),
    linear-gradient(180deg, #fffaf0, #f6eddb);
  box-shadow:
    0 13px 28px rgba(69, 49, 30, 0.09),
    inset 0 -4px 0 rgba(166, 62, 51, 0.08);
}





/* 海棠形图标底座 */
.stat-icon {
  width: 52px;
  height: 52px;
  flex-basis: 52px;
  border: 2px solid rgba(226, 187, 112, 0.8);
  border-radius: 46% 46% 46% 46% / 38% 38% 38% 38%;
  box-shadow:
    inset 0 0 0 4px rgba(255, 242, 207, 0.15),
    0 5px 12px rgba(83, 52, 28, 0.15);
}

/* 标题区：米黄色底框 */
.section-heading {
  position: relative;
  padding: 20px 26px 20px 32px;
  border: 1px solid rgba(150, 83, 54, 0.22);
  border-radius: 6px 6px 22px 22px;
  background: linear-gradient(
    118deg,
    rgba(250, 239, 210, 0.94),
    rgba(243, 228, 192, 0.8)
  );
  box-shadow: 0 14px 35px rgba(82, 53, 35, 0.08);
}

/* 标题左侧中式竖线 */
.section-heading::before {
  position: absolute;
  top: 22px;
  bottom: 22px;
  left: 14px;
  width: 5px;
  border-radius: 5px;
  background: linear-gradient(#a73d33, #d2a151);
  content: "";
}

/* 下方大面板采用宫殿窗棂暗纹 */
.period-panel,
.feature-panel {
  position: relative;
  overflow: hidden;
  border: none !important;
  background:
    linear-gradient(rgba(255, 251, 241, 0.96), rgba(250, 244, 231, 0.96)),
    repeating-linear-gradient(
      90deg,
      transparent 0 30px,
      rgba(157, 54, 46, 0.06) 31px 33px
    );
  box-shadow: 0 15px 35px rgba(64, 45, 27, 0.09);
}



/* 功能入口改为古建展签卡片 */
.feature-item {
  position: relative;
  border: none;
  border-radius: 7px;
  background:
    linear-gradient(135deg, #fbf4e4, #f0dfbd);
  box-shadow:
    inset 0 0 0 1px rgba(173, 115, 55, 0.14),
    0 5px 13px rgba(74, 49, 27, 0.06);
}

.feature-item::before {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 5px;
  border-radius: 7px 0 0 7px;
  background: linear-gradient(#a83e34, #c99649);
  content: "";
}

.feature-item:hover {
  background: linear-gradient(135deg, #fff9eb, #efd7aa);
  box-shadow: 0 10px 22px rgba(111, 66, 33, 0.13);
}

.feature-icon {
  color: #ffecc1;
  background:
    radial-gradient(circle, #b3483b 0 53%, #873028 54% 100%);
  border: 2px solid #d4a757;
  border-radius: 50%;
}

/* 底部两张大卡片：古建展签样式 */
.period-panel,
.feature-panel,
.rank-panel {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(153, 61, 43, 0.45) !important;
  border-radius: 12px !important;

  background:
    /* 四角回纹 */
    linear-gradient(#a64b38, #a64b38) left 10px top 10px / 22px 1px no-repeat,
    linear-gradient(#a64b38, #a64b38) left 10px top 10px / 1px 22px no-repeat,
    linear-gradient(#a64b38, #a64b38) right 10px top 10px / 22px 1px no-repeat,
    linear-gradient(#a64b38, #a64b38) right 10px top 10px / 1px 22px no-repeat,
    linear-gradient(#a64b38, #a64b38) left 10px bottom 10px / 22px 1px no-repeat,
    linear-gradient(#a64b38, #a64b38) left 10px bottom 10px / 1px 22px no-repeat,
    linear-gradient(#a64b38, #a64b38) right 10px bottom 10px / 22px 1px no-repeat,
    linear-gradient(#a64b38, #a64b38) right 10px bottom 10px / 1px 22px no-repeat,
    linear-gradient(
      135deg,
      rgba(255, 253, 247, 0.98),
      rgba(250, 241, 222, 0.96)
    ) !important;

  box-shadow:
    0 12px 28px rgba(94, 48, 33, 0.09),
    inset 0 0 0 5px rgba(255, 250, 237, 0.75) !important;
}



/* 保证卡片中的图表和文字位于水印上层 */
.period-panel > *,
.feature-panel > *,
.rank-panel > * {
  position: relative;
  z-index: 1;
}

/* 标题前增加宫灯式装饰 */
.period-panel h2::before,
.feature-panel h2::before {
  content: "◆";
  margin-right: 9px;
  color: #b56b3f;
  font-size: 14px;
}

/* 鼠标经过时轻微提亮，不产生夸张位移 */
.period-panel:hover,
.feature-panel:hover,
.rank-panel:hover {
  border-color: rgba(153, 61, 43, 0.68) !important;
  box-shadow:
    0 15px 34px rgba(94, 48, 33, 0.13),
    inset 0 0 0 5px rgba(255, 250, 237, 0.85) !important;
}

/* 底部两张卡片的古建筑水印 */
.period-panel::after,
.feature-panel::after,
.rank-panel::after {
  content: "";
  position: absolute;
  right: 18px;
  bottom: 8px;

  width: 500px;
  height: 240px;

  background-image: url("../assets/palace-watermark.png");
  background-repeat: no-repeat;
  background-position: right bottom;
  background-size: contain;

  opacity: 0.32;
  pointer-events: none;
  z-index: 0;
}

/* 卡片内容显示在水印上方 */
.period-panel > *,
.feature-panel > * {
  position: relative;
  z-index: 1;
}
/* 清除原来的屋檐和底座 */
.stat-card::before,
.stat-card::after {
  content: none !important;
  display: none !important;
}

/* 完整古建筑卡片边框 */
.stat-card {
  position: relative;
  overflow: hidden;

  min-height: 160px;
  padding: 38px 32px 28px;

  border: none !important;
  border-radius: 8px !important;

  background-color: #fffaf0 !important;
  background-image: url("../assets/stat-card-frame-elegant.png") !important;
  background-repeat: no-repeat !important;
  background-position: center !important;
  background-size: 100% 100% !important;

  box-shadow: 0 10px 24px rgba(92, 54, 35, 0.08) !important;
}

/* 内容保持在边框内部 */
.stat-card > * {
  position: relative;
  z-index: 1;
}

/* 底部两个可视化表格：省级分布与建筑类型分布 */
.rank-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

.rank-panel::after {
  right: 14px;
  bottom: 6px;
  width: 340px;
  height: 165px;
  opacity: 0.2;
}

.rank-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 16px;
}

.rank-row {
  display: grid;
  grid-template-columns: 26px 104px minmax(0, 1fr) 44px;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  border-radius: 6px;
  transition: 0.25s ease;
}

.rank-no {
  color: #b08a5c;
  font-family: Georgia, serif;
  font-size: 12px;
}

.rank-row strong {
  overflow: hidden;
  color: #1c453d;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 15px;
  letter-spacing: 0.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rank-track {
  position: relative;
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(176, 138, 92, 0.16);
}

.rank-track i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #a83e34, #c99649);
  transition: filter 0.25s ease;
}

.rank-row b {
  color: #9c4035;
  font-size: 13px;
  text-align: right;
}

.rank-row:hover {
  background: linear-gradient(135deg, #fff9eb, #f4e2bd);
  box-shadow: 0 8px 18px rgba(111, 66, 33, 0.12);
  transform: translateX(4px);
}

.rank-row:hover .rank-track i {
  filter: brightness(1.08) saturate(1.05);
}

.rank-empty {
  margin: 0;
  padding: 7px 10px;
  color: #7a8981;
  font-size: 12px;
}
</style>

