<template>
  <main class="search-page">
    <section class="page-banner">
      <div class="banner-copy">
        <span class="eyebrow">KNOWLEDGE RETRIEVAL</span>
        <h1>古建筑高级检索</h1>
        <p>
          依据名称、地域、建造时代和保护级别，从知识图谱中组合检索中华古建筑。
        </p>
      </div>
      <img
        src="../assets/hero-palace-watermark.png"
        class="banner-building"
        alt=""
      />
    </section>

    <section class="heritage-gallery" aria-hidden="true">
      <div class="gallery-title">
        <span>千年营造</span><i></i><strong>中华古建筑图鉴</strong><i></i
        ><span>一览古今</span>
      </div>
      <div class="gallery-scenes">
        <div class="scene scene-pagoda"><span>古塔遗韵</span></div>
        <div class="scene scene-palace"><span>宫殿营造</span></div>
        <div class="scene scene-gate"><span>城楼古迹</span></div>
      </div>
    </section>

    <section class="search-panel">
      <div class="panel-title">
        <SlidersHorizontal :size="20" /><span>组合检索条件</span>
      </div>
      <div class="filter-grid">
        <label class="field keyword-field">
          <span>建筑名称</span>
          <div class="input-wrap">
            <Search :size="18" /><input
              v-model.trim="query.keyword"
              placeholder="请输入古建筑名称"
              @keyup.enter="startSearch"
            />
          </div>
        </label>
        <label class="field"
          ><span>所在省份</span
          ><select v-model="query.province">
            <option value="">全部省份</option>
            <option v-for="item in filters.provinces" :key="item" :value="item">
              {{ item }}
            </option>
          </select></label
        >
        <label class="field"
          ><span>建造时代</span
          ><select v-model="query.era">
            <option value="">全部时代</option>
            <option v-for="item in filters.eras" :key="item" :value="item">
              {{ item }}
            </option>
          </select></label
        >
        <label class="field"
          ><span>保护级别</span
          ><select v-model="query.protection">
            <option value="">全部级别</option>
            <option
              v-for="item in filters.protections"
              :key="item"
              :value="item"
            >
              {{ item }}
            </option>
          </select></label
        >
      </div>
      <div class="search-actions">
        <button class="reset-button" @click="resetSearch">
          <RotateCcw :size="17" />重置条件
        </button>
        <button class="search-button" @click="startSearch">
          <Search :size="18" />开始检索
        </button>
      </div>
    </section>

    <section class="result-section">
      <div class="section-heading">
        <div>
          <span class="eyebrow">SEARCH RESULTS</span>
          <h2>知识图谱检索结果</h2>
        </div>
        <p>
          共检索到 <strong>{{ total }}</strong> 条古建筑记录
        </p>
      </div>
      <div v-if="loading" class="state-card">
        正在从 Neo4j 知识图谱中查询数据……
      </div>
      <div v-else-if="errorMessage" class="state-card error">
        {{ errorMessage }}
      </div>
      <div v-else-if="buildings.length === 0" class="state-card">
        暂未检索到符合条件的古建筑，请调整筛选条件。
      </div>
      <div v-else class="building-grid">
        <article
          v-for="building in buildings"
          :key="building.record_id"
          class="building-card"
        >
          <div class="card-content">
            <div class="card-number">
              {{ building.record_id || "古建档案" }}
            </div>
            <h3>{{ building.name || "未命名古建筑" }}</h3>
            <div class="meta-list">
              <p>
                <MapPin :size="16" /><span>{{
                  building.province || "地点待考证"
                }}</span>
              </p>
              <p>
                <Clock3 :size="16" /><span>{{
                  building.era || "时代待考证"
                }}</span>
              </p>
              <p>
                <Landmark :size="16" /><span>{{
                  building.category || "古建筑"
                }}</span>
              </p>
              <p>
                <ShieldCheck :size="16" /><span>{{
                  building.protection_level || "保护级别待考证"
                }}</span>
              </p>
            </div>
            <button
              class="detail-button"
              @click="openDetail(building)"
            >
              查看知识详情<ChevronRight :size="17" />
            </button>
          </div>
        </article>
      </div>
      <div v-if="total > pageSize" class="pagination">
        <button :disabled="page === 1" @click="changePage(page - 1)">
          上一页
        </button>
        <span>第 {{ page }} / {{ totalPages }} 页</span>
        <button :disabled="page >= totalPages" @click="changePage(page + 1)">
          下一页
        </button>
      </div>
    </section>

    <div v-if="detailVisible" class="drawer-mask" @click.self="closeDetail">
      <aside class="detail-drawer">
        <button class="close-button" @click="closeDetail">
          <X :size="21" />
        </button>
        <span class="eyebrow">ARCHITECTURE PROFILE</span>
        <h2>{{ detail.name || "古建筑详情" }}</h2>
        <div class="detail-divider"></div>
        <div class="detail-photo" :class="{ placeholder: !detail.image_url }">
          <div class="detail-photo-frame" aria-hidden="true"></div>
          <img
            v-if="detail.image_url"
            :src="detail.image_url"
            :alt="detail.name || '古建筑图片'"
            loading="lazy"
          />
          <template v-else>
            <Landmark :size="42" />
            <em class="no-image-label">暂无可用图片</em>
          </template>
        </div>
        <div v-if="detailLoading" class="detail-state">
          正在读取知识图谱详情……
        </div>
        <div v-else-if="detailError" class="detail-state detail-error">
          {{ detailError }}
        </div>
        <dl>
          <div>
            <dt>记录编号</dt>
            <dd>{{ detail.record_id || "—" }}</dd>
          </div>
          <div>
            <dt>所在省份</dt>
            <dd>{{ detail.province || "—" }}</dd>
          </div>
          <div>
            <dt>具体地点</dt>
            <dd>{{ detail.location || "—" }}</dd>
          </div>
          <div>
            <dt>建造时代</dt>
            <dd>{{ detail.era || "—" }}</dd>
          </div>
          <div>
            <dt>建筑类别</dt>
            <dd>{{ detail.category || "—" }}</dd>
          </div>
          <div>
            <dt>保护级别</dt>
            <dd>{{ detail.protection_level || "—" }}</dd>
          </div>
        </dl>
        <div v-if="detail.summary_text" class="summary">
          <h3>建筑简介</h3>
          <p>{{ detail.summary_text }}</p>
        </div>
        <img
          src="../assets/palace-watermark.png"
          class="drawer-watermark"
          alt=""
        />
      </aside>
    </div>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import {
  ChevronRight,
  Clock3,
  Landmark,
  MapPin,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  X,
} from "lucide-vue-next";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const query = reactive({ keyword: "", province: "", era: "", protection: "" });
const filters = reactive({ provinces: [], eras: [], protections: [] });
const buildings = ref([]),
  total = ref(0),
  page = ref(1),
  loading = ref(false),
  errorMessage = ref("");
const pageSize = 12;
const detailVisible = ref(false),
  detail = ref({}),
  detailLoading = ref(false),
  detailError = ref("");
const totalPages = computed(() =>
  Math.max(1, Math.ceil(total.value / pageSize)),
);

function listValue(data, ...keys) {
  for (const key of keys)
    if (Array.isArray(data?.[key]))
      return data[key]
        .map((item) => (typeof item === "object" ? item.name : item))
        .filter(Boolean);
  return [];
}

async function loadFilters() {
  try {
    const response = await fetch(`${API_BASE}/api/filters`);
    if (!response.ok) throw new Error();
    const data = await response.json();
    filters.provinces = listValue(data, "provinces", "province");
    filters.eras = listValue(data, "eras", "periods", "era");
    filters.protections = listValue(
      data,
      "protections",
      "protection_levels",
      "protection",
    );
  } catch (error) {
    console.error("筛选条件加载失败", error);
  }
}

async function searchBuildings() {
  loading.value = true;
  errorMessage.value = "";
  const params = new URLSearchParams({
    page: String(page.value),
    page_size: String(pageSize),
  });
  Object.entries(query).forEach(
    ([key, value]) => value && params.append(key, value),
  );
  try {
    const response = await fetch(`${API_BASE}/api/buildings?${params}`);
    if (!response.ok) throw new Error();
    const data = await response.json();
    buildings.value =
      data.items || data.results || data.buildings || data.data || [];
    total.value = data.total ?? data.total_count ?? buildings.value.length;
  } catch {
    buildings.value = [];
    total.value = 0;
    errorMessage.value = "无法连接检索服务，请确认 FastAPI 和 Neo4j 已启动。";
  } finally {
    loading.value = false;
  }
}

function startSearch() {
  page.value = 1;
  searchBuildings();
}
function resetSearch() {
  Object.assign(query, { keyword: "", province: "", era: "", protection: "" });
  page.value = 1;
  searchBuildings();
}
function changePage(value) {
  page.value = value;
  searchBuildings();
  window.scrollTo({ top: 420, behavior: "smooth" });
}
function unwrapBuilding(payload) {
  if (!payload || typeof payload !== "object") return {};

  const candidate =
    payload.building ??
    payload.item ??
    payload.detail ??
    payload.result ??
    payload.data ??
    payload;

  if (Array.isArray(candidate)) return candidate[0] ?? {};

  if (candidate?.building && typeof candidate.building === "object") {
    return candidate.building;
  }

  return candidate && typeof candidate === "object" ? candidate : {};
}

async function openDetail(building) {
  const recordId = building?.record_id;
  if (!recordId) return;

  detail.value = { ...building };
  detailVisible.value = true;
  detailLoading.value = true;
  detailError.value = "";

  try {
    const response = await fetch(
      `${API_BASE}/api/buildings/${encodeURIComponent(recordId)}`,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const payload = await response.json();
    const loadedDetail = unwrapBuilding(payload);

    detail.value = {
      ...building,
      ...loadedDetail,
      record_id: loadedDetail.record_id || building.record_id,
      name: loadedDetail.name || building.name,
    };
  } catch (error) {
    console.error("古建筑详情加载失败", error);
    detailError.value = "详细介绍暂时无法读取，以下为检索结果中的基础信息。";
  } finally {
    detailLoading.value = false;
  }
}
function closeDetail() {
  detailVisible.value = false;
  detail.value = {};
  detailLoading.value = false;
  detailError.value = "";
}
onMounted(async () => {
  await loadFilters();
  await searchBuildings();
});
</script>

<style scoped>
.search-page {
  display: grid;
  gap: 26px;
  padding-bottom: 48px;
  color: #29443e;
}
.page-banner,
.heritage-gallery,
.search-panel,
.result-section {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(150, 83, 54, 0.22);
  background: rgba(255, 251, 241, 0.92);
  box-shadow: 0 14px 35px rgba(82, 53, 35, 0.08);
}
.page-banner {
  min-height: 205px;
  display: flex;
  align-items: center;
  padding: 38px 54px;
  border-radius: 6px 6px 22px 22px;
}
.banner-copy {
  position: relative;
  z-index: 2;
  max-width: 720px;
}
.eyebrow {
  color: #b07a39;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 3px;
}
h1,
h2,
h3 {
  font-family: "STKaiti", "KaiTi", serif;
}
h1 {
  margin: 8px 0 12px;
  color: #8f3328;
  font-size: clamp(32px, 4vw, 50px);
  font-weight: 600;
}
.page-banner p {
  color: #6d736c;
  line-height: 1.9;
}
.banner-building {
  position: absolute;
  right: -35px;
  bottom: -18px;
  width: 58%;
  max-height: 210px;
  object-fit: contain;
  object-position: right bottom;
  opacity: 0.2;
  pointer-events: none;
}
.heritage-gallery {
  padding: 20px 28px 25px;
  border-radius: 15px;
  background: linear-gradient(
    180deg,
    rgba(255, 251, 241, 0.96),
    rgba(246, 235, 215, 0.94)
  );
}
.heritage-gallery:before {
  content: "";
  position: absolute;
  inset: 7px;
  border: 1px solid rgba(184, 139, 78, 0.16);
  border-radius: 10px;
  pointer-events: none;
}
.gallery-title {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
  margin-bottom: 15px;
  color: #96603e;
  font-family: "STKaiti", "KaiTi", serif;
}
.gallery-title strong {
  color: #89372e;
  font-size: 22px;
  font-weight: 500;
  letter-spacing: 5px;
}
.gallery-title span {
  color: #ad8a62;
  font-size: 13px;
  letter-spacing: 2px;
}
.gallery-title i {
  width: 45px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #bd8b50, transparent);
}
.gallery-scenes {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: 0.9fr 1.35fr 0.9fr;
  gap: 15px;
}
.scene {
  position: relative;
  overflow: hidden;
  height: 128px;
  border-radius: 10px;
  border: 1px solid rgba(165, 97, 59, 0.19);
  background-image: url("../assets/hero-palace-watermark.png");
  background-repeat: no-repeat;
  background-size: 640px auto;
  background-color: rgba(250, 242, 226, 0.65);
}
.scene:after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 45%, rgba(127, 46, 38, 0.78));
}
.scene span {
  position: absolute;
  left: 17px;
  bottom: 11px;
  z-index: 2;
  color: #fff8e7;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 17px;
  letter-spacing: 3px;
}
.scene-pagoda {
  background-position: left bottom;
}
.scene-palace {
  background-position: center bottom;
}
.scene-gate {
  background-position: right bottom;
}
.search-panel,
.result-section {
  padding: 30px 34px;
  border-radius: 15px;
}
.search-panel:after,
.result-section:after {
  content: "";
  position: absolute;
  right: 18px;
  bottom: 8px;
  width: 250px;
  height: 115px;
  background: url("../assets/palace-watermark.png") right bottom/contain
    no-repeat;
  opacity: 0.055;
  pointer-events: none;
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 23px;
  color: #96382d;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 21px;
}
.filter-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1.5fr repeat(3, 1fr);
  gap: 18px;
}
.field {
  display: grid;
  gap: 9px;
}
.field > span {
  color: #6f665b;
  font-size: 14px;
}
.input-wrap {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 14px;
  border: 1px solid #dcc9aa;
  border-radius: 8px;
  background: rgba(255, 253, 247, 0.92);
  color: #aa6d3f;
}
input,
select {
  width: 100%;
  height: 46px;
  border: 1px solid #dcc9aa;
  border-radius: 8px;
  outline: none;
  background: rgba(255, 253, 247, 0.92);
  color: #314741;
  font: inherit;
}
input {
  border: 0;
  background: transparent;
}
select {
  padding: 0 13px;
}
select:focus,
.input-wrap:focus-within {
  border-color: #a54a38;
  box-shadow: 0 0 0 3px rgba(165, 74, 56, 0.09);
}
.search-actions {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 22px;
}
button {
  font: inherit;
  cursor: pointer;
}
.reset-button,
.search-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-width: 132px;
  height: 43px;
  border-radius: 7px;
}
.reset-button {
  border: 1px solid #cba98a;
  background: #fffaf0;
  color: #76594a;
}
.search-button {
  border: 1px solid #9b342b;
  background: linear-gradient(135deg, #a83e31, #842b25);
  color: #fff9e9;
  box-shadow: 0 8px 18px rgba(132, 43, 37, 0.18);
}
.section-heading {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 25px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(164, 75, 54, 0.22);
}
.section-heading h2 {
  margin: 5px 0 0;
  color: #2d5148;
  font-size: 27px;
  font-weight: 500;
}
.section-heading p {
  color: #77817b;
  font-size: 14px;
}
.section-heading strong {
  margin: 0 5px;
  color: #9e3b30;
  font-size: 19px;
}
.building-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 19px;
}
.building-card {
  position: relative;
  overflow: hidden;
  min-height: 310px;
  padding: 48px 35px 38px;
  border: 0;
  border-radius: 8px;
  background-color: rgba(255, 251, 240, 0.96);
  background-image:
    url("../assets/stat-card-frame-elegant.png"),
    linear-gradient(180deg, #fffdf7, #f8edda);
  background-repeat: no-repeat, no-repeat;
  /* 只放大装饰边框并稍微上移，卡片本身尺寸保持不变。 */
  background-position:
    center 47%,
    center;
  background-size:
    112% 112%,
    cover;
  box-shadow: 0 12px 25px rgba(91, 54, 34, 0.08);
  transition: 0.25s ease;
}
.building-card:hover {
  transform: translateY(-5px);
  filter: saturate(1.04);
  box-shadow: 0 18px 34px rgba(91, 54, 34, 0.14);
}
.building-card::after {
  content: "";
  position: absolute;
  right: 23px;
  bottom: 24px;
  width: 155px;
  height: 70px;
  background: url("../assets/palace-watermark.png") right bottom/contain
    no-repeat;
  opacity: 0.07;
  pointer-events: none;
}
.card-content {
  position: relative;
  z-index: 2;
}
.card-number {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 3px 10px;
  border: 1px solid rgba(172, 111, 67, 0.25);
  border-radius: 3px;
  background: rgba(184, 132, 72, 0.09);
  color: #9c663f;
  font-size: 11px;
  letter-spacing: 1.4px;
}
.building-card h3 {
  margin: 9px 0 17px;
  color: #8c352b;
  font-size: 23px;
  font-weight: 600;
}
.meta-list {
  display: grid;
  gap: 10px;
}
.meta-list p {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: #63706a;
  font-size: 14px;
}
.meta-list svg {
  color: #a5663c;
}
.detail-button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  margin-top: 20px;
  padding: 10px 13px;
  border: 1px solid rgba(132, 42, 34, 0.42);
  border-radius: 6px;
  background: linear-gradient(135deg, #a43e31, #873028);
  color: #fff8e5;
  box-shadow: 0 7px 15px rgba(121, 43, 34, 0.14);
}
.detail-button:hover {
  background: linear-gradient(135deg, #b34b3b, #92372d);
}
.state-card {
  position: relative;
  z-index: 1;
  padding: 55px;
  text-align: center;
  color: #6d756f;
}
.state-card.error {
  color: #9d352e;
}
.pagination {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  margin-top: 28px;
}
.pagination button {
  padding: 8px 18px;
  border: 1px solid #c69a71;
  border-radius: 6px;
  background: #fffaf0;
  color: #823c32;
}
.pagination button:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}
.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  justify-content: flex-end;
  background: rgba(34, 39, 35, 0.3);
  backdrop-filter: blur(3px);
}
.detail-drawer {
  position: relative;
  overflow-y: auto;
  width: min(480px, 92vw);
  height: 100%;
  padding: 44px 38px;
  background: #fbf4e8;
  box-shadow: -18px 0 45px rgba(47, 36, 28, 0.2);
}
.close-button {
  position: absolute;
  top: 23px;
  right: 24px;
  display: grid;
  place-items: center;
  border: 0;
  background: transparent;
  color: #8e4034;
}
.detail-drawer h2 {
  margin: 8px 0 16px;
  color: #8e342b;
  font-size: 34px;
}
.detail-divider {
  height: 2px;
  margin-bottom: 23px;
  background: linear-gradient(90deg, #9c392f, #cda15b, transparent);
}
/* 详情配图：与智能推荐页一致的建筑图片 + bk03.png 描金边框 */
.detail-photo {
  position: relative;
  z-index: 1;
  height: 200px;
  margin: 0 0 36px;
  background: #eee3cf;
}
.detail-photo-frame {
  position: absolute;
  inset: -32px -16px;
  z-index: 3;
  background: url("../assets/bk03.png") center / 100% 100% no-repeat;
  pointer-events: none;
}
.detail-photo img {
  position: relative;
  z-index: 2;
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  border-radius: 2px;
}
.detail-photo.placeholder {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: rgba(141, 85, 50, 0.35);
  background: linear-gradient(145deg, #f3ead8, #e7d6bb);
}
.no-image-label {
  position: relative;
  z-index: 2;
  color: #9a806f;
  font-size: 12px;
  font-style: normal;
}
.detail-state {
  position: relative;
  z-index: 1;
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(180, 137, 79, 0.2);
  border-radius: 6px;
  background: rgba(255, 250, 238, 0.72);
  color: #8b765e;
  font-size: 13px;
}
.detail-state.detail-error {
  border-color: rgba(155, 57, 47, 0.16);
  color: #95483d;
}
.detail-drawer dl {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 5px;
}
.detail-drawer dl div {
  display: grid;
  grid-template-columns: 100px 1fr;
  padding: 11px 0;
  border-bottom: 1px dashed rgba(137, 84, 57, 0.2);
}
dt {
  color: #957153;
}
dd {
  margin: 0;
  color: #314943;
}
.summary {
  position: relative;
  z-index: 1;
  margin-top: 25px;
}
.summary h3 {
  color: #90372d;
}
.summary p {
  color: #5f6b65;
  line-height: 1.9;
}
.drawer-watermark {
  position: absolute;
  right: -35px;
  bottom: 15px;
  width: 360px;
  opacity: 0.08;
  pointer-events: none;
}
@media (max-width: 1100px) {
  .filter-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .building-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 700px) {
  .page-banner,
  .heritage-gallery,
  .search-panel,
  .result-section {
    padding: 25px 20px;
  }
  .filter-grid,
  .building-grid,
  .gallery-scenes {
    grid-template-columns: 1fr;
  }
  .section-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }
  .banner-building {
    width: 90%;
    opacity: 0.1;
  }
  .gallery-title span,
  .gallery-title i {
    display: none;
  }
  .scene {
    height: 110px;
    background-size: 520px auto;
  }
  .building-card {
    padding: 45px 31px 35px;
  }
}
</style>
