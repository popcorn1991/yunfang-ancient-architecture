<script setup>
import { computed, onMounted, ref } from "vue";
import {
  BarChart3,
  BookOpenCheck,
  Building2,
  Crown,
  Database,
  History,
  Image,
  Landmark,
  Layers3,
  LoaderCircle,
  MapPin,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-vue-next";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const loading = ref(false);
const errorMessage = ref("");
const buildings = ref([]);
const systemStats = ref({});
const selectedProvince = ref("");

const palette = [
  "#8f3b32",
  "#b06f3c",
  "#c29552",
  "#567a6a",
  "#7087a0",
  "#9b6d83",
  "#75644e",
];

function unwrap(payload) {
  return payload?.data ?? payload ?? {};
}

function pick(object, keys, fallback = "") {
  for (const key of keys) {
    const value = object?.[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return fallback;
}

async function requestJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`接口返回 ${response.status}`);
  return response.json();
}

function normalizeBuilding(item, index) {
  return {
    id: String(pick(item, ["record_id", "id"], `building-${index}`)),
    name: String(pick(item, ["name", "title"], "未命名古建筑")),
    province: String(pick(item, ["province", "province_name"], "未知地区")),
    era: String(pick(item, ["era", "dynasty"], "时代待考")),
    period: String(pick(item, ["period", "historical_period"], "时期待考")),
    protection: String(
      pick(item, ["protection_level", "protection"], "保护级别待考"),
    ),
    image: String(pick(item, ["image_url", "image"], "")),
    summary: String(pick(item, ["summary_text", "summary"], "")),
  };
}

async function loadCompleteCatalog() {
  const pageSize = 100;
  const firstPayload = await requestJson(
    `${API_BASE_URL}/api/buildings?page=1&page_size=${pageSize}`,
  );
  const firstData = unwrap(firstPayload);
  const firstItems = firstData.items ?? firstData.results ?? [];
  const total = Number(firstData.total ?? firstItems.length);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const restPayloads = await Promise.all(
    Array.from({ length: pageCount - 1 }, (_, index) =>
      requestJson(
        `${API_BASE_URL}/api/buildings?page=${index + 2}&page_size=${pageSize}`,
      ),
    ),
  );
  const allItems = [
    ...firstItems,
    ...restPayloads.flatMap((payload) => unwrap(payload).items ?? []),
  ];
  const uniqueItems = new Map();
  allItems.forEach((item, index) => {
    const building = normalizeBuilding(item, index);
    uniqueItems.set(building.id, building);
  });
  return [...uniqueItems.values()];
}

async function loadAnalysis() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const [statsPayload, catalog] = await Promise.all([
      requestJson(`${API_BASE_URL}/api/stats`),
      loadCompleteCatalog(),
    ]);
    systemStats.value = unwrap(statsPayload);
    buildings.value = catalog;
  } catch (error) {
    errorMessage.value = `统计数据加载失败：${error.message}。请确认后端与 Neo4j 已启动。`;
  } finally {
    loading.value = false;
  }
}

const provinceOptions = computed(() =>
  [...new Set(buildings.value.map((item) => item.province).filter(Boolean))]
    .filter((name) => name !== "未知地区")
    .sort((a, b) => a.localeCompare(b, "zh-CN")),
);

const filteredBuildings = computed(() =>
  selectedProvince.value
    ? buildings.value.filter((item) => item.province === selectedProvince.value)
    : buildings.value,
);

function aggregate(items, key, unknownLabel) {
  const counts = new Map();
  items.forEach((item) => {
    const name = item[key] || unknownLabel;
    counts.set(name, (counts.get(name) ?? 0) + 1);
  });
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh-CN"));
}

const provinceRanking = computed(() =>
  aggregate(filteredBuildings.value, "province", "未知地区").slice(0, 12),
);
const eraRanking = computed(() =>
  aggregate(filteredBuildings.value, "era", "时代待考").slice(0, 12),
);
const periodRanking = computed(() =>
  aggregate(filteredBuildings.value, "period", "时期待考").slice(0, 6),
);
const protectionRanking = computed(() =>
  aggregate(filteredBuildings.value, "protection", "保护级别待考").slice(0, 6),
);

function percentage(value, total = filteredBuildings.value.length) {
  if (!total) return "0.0";
  return ((value / total) * 100).toFixed(1);
}

function barWidth(value, rows) {
  const maximum = Math.max(...rows.map((item) => item.count), 1);
  return `${Math.max(4, (value / maximum) * 100)}%`;
}

const imageCount = computed(
  () => filteredBuildings.value.filter((item) => item.image).length,
);
const summaryCount = computed(
  () => filteredBuildings.value.filter((item) => item.summary).length,
);
const eraKnownCount = computed(
  () =>
    filteredBuildings.value.filter(
      (item) => item.era && item.era !== "时代待考",
    ).length,
);
const protectionKnownCount = computed(
  () =>
    filteredBuildings.value.filter(
      (item) => item.protection && item.protection !== "保护级别待考",
    ).length,
);

const overviewCards = computed(() => [
  {
    label: selectedProvince.value ? "当前筛选建筑" : "古建筑总量",
    value: filteredBuildings.value.length,
    suffix: "座",
    icon: Landmark,
    detail: selectedProvince.value || "完整知识图谱目录",
  },
  {
    label: "覆盖省级地区",
    value: new Set(filteredBuildings.value.map((item) => item.province)).size,
    suffix: "个",
    icon: MapPin,
    detail: selectedProvince.value ? "当前所选地区" : "跨地域文化遗产",
  },
  {
    label: "时代类别",
    value: new Set(filteredBuildings.value.map((item) => item.era)).size,
    suffix: "类",
    icon: History,
    detail: `时代字段覆盖率 ${percentage(eraKnownCount.value)}%`,
  },
  {
    label: "图谱关系总量",
    value: Number(systemStats.value.relationship_count ?? 0).toLocaleString(),
    suffix: "条",
    icon: Layers3,
    detail: "Neo4j 实时统计",
  },
]);

const donutStyle = computed(() => {
  const total = periodRanking.value.reduce((sum, item) => sum + item.count, 0);
  if (!total) return { background: "#e7dcc7" };
  let start = 0;
  const segments = periodRanking.value.map((item, index) => {
    const end = start + (item.count / total) * 100;
    const segment = `${palette[index % palette.length]} ${start}% ${end}%`;
    start = end;
    return segment;
  });
  return { background: `conic-gradient(${segments.join(",")})` };
});

const leadingProvince = computed(() => provinceRanking.value[0]);
const leadingEra = computed(() => eraRanking.value[0]);

onMounted(loadAnalysis);
</script>

<template>
  <main class="analysis-page">
    <section class="hero-section">
      <div class="hero-copy">
        <span class="eyebrow"><BarChart3 :size="15" /> DATA INSIGHT</span>
        <h1>统计分析</h1>
        <p>
          从地域分布、历史时代与数据质量等维度，观察中华古建筑知识图谱的整体结构。
        </p>
      </div>
      <div class="hero-palace" aria-hidden="true"></div>
    </section>

    <section class="toolbar-panel">
      <div class="toolbar-title">
        <span class="round-icon"><TrendingUp :size="21" /></span>
        <div>
          <strong>图谱数据洞察</strong>
          <small>基于 Neo4j 中的真实古建筑记录动态计算</small>
        </div>
      </div>
      <label>
        <MapPin :size="16" />
        <select v-model="selectedProvince" :disabled="loading">
          <option value="">全国范围</option>
          <option
            v-for="province in provinceOptions"
            :key="province"
            :value="province"
          >
            {{ province }}
          </option>
        </select>
      </label>
      <button type="button" :disabled="loading" @click="loadAnalysis">
        <LoaderCircle v-if="loading" class="spinning" :size="16" />
        <RefreshCw v-else :size="16" />
        刷新数据
      </button>
    </section>

    <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

    <section class="overview-grid">
      <article
        v-for="(card, index) in overviewCards"
        :key="card.label"
        class="overview-card"
      >
        <div class="card-watermark" aria-hidden="true"></div>
        <span class="overview-icon"
          ><component :is="card.icon" :size="22"
        /></span>
        <div>
          <small>{{ card.label }}</small>
          <p>
            <strong>{{ card.value }}</strong
            >{{ card.suffix }}
          </p>
          <em>{{ card.detail }}</em>
        </div>
        <b>0{{ index + 1 }}</b>
      </article>
    </section>

    <section v-if="loading" class="loading-state">
      <LoaderCircle class="spinning" :size="36" />
      <strong>正在汇总完整古建筑目录……</strong>
      <span>系统将自动读取全部分页并计算统计结果</span>
    </section>

    <template v-else>
      <section class="analysis-grid primary-grid">
        <article class="chart-panel province-panel ornate-panel">
          <div class="ornate-frame" aria-hidden="true"></div>
          <header class="panel-header">
            <div>
              <span class="section-kicker">REGIONAL DISTRIBUTION</span>
              <h2>地域分布排行</h2>
              <p>按省级行政区统计古建筑数量，展示数量前12位</p>
            </div>
            <MapPin :size="25" />
          </header>
          <div class="horizontal-chart">
            <div
              v-for="(item, index) in provinceRanking"
              :key="item.name"
              class="bar-row"
            >
              <span class="rank">{{ String(index + 1).padStart(2, "0") }}</span>
              <strong>{{ item.name }}</strong>
              <div class="bar-track">
                <i
                  :style="{
                    width: barWidth(item.count, provinceRanking),
                    background: palette[index % palette.length],
                  }"
                ></i>
              </div>
              <b>{{ item.count }}</b>
            </div>
          </div>
        </article>

        <article class="chart-panel era-panel">
          <header class="panel-header">
            <div>
              <span class="section-kicker">DYNASTY PROFILE</span>
              <h2>建造时代分布</h2>
              <p>{{ selectedProvince || "全国" }}古建筑时代数量排行</p>
            </div>
            <History :size="25" />
          </header>
          <div class="column-chart">
            <div
              v-for="(item, index) in eraRanking.slice(0, 8)"
              :key="item.name"
              class="column-item"
            >
              <span>{{ item.count }}</span>
              <div class="column-track">
                <i
                  :style="{
                    height: barWidth(item.count, eraRanking),
                    background: `linear-gradient(180deg, ${palette[index % palette.length]}, #d9bd86)`,
                  }"
                ></i>
              </div>
              <strong :title="item.name">{{ item.name }}</strong>
            </div>
          </div>
        </article>
      </section>

      <section class="analysis-grid secondary-grid">
        <article class="chart-panel period-panel">
          <header class="panel-header compact">
            <div>
              <span class="section-kicker">HISTORICAL PERIOD</span>
              <h2>历史时期构成</h2>
            </div>
            <ScrollText :size="23" />
          </header>
          <div class="donut-layout">
            <div class="donut-chart" :style="donutStyle">
              <div>
                <strong>{{ filteredBuildings.length }}</strong>
                <span>建筑记录</span>
              </div>
            </div>
            <ul class="legend-list">
              <li v-for="(item, index) in periodRanking" :key="item.name">
                <i :style="{ background: palette[index % palette.length] }"></i>
                <span>{{ item.name }}</span>
                <strong>{{ item.count }}</strong>
                <em>{{ percentage(item.count) }}%</em>
              </li>
            </ul>
          </div>
        </article>

        <article class="chart-panel protection-panel ornate-panel">
          <div class="ornate-frame" aria-hidden="true"></div>
          <header class="panel-header compact">
            <div>
              <span class="section-kicker">HERITAGE PROTECTION</span>
              <h2>保护级别统计</h2>
            </div>
            <Crown :size="23" />
          </header>
          <div class="protection-list">
            <div v-for="(item, index) in protectionRanking" :key="item.name">
              <span><ShieldCheck :size="14" />{{ item.name }}</span>
              <div>
                <i
                  :style="{
                    width: barWidth(item.count, protectionRanking),
                    background: palette[index % palette.length],
                  }"
                ></i>
              </div>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
        </article>

        <article class="chart-panel quality-panel">
          <header class="panel-header compact">
            <div>
              <span class="section-kicker">DATA COMPLETENESS</span>
              <h2>数据完整度</h2>
            </div>
            <BookOpenCheck :size="23" />
          </header>
          <div class="quality-list">
            <div>
              <span><History :size="15" />时代信息</span>
              <strong>{{ percentage(eraKnownCount) }}%</strong>
              <i><b :style="{ width: `${percentage(eraKnownCount)}%` }"></b></i>
            </div>
            <div>
              <span><ShieldCheck :size="15" />保护信息</span>
              <strong>{{ percentage(protectionKnownCount) }}%</strong>
              <i
                ><b
                  :style="{ width: `${percentage(protectionKnownCount)}%` }"
                ></b
              ></i>
            </div>
            <div>
              <span><ScrollText :size="15" />摘要语料</span>
              <strong>{{ percentage(summaryCount) }}%</strong>
              <i><b :style="{ width: `${percentage(summaryCount)}%` }"></b></i>
            </div>
            <div>
              <span><Image :size="15" />建筑图片</span>
              <strong>{{ percentage(imageCount) }}%</strong>
              <i><b :style="{ width: `${percentage(imageCount)}%` }"></b></i>
            </div>
          </div>
        </article>
      </section>

      <section class="insight-strip">
        <span class="insight-symbol"><Sparkles :size="20" /></span>
        <div>
          <small>AUTOMATIC INSIGHT</small>
          <strong>图谱洞察</strong>
        </div>
        <p v-if="leadingProvince && leadingEra">
          当前范围内，<b>{{ leadingProvince.name }}</b
          >收录数量最高，共{{ leadingProvince.count }}座；<b>{{
            leadingEra.name
          }}</b
          >为数量最多的建造时代，共{{ leadingEra.count }}座。时代信息覆盖率为{{
            percentage(eraKnownCount)
          }}%，摘要语料覆盖率为{{ percentage(summaryCount) }}%。
        </p>
        <Database :size="30" />
      </section>
    </template>
  </main>
</template>

<style scoped>
.analysis-page {
  --ink: #3f342e;
  --muted: #806f63;
  --red: #943a32;
  --gold: #b4874f;
  min-height: 100vh;
  padding: 30px clamp(18px, 3.5vw, 58px) 54px;
  color: var(--ink);
  /* 不铺底色，直接使用全局 body 背景，消除"大底框"观感 */
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

.hero-section {
  position: relative;
  min-height: 145px;
  display: flex;
  align-items: center;
  overflow: hidden;
  padding: 22px 31px;
  border: 1px solid rgba(150, 83, 54, 0.22);
  border-radius: 6px 6px 22px 22px;
  background: rgba(255, 251, 241, 0.92);
  box-shadow: 0 14px 35px rgba(82, 53, 35, 0.08);
}

.hero-copy {
  position: relative;
  z-index: 2;
  max-width: 680px;
}

.eyebrow,
.section-kicker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #a26e3c;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
}

.hero-copy h1 {
  margin: 8px 0 7px;
  color: #7d2926;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: clamp(35px, 4vw, 52px);
  font-weight: 600;
  letter-spacing: 0.12em;
}

.hero-copy p {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.8;
}

.hero-palace {
  position: absolute;
  right: 1%;
  bottom: -42px;
  width: 430px;
  height: 220px;
  opacity: 0.16;
  background: url("../assets/hero-palace-watermark.png") right bottom / contain
    no-repeat;
}

.toolbar-panel {
  display: grid;
  grid-template-columns: 1fr 230px auto;
  align-items: center;
  gap: 16px;
  margin-top: 22px;
  padding: 17px 21px;
  border: 1px solid rgba(164, 118, 68, 0.32);
  border-radius: 8px;
  background: rgba(255, 251, 239, 0.8);
  box-shadow: 0 10px 30px rgba(81, 52, 34, 0.06);
}

.toolbar-title {
  display: flex;
  align-items: center;
  gap: 11px;
}

.toolbar-title > div {
  display: grid;
  gap: 2px;
}

.toolbar-title strong {
  color: #75362f;
  font-size: 16px;
}

.toolbar-title small {
  color: var(--muted);
  font-size: 11px;
}

.round-icon {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  color: #f8e5b8;
  border-radius: 50%;
  background: linear-gradient(135deg, #a34036, #742720);
}

.toolbar-panel label {
  height: 39px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 11px;
  color: #9b6e3d;
  border: 1px solid #cdb384;
  border-radius: 7px;
  background: linear-gradient(#fff9e9, #f2e2bf);
}

.toolbar-panel select {
  width: 100%;
  color: #55453b;
  border: 0;
  outline: 0;
  background: transparent;
  font-family: inherit;
}

.toolbar-panel button,
.result-button {
  height: 39px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 17px;
  color: #fff8e8;
  border: 0;
  border-radius: 6px;
  background: linear-gradient(135deg, #a63e34, #76251f);
  box-shadow: 0 6px 14px rgba(113, 38, 31, 0.17);
  cursor: pointer;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 15px;
  margin-top: 18px;
}

.overview-card {
  position: relative;
  min-height: 112px;
  display: flex;
  align-items: center;
  gap: 14px;
  overflow: hidden;
  padding: 18px 19px;
  border: 1px solid rgba(174, 131, 78, 0.28);
  border-radius: 8px;
  background: rgba(255, 251, 239, 0.85);
  box-shadow: 0 9px 25px rgba(75, 48, 31, 0.06);
}

.card-watermark {
  position: absolute;
  right: -20px;
  bottom: -35px;
  width: 145px;
  height: 110px;
  opacity: 0.07;
  background: url("../assets/palace-watermark.png") right bottom / contain
    no-repeat;
}

.overview-icon {
  flex: 0 0 auto;
  width: 43px;
  height: 43px;
  display: grid;
  place-items: center;
  color: #8e3c33;
  border: 1px solid rgba(173, 126, 69, 0.32);
  border-radius: 50%;
  background: #f4e6c9;
}

.overview-card > div:not(.card-watermark) {
  position: relative;
  z-index: 1;
  min-width: 0;
}

.overview-card small,
.overview-card em {
  display: block;
  color: var(--muted);
  font-size: 11px;
  font-style: normal;
}

.overview-card p {
  margin: 2px 0 3px;
  color: #7b352f;
  font-size: 12px;
}

.overview-card p strong {
  margin-right: 4px;
  font-family: Georgia, serif;
  font-size: 27px;
  font-weight: 500;
}

.overview-card > b {
  position: absolute;
  right: 12px;
  top: 8px;
  color: rgba(134, 86, 47, 0.16);
  font-family: Georgia, serif;
  font-size: 22px;
  font-style: italic;
}

.analysis-grid {
  display: grid;
  gap: 17px;
  margin-top: 17px;
}

.primary-grid {
  grid-template-columns: 1.55fr 1fr;
}

.secondary-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.chart-panel {
  position: relative;
  min-width: 0;
  overflow: hidden;
  padding: 21px 22px 23px;
  border: 1px solid rgba(168, 122, 70, 0.29);
  border-radius: 8px;
  background: rgba(255, 252, 243, 0.86);
  box-shadow: 0 11px 30px rgba(74, 46, 29, 0.07);
}

.ornate-frame {
  position: absolute;
  inset: 0;
  z-index: 4;
  opacity: 0.24;
  background: url("../assets/search-card-frame-v2.png") center / 102% 135%
    no-repeat;
  pointer-events: none;
}

.chart-panel > *:not(.ornate-frame) {
  position: relative;
  z-index: 1;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 15px;
  padding-bottom: 14px;
  color: #a47743;
  border-bottom: 1px solid rgba(169, 126, 77, 0.18);
}

.panel-header.compact {
  padding-bottom: 12px;
}

.panel-header h2 {
  margin: 4px 0 2px;
  color: #6e342f;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 21px;
  font-weight: 600;
}

.panel-header p {
  margin: 0;
  color: var(--muted);
  font-size: 11px;
}

.horizontal-chart {
  display: grid;
  gap: 9px;
  margin-top: 16px;
}

.bar-row {
  display: grid;
  grid-template-columns: 25px 68px 1fr 42px;
  align-items: center;
  gap: 9px;
  font-size: 11px;
}

.bar-row .rank {
  color: #aa8b67;
  font-family: Georgia, serif;
  font-size: 10px;
}

.bar-row strong {
  overflow: hidden;
  color: #675248;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bar-track {
  height: 8px;
  overflow: hidden;
  border-radius: 10px;
  background: #eadfc9;
}

.bar-track i {
  height: 100%;
  display: block;
  border-radius: inherit;
}

.bar-row b {
  color: #8a4338;
  font-family: Georgia, serif;
  text-align: right;
}

.column-chart {
  height: 285px;
  display: flex;
  align-items: flex-end;
  gap: 9px;
  padding-top: 26px;
}

.column-item {
  min-width: 0;
  height: 100%;
  flex: 1;
  display: grid;
  grid-template-rows: 18px 1fr 38px;
  align-items: end;
  gap: 5px;
  text-align: center;
}

.column-item > span {
  color: #875144;
  font-family: Georgia, serif;
  font-size: 10px;
}

.column-track {
  position: relative;
  width: 65%;
  height: 100%;
  justify-self: center;
  overflow: hidden;
  border-radius: 4px 4px 0 0;
  background: repeating-linear-gradient(
    to top,
    rgba(207, 186, 150, 0.21) 0,
    rgba(207, 186, 150, 0.21) 1px,
    transparent 1px,
    transparent 25%
  );
}

.column-track i {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  min-height: 4px;
  border-radius: inherit;
  opacity: 0.88;
}

.column-item strong {
  align-self: start;
  overflow: hidden;
  color: #6f5a4e;
  font-size: 10px;
  font-weight: 500;
  line-height: 1.35;
  text-overflow: ellipsis;
}

.donut-layout {
  display: grid;
  grid-template-columns: 125px 1fr;
  align-items: center;
  gap: 17px;
  min-height: 205px;
  padding-top: 12px;
}

.donut-chart {
  width: 120px;
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  border-radius: 50%;
  box-shadow: inset 0 0 0 1px rgba(111, 68, 38, 0.12);
}

.donut-chart > div {
  width: 67px;
  aspect-ratio: 1;
  display: grid;
  place-content: center;
  border-radius: 50%;
  background: #faf2e2;
  text-align: center;
}

.donut-chart strong {
  color: #7e372f;
  font-family: Georgia, serif;
  font-size: 19px;
}

.donut-chart span {
  color: #8b7868;
  font-size: 9px;
}

.legend-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.legend-list li {
  display: grid;
  grid-template-columns: 8px 1fr 35px 40px;
  align-items: center;
  gap: 7px;
  color: #705c50;
  font-size: 10px;
}

.legend-list li > i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.legend-list strong {
  color: #7e4036;
  text-align: right;
}

.legend-list em {
  color: #9b8979;
  font-style: normal;
  text-align: right;
}

.protection-list,
.quality-list {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}

.protection-list > div {
  display: grid;
  grid-template-columns: 1fr 1.1fr 36px;
  align-items: center;
  gap: 8px;
}

.protection-list span,
.quality-list span {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #70594d;
  font-size: 10px;
}

.protection-list > div > div {
  height: 6px;
  overflow: hidden;
  border-radius: 8px;
  background: #eadfc9;
}

.protection-list i {
  height: 100%;
  display: block;
  border-radius: inherit;
}

.protection-list strong {
  color: #8b463b;
  font-family: Georgia, serif;
  font-size: 11px;
  text-align: right;
}

.quality-list > div {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 7px 10px;
}

.quality-list strong {
  color: #8b463b;
  font-family: Georgia, serif;
  font-size: 11px;
}

.quality-list > div > i {
  grid-column: 1 / -1;
  height: 7px;
  overflow: hidden;
  border-radius: 8px;
  background: #eadfc9;
}

.quality-list b {
  height: 100%;
  display: block;
  border-radius: inherit;
  background: linear-gradient(90deg, #a5483c, #c7a05d);
}

.insight-strip {
  display: grid;
  grid-template-columns: auto auto 1fr auto;
  align-items: center;
  gap: 14px;
  margin-top: 17px;
  padding: 17px 21px;
  border: 1px solid rgba(163, 115, 64, 0.28);
  border-radius: 8px;
  background:
    url("../assets/palace-watermark.png") right -15px bottom -65px / 225px auto
      no-repeat,
    rgba(251, 244, 228, 0.88);
}

.insight-symbol {
  width: 39px;
  height: 39px;
  display: grid;
  place-items: center;
  color: #f5dfaa;
  border-radius: 50%;
  background: #8d372f;
}

.insight-strip > div {
  display: grid;
}

.insight-strip small {
  color: #aa7c49;
  font-size: 8px;
  letter-spacing: 1px;
}

.insight-strip strong {
  color: #773a33;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 17px;
}

.insight-strip p {
  margin: 0;
  color: #725d51;
  font-size: 11px;
  line-height: 1.8;
}

.insight-strip p b {
  color: #913b33;
}

.insight-strip > svg {
  color: rgba(157, 106, 57, 0.36);
}

.loading-state {
  min-height: 330px;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 10px;
  margin-top: 18px;
  color: #987345;
}

.loading-state strong {
  color: #73453b;
}

.loading-state span {
  color: var(--muted);
  font-size: 11px;
}

.error-message {
  margin: 15px 0 0;
  padding: 10px 13px;
  color: #8e302b;
  border: 1px solid rgba(160, 57, 49, 0.22);
  border-radius: 6px;
  background: rgba(255, 240, 226, 0.75);
  font-size: 12px;
}

.spinning {
  animation: spin 0.85s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1120px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .primary-grid,
  .secondary-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .analysis-page {
    padding-inline: 14px;
  }

  .toolbar-panel {
    grid-template-columns: 1fr;
  }

  .overview-grid {
    grid-template-columns: 1fr;
  }

  .hero-palace {
    opacity: 0.08;
  }

  .bar-row {
    grid-template-columns: 22px 60px 1fr 35px;
  }

  .donut-layout {
    grid-template-columns: 1fr;
    justify-items: center;
  }

  .legend-list {
    width: 100%;
  }

  .insight-strip {
    grid-template-columns: auto 1fr;
  }

  .insight-strip p {
    grid-column: 1 / -1;
  }

  .insight-strip > svg {
    display: none;
  }
}
</style>
