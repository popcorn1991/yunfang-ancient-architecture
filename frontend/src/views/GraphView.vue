<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import * as echarts from "echarts";
import {
  Download,
  Focus,
  Network,
  RotateCcw,
  Search,
  Sparkles,
} from "lucide-vue-next";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const chartElement = ref(null);
const recordId = ref("CAB00001");
const loading = ref(false);
const errorMessage = ref("");
const nodeCount = ref(0);
const relationCount = ref(0);
const selectedNode = ref(null);
const graphData = ref({ nodes: [], links: [] });
const viewMode = ref("single");
const provinceName = ref("");
const entityInput = ref("");
const provinceOptions = ref([]);

const modeTabs = [
  { value: "single", label: "单体图谱" },
  { value: "overview", label: "全库总图谱" },
  { value: "province", label: "省份图谱" },
  { value: "relations", label: "实体关系" },
];

const modeHint = computed(() => {
  if (viewMode.value === "overview") {
    return "总图谱按省份分区环形排版：外环为全部古建筑（按省份扇区归位），中环为省级行政区枢纽，中心为时代、类型、构件等共享实体。滚轮缩放查看细节，悬停节点可显示名称。";
  }
  if (viewMode.value === "relations") {
    return "输入两个及以上实体（支持建筑名、省份、时代、人物、构件、材料等，编号 CAB 开头），展示它们之间的直接关系与共同邻居。";
  }
  return "";
});

let chart = null;

const typeStyles = {
  古建筑: "#9f2f2f",
  省级行政区: "#467463",
  具体地点: "#4f7f88",
  时代: "#bc843d",
  保护级别: "#75618d",
  建筑类型: "#c56b45",
  建筑构件: "#667b9a",
  建筑材料: "#8d674b",
  历史人物: "#a65569",
  历史时期: "#7c8a5a",
  其他: "#8a8377",
};

// 数据库节点标签与图例类别的别名对齐
const typeAliases = {
  人物: "历史人物",
};

function pick(object, keys, fallback = "") {
  for (const key of keys) {
    const value = object?.[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return fallback;
}

function normalizeType(node) {
  const raw = pick(
    node,
    ["node_type", "type", "category", "label", "labels"],
    "其他",
  );
  const text = Array.isArray(raw) ? raw[0] : raw;
  const mapped = typeAliases[text] ?? text;
  return typeStyles[mapped] ? mapped : "其他";
}

function normalizeGraph(payload) {
  const body = payload?.data ?? payload ?? {};
  const rawNodes = body.nodes ?? body.graph?.nodes ?? [];
  const rawLinks =
    body.links ?? body.edges ?? body.relationships ?? body.graph?.links ?? [];

  const nodes = rawNodes.map((node, index) => {
    const type = normalizeType(node);
    const id = String(
      pick(node, ["id", "node_id", "record_id", "name"], `node-${index}`),
    );
    const name = String(pick(node, ["name", "title", "label"], id));
    const properties = node.properties ?? node.props ?? node;

    return {
      id,
      name,
      category: type,
      symbolSize: type === "古建筑" ? 66 : 42,
      // 关系图谱接口按 [种子..., 桥接...] 顺序返回节点，据此标记所选实体
      isSeed: index < (Number(body.matched_seeds) || 0),
      itemStyle: {
        color: typeStyles[type],
        borderColor: "#fff8e9",
        borderWidth: 3,
        shadowBlur: type === "古建筑" ? 18 : 8,
        shadowColor: `${typeStyles[type]}55`,
      },
      properties,
      raw: node,
    };
  });

  const ids = new Set(nodes.map((node) => node.id));
  const nameToId = new Map(nodes.map((node) => [node.name, node.id]));

  const links = rawLinks
    .map((link) => {
      const rawSource = pick(link, ["source", "start_id", "from", "start"]);
      const rawTarget = pick(link, ["target", "end_id", "to", "end"]);
      const source = ids.has(String(rawSource))
        ? String(rawSource)
        : nameToId.get(String(rawSource));
      const target = ids.has(String(rawTarget))
        ? String(rawTarget)
        : nameToId.get(String(rawTarget));

      return {
        source,
        target,
        value: String(
          pick(
            link,
            ["relation", "relation_type", "type", "name", "label"],
            "关联",
          ),
        ),
      };
    })
    .filter((link) => link.source && link.target);

  return { nodes, links };
}

// 总图谱预计算排版：中心共享实体环 → 省份枢纽环（扇区按建筑数分配）→ 建筑外环
function layoutOverviewGraph(nodes, links) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const buildingProvince = new Map();

  links.forEach((link) => {
    const source = nodeById.get(link.source);
    const target = nodeById.get(link.target);
    if (!source || !target) return;
    const building =
      source.category === "古建筑"
        ? source
        : target.category === "古建筑"
          ? target
          : null;
    const other = building === source ? target : source;
    if (
      building &&
      other.category === "省级行政区" &&
      !buildingProvince.has(building.id)
    ) {
      buildingProvince.set(building.id, other.id);
    }
  });

  nodes.forEach((node) => {
    node.label = { show: false };
  });

  const provinces = nodes.filter((node) => node.category === "省级行政区");
  const groups = new Map(provinces.map((node) => [node.id, []]));
  const unassigned = [];
  let buildingTotal = 0;
  nodes.forEach((node) => {
    if (node.category !== "古建筑") return;
    buildingTotal += 1;
    const pid = buildingProvince.get(node.id);
    if (pid && groups.has(pid)) groups.get(pid).push(node);
    else unassigned.push(node);
  });

  // 省份扇区：角度份额 ∝ 该省建筑数，建筑沿扇区弧线排布、双环交错
  const sortedProvinces = [...provinces].sort(
    (a, b) =>
      groups.get(b.id).length - groups.get(a.id).length ||
      a.name.localeCompare(b.name, "zh-CN"),
  );
  const SLICE_PAD = 5;
  const PROVINCE_R = 620;
  const BUILDING_RINGS = [780, 845];
  let angle = -Math.PI / 2;
  const sliceTotal = buildingTotal + SLICE_PAD * sortedProvinces.length;

  sortedProvinces.forEach((province) => {
    const list = groups
      .get(province.id)
      .sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    const span = ((list.length + SLICE_PAD) / sliceTotal) * Math.PI * 2;
    const center = angle + span / 2;

    province.x = Math.cos(center) * PROVINCE_R;
    province.y = Math.sin(center) * PROVINCE_R;
    province.symbolSize = 30 + Math.min(24, list.length / 5);
    province.label = {
      show: true,
      fontSize: 12,
      fontWeight: 700,
      color: "#467463",
      formatter: `${province.name}\n${list.length} 处`,
    };

    const innerSpan = span * 0.86;
    const start = center - innerSpan / 2;
    list.forEach((building, index) => {
      const t = (index + 0.5) / Math.max(1, list.length);
      const a = start + innerSpan * t;
      const r = BUILDING_RINGS[index % BUILDING_RINGS.length];
      building.x = Math.cos(a) * r;
      building.y = Math.sin(a) * r;
      building.symbolSize = 6.5;
    });
    angle += span;
  });

  // 无省份数据的建筑排到最外环
  const OUTER_R = 925;
  unassigned.forEach((building, index) => {
    const a = -Math.PI / 2 + ((index + 0.5) / unassigned.length) * Math.PI * 2;
    building.x = Math.cos(a) * OUTER_R;
    building.y = Math.sin(a) * OUTER_R;
    building.symbolSize = 6.5;
  });

  // 中心内环：共享实体按类别分环，体量大的类别（时代、地点）放外圈、缩小字号
  const innerRings = [
    { category: "保护级别", r: 110, size: 20, label: 11 },
    { category: "历史时期", r: 160, size: 16, label: 10 },
    { category: "历史人物", r: 205, size: 14, label: 9 },
    { category: "建筑材料", r: 245, size: 13, label: 9 },
    { category: "建筑构件", r: 285, size: 13, label: 9 },
    { category: "建筑类型", r: 330, size: 14, label: 10 },
    { category: "时代", r: 405, size: 10, label: 8 },
    { category: "具体地点", r: 495, size: 8, label: 0 },
  ];
  innerRings.forEach(({ category, r, size, label }) => {
    const ring = nodes
      .filter((node) => node.category === category)
      .sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    ring.forEach((node, index) => {
      const a = -Math.PI / 2 + ((index + 0.5) / ring.length) * Math.PI * 2;
      node.x = Math.cos(a) * r;
      node.y = Math.sin(a) * r;
      node.symbolSize = size;
      if (label > 0) {
        node.label = { show: true, fontSize: label, color: "#655047" };
      }
    });
  });

  // 兜底：未识别类别的节点放到地点与省份之间的环上
  const fallback = nodes.filter(
    (node) => node.x === undefined || node.y === undefined,
  );
  fallback.forEach((node, index) => {
    const a = -Math.PI / 2 + ((index + 0.5) / fallback.length) * Math.PI * 2;
    node.x = Math.cos(a) * 560;
    node.y = Math.sin(a) * 560;
    node.symbolSize = 10;
  });
}

function buildOverviewOption(nodes, links) {
  layoutOverviewGraph(nodes, links);
  const usedTypes = [...new Set(nodes.map((node) => node.category))];

  return {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(255, 250, 239, 0.96)",
      borderColor: "#d8b67b",
      textStyle: { color: "#472f27" },
      formatter(params) {
        if (params.dataType === "edge") {
          return `${params.data.source} · ${params.data.value} · ${params.data.target}`;
        }
        return `<strong>${params.data.name}</strong><br/>类型：${params.data.category}`;
      },
    },
    legend: {
      top: 18,
      left: 22,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: "#655047", fontSize: 12 },
      data: usedTypes,
    },
    graphic: [
      {
        type: "circle",
        left: "center",
        top: "middle",
        shape: { cx: 0, cy: 0, r: 52 },
        style: {
          fill: "rgba(159, 47, 47, 0.07)",
          stroke: "rgba(159, 47, 47, 0.55)",
          lineWidth: 1.5,
        },
        silent: true,
      },
      {
        type: "text",
        left: "center",
        top: "middle",
        style: {
          text: "中华古建筑\n知识总图谱",
          align: "center",
          fill: "#9f2f2f",
          fontSize: 13,
          fontWeight: 700,
          lineHeight: 19,
        },
        silent: true,
      },
    ],
    series: [
      {
        type: "graph",
        layout: "none",
        data: nodes,
        links,
        categories: usedTypes.map((name) => ({
          name,
          itemStyle: { color: typeStyles[name] },
        })),
        roam: true,
        draggable: false,
        cursor: "pointer",
        edgeSymbol: ["none", "none"],
        label: { show: false },
        edgeLabel: { show: false },
        lineStyle: {
          color: "#b8a07e",
          width: 0.7,
          opacity: 0.15,
          curveness: 0.12,
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: { width: 1.8, opacity: 0.75 },
          label: { show: true, fontSize: 12, fontWeight: 600 },
        },
      },
    ],
  };
}

// 环形排版的类别次序（由内到外、按知识维度展开）
const RING_CATEGORY_ORDER = [
  "省级行政区",
  "历史时期",
  "时代",
  "保护级别",
  "建筑类型",
  "具体地点",
  "建筑构件",
  "建筑材料",
  "历史人物",
  "古建筑",
  "其他",
];

function sortByName(list) {
  return [...list].sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
}

// 单体图谱：建筑居中，邻居按类别扇区沿环展开
function layoutSingleGraph(nodes) {
  const center =
    nodes.find((node) => node.id === recordId.value.trim()) ??
    nodes.find((node) => node.category === "古建筑") ??
    nodes[0];
  nodes.forEach((node) => {
    node.label = { show: false };
  });
  if (!center) return;

  center.x = 0;
  center.y = 0;
  center.symbolSize = 92;
  center.label = {
    show: true,
    position: "bottom",
    distance: 12,
    fontSize: 15,
    fontWeight: 700,
    color: "#9f2f2f",
  };

  const neighbors = nodes.filter((node) => node !== center);
  const groups = [];
  RING_CATEGORY_ORDER.forEach((category) => {
    const list = sortByName(
      neighbors.filter((node) => node.category === category),
    );
    if (list.length) groups.push(list);
  });
  const slotTotal = neighbors.length + groups.length * 2;
  const R = 300;
  let angle = -Math.PI / 2;

  groups.forEach((list) => {
    const span = ((list.length + 2) / slotTotal) * Math.PI * 2;
    const innerSpan = span * 0.82;
    const start = angle + (span - innerSpan) / 2;
    const rings = list.length > 24 ? [R, R + 76] : [R];
    list.forEach((node, index) => {
      const a = start + innerSpan * ((index + 0.5) / list.length);
      const r = rings[index % rings.length];
      node.x = Math.cos(a) * r;
      node.y = Math.sin(a) * r;
      node.symbolSize = 34;
      node.label = {
        show: true,
        position: "bottom",
        distance: 6,
        fontSize: 11,
        color: "#4d3a32",
        width: 92,
        overflow: "truncate",
      };
    });
    angle += span;
  });
}

// 省份图谱：省份居中，共享实体内环，省内建筑外环
function layoutProvinceGraph(nodes) {
  const center =
    nodes.find((node) => node.category === "省级行政区") ?? nodes[0];
  nodes.forEach((node) => {
    node.label = { show: false };
  });
  if (!center) return;

  center.x = 0;
  center.y = 0;
  center.symbolSize = 74;
  center.label = {
    show: true,
    position: "bottom",
    distance: 10,
    fontSize: 15,
    fontWeight: 700,
    color: "#467463",
  };

  const innerRings = [
    { category: "保护级别", r: 150, size: 20 },
    { category: "历史时期", r: 195, size: 16 },
    { category: "历史人物", r: 240, size: 14 },
    { category: "建筑材料", r: 285, size: 13 },
    { category: "建筑构件", r: 330, size: 13 },
    { category: "建筑类型", r: 380, size: 14 },
    { category: "时代", r: 440, size: 11 },
    { category: "具体地点", r: 505, size: 9 },
  ];
  innerRings.forEach(({ category, r, size }) => {
    const ring = sortByName(
      nodes.filter((node) => node.category === category),
    );
    ring.forEach((node, index) => {
      const a = -Math.PI / 2 + ((index + 0.5) / ring.length) * Math.PI * 2;
      node.x = Math.cos(a) * r;
      node.y = Math.sin(a) * r;
      node.symbolSize = size;
      if (category !== "具体地点") {
        node.label = {
          show: true,
          fontSize: 10,
          color: "#655047",
          width: 80,
          overflow: "truncate",
        };
      }
    });
  });

  const buildings = sortByName(
    nodes.filter((node) => node.category === "古建筑"),
  );
  const rings =
    buildings.length > 120
      ? [620, 680, 740]
      : buildings.length > 50
        ? [620, 680]
        : [620];
  buildings.forEach((node, index) => {
    const a = -Math.PI / 2 + ((index + 0.5) / buildings.length) * Math.PI * 2;
    const r = rings[index % rings.length];
    node.x = Math.cos(a) * r;
    node.y = Math.sin(a) * r;
    node.symbolSize = 10;
  });
}

// 实体关系图谱：所选实体内环，桥接邻居外环
function layoutRelationsGraph(nodes) {
  const seeds = nodes.filter((node) => node.isSeed);
  const bridges = sortByName(nodes.filter((node) => !node.isSeed));
  nodes.forEach((node) => {
    node.label = { show: false };
  });

  if (seeds.length === 1) {
    seeds[0].x = 0;
    seeds[0].y = 0;
  } else {
    const seedR = Math.min(240, 80 + seeds.length * 22);
    seeds.forEach((node, index) => {
      const a = -Math.PI / 2 + ((index + 0.5) / seeds.length) * Math.PI * 2;
      node.x = Math.cos(a) * seedR;
      node.y = Math.sin(a) * seedR;
    });
  }
  seeds.forEach((node) => {
    node.symbolSize = 50;
    node.label = {
      show: true,
      position: "bottom",
      distance: 8,
      fontSize: 12,
      fontWeight: 700,
      color: "#4d3a32",
      width: 110,
      overflow: "truncate",
    };
  });

  const bridgeR =
    (seeds.length === 1 ? 0 : Math.min(240, 80 + seeds.length * 22)) + 230;
  const rings = bridges.length > 60 ? [bridgeR, bridgeR + 80] : [bridgeR];
  bridges.forEach((node, index) => {
    const a = -Math.PI / 2 + ((index + 0.5) / bridges.length) * Math.PI * 2;
    const r = rings[index % rings.length];
    node.x = Math.cos(a) * r;
    node.y = Math.sin(a) * r;
    node.symbolSize = 26;
    node.label = {
      show: true,
      position: "bottom",
      distance: 5,
      fontSize: 10,
      color: "#655047",
      width: 80,
      overflow: "truncate",
    };
  });
}

function buildOption(nodes, links) {
  if (viewMode.value === "overview") return buildOverviewOption(nodes, links);

  if (viewMode.value === "province") layoutProvinceGraph(nodes);
  else if (viewMode.value === "relations") layoutRelationsGraph(nodes);
  else layoutSingleGraph(nodes);

  const usedTypes = [...new Set(nodes.map((node) => node.category))];
  const showEdgeLabel = viewMode.value !== "province" && links.length <= 60;

  return {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(255, 250, 239, 0.96)",
      borderColor: "#d8b67b",
      textStyle: { color: "#472f27" },
      formatter(params) {
        if (params.dataType === "edge") {
          return `${params.data.source} · ${params.data.value} · ${params.data.target}`;
        }
        return `<strong>${params.data.name}</strong><br/>类型：${params.data.category}`;
      },
    },
    legend: {
      top: 18,
      left: 22,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: "#655047", fontSize: 12 },
      data: usedTypes,
    },
    series: [
      {
        type: "graph",
        layout: "none",
        data: nodes,
        links,
        categories: usedTypes.map((name) => ({
          name,
          itemStyle: { color: typeStyles[name] },
        })),
        roam: true,
        draggable: false,
        cursor: "pointer",
        edgeSymbol: links.length <= 300 ? ["none", "arrow"] : ["none", "none"],
        edgeSymbolSize: [0, 7],
        label: { show: false },
        edgeLabel: {
          show: showEdgeLabel,
          color: "#866e5e",
          fontSize: 10,
          formatter: "{c}",
          backgroundColor: "rgba(250, 244, 228, 0.82)",
          padding: [2, 4],
          borderRadius: 3,
        },
        lineStyle: {
          color: "#b69b77",
          width: 1.2,
          opacity: 0.5,
          curveness: 0.1,
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: { width: 2.4, opacity: 0.95 },
          label: { show: true, fontSize: 12, fontWeight: 600 },
        },
      },
    ],
  };
}

function renderGraph() {
  if (!chartElement.value) return;
  if (!chart) {
    chart = echarts.init(chartElement.value);
    chart.on("click", (params) => {
      if (params.dataType === "node") selectedNode.value = params.data;
    });
  }
  chart.setOption(
    buildOption(graphData.value.nodes, graphData.value.links),
    true,
  );
}

function switchMode(mode) {
  viewMode.value = mode;
  errorMessage.value = "";
  if (mode === "province" && !provinceOptions.value.length) {
    loadProvinceOptions();
  }
}

async function loadProvinceOptions() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/filters`);
    if (!response.ok) throw new Error(`接口返回 ${response.status}`);
    const data = await response.json();
    provinceOptions.value = Array.isArray(data.provinces) ? data.provinces : [];
  } catch {
    provinceOptions.value = [];
  }
}

function buildGraphUrl() {
  if (viewMode.value === "overview") {
    return `${API_BASE_URL}/api/graph/overview`;
  }
  if (viewMode.value === "province") {
    if (!provinceName.value) {
      throw new Error("请先选择一个省级行政区。");
    }
    return `${API_BASE_URL}/api/graph/province/${encodeURIComponent(provinceName.value)}`;
  }
  if (viewMode.value === "relations") {
    const entries = entityInput.value
      .split(/[,，、;；]+/)
      .map((entry) => entry.trim())
      .filter(Boolean);
    if (entries.length < 2) {
      throw new Error("请至少输入两个实体，用逗号分隔，例如：应县木塔,鲁班,唐代。");
    }
    const names = [];
    const ids = [];
    entries.forEach((entry) => {
      if (/^[A-Za-z]{2,6}\d{3,}$/.test(entry)) {
        ids.push(entry);
      } else {
        names.push(entry);
      }
    });
    const params = new URLSearchParams();
    if (names.length) params.set("names", names.join(","));
    if (ids.length) params.set("ids", ids.join(","));
    return `${API_BASE_URL}/api/graph/relations?${params.toString()}`;
  }
  const id = recordId.value.trim();
  if (!id) {
    throw new Error("请输入古建筑记录编号，例如 CAB00001。");
  }
  return `${API_BASE_URL}/api/graph/${encodeURIComponent(id)}`;
}

async function loadGraph() {
  loading.value = true;
  errorMessage.value = "";
  selectedNode.value = null;

  let url;
  try {
    url = buildGraphUrl();
  } catch (error) {
    errorMessage.value = error.message;
    loading.value = false;
    return;
  }

  try {
    const response = await fetch(url);
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail || `接口返回 ${response.status}`);
    }
    const normalized = normalizeGraph(await response.json());
    if (!normalized.nodes.length) throw new Error("未查询到图谱节点");

    graphData.value = normalized;
    nodeCount.value = normalized.nodes.length;
    relationCount.value = normalized.links.length;
    selectedNode.value =
      normalized.nodes.find((node) => node.category === "古建筑") ??
      normalized.nodes[0];
    await nextTick();
    renderGraph();
  } catch (error) {
    graphData.value = { nodes: [], links: [] };
    nodeCount.value = 0;
    relationCount.value = 0;
    errorMessage.value = `图谱加载失败：${error.message}。请确认后端和 Neo4j 已启动。`;
    chart?.clear();
  } finally {
    loading.value = false;
  }
}

function resetView() {
  renderGraph();
}

function focusMainNode() {
  const node = graphData.value.nodes.find((item) => item.category === "古建筑");
  if (!node || !chart) return;
  selectedNode.value = node;
  chart.dispatchAction({
    type: "focusNodeAdjacency",
    seriesIndex: 0,
    dataIndex: graphData.value.nodes.indexOf(node),
  });
}

function downloadGraph() {
  if (!chart) return;
  const link = document.createElement("a");
  link.href = chart.getDataURL({ pixelRatio: 2, backgroundColor: "#f8f1df" });
  link.download = `${recordId.value || "古建筑"}_知识图谱.png`;
  link.click();
}

function readableProperties(node) {
  if (!node?.properties) return [];
  const ignored = new Set([
    "raw",
    "x",
    "y",
    "vx",
    "vy",
    "fixed",
    "symbolSize",
    "itemStyle",
  ]);
  return Object.entries(node.properties)
    .filter(
      ([key, value]) =>
        !ignored.has(key) &&
        value !== "" &&
        value !== null &&
        typeof value !== "object",
    )
    .slice(0, 8);
}

function resizeChart() {
  chart?.resize();
}

onMounted(() => {
  window.addEventListener("resize", resizeChart);
  loadGraph();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <main class="graph-page">
    <section class="page-heading">
      <div class="heading-copy">
        <span class="eyebrow"><Sparkles :size="15" /> KNOWLEDGE GRAPH</span>
        <h1>图谱探索</h1>
        <p>
          从一座古建筑出发，探索地域、时代、类型、构件与历史文化之间的关联。
        </p>
      </div>
      <div class="heading-watermark" aria-hidden="true"></div>
    </section>

    <section class="query-panel">
      <div class="query-copy">
        <Network :size="22" />
        <div>
          <strong>图谱检索</strong>
          <span>单体图谱 · 全库总图谱 · 省份图谱 · 多实体关系图谱</span>
        </div>
      </div>
      <div class="mode-tabs" role="tablist">
        <button
          v-for="tab in modeTabs"
          :key="tab.value"
          type="button"
          :class="{ active: viewMode === tab.value }"
          @click="switchMode(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
      <form class="query-form" @submit.prevent="loadGraph">
        <input
          v-if="viewMode === 'single'"
          v-model="recordId"
          placeholder="例如：CAB00001"
          aria-label="古建筑记录编号"
        />
        <select
          v-else-if="viewMode === 'province'"
          v-model="provinceName"
          aria-label="选择省级行政区"
        >
          <option value="">选择省级行政区</option>
          <option v-for="item in provinceOptions" :key="item" :value="item">
            {{ item }}
          </option>
        </select>
        <input
          v-else-if="viewMode === 'relations'"
          v-model="entityInput"
          placeholder="例如：应县木塔,唐代"
          aria-label="实体名称，逗号分隔"
        />
        <button type="submit" :disabled="loading">
          <Search :size="17" />
          {{ loading ? "正在加载" : "探索图谱" }}
        </button>
      </form>
    </section>

    <p v-if="modeHint" class="mode-hint">{{ modeHint }}</p>

    <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

    <section class="workspace">
      <article class="graph-card">
        <header class="card-toolbar">
          <div>
            <span class="section-kicker">RELATION NETWORK</span>
            <h2>古建筑关联网络</h2>
          </div>
          <div class="graph-stats">
            <span
              ><b>{{ nodeCount }}</b> 个节点</span
            >
            <i></i>
            <span
              ><b>{{ relationCount }}</b> 条关系</span
            >
          </div>
          <div class="toolbar-actions">
            <button type="button" title="聚焦中心节点" @click="focusMainNode">
              <Focus :size="17" />
            </button>
            <button type="button" title="重置视图" @click="resetView">
              <RotateCcw :size="17" />
            </button>
            <button type="button" title="导出PNG图片" @click="downloadGraph">
              <Download :size="17" />
            </button>
          </div>
        </header>

        <div ref="chartElement" class="graph-canvas"></div>
        <p class="interaction-tip">
          滚轮缩放 · 拖动画布 · 拖拽节点 · 单击查看详情
        </p>
      </article>

      <aside class="detail-card">
        <div class="detail-illustration" aria-hidden="true"></div>
        <span class="section-kicker">NODE PROFILE</span>
        <h2>节点信息</h2>

        <template v-if="selectedNode">
          <div class="node-title">
            <span
              class="node-dot"
              :style="{ background: typeStyles[selectedNode.category] }"
            ></span>
            <div>
              <strong>{{ selectedNode.name }}</strong>
              <small>{{ selectedNode.category }}</small>
            </div>
          </div>

          <dl class="property-list">
            <template
              v-for="([key, value], index) in readableProperties(selectedNode)"
              :key="`${key}-${index}`"
            >
              <dt>{{ key }}</dt>
              <dd>{{ value }}</dd>
            </template>
          </dl>
        </template>

        <div v-else class="empty-detail">
          <Network :size="34" />
          <p>单击图中的节点<br />查看实体属性</p>
        </div>

        <div class="legend-block">
          <h3>实体图例</h3>
          <div class="legend-grid">
            <span v-for="(color, type) in typeStyles" :key="type">
              <i :style="{ background: color }"></i>{{ type }}
            </span>
          </div>
        </div>
      </aside>
    </section>
  </main>
</template>

<style scoped>
.graph-page {
  --paper: #f8f1df;
  --ink: #49342d;
  --muted: #866f62;
  --red: #9f2f2f;
  --gold: #b98543;
  min-height: calc(100vh - 76px);
  padding: 34px clamp(24px, 5vw, 76px) 58px;
  color: var(--ink);
  /* 不铺底色，直接使用全局 body 背景，消除"大底框"观感 */
}

.page-heading,
.query-panel,
.workspace {
  width: min(1480px, 100%);
  margin-inline: auto;
}

.page-heading {
  position: relative;
  min-height: 150px;
  display: flex;
  align-items: center;
  overflow: hidden;
  padding: 26px 38px;
  border: 1px solid rgba(150, 83, 54, 0.22);
  border-radius: 6px 6px 22px 22px;
  background: rgba(255, 251, 241, 0.92);
  box-shadow: 0 14px 35px rgba(82, 53, 35, 0.08);
}

.heading-copy {
  position: relative;
  z-index: 1;
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
  margin: 8px 0 6px;
  color: #7f2727;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: clamp(34px, 4vw, 52px);
  font-weight: 600;
  letter-spacing: 0.12em;
}

.page-heading p {
  margin: 0;
  color: var(--muted);
  font-size: 15px;
}

.heading-watermark {
  position: absolute;
  right: 2%;
  bottom: -34px;
  width: 380px;
  height: 190px;
  opacity: 0.16;
  background: url("../assets/hero-palace-watermark.png") right bottom / contain
    no-repeat;
}

.query-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-top: 22px;
  padding: 18px 22px;
  border: 1px solid rgba(160, 112, 65, 0.3);
  border-radius: 6px;
  background: rgba(255, 251, 240, 0.74);
  box-shadow: 0 10px 28px rgba(91, 60, 39, 0.07);
}

.query-copy {
  display: flex;
  align-items: center;
  gap: 13px;
  color: var(--red);
}

.query-copy div {
  display: grid;
  gap: 3px;
}

.query-copy span {
  color: var(--muted);
  font-size: 12px;
}

.query-form {
  display: flex;
  min-width: min(480px, 48%);
}

.query-form input {
  flex: 1;
  min-width: 0;
  padding: 12px 15px;
  color: var(--ink);
  border: 1px solid #d4bea0;
  border-right: 0;
  border-radius: 5px 0 0 5px;
  outline: none;
  background: rgba(255, 255, 255, 0.72);
}

.query-form input:focus {
  border-color: var(--red);
  box-shadow: inset 0 0 0 1px var(--red);
}

.query-form button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 20px;
  color: #fffaf0;
  border: 0;
  border-radius: 0 5px 5px 0;
  background: linear-gradient(135deg, #a43b36, #792526);
  cursor: pointer;
}

.query-form button:disabled {
  opacity: 0.65;
  cursor: wait;
}

.mode-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex-shrink: 0;
}

.mode-tabs button {
  padding: 9px 16px;
  color: #7d6350;
  font-size: 13px;
  border: 1px solid #d4bea0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition:
    color 0.18s ease,
    background 0.18s ease,
    border-color 0.18s ease;
}

.mode-tabs button.active {
  color: #fffaf0;
  border-color: #8e2b27;
  background: linear-gradient(135deg, #a43b36, #792526);
}

.query-form select {
  flex: 1;
  min-width: 0;
  padding: 12px 15px;
  color: var(--ink);
  border: 1px solid #d4bea0;
  border-right: 0;
  border-radius: 5px 0 0 5px;
  outline: none;
  background: rgba(255, 255, 255, 0.72);
}

.query-form select:focus {
  border-color: var(--red);
  box-shadow: inset 0 0 0 1px var(--red);
}

.mode-hint {
  width: min(1480px, 100%);
  margin: 10px auto -4px;
  color: #8d7663;
  font-size: 12px;
}

.error-message {
  width: min(1480px, 100%);
  margin: 14px auto -6px;
  padding: 10px 14px;
  color: #8a2929;
  border-left: 3px solid #a33a35;
  background: rgba(166, 54, 49, 0.08);
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 310px;
  gap: 20px;
  margin-top: 22px;
}

.graph-card,
.detail-card {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(162, 117, 69, 0.34);
  border-radius: 8px;
  background: rgba(255, 252, 243, 0.83);
  box-shadow: 0 16px 42px rgba(71, 47, 32, 0.09);
}

.graph-card::before,
.detail-card::before {
  content: "";
  position: absolute;
  inset: 8px;
  z-index: 0;
  pointer-events: none;
  border: 1px solid rgba(181, 136, 73, 0.16);
}

.card-toolbar {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 26px;
  padding: 21px 24px 15px;
  border-bottom: 1px solid rgba(162, 117, 69, 0.2);
}

h2 {
  margin: 5px 0 0;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 24px;
  font-weight: 600;
}

.graph-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--muted);
  font-size: 12px;
}

.graph-stats b {
  color: var(--red);
  font-size: 18px;
}

.graph-stats i {
  width: 1px;
  height: 24px;
  background: #d9c6a8;
}

.toolbar-actions {
  display: flex;
  gap: 7px;
}

.toolbar-actions button {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  color: #7f4136;
  border: 1px solid #d8b98e;
  border-radius: 4px;
  background: rgba(255, 250, 239, 0.78);
  cursor: pointer;
}

.toolbar-actions button:hover {
  color: #fff;
  border-color: var(--red);
  background: var(--red);
}

.graph-canvas {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 620px;
  background:
    linear-gradient(rgba(194, 155, 103, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(194, 155, 103, 0.07) 1px, transparent 1px);
  background-size: 34px 34px;
}

.interaction-tip {
  position: absolute;
  left: 22px;
  bottom: 14px;
  z-index: 3;
  margin: 0;
  color: #9a8578;
  font-size: 11px;
}

.detail-card {
  min-height: 700px;
  padding: 27px 25px;
}

.detail-card > *:not(.detail-illustration) {
  position: relative;
  z-index: 1;
}

.detail-illustration {
  position: absolute;
  right: -55px;
  bottom: 0;
  width: 310px;
  height: 220px;
  opacity: 0.1;
  background: url("../assets/palace-watermark.png") right bottom / contain
    no-repeat;
}

.node-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 24px 0 20px;
  padding: 15px;
  border-left: 3px solid var(--gold);
  background: rgba(183, 134, 67, 0.08);
}

.node-dot {
  width: 13px;
  height: 13px;
  flex: 0 0 auto;
  border: 2px solid #fff8e9;
  border-radius: 50%;
  box-shadow: 0 0 0 1px #c9ab7d;
}

.node-title div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.node-title strong {
  overflow: hidden;
  font-size: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-title small {
  color: var(--muted);
}

.property-list {
  margin: 0;
}

.property-list dt {
  margin-top: 11px;
  color: #a17447;
  font-size: 11px;
}

.property-list dd {
  margin: 3px 0 0;
  padding-bottom: 9px;
  overflow-wrap: anywhere;
  border-bottom: 1px dashed rgba(152, 116, 75, 0.25);
  font-size: 13px;
  line-height: 1.55;
}

.empty-detail {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 230px;
  color: #a38e7d;
  text-align: center;
  line-height: 1.7;
}

.legend-block {
  margin-top: 28px;
  padding-top: 18px;
  border-top: 1px solid rgba(162, 117, 69, 0.22);
}

.legend-block h3 {
  margin: 0 0 13px;
  font-size: 14px;
}

.legend-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 8px;
}

.legend-grid span {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #715e54;
  font-size: 11px;
}

.legend-grid i {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
}

@media (max-width: 1000px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .detail-card {
    min-height: auto;
  }

  .query-panel {
    align-items: stretch;
    flex-direction: column;
  }

  .query-form {
    min-width: 100%;
  }
}

@media (max-width: 680px) {
  .graph-page {
    padding-inline: 14px;
  }

  .card-toolbar {
    grid-template-columns: 1fr auto;
  }

  .graph-stats {
    grid-column: 1 / -1;
    grid-row: 2;
  }

  .graph-canvas {
    height: 520px;
  }

  .heading-watermark {
    opacity: 0.08;
  }
}
</style>
