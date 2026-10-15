<script setup>
import { computed, onMounted, ref } from "vue";
import {
  Building2,
  ChevronRight,
  Compass,
  Crown,
  History,
  Landmark,
  LoaderCircle,
  MapPin,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
  Star,
  Tag,
  X,
} from "lucide-vue-next";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const seedId = ref("");
const seedQuery = ref("");
const provincePreference = ref("");
const locationPreference = ref("");
const eraPreference = ref("");
const typePreference = ref("");
const componentPreference = ref("");
const materialPreference = ref("");
const personPreference = ref("");
const protectionPreference = ref("");
const buildingCatalog = ref([]);
const databaseFilters = ref({
  provinces: [],
  locations: [],
  eras: [],
  types: [],
  components: [],
  materials: [],
  persons: [],
  protections: [],
});
const catalogLoading = ref(false);
const loading = ref(false);
const errorMessage = ref("");
const seedBuilding = ref(null);
const recommendations = ref([]);
const selectedBuilding = ref(null);

function uniqueOptions(key, filterKey) {
  return computed(() =>
    [
      ...new Set(
        [
          ...buildingCatalog.value.flatMap((item) => {
            const value = item[key];
            return Array.isArray(value) ? value : value ? [value] : [];
          }),
          ...databaseFilters.value[filterKey],
        ].filter(Boolean),
      ),
    ].sort((a, b) => a.localeCompare(b, "zh-CN")),
  );
}

const buildingOptions = computed(() =>
  [...buildingCatalog.value].sort((a, b) =>
    a.name.localeCompare(b.name, "zh-CN"),
  ),
);
const provinceOptions = uniqueOptions("province", "provinces");
const locationOptions = uniqueOptions("locations", "locations");
const eraOptions = uniqueOptions("era", "eras");
const typeOptions = uniqueOptions("type", "types");
const componentOptions = uniqueOptions("components", "components");
const materialOptions = uniqueOptions("materials", "materials");
const personOptions = uniqueOptions("persons", "persons");
const protectionOptions = uniqueOptions("protection", "protections");

function resolveSeedBuilding() {
  const query = seedQuery.value.trim().toLowerCase();
  if (!query) return null;

  return (
    buildingCatalog.value.find(
      (item) =>
        item.id.toLowerCase() === query || item.name.toLowerCase() === query,
    ) ??
    buildingCatalog.value.find((item) =>
      item.name.toLowerCase().includes(query),
    )
  );
}

function pick(object, keys, fallback = "") {
  for (const key of keys) {
    const value = object?.[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return fallback;
}

function unwrap(payload) {
  return payload?.data ?? payload ?? {};
}

function toList(value) {
  return Array.isArray(value)
    ? value.map((entry) => String(entry).trim()).filter(Boolean)
    : [];
}

function normalizeBuilding(item, index = 0) {
  const scoreValue = Number(
    pick(
      item,
      ["score", "similarity", "recommendation_score", "match_score"],
      NaN,
    ),
  );
  const score = Number.isFinite(scoreValue)
    ? Math.min(
        100,
        Math.max(0, scoreValue <= 1 ? scoreValue * 100 : scoreValue),
      )
    : null;

  return {
    id: String(pick(item, ["record_id", "id", "building_id"], `item-${index}`)),
    name: String(
      pick(item, ["name", "title", "article_title"], "未命名古建筑"),
    ),
    province: String(pick(item, ["province", "province_name"], "")),
    location: String(
      pick(item, ["location", "address", "specific_location"], ""),
    ),
    era: String(pick(item, ["era", "dynasty", "period"], "")),
    type: String(pick(item, ["category", "type", "building_type"], "")),
    protection: String(
      pick(item, ["protection_level", "protection", "protection_name"], ""),
    ),
    summary: String(pick(item, ["summary_text", "summary", "description"], "")),
    image: String(pick(item, ["image_url", "image", "cover"], "")),
    types: toList(item.types),
    locations: toList(item.locations),
    components: toList(item.components),
    materials: toList(item.materials),
    persons: toList(item.persons),
    score,
    reason: String(
      pick(item, ["reason", "recommendation_reason", "explanation"], ""),
    ),
    raw: item,
  };
}

function normalizeSeed(payload) {
  const data = unwrap(payload);
  const candidate = data.building ?? data.item ?? data.result ?? data;
  return normalizeBuilding(candidate);
}

function normalizeRecommendations(payload) {
  const data = unwrap(payload);
  const list = Array.isArray(data)
    ? data
    : (data.recommendations ??
      data.items ??
      data.results ??
      data.buildings ??
      []);
  return list.map(normalizeBuilding);
}

function textMatches(actual, expected) {
  if (!expected.trim()) return false;
  const left = String(actual ?? "").toLowerCase();
  const right = expected.trim().toLowerCase();
  return left.includes(right) || right.includes(left);
}

function listMatches(list, expected) {
  if (!expected.trim()) return false;
  return list.some((entry) => textMatches(entry, expected));
}

// 8 类可选条件：行政区、地点、时代、类型、构件、材料、人物、保护级别
const preferenceRules = computed(() => [
  { field: "province", label: "地域偏好", value: provincePreference.value },
  { field: "locations", label: "地点偏好", value: locationPreference.value, list: true },
  { field: "era", label: "时代偏好", value: eraPreference.value },
  { field: "type", label: "类型偏好", value: typePreference.value },
  { field: "components", label: "构件偏好", value: componentPreference.value, list: true },
  { field: "materials", label: "材料偏好", value: materialPreference.value, list: true },
  { field: "persons", label: "人物偏好", value: personPreference.value, list: true },
  { field: "protection", label: "保护级别偏好", value: protectionPreference.value },
]);

function ruleMatches(item, rule) {
  if (!rule.value.trim()) return true;
  return rule.list
    ? listMatches(item[rule.field] ?? [], rule.value)
    : textMatches(item[rule.field], rule.value);
}

function preferenceTags(item) {
  return preferenceRules.value
    .filter((rule) => rule.value.trim() && ruleMatches(item, rule))
    .map((rule) => rule.label);
}

function recommendationReasons(item) {
  if (item.reason) return [item.reason];

  const reasons = [];
  if (seedBuilding.value) {
    if (item.province && item.province === seedBuilding.value.province) {
      reasons.push(`与${seedBuilding.value.name}位于同一省级行政区`);
    }
    if (item.era && item.era === seedBuilding.value.era) {
      reasons.push(`同属${item.era}建筑`);
    }
    if (item.type && item.type === seedBuilding.value.type) {
      reasons.push(`建筑类别同为${item.type}`);
    }
  }

  preferenceTags(item).forEach((tag) => reasons.push(`符合${tag}`));
  return reasons.length ? reasons.slice(0, 3) : ["由知识图谱关联路径综合推荐"];
}

function matchesSelectedPreferences(item) {
  return preferenceRules.value.every((rule) => ruleMatches(item, rule));
}

const filteredRecommendations = computed(() => {
  const filtered = recommendations.value
    .filter(matchesSelectedPreferences)
    .map((item, index) => ({
      ...item,
      originalOrder: index,
      preferenceCount: preferenceTags(item).length,
    }));

  if (activePreferenceCount.value) {
    filtered.sort(
      (a, b) =>
        b.preferenceCount - a.preferenceCount ||
        (b.score ?? -1) - (a.score ?? -1) ||
        a.originalOrder - b.originalOrder,
    );
  }

  return filtered;
});

const displayedRecommendations = computed(() => filteredRecommendations.value);

const activePreferenceCount = computed(
  () => preferenceRules.value.filter((rule) => rule.value.trim()).length,
);

async function requestJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`接口返回 ${response.status}`);
  return response.json();
}

function normalizeFilterValues(values) {
  if (!Array.isArray(values)) return [];
  return values
    .map((value) =>
      typeof value === "string"
        ? value
        : String(pick(value, ["name", "value", "label"], "")),
    )
    .map((value) => value.trim())
    .filter(Boolean);
}

async function loadDatabaseFilters() {
  try {
    const payload = await requestJson(`${API_BASE_URL}/api/filters`);
    const data = unwrap(payload);
    databaseFilters.value = {
      provinces: normalizeFilterValues(
        pick(data, ["provinces", "province_options", "province"], []),
      ),
      locations: normalizeFilterValues(pick(data, ["locations"], [])),
      eras: normalizeFilterValues(
        pick(data, ["eras", "periods", "dynasties", "era_options"], []),
      ),
      types: normalizeFilterValues(
        pick(
          data,
          ["categories", "types", "building_types", "type_options"],
          [],
        ),
      ),
      components: normalizeFilterValues(pick(data, ["components"], [])),
      materials: normalizeFilterValues(pick(data, ["materials"], [])),
      persons: normalizeFilterValues(pick(data, ["persons"], [])),
      protections: normalizeFilterValues(
        pick(data, ["protections", "protection_levels"], []),
      ),
    };
  } catch {
    // 接口不可用时仍可使用从完整建筑目录汇总出的真实选项。
  }
}

async function loadBuildingCatalog() {
  catalogLoading.value = true;
  try {
    // 后端每页最多返回100条：先读取总数，再并发获取全部分页。
    const pageSize = 100;
    const firstPayload = await requestJson(
      `${API_BASE_URL}/api/buildings?page=1&page_size=${pageSize}`,
    );
    const firstData = unwrap(firstPayload);
    const firstList = Array.isArray(firstData)
      ? firstData
      : (firstData.items ?? firstData.results ?? firstData.buildings ?? []);
    const total = Number(
      firstData.total ?? firstData.pagination?.total ?? firstList.length,
    );
    const pageCount = Math.max(1, Math.ceil(total / pageSize));
    const remainingPayloads = await Promise.all(
      Array.from({ length: pageCount - 1 }, (_, index) =>
        requestJson(
          `${API_BASE_URL}/api/buildings?page=${index + 2}&page_size=${pageSize}`,
        ),
      ),
    );
    const remainingLists = remainingPayloads.flatMap((pagePayload) => {
      const pageData = unwrap(pagePayload);
      return Array.isArray(pageData)
        ? pageData
        : (pageData.items ?? pageData.results ?? pageData.buildings ?? []);
    });
    const completeList = [...firstList, ...remainingLists];
    const uniqueBuildings = new Map();
    completeList.forEach((item, index) => {
      const building = normalizeBuilding(item, index);
      if (building.id && !building.id.startsWith("item-")) {
        uniqueBuildings.set(building.id, building);
      }
    });

    buildingCatalog.value = [...uniqueBuildings.values()]
      .map(normalizeBuilding)
      .filter(
        (item) =>
          item.id &&
          !item.id.startsWith("item-") &&
          item.name !== "未命名古建筑",
      )
      .sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
  } catch (error) {
    errorMessage.value = `古建筑选项加载失败：${error.message}。请确认后端已经启动。`;
  } finally {
    catalogLoading.value = false;
  }
}

async function enrichRecommendationDetails(items) {
  return Promise.all(
    items.map(async (item) => {
      if (item.image && item.summary) return item;

      try {
        const payload = await requestJson(
          `${API_BASE_URL}/api/buildings/${encodeURIComponent(item.id)}`,
        );
        const detail = normalizeSeed(payload);

        return {
          ...detail,
          ...item,
          province: item.province || detail.province,
          location: item.location || detail.location,
          era: item.era || detail.era,
          type: item.type || detail.type,
          protection: item.protection || detail.protection,
          summary: item.summary || detail.summary,
          image: item.image || detail.image,
          score: item.score ?? detail.score,
          reason: item.reason || detail.reason,
        };
      } catch {
        return item;
      }
    }),
  );
}

function buildDefaultRecommendations() {
  // 未指定基准建筑与偏好时，对全部古建筑排序后整体推荐，不做数量截断。
  return [...buildingCatalog.value]
    .sort((a, b) => {
      const qualityA = [a.image, a.summary, a.protection, a.location].filter(
        Boolean,
      ).length;
      const qualityB = [b.image, b.summary, b.protection, b.location].filter(
        Boolean,
      ).length;
      return qualityB - qualityA || a.name.localeCompare(b.name, "zh-CN");
    })
    .map((item) => ({
      ...item,
      score: null,
      reason: "综合资料完整度与知识图谱关联的全库推荐",
    }));
}

function buildAttributeRecommendations(seed = null) {
  const preferenceWeights = [
    ["province", provincePreference.value, 0.22],
    ["era", eraPreference.value, 0.22],
    ["type", typePreference.value, 0.22],
  ];
  const seedWeights = [
    ["province", 0.28],
    ["era", 0.27],
    ["type", 0.25],
    ["protection", 0.2],
  ];

  const hasPreferences = preferenceWeights.some(([, value]) => value.trim());
  if (!seed && !hasPreferences) return buildDefaultRecommendations();

  return buildingCatalog.value
    .filter((item) => !seed || item.id !== seed.id)
    .map((item) => {
      let matchedWeight = 0;
      let availableWeight = 0;

      seedWeights.forEach(([key, weight]) => {
        if (!seed) return;
        if (!seed[key] || !item[key]) return;
        availableWeight += weight;
        if (item[key] === seed[key]) matchedWeight += weight;
      });

      preferenceWeights.forEach(([key, expected, weight]) => {
        if (!expected.trim()) return;
        availableWeight += weight;
        if (textMatches(item[key], expected)) matchedWeight += weight;
      });

      const score = availableWeight
        ? (matchedWeight / availableWeight) * 100
        : null;

      return {
        ...item,
        score,
        reason: "",
      };
    })
    .filter((item) => item.score !== null && item.score > 0)
    .sort((a, b) => b.score - a.score);
}

function mergeRecommendations(primary, secondary) {
  const merged = new Map();
  [...primary, ...secondary].forEach((item) => {
    const existing = merged.get(item.id);
    if (!existing) {
      merged.set(item.id, item);
      return;
    }
    merged.set(item.id, {
      ...item,
      ...existing,
      image: existing.image || item.image,
      summary: existing.summary || item.summary,
      reason: existing.reason || item.reason,
      score: existing.score ?? item.score,
    });
  });
  return [...merged.values()];
}

async function loadRecommendations() {
  const selectedSeed = resolveSeedBuilding();
  if (seedQuery.value.trim() && !selectedSeed) {
    errorMessage.value =
      "没有找到对应的古建筑，请从候选列表选择或输入更准确的名称。";
    return;
  }

  const id = selectedSeed?.id ?? "";
  seedId.value = id;

  loading.value = true;
  errorMessage.value = "";
  selectedBuilding.value = null;

  try {
    let normalizedRecommendations = [];

    if (id) {
      const [buildingResult, recommendationResult] = await Promise.all([
        requestJson(`${API_BASE_URL}/api/buildings/${encodeURIComponent(id)}`),
        requestJson(
          `${API_BASE_URL}/api/recommendations/${encodeURIComponent(id)}`,
        ),
      ]);

      seedBuilding.value = normalizeSeed(buildingResult);
      // 仅对图谱推荐接口返回的少量结果补全详情；目录内数据已含全部字段。
      const apiRecommendations = await enrichRecommendationDetails(
        normalizeRecommendations(recommendationResult).filter(
          (item) => item.id !== id,
        ),
      );

      const attributeCandidates = buildAttributeRecommendations(
        seedBuilding.value,
      );
      normalizedRecommendations = mergeRecommendations(
        apiRecommendations,
        attributeCandidates,
      );
    } else {
      seedBuilding.value = null;
      normalizedRecommendations = buildAttributeRecommendations();
    }

    recommendations.value = normalizedRecommendations;

    if (!recommendations.value.length) {
      errorMessage.value =
        "当前建筑暂无可计算的相似候选，请更换基准古建筑或选择旅游偏好。";
    }
  } catch (error) {
    seedBuilding.value = null;
    recommendations.value = [];
    errorMessage.value = `推荐加载失败：${error.message}。请确认后端与 Neo4j 已启动。`;
  } finally {
    loading.value = false;
  }
}

async function resetPreferences() {
  seedId.value = "";
  seedQuery.value = "";
  provincePreference.value = "";
  locationPreference.value = "";
  eraPreference.value = "";
  typePreference.value = "";
  componentPreference.value = "";
  materialPreference.value = "";
  personPreference.value = "";
  protectionPreference.value = "";
  await loadRecommendations();
}

function scoreText(score) {
  return score === null ? "图谱推荐" : `${score.toFixed(1)}%`;
}

onMounted(async () => {
  await Promise.all([loadBuildingCatalog(), loadDatabaseFilters()]);
  await loadRecommendations();
});
</script>

<template>
  <main class="recommend-page">
    <section class="hero-section">
      <div class="hero-copy">
        <span class="eyebrow"><Sparkles :size="15" /> INTELLIGENT TRAVEL</span>
        <h1>智能推荐</h1>
        <p>
          以知识图谱关联为基础，结合地域、时代与建筑类型偏好，发现值得探访的中华古建筑。
        </p>
      </div>
      <div class="hero-palace" aria-hidden="true"></div>
    </section>

    <section class="preference-panel">
      <div class="panel-heading">
        <div class="heading-icon"><Compass :size="23" /></div>
        <div>
          <strong>定制你的古建旅程</strong>
          <span
            >古建筑、行政区、地点、时代、类型、构件、材料、人物、保护级别均为可选下拉，
            可任选 0–8 项条件组合推荐</span
          >
        </div>
      </div>

      <div class="preference-form">
        <label class="seed-field">
          <span>基准古建筑（可选）</span>
          <div class="select-shell">
            <Landmark :size="17" />
            <select v-model="seedQuery" :disabled="catalogLoading">
              <option value="">
                {{
                  catalogLoading
                    ? "正在加载候选……"
                    : "不限，从全部古建筑中推荐"
                }}
              </option>
              <option
                v-for="building in buildingOptions"
                :key="building.id"
                :value="building.id"
              >
                {{ building.name
                }}{{ building.province ? ` · ${building.province}` : "" }}
              </option>
            </select>
          </div>
        </label>

        <label>
          <span>行政区（可选）</span>
          <div class="select-shell">
            <MapPin :size="16" />
            <select v-model="provincePreference">
              <option value="">不限行政区</option>
              <option
                v-for="province in provinceOptions"
                :key="province"
                :value="province"
              >
                {{ province }}
              </option>
            </select>
          </div>
        </label>

        <label>
          <span>地点（可选）</span>
          <div class="select-shell">
            <Route :size="16" />
            <select v-model="locationPreference">
              <option value="">不限地点</option>
              <option
                v-for="location in locationOptions"
                :key="location"
                :value="location"
              >
                {{ location }}
              </option>
            </select>
          </div>
        </label>

        <label>
          <span>时代（可选）</span>
          <div class="select-shell">
            <History :size="16" />
            <select v-model="eraPreference">
              <option value="">不限时代</option>
              <option v-for="era in eraOptions" :key="era" :value="era">
                {{ era }}
              </option>
            </select>
          </div>
        </label>

        <label>
          <span>类型（可选）</span>
          <div class="select-shell">
            <Building2 :size="16" />
            <select v-model="typePreference">
              <option value="">不限类型</option>
              <option v-for="type in typeOptions" :key="type" :value="type">
                {{ type }}
              </option>
            </select>
          </div>
        </label>

        <label>
          <span>构件（可选）</span>
          <div class="select-shell">
            <Building2 :size="16" />
            <select v-model="componentPreference">
              <option value="">不限构件</option>
              <option
                v-for="component in componentOptions"
                :key="component"
                :value="component"
              >
                {{ component }}
              </option>
            </select>
          </div>
        </label>

        <label>
          <span>材料（可选）</span>
          <div class="select-shell">
            <Tag :size="16" />
            <select v-model="materialPreference">
              <option value="">不限材料</option>
              <option
                v-for="material in materialOptions"
                :key="material"
                :value="material"
              >
                {{ material }}
              </option>
            </select>
          </div>
        </label>

        <label>
          <span>人物（可选）</span>
          <div class="select-shell">
            <Crown :size="16" />
            <select v-model="personPreference">
              <option value="">不限人物</option>
              <option
                v-for="person in personOptions"
                :key="person"
                :value="person"
              >
                {{ person }}
              </option>
            </select>
          </div>
        </label>

        <label>
          <span>保护级别（可选）</span>
          <div class="select-shell">
            <ShieldCheck :size="16" />
            <select v-model="protectionPreference">
              <option value="">不限保护级别</option>
              <option
                v-for="protection in protectionOptions"
                :key="protection"
                :value="protection"
              >
                {{ protection }}
              </option>
            </select>
          </div>
        </label>

        <button
          class="recommend-button"
          type="button"
          :disabled="loading"
          @click="loadRecommendations"
        >
          <LoaderCircle v-if="loading" class="spinning" :size="18" />
          <Sparkles v-else :size="18" />
          {{ loading ? "正在计算" : "生成推荐" }}
        </button>
      </div>
    </section>

    <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

    <section v-if="seedBuilding" class="seed-summary">
      <div class="seed-symbol"><Landmark :size="28" /></div>
      <div class="seed-title">
        <span>当前推荐起点</span>
        <strong>{{ seedBuilding.name }}</strong>
      </div>
      <div class="seed-facts">
        <span v-if="seedBuilding.province"
          ><MapPin :size="14" />{{ seedBuilding.province }}</span
        >
        <span v-if="seedBuilding.era"
          ><History :size="14" />{{ seedBuilding.era }}</span
        >
        <span v-if="seedBuilding.type"
          ><Tag :size="14" />{{ seedBuilding.type }}</span
        >
        <span v-if="seedBuilding.protection"
          ><ShieldCheck :size="14" />{{ seedBuilding.protection }}</span
        >
      </div>
      <div class="seed-route"><Route :size="42" /></div>
    </section>

    <section class="result-section">
      <header class="result-heading">
        <div>
          <span class="section-kicker">PERSONALIZED DISCOVERY</span>
          <h2>为你推荐</h2>
          <p>
            <template v-if="activePreferenceCount">
              按 {{ activePreferenceCount }} 项条件筛选出
              {{ filteredRecommendations.length }} 条真实匹配结果
            </template>
            <template v-else>
              共获得 {{ filteredRecommendations.length }} 条推荐结果
            </template>
          </p>
        </div>
        <button type="button" @click="resetPreferences">
          <RefreshCw :size="15" />重置偏好
        </button>
      </header>

      <div v-if="loading" class="loading-state">
        <LoaderCircle class="spinning" :size="34" />
        <p>正在沿知识图谱关系计算相似古建筑……</p>
      </div>

      <div v-else-if="displayedRecommendations.length" class="recommend-grid">
        <article
          v-for="(item, index) in displayedRecommendations"
          :key="item.id"
          class="recommend-card"
        >
          <div class="rank-number">
            {{ String(index + 1).padStart(2, "0") }}
          </div>

          <div class="card-topline">
            <span class="type-label"
              ><Building2 :size="13" />{{ item.type || "古建筑" }}</span
            >
            <span class="score-label"
              ><Star :size="13" />{{ scoreText(item.score) }}</span
            >
          </div>

          <div class="card-image" :class="{ placeholder: !item.image }">
            <div class="image-frame" aria-hidden="true"></div>
            <img
              v-if="item.image"
              :src="item.image"
              :alt="item.name"
              loading="lazy"
            />
            <template v-else>
              <Landmark :size="58" />
              <em class="no-image-label">暂无可用图片</em>
            </template>
            <span v-if="item.protection"
              ><Crown :size="13" />{{ item.protection }}</span
            >
          </div>

          <div class="card-content">
            <h3>{{ item.name }}</h3>
            <div class="meta-row">
              <span v-if="item.province"
                ><MapPin :size="13" />{{ item.province }}</span
              >
              <span v-if="item.era"><History :size="13" />{{ item.era }}</span>
            </div>

            <p class="summary">
              {{ item.summary || "点击查看该古建筑的知识图谱属性与推荐依据。" }}
            </p>

            <div class="reason-list">
              <span v-for="reason in recommendationReasons(item)" :key="reason">
                <Sparkles :size="11" />{{ reason }}
              </span>
            </div>

            <button type="button" @click="selectedBuilding = item">
              查看推荐依据<ChevronRight :size="15" />
            </button>
          </div>
        </article>
      </div>

      <div v-else class="empty-state">
        <Compass :size="46" />
        <strong>没有同时满足当前条件的古建筑</strong>
        <span>请减少一项偏好条件，或重置后重新筛选</span>
      </div>
    </section>

    <div
      v-if="selectedBuilding"
      class="drawer-mask"
      @click.self="selectedBuilding = null"
    >
      <aside class="detail-drawer">
        <button
          class="close-button"
          type="button"
          @click="selectedBuilding = null"
        >
          <X :size="19" />
        </button>
        <div class="drawer-watermark" aria-hidden="true"></div>
        <span class="section-kicker">RECOMMENDATION DETAIL</span>
        <h2>{{ selectedBuilding.name }}</h2>
        <p class="record-id">记录编号：{{ selectedBuilding.id }}</p>

        <div class="detail-score">
          <Star :size="22" />
          <div>
            <span>图谱匹配度</span>
            <strong>{{ scoreText(selectedBuilding.score) }}</strong>
          </div>
        </div>

        <dl>
          <template v-if="selectedBuilding.province"
            ><dt>所在省份</dt>
            <dd>{{ selectedBuilding.province }}</dd></template
          >
          <template v-if="selectedBuilding.location"
            ><dt>具体地点</dt>
            <dd>{{ selectedBuilding.location }}</dd></template
          >
          <template v-if="selectedBuilding.era"
            ><dt>建造时代</dt>
            <dd>{{ selectedBuilding.era }}</dd></template
          >
          <template v-if="selectedBuilding.type"
            ><dt>建筑类型</dt>
            <dd>{{ selectedBuilding.type }}</dd></template
          >
          <template v-if="selectedBuilding.protection"
            ><dt>保护级别</dt>
            <dd>{{ selectedBuilding.protection }}</dd></template
          >
        </dl>

        <div class="detail-reasons">
          <h3>推荐依据</h3>
          <p
            v-for="reason in recommendationReasons(selectedBuilding)"
            :key="reason"
          >
            <Sparkles :size="13" />{{ reason }}
          </p>
        </div>

        <div v-if="selectedBuilding.summary" class="detail-summary">
          <h3>建筑简介</h3>
          <p>{{ selectedBuilding.summary }}</p>
        </div>
      </aside>
    </div>
  </main>
</template>

<style scoped>
.recommend-page {
  --paper: #f8f1df;
  --ink: #4a352e;
  --muted: #897064;
  --red: #96352e;
  --deep-red: #702421;
  --gold: #b78646;
  min-height: calc(100vh - 100px);
  padding: 30px clamp(22px, 5vw, 76px) 64px;
  color: var(--ink);
  /* 不铺底色，直接使用全局 body 背景，消除"大底框"观感 */
}

.hero-section,
.preference-panel,
.seed-summary,
.result-section,
.error-message {
  width: min(1480px, 100%);
  margin-inline: auto;
}

.hero-section {
  position: relative;
  min-height: 155px;
  display: flex;
  align-items: center;
  overflow: hidden;
  padding: 24px 38px;
  border: 1px solid rgba(150, 83, 54, 0.22);
  border-radius: 6px 6px 22px 22px;
  background: rgba(255, 251, 241, 0.92);
  box-shadow: 0 14px 35px rgba(82, 53, 35, 0.08);
}

.hero-copy {
  position: relative;
  z-index: 2;
  max-width: 760px;
}

.eyebrow,
.section-kicker {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--gold);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.18em;
}

h1 {
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
  font-size: 15px;
}

.hero-palace {
  position: absolute;
  right: 1%;
  bottom: -42px;
  width: 420px;
  height: 215px;
  opacity: 0.17;
  background: url("../assets/hero-palace-watermark.png") right bottom / contain
    no-repeat;
}

.preference-panel {
  margin-top: 22px;
  padding: 20px 23px 23px;
  border: 1px solid rgba(163, 116, 67, 0.34);
  border-radius: 7px;
  background:
    url("../assets/palace-watermark.png") right 5px bottom -20px / 440px auto
      no-repeat,
    rgba(255, 252, 243, 0.82);
  box-shadow: 0 13px 34px rgba(79, 50, 32, 0.07);
}

.panel-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 17px;
}

.heading-icon {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  color: #f7e2b1;
  border-radius: 50%;
  background: linear-gradient(135deg, #a23b32, #772520);
  box-shadow: 0 5px 14px rgba(112, 36, 31, 0.18);
}

.panel-heading div:last-child {
  display: grid;
  gap: 3px;
}

.panel-heading strong {
  color: #73302a;
  font-size: 17px;
}

.panel-heading span {
  color: var(--muted);
  font-size: 12px;
}

.preference-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  align-items: end;
  gap: 12px;
}

.preference-form label {
  min-width: 0;
  display: grid;
  gap: 7px;
}

.preference-form label > span {
  color: #755c50;
  font-size: 12px;
}

.input-shell,
.select-shell {
  height: 42px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  color: #9b6e3d;
  border: 1px solid #d9c09a;
  border-radius: 8px;
  background: #fbf3dc;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.7),
    0 2px 6px rgba(114, 78, 43, 0.07);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.input-shell:focus-within,
.select-shell:focus-within {
  border-color: #b78646;
  background: #fdf6e6;
  box-shadow:
    0 0 0 3px rgba(183, 134, 70, 0.14),
    0 4px 12px rgba(114, 78, 43, 0.09);
}

.input-shell input,
.select-shell input,
.select-shell select {
  font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
}

.select-shell option {
  color: #4a352e;
  font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
  background: #fdf7e8;
}

.input-shell input,
.select-shell input {
  width: 100%;
  min-width: 0;
  color: var(--ink);
  font-family: inherit;
  font-size: 13px;
  border: 0;
  outline: 0;
  background: transparent;
}

.input-shell input::placeholder,
.select-shell input::placeholder {
  color: #9d8970;
  opacity: 1;
}

.select-shell input:disabled {
  color: #9d8a7e;
  cursor: wait;
}

.select-shell select {
  width: 100%;
  min-width: 0;
  overflow: hidden;
  color: var(--ink);
  font-family: inherit;
  font-size: 13px;
  border: 0;
  outline: 0;
  background: transparent;
  text-overflow: ellipsis;
  cursor: pointer;
}

.select-shell select:disabled {
  color: #9d8a7e;
  cursor: wait;
}

.recommend-button {
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 0 20px;
  color: #fff9e9;
  border: 0;
  border-radius: 5px;
  background: linear-gradient(135deg, #a63c33, #76241f);
  box-shadow: 0 7px 16px rgba(119, 36, 31, 0.18);
  cursor: pointer;
  white-space: nowrap;
}

.recommend-button:disabled {
  opacity: 0.65;
  cursor: wait;
}

.spinning {
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-message {
  box-sizing: border-box;
  margin-top: 15px;
  padding: 11px 14px;
  color: #8a2927;
  border-left: 3px solid #9f3730;
  background: rgba(159, 55, 48, 0.08);
}

.seed-summary {
  position: relative;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: auto auto 1fr auto;
  align-items: center;
  gap: 17px;
  margin-top: 18px;
  padding: 17px 22px;
  overflow: hidden;
  border: 1px solid rgba(173, 127, 68, 0.29);
  border-radius: 6px;
  background: linear-gradient(
    100deg,
    rgba(153, 54, 45, 0.07),
    rgba(255, 252, 242, 0.78)
  );
}

.seed-symbol {
  width: 47px;
  height: 47px;
  display: grid;
  place-items: center;
  color: var(--red);
  border: 1px solid #cfa873;
  border-radius: 50%;
  background: #fff9e9;
}

.seed-title {
  display: grid;
  gap: 4px;
}

.seed-title span {
  color: var(--muted);
  font-size: 11px;
}

.seed-title strong {
  color: #74302a;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 20px;
}

.seed-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
}

.seed-facts span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  color: #70594d;
  border: 1px solid rgba(179, 137, 85, 0.25);
  border-radius: 20px;
  background: rgba(255, 251, 240, 0.76);
  font-size: 11px;
}

.seed-route {
  color: rgba(157, 102, 54, 0.35);
}

.result-section {
  margin-top: 29px;
}

.result-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 17px;
}

.result-heading h2 {
  margin: 5px 0 3px;
  color: #63322e;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 29px;
  font-weight: 600;
}

.result-heading p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

.result-heading button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  color: #7d5541;
  border: 1px solid #d5b98f;
  border-radius: 4px;
  background: rgba(255, 251, 241, 0.7);
  cursor: pointer;
}

.recommend-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 17px;
}

.recommend-card {
  position: relative;
  min-width: 0;
  overflow: hidden;
  border: 0;
  border-radius: 12px;
  background: rgba(255, 252, 243, 0.9);
  box-shadow: 0 12px 30px rgba(72, 46, 31, 0.08);
  transition:
    transform 0.24s ease,
    box-shadow 0.24s ease;
}

.recommend-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 18px 34px rgba(83, 49, 30, 0.14);
}

.rank-number {
  position: absolute;
  top: 12px;
  right: 15px;
  z-index: 3;
  color: rgba(134, 73, 46, 0.36);
  font-family: Georgia, serif;
  font-size: 24px;
  font-style: italic;
}

.card-topline {
  position: relative;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  padding: 16px 48px 11px 16px;
}

.type-label,
.score-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #8b5a42;
  font-size: 11px;
}

.score-label {
  color: #a47436;
}

.card-image {
  position: relative;
  height: 148px;
  margin: 4px 20px 8px;
  overflow: visible;
  border: 0;
  background: #eee3cf;
}

.card-image::before {
  content: none;
}

/* 建筑图片专用装饰边框：按 bk03.png 实测金线占比（横向92.8%、纵向75.1%）反推，
   使 388×196 的金线恰好贴合 360×148 的图片四边 */
.image-frame {
  position: absolute;
  inset: -24px -14px;
  z-index: 3;
  background: url("../assets/bk03.png") center / 100% 100% no-repeat;
  pointer-events: none;
}

.card-image img {
  position: relative;
  z-index: 2;
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
  border-radius: 2px;
  transition: transform 0.35s ease;
}

.recommend-card:hover .card-image img {
  transform: scale(1.045);
}

.card-image.placeholder {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: rgba(141, 85, 50, 0.35);
  background: linear-gradient(145deg, #f3ead8, #e7d6bb);
}

.card-image.placeholder > svg {
  position: relative;
  z-index: 2;
}

.no-image-label {
  position: relative;
  z-index: 2;
  color: #9a806f;
  font-size: 11px;
  font-style: normal;
}

.card-image > span {
  position: absolute;
  left: 8px;
  bottom: 8px;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: calc(100% - 16px);
  padding: 4px 7px;
  overflow: hidden;
  color: #fff9e9;
  border-radius: 2px;
  background: rgba(113, 39, 34, 0.84);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-content {
  position: relative;
  z-index: 2;
  padding: 15px 17px 18px;
}

.card-content h3 {
  margin: 0 0 8px;
  overflow: hidden;
  color: #5e302c;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 20px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-row {
  display: flex;
  gap: 11px;
  min-height: 18px;
  color: #896e5f;
  font-size: 11px;
}

.meta-row span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.summary {
  min-height: 43px;
  display: -webkit-box;
  margin: 9px 0;
  overflow: hidden;
  color: #746158;
  font-size: 12px;
  line-height: 1.75;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.reason-list {
  min-height: 50px;
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 5px;
  margin: 10px 0 13px;
}

.reason-list span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 7px;
  color: #8a533b;
  border: 1px solid rgba(183, 131, 69, 0.23);
  border-radius: 12px;
  background: rgba(190, 142, 75, 0.08);
  font-size: 9px;
}

.card-content > button {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  width: 100%;
  padding: 8px 0 0;
  color: var(--red);
  border: 0;
  border-top: 1px solid rgba(172, 126, 76, 0.18);
  background: transparent;
  font-size: 12px;
  cursor: pointer;
}

.loading-state,
.empty-state {
  min-height: 340px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 12px;
  color: #9b806f;
  border: 1px dashed rgba(159, 113, 66, 0.36);
  background: rgba(255, 251, 240, 0.58);
}

.empty-state strong {
  color: #765043;
}

.empty-state span,
.loading-state p {
  margin: 0;
  font-size: 12px;
}

.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  justify-content: flex-end;
  background: rgba(47, 33, 27, 0.34);
  backdrop-filter: blur(3px);
}

.detail-drawer {
  position: relative;
  box-sizing: border-box;
  width: min(470px, 92vw);
  height: 100%;
  padding: 39px 34px;
  overflow-y: auto;
  border-left: 1px solid #c8a878;
  background: #fbf5e8;
  box-shadow: -16px 0 40px rgba(51, 31, 22, 0.18);
}

.close-button {
  position: absolute;
  top: 18px;
  right: 18px;
  z-index: 3;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  color: #825144;
  border: 1px solid #d1b487;
  border-radius: 50%;
  background: #fffaf0;
  cursor: pointer;
}

.drawer-watermark {
  position: absolute;
  right: -55px;
  bottom: -20px;
  width: 350px;
  height: 260px;
  opacity: 0.09;
  background: url("../assets/palace-watermark.png") right bottom / contain
    no-repeat;
}

.detail-drawer > *:not(.drawer-watermark) {
  position: relative;
  z-index: 1;
}

.detail-drawer h2 {
  margin: 9px 0 5px;
  color: #71312c;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 30px;
  font-weight: 600;
}

.record-id {
  margin: 0;
  color: #9a8274;
  font-size: 11px;
}

.detail-score {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 25px 0 19px;
  padding: 15px;
  color: #a16b2e;
  border-left: 3px solid #b68746;
  background: rgba(186, 135, 67, 0.09);
}

.detail-score div {
  display: grid;
  gap: 3px;
}

.detail-score span {
  color: #836c5d;
  font-size: 11px;
}

.detail-score strong {
  font-size: 20px;
}

.detail-drawer dl {
  display: grid;
  grid-template-columns: 78px 1fr;
  gap: 0 12px;
  margin: 0;
}

.detail-drawer dt,
.detail-drawer dd {
  padding: 10px 0;
  border-bottom: 1px dashed rgba(157, 111, 68, 0.25);
  font-size: 12px;
}

.detail-drawer dt {
  color: #a07449;
}

.detail-drawer dd {
  margin: 0;
  color: #59433a;
}

.detail-reasons,
.detail-summary {
  margin-top: 24px;
}

.detail-reasons h3,
.detail-summary h3 {
  margin: 0 0 11px;
  color: #6f3c34;
  font-size: 14px;
}

.detail-reasons p {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin: 7px 0;
  color: #715c51;
  font-size: 12px;
  line-height: 1.6;
}

.detail-summary p {
  margin: 0;
  color: #715e54;
  font-size: 12px;
  line-height: 1.9;
}

@media (max-width: 1250px) {
  .preference-form {
    grid-template-columns: repeat(3, 1fr);
  }

  .seed-field {
    grid-column: span 2;
  }

  .recommend-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .recommend-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .seed-summary {
    grid-template-columns: auto 1fr;
  }

  .seed-facts {
    grid-column: 1 / -1;
  }

  .seed-route {
    display: none;
  }
}

@media (max-width: 650px) {
  .recommend-page {
    padding-inline: 14px;
  }

  .preference-form {
    grid-template-columns: 1fr;
  }

  .seed-field {
    grid-column: auto;
  }

  .recommend-grid {
    grid-template-columns: 1fr;
  }

  .result-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .hero-palace {
    opacity: 0.08;
  }
}
</style>
