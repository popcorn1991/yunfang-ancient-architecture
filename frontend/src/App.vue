<script setup>
import { onMounted, ref } from "vue"
import logo01 from "./assets/logo01.png"
import {
  BarChart3,
  Database,
  LayoutDashboard,
  MessageCircle,
  Network,
  Search,
  Sparkles
} from "lucide-vue-next"

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"

const connected = ref(false)
const checking = ref(true)

const navItems = [
  { name: "数据总览", path: "/", icon: LayoutDashboard },
  { name: "高级检索", path: "/search", icon: Search },
  { name: "图谱探索", path: "/graph", icon: Network },
  { name: "智能推荐", path: "/recommend", icon: Sparkles },
  { name: "统计分析", path: "/analysis", icon: BarChart3 },
  { name: "智能问答", path: "/qa", icon: MessageCircle }
]

async function checkBackend() {
  checking.value = true

  try {
    const response = await fetch(`${API_BASE}/api/health`)
    connected.value = response.ok
  } catch {
    connected.value = false
  } finally {
    checking.value = false
  }
}

onMounted(checkBackend)
</script>

<template>
  <div class="app-shell">
    <aside class="side-navigation">
      <div class="brand">
        <div class="brand-icon">
          <img :src="logo01" alt="云访古建 logo" class="brand-logo" />
        </div>

        <div class="brand-text">
          <strong>云访古建</strong>
          <span>中华古建筑知识图谱</span>
        </div>
      </div>

      <div class="side-decoration" aria-hidden="true">
        <span></span>
        <strong>中华营造</strong>
        <span></span>
      </div>

      <nav class="main-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
        >
          <component :is="item.icon" :size="17" />
          <span>{{ item.name }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <button
          class="database-status"
          :class="{ connected }"
          title="点击重新检测后端连接"
          @click="checkBackend"
        >
          <Database :size="16" />
          <span v-if="checking">正在检测</span>
          <span v-else-if="connected">Neo4j 已连接</span>
          <span v-else>服务未连接</span>
          <i></i>
        </button>

        <p>知识图谱 · 数字传承</p>
      </div>
    </aside>

    <div class="content-shell">
      <div class="top-decoration">
        <span></span>
        <strong>中华营造 · 数字传承</strong>
        <span></span>
      </div>

      <main class="page-container">
        <RouterView />
      </main>

      <footer class="site-footer">
        <div class="footer-emblem">云访古建</div>

        <div>
          <strong>中华古建筑智能旅游推荐系统</strong>
          <p>知识图谱 · 智能检索 · 旅游推荐 · 文化传播</p>
        </div>

        <span class="footer-note">数据由 Neo4j 图数据库提供支持</span>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.side-navigation {
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 80;
  display: flex;
  flex-direction: column;
  width: 238px;
  padding: 27px 18px 22px;
  border-right: 1px solid rgba(149, 62, 45, 0.18);
  background:
    linear-gradient(
      180deg,
      rgba(255, 250, 239, 0.96) 0%,
      rgba(255, 250, 239, 0.78) 46%,
      rgba(252, 244, 226, 0.42) 100%
    ),
    url("./assets/nav-palace-bg.jpg") center bottom / cover no-repeat;
  box-shadow: 7px 0 24px rgba(75, 46, 31, 0.08);
  backdrop-filter: blur(14px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 7px;
}

.brand-icon {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  padding: 2px;
  border: 2px solid rgba(255, 255, 255, 0.92);
  border-radius: 50%;
  background: linear-gradient(135deg, #fffaf0, #f6e7d0 42%, #f2f8ff 100%);
  box-shadow: 0 5px 13px rgba(123, 43, 35, 0.18), 0 0 0 1px rgba(197, 147, 81, 0.4);
  overflow: hidden;
}

.brand-logo {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  border-radius: 50%;
  background: #fff;
}

.brand-text {
  display: grid;
  white-space: nowrap;
}

.brand-text strong {
  color: #883229;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 4px;
}

.brand-text span {
  margin-top: 2px;
  color: #a17c5a;
  font-size: 11px;
  letter-spacing: 1px;
}

.side-decoration {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 24px 8px 17px;
  color: #b18b60;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 11px;
  letter-spacing: 3px;
  white-space: nowrap;
}

.side-decoration span {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, #c4975d);
}

.side-decoration span:last-child {
  background: linear-gradient(90deg, #c4975d, transparent);
}

.main-nav {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 45px;
  padding: 0 15px;
  border: 1px solid transparent;
  border-radius: 9px;
  color: #65716a;
  font-size: 14px;
  letter-spacing: 1px;
  text-decoration: none;
  transition: 0.22s ease;
}

.nav-item:hover {
  color: #91382e;
  border-color: rgba(158, 61, 48, 0.1);
  background: rgba(158, 61, 48, 0.055);
  transform: translateX(3px);
}

.nav-item.router-link-exact-active {
  color: #91382e;
  border-color: rgba(158, 61, 48, 0.16);
  background: linear-gradient(90deg, rgba(158, 61, 48, 0.12), rgba(208, 161, 83, 0.06));
  box-shadow: inset 3px 0 0 #9a3d32;
}

.nav-item.router-link-exact-active::after {
  content: "";
  position: absolute;
  right: 14px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #c3904f;
  box-shadow: 0 0 0 4px rgba(195, 144, 79, 0.12);
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 18px;
  border-top: 1px solid rgba(150, 85, 51, 0.16);
}

.sidebar-footer p {
  margin: 12px 0 0;
  color: #aa8b6b;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 11px;
  letter-spacing: 2px;
  text-align: center;
}

.database-status {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid rgba(151, 91, 58, 0.22);
  border-radius: 8px;
  background: rgba(255, 252, 244, 0.9);
  color: #8b5c43;
  font-size: 12px;
  cursor: pointer;
}

.database-status i {
  margin-left: auto;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #b94b3d;
  box-shadow: 0 0 0 3px rgba(185, 75, 61, 0.11);
}

.database-status.connected i {
  background: #397e6d;
  box-shadow: 0 0 0 3px rgba(57, 126, 109, 0.12);
}

.content-shell {
  min-width: 0;
  margin-left: 238px;
}

.top-decoration {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 13px;
  height: 34px;
  color: #b18b60;
  font-family: "STKaiti", "KaiTi", serif;
  font-size: 12px;
  letter-spacing: 4px;
}

.top-decoration span {
  width: 70px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #c4975d);
}

.top-decoration span:last-child {
  background: linear-gradient(90deg, #c4975d, transparent);
}

.page-container {
  position: relative;
  width: min(1800px, calc(100% - 80px));
  margin: 0 auto;
}

.site-footer {
  display: flex;
  align-items: center;
  gap: 14px;
  width: min(1800px, calc(100% - 80px));
  margin: 30px auto 0;
  padding: 25px 5px 34px;
  border-top: 1px solid rgba(150, 85, 51, 0.18);
  color: #87715e;
}

.footer-emblem {
  display: grid;
  place-items: center;
  width: 45px;
  height: 45px;
  border: 1px solid #aa4a3b;
  color: #97382e;
  font-family: "STKaiti", "KaiTi", serif;
}

.site-footer strong {
  color: #6d4939;
  font-family: "STKaiti", "KaiTi", serif;
}

.site-footer p {
  margin: 4px 0 0;
  font-size: 12px;
}

.footer-note {
  margin-left: auto;
  font-size: 12px;
}

@media (max-width: 1150px) {
  .side-navigation {
    width: 204px;
    padding-right: 13px;
    padding-left: 13px;
  }

  .content-shell {
    margin-left: 204px;
  }

  .brand-text span {
    display: none;
  }
}

@media (max-width: 700px) {
  .side-navigation {
    top: auto;
    right: 0;
    bottom: 0;
    width: auto;
    height: 66px;
    padding: 7px 10px;
    border-top: 1px solid rgba(149, 62, 45, 0.18);
    border-right: 0;
    background: rgba(255, 250, 239, 0.97);
    box-shadow: 0 -5px 18px rgba(75, 46, 31, 0.08);
  }

  .brand,
  .side-decoration,
  .sidebar-footer {
    display: none;
  }

  .main-nav {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 2px;
    height: 100%;
  }

  .nav-item {
    flex-direction: column;
    justify-content: center;
    gap: 3px;
    min-width: 0;
    min-height: 0;
    padding: 3px 1px;
    font-size: 10px;
    letter-spacing: 0;
  }

  .nav-item:hover {
    transform: none;
  }

  .nav-item.router-link-exact-active {
    box-shadow: inset 0 -3px 0 #9a3d32;
  }

  .nav-item.router-link-exact-active::after {
    display: none;
  }

  .content-shell {
    margin-left: 0;
    padding-bottom: 66px;
  }

  .page-container,
  .site-footer {
    width: min(100% - 28px, 1800px);
  }

  .footer-note {
    display: none;
  }
}
</style>
