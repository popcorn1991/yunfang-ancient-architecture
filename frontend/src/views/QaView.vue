<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import {
  Bot,
  Building2,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  History,
  Landmark,
  LoaderCircle,
  MapPin,
  MessageCircleMore,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-vue-next";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const question = ref("");
const loading = ref(false);
const filtersLoading = ref(false);
const errorMessage = ref("");
const conversationRef = ref(null);
const filters = ref({ provinces: [], periods: [] });
const messages = ref([
  {
    id: 1,
    role: "assistant",
    text: "你好，我是云访古建问答助手。你可以询问某个省份或历史时期收录了哪些古建筑，也可以查询数量，或请求推荐与某座古建筑相似的景点。",
    intent: "使用引导",
    data: [],
    time: formatTime(new Date()),
  },
]);

function formatTime(date) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function unwrap(payload) {
  return payload?.data ?? payload ?? {};
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = "";
    try {
      detail = (await response.json())?.detail ?? "";
    } catch {
      detail = "";
    }
    throw new Error(detail || `接口返回 ${response.status}`);
  }
  return response.json();
}

function normalizeNames(values) {
  if (!Array.isArray(values)) return [];
  return values
    .map((value) => (typeof value === "string" ? value : value?.name))
    .filter(Boolean);
}

async function loadFilters() {
  filtersLoading.value = true;
  try {
    const payload = await requestJson(`${API_BASE_URL}/api/filters`);
    const data = unwrap(payload);
    filters.value = {
      provinces: normalizeNames(data.provinces),
      periods: normalizeNames(data.periods),
    };
  } catch {
    filters.value = { provinces: [], periods: [] };
  } finally {
    filtersLoading.value = false;
  }
}

const suggestedQuestions = computed(() => {
  const provinceA = filters.value.provinces[0];
  const provinceB = filters.value.provinces[1] ?? provinceA;
  const period = filters.value.periods[0];
  return [
    provinceA ? `${provinceA}有多少古建筑？` : "山东省有多少古建筑？",
    provinceB ? `${provinceB}有哪些古建筑？` : "上海市有哪些古建筑？",
    period ? `${period}有哪些古建筑？` : "哪些古建筑值得了解？",
    "推荐与兴圣教寺塔相似的古建筑",
  ];
});

const answerCount = computed(
  () =>
    messages.value.filter((message) => message.role === "assistant").length - 1,
);

const latestResultCount = computed(() => {
  const latest = [...messages.value]
    .reverse()
    .find((message) => message.role === "assistant" && message.data?.length);
  return latest?.data.length ?? 0;
});

async function scrollToBottom() {
  await nextTick();
  const element = conversationRef.value;
  if (element) element.scrollTop = element.scrollHeight;
}

// 多轮上下文：取最近一条助手回答的基准建筑，支持"它/这些"等指代追问
function previousContext() {
  const last = [...messages.value]
    .reverse()
    .find((message) => message.role === "assistant" && !message.failed);
  return {
    last_seed: last?.seed || null,
    last_building: last?.representative || null,
  };
}

async function submitQuestion(preset = "") {
  const content = String(preset || question.value).trim();
  if (!content || loading.value) return;

  messages.value.push({
    id: Date.now(),
    role: "user",
    text: content,
    time: formatTime(new Date()),
  });
  question.value = "";
  loading.value = true;
  errorMessage.value = "";
  await scrollToBottom();

  try {
    const payload = await requestJson(`${API_BASE_URL}/api/qa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: content, ...previousContext() }),
    });
    // /api/qa 的 data 是结果数组，不是通用响应包裹层，需保留 answer 与 intent。
    const data = payload?.answer ? payload : unwrap(payload);
    messages.value.push({
      id: Date.now() + 1,
      role: "assistant",
      text: data.answer || "当前问题暂未得到有效答案。",
      intent: data.intent || "知识图谱问答",
      data: Array.isArray(data.data) ? data.data : [],
      // 证据来源与可追溯信息，用于气泡下方展示
      source: data.source || "",
      evidenceCount: Number(data.evidence_count) || 0,
      seed: data.seed || "",
      representative: data.representative || "",
      time: formatTime(new Date()),
    });
  } catch (error) {
    errorMessage.value = `问答请求失败：${error.message}。请确认后端与 Neo4j 已启动。`;
    messages.value.push({
      id: Date.now() + 1,
      role: "assistant",
      text: "暂时无法连接知识图谱服务，请稍后重试。",
      intent: "服务异常",
      data: [],
      time: formatTime(new Date()),
      failed: true,
    });
  } finally {
    loading.value = false;
    await scrollToBottom();
  }
}

function clearConversation() {
  messages.value = [messages.value[0]];
  errorMessage.value = "";
  question.value = "";
}

function buildingName(item) {
  return item.name || item.title || "未命名古建筑";
}

function buildingProvince(item) {
  return item.province || "地区待考";
}

function buildingPeriod(item) {
  return item.period || item.era || "时代待考";
}

onMounted(loadFilters);
</script>

<template>
  <main class="qa-page">
    <section class="hero-section">
      <div class="hero-copy">
        <span class="eyebrow"><Sparkles :size="15" /> KNOWLEDGE ASSISTANT</span>
        <h1>智能问答</h1>
        <p>
          以自然语言访问中华古建筑知识图谱，在真实实体与关系中检索答案和推荐结果。
        </p>
      </div>
      <div class="hero-palace" aria-hidden="true"></div>
    </section>

    <section class="assistant-status">
      <div class="assistant-brand">
        <span><Bot :size="23" /></span>
        <div>
          <strong>云访古建助手</strong>
          <small><i></i>知识图谱服务已连接</small>
        </div>
      </div>
      <div class="status-items">
        <span><Database :size="15" />数据来源：Neo4j</span>
        <span
          ><MessageCircleMore :size="15" />已完成 {{ answerCount }} 次问答</span
        >
        <span
          ><Building2 :size="15" />最近返回 {{ latestResultCount }} 条记录</span
        >
      </div>
      <button type="button" @click="clearConversation">
        <RotateCcw :size="15" />清空对话
      </button>
    </section>

    <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>

    <section class="workspace-grid">
      <aside class="guide-panel">
        <header>
          <span><CircleHelp :size="20" /></span>
          <div>
            <strong>你可以这样问</strong>
            <small>点击示例直接发起查询</small>
          </div>
        </header>

        <div class="suggestion-list">
          <button
            v-for="(item, index) in suggestedQuestions"
            :key="item"
            type="button"
            :disabled="loading || filtersLoading"
            @click="submitQuestion(item)"
          >
            <i>0{{ index + 1 }}</i>
            <span>{{ item }}</span>
            <ChevronRight :size="15" />
          </button>
        </div>

        <div class="ability-list">
          <span><Search :size="15" />条件检索</span>
          <span><MapPin :size="15" />地域查询</span>
          <span><History :size="15" />时期查询</span>
          <span><Sparkles :size="15" />相似推荐</span>
        </div>

        <div class="guide-figure" aria-hidden="true"></div>

        <div class="guide-note">
          <ShieldCheck :size="17" />
          <p>
            回答仅依据当前知识图谱中的实体与关系生成，未检索到的信息不会被臆造。
          </p>
        </div>
      </aside>

      <section class="chat-panel">
        <div class="ornate-frame" aria-hidden="true"></div>
        <header class="chat-header">
          <div>
            <span class="section-kicker">GRAPH QUESTION ANSWERING</span>
            <h2>古建问答空间</h2>
          </div>
          <Landmark :size="27" />
        </header>

        <div ref="conversationRef" class="conversation">
          <article
            v-for="message in messages"
            :key="message.id"
            class="message-row"
            :class="message.role"
          >
            <span class="avatar">
              <Bot v-if="message.role === 'assistant'" :size="19" />
              <UserRound v-else :size="18" />
            </span>

            <div class="message-content">
              <div class="message-meta">
                <strong>{{
                  message.role === "assistant" ? "云访古建助手" : "我"
                }}</strong>
                <span><Clock3 :size="11" />{{ message.time }}</span>
              </div>

              <div class="message-bubble" :class="{ failed: message.failed }">
                <span v-if="message.intent" class="intent-tag">
                  {{ message.intent }}
                </span>
                <p>{{ message.text }}</p>
                <div
                  v-if="message.source || message.evidenceCount"
                  class="evidence-line"
                >
                  <Database :size="11" />
                  <span>来源：{{ message.source || "Neo4j知识图谱" }}</span>
                  <em v-if="message.evidenceCount">
                    · 证据 {{ message.evidenceCount }} 条
                  </em>
                </div>
              </div>

              <div v-if="message.data?.length" class="answer-results">
                <article
                  v-for="item in message.data"
                  :key="
                    item.record_id ||
                    `${buildingName(item)}-${buildingProvince(item)}`
                  "
                  class="result-card"
                >
                  <div class="result-image" :class="{ empty: !item.image_url }">
                    <img
                      v-if="item.image_url"
                      :src="item.image_url"
                      :alt="buildingName(item)"
                    />
                    <Landmark v-else :size="31" />
                  </div>
                  <div class="result-copy">
                    <strong>{{ buildingName(item) }}</strong>
                    <p>
                      <span
                        ><MapPin :size="12" />{{ buildingProvince(item) }}</span
                      >
                      <span
                        ><History :size="12" />{{ buildingPeriod(item) }}</span
                      >
                    </p>
                    <small v-if="item.location">{{ item.location }}</small>
                    <em v-if="item.confidence !== undefined">
                      推荐置信度：{{
                        (Number(item.confidence) * 100).toFixed(1)
                      }}%
                    </em>
                  </div>
                </article>
              </div>
            </div>
          </article>

          <article v-if="loading" class="message-row assistant thinking-row">
            <span class="avatar"><Bot :size="19" /></span>
            <div class="message-content">
              <div class="message-meta"><strong>云访古建助手</strong></div>
              <div class="message-bubble thinking">
                <LoaderCircle class="spinning" :size="16" />
                <span>正在解析问题并查询知识图谱</span>
                <i></i><i></i><i></i>
              </div>
            </div>
          </article>
        </div>

        <form class="question-form" @submit.prevent="submitQuestion()">
          <div class="input-shell">
            <MessageCircleMore :size="19" />
            <textarea
              v-model="question"
              rows="1"
              maxlength="120"
              placeholder="请输入问题，例如：山东省有多少古建筑？"
              @keydown.enter.exact.prevent="submitQuestion()"
            ></textarea>
            <span>{{ question.length }}/120</span>
          </div>
          <button type="submit" :disabled="loading || !question.trim()">
            <LoaderCircle v-if="loading" class="spinning" :size="17" />
            <Send v-else :size="17" />
            {{ loading ? "查询中" : "发送问题" }}
          </button>
        </form>
      </section>
    </section>
  </main>
</template>

<style scoped>
.qa-page {
  --ink: #40352f;
  --muted: #806f63;
  --red: #943a32;
  --gold: #b58951;
  min-height: 100vh;
  padding: 30px clamp(18px, 3.5vw, 58px) 50px;
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
  max-width: 720px;
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

.assistant-status {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 22px;
  margin-top: 22px;
  padding: 15px 19px;
  border: 1px solid rgba(164, 118, 68, 0.32);
  border-radius: 8px;
  background: rgba(255, 251, 239, 0.82);
  box-shadow: 0 10px 28px rgba(81, 52, 34, 0.06);
}

.assistant-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.assistant-brand > span {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  color: #f6e2b2;
  border-radius: 50%;
  background: linear-gradient(135deg, #a33f35, #742720);
}

.assistant-brand > div {
  display: grid;
  gap: 3px;
}

.assistant-brand strong {
  color: #74362f;
  font-size: 15px;
}

.assistant-brand small {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #75896d;
  font-size: 10px;
}

.assistant-brand small i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #6f946d;
  box-shadow: 0 0 0 3px rgba(111, 148, 109, 0.13);
}

.status-items {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 9px;
}

.status-items span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 9px;
  color: #776052;
  border: 1px solid rgba(178, 134, 81, 0.22);
  border-radius: 18px;
  background: rgba(247, 237, 215, 0.62);
  font-size: 10px;
}

.assistant-status > button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  color: #805344;
  border: 1px solid #d5bb92;
  border-radius: 5px;
  background: rgba(255, 250, 237, 0.74);
  cursor: pointer;
}

.workspace-grid {
  display: grid;
  grid-template-columns: 275px minmax(0, 1fr);
  gap: 17px;
  margin-top: 17px;
}

.guide-panel,
.chat-panel {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(168, 122, 70, 0.3);
  border-radius: 9px;
  background: rgba(255, 252, 243, 0.87);
  box-shadow: 0 12px 32px rgba(74, 46, 29, 0.07);
}

.guide-panel {
  display: flex;
  flex-direction: column;
  padding: 20px;
}

.guide-figure {
  position: relative;
  flex: 1;
  min-height: 90px;
  margin-top: 12px;
  opacity: 0.5;
  background: url("../assets/pavilion-composition.png") center bottom / contain
    no-repeat;
}

.guide-panel header {
  position: relative;
  display: flex;
  align-items: center;
  gap: 9px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(167, 124, 74, 0.18);
}

.guide-panel header > span {
  width: 35px;
  height: 35px;
  display: grid;
  place-items: center;
  color: #8e3b32;
  border-radius: 50%;
  background: #f2e2c0;
}

.guide-panel header > div {
  display: grid;
  gap: 2px;
}

.guide-panel header strong {
  color: #73362f;
  font-size: 16px;
}

.guide-panel header small {
  color: var(--muted);
  font-size: 11.5px;
}

.suggestion-list {
  position: relative;
  display: grid;
  gap: 9px;
  margin-top: 15px;
}

.suggestion-list button {
  min-height: 62px;
  display: grid;
  grid-template-columns: 26px 1fr auto;
  align-items: center;
  gap: 9px;
  padding: 10px 12px;
  color: #675348;
  border: 1px solid rgba(184, 140, 87, 0.24);
  border-radius: 6px;
  background: linear-gradient(135deg, #fffaf0, #f3e5c8);
  text-align: left;
  cursor: pointer;
  transition: 0.2s ease;
}

.suggestion-list button:hover {
  border-color: #bd9664;
  transform: translateX(3px);
}

.suggestion-list i {
  color: #b08a5c;
  font-family: Georgia, serif;
  font-size: 12px;
  font-style: normal;
}

.suggestion-list span {
  font-size: 13px;
  line-height: 1.5;
}

.suggestion-list svg {
  color: #a46f3e;
}

.ability-list {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 17px;
  margin-bottom: 0;
}

.ability-list span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #806653;
  font-size: 11.5px;
}

.guide-note {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-top: 12px;
  padding: 12px;
  color: #8d674b;
  border-left: 2px solid #b88b54;
  background: rgba(242, 228, 201, 0.5);
}

.guide-note p {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.65;
}

.chat-panel {
  min-height: 640px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
}

.ornate-frame {
  position: absolute;
  inset: 0;
  z-index: 8;
  opacity: 0.18;
  background: url("../assets/search-card-frame-v2.png") center / 102% 135%
    no-repeat;
  pointer-events: none;
}

.chat-header {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 23px 14px;
  color: #a27340;
  border-bottom: 1px solid rgba(169, 126, 77, 0.19);
}

.chat-header h2 {
  margin: 4px 0 0;
  color: #6e342f;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 22px;
  font-weight: 600;
}

.conversation {
  position: relative;
  z-index: 2;
  max-height: 535px;
  overflow-y: auto;
  padding: 22px 25px;
  scroll-behavior: smooth;
}

.conversation::-webkit-scrollbar {
  width: 6px;
}

.conversation::-webkit-scrollbar-thumb {
  border-radius: 8px;
  background: #d1b486;
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 20px;
}

.message-row.user {
  flex-direction: row-reverse;
}

.avatar {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  color: #f6e0ad;
  border-radius: 50%;
  background: linear-gradient(135deg, #9c3c33, #6d2721);
  box-shadow: 0 5px 12px rgba(101, 42, 34, 0.15);
}

.user .avatar {
  color: #81583d;
  border: 1px solid #d2b588;
  background: #f2e3c5;
}

.message-content {
  width: min(78%, 760px);
}

.user .message-content {
  display: grid;
  justify-items: end;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 5px;
}

.message-meta strong {
  color: #684b40;
  font-size: 10px;
}

.message-meta span {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: #a18d7d;
  font-size: 8px;
}

.message-bubble {
  position: relative;
  display: inline-block;
  max-width: 100%;
  padding: 12px 14px;
  color: #604e44;
  border: 1px solid rgba(178, 134, 82, 0.24);
  border-radius: 3px 12px 12px 12px;
  background: #fbf3e2;
  box-shadow: 0 5px 14px rgba(76, 49, 31, 0.05);
}

.user .message-bubble {
  color: #fff8e9;
  border-color: transparent;
  border-radius: 12px 3px 12px 12px;
  background: linear-gradient(135deg, #9f4036, #7c2c26);
}

.message-bubble.failed {
  color: #8a302b;
  background: #fff0e8;
}

.message-bubble p {
  margin: 0;
  font-size: 12px;
  line-height: 1.8;
}

.intent-tag {
  display: inline-block;
  margin-bottom: 7px;
  padding: 3px 7px;
  color: #8b493b;
  border: 1px solid rgba(165, 105, 58, 0.22);
  border-radius: 12px;
  background: rgba(239, 220, 184, 0.55);
  font-size: 8px;
}

.evidence-line {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 8px;
  padding-top: 7px;
  color: #8b7a63;
  border-top: 1px dashed rgba(178, 134, 82, 0.32);
  font-size: 9px;
}

.evidence-line em {
  color: #a26c3b;
  font-style: normal;
}

.answer-results {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  margin-top: 10px;
}

.result-card {
  min-width: 0;
  display: grid;
  grid-template-columns: 70px 1fr;
  gap: 10px;
  padding: 8px;
  border: 1px solid rgba(178, 132, 77, 0.24);
  border-radius: 6px;
  background: rgba(255, 250, 237, 0.9);
}

.result-image {
  height: 66px;
  display: grid;
  place-items: center;
  overflow: hidden;
  color: #af8b60;
  border-radius: 4px;
  background: #eadcc2;
}

.result-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.result-copy {
  min-width: 0;
  display: grid;
  align-content: center;
  gap: 4px;
}

.result-copy > strong {
  overflow: hidden;
  color: #753a33;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-copy p {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin: 0;
}

.result-copy p span {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: #806b5e;
  font-size: 8px;
}

.result-copy small,
.result-copy em {
  overflow: hidden;
  color: #9a8879;
  font-size: 8px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-copy em {
  color: #a26c3b;
}

.thinking {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.thinking > span {
  font-size: 10px;
}

.thinking > i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #b18350;
  animation: pulse 1s ease-in-out infinite;
}

.thinking > i:nth-last-child(2) {
  animation-delay: 0.15s;
}

.thinking > i:last-child {
  animation-delay: 0.3s;
}

.question-form {
  position: relative;
  z-index: 9;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  padding: 15px 20px 19px;
  border-top: 1px solid rgba(169, 126, 77, 0.2);
  background: rgba(248, 239, 220, 0.72);
}

.input-shell {
  min-height: 44px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 9px;
  padding: 0 12px;
  color: #9b6d3d;
  border: 1px solid #cdb384;
  border-radius: 7px;
  background: linear-gradient(#fff9e9, #f2e2bf);
  box-shadow: inset 0 1px rgba(255, 255, 255, 0.8);
}

.input-shell:focus-within {
  border-color: #a87743;
  box-shadow: 0 0 0 2px rgba(168, 119, 67, 0.11);
}

.input-shell textarea {
  width: 100%;
  padding: 11px 0;
  resize: none;
  color: #53453c;
  border: 0;
  outline: 0;
  background: transparent;
  font-family: inherit;
  font-size: 12px;
}

.input-shell textarea::placeholder {
  color: #9f8a71;
}

.input-shell > span {
  color: #ad9780;
  font-size: 8px;
}

.question-form > button {
  min-width: 108px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: #fff8e8;
  border: 0;
  border-radius: 6px;
  background: linear-gradient(135deg, #a53e34, #76251f);
  box-shadow: 0 7px 15px rgba(112, 38, 31, 0.16);
  cursor: pointer;
}

.question-form > button:disabled,
.suggestion-list button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
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

@keyframes pulse {
  0%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  50% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

@media (max-width: 980px) {
  .assistant-status {
    grid-template-columns: 1fr auto;
  }

  .status-items {
    grid-column: 1 / -1;
    grid-row: 2;
    justify-content: flex-start;
  }

  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .guide-panel {
    order: 2;
  }
}

@media (max-width: 650px) {
  .qa-page {
    padding-inline: 14px;
  }

  .hero-palace {
    opacity: 0.08;
  }

  .assistant-status {
    grid-template-columns: 1fr;
  }

  .status-items {
    grid-column: auto;
    grid-row: auto;
  }

  .assistant-status > button {
    justify-self: start;
  }

  .chat-panel {
    min-height: 600px;
  }

  .message-content {
    width: calc(100% - 46px);
  }

  .answer-results {
    grid-template-columns: 1fr;
  }

  .question-form {
    grid-template-columns: 1fr;
  }

  .question-form > button {
    height: 42px;
  }
}
</style>
