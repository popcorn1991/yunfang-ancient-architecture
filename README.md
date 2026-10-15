# 云访古建

基于知识图谱的中华古建筑检索与智能旅游推荐系统

“云访古建”面向中华古建筑知识查询与文旅应用场景，以 Neo4j 知识图谱为数据底座，实现古建筑信息的结构化管理、组合检索、关系探索、智能推荐、统计分析和自然语言问答。

## 项目功能

* **数据总览**：展示古建筑知识图谱的数据规模及主要内容。
* **高级检索**：按照建筑名称、省份、时代、建筑类型和保护级别等条件组合查询。
* **图谱探索**：以交互式关系图展示古建筑与地点、时代、类型、构件、材料、人物等实体之间的关联。
* **智能推荐**：依据地域、时代、建筑类型等图谱关系生成可解释的旅游推荐结果。
* **统计分析**：统计不同省份、时代、类型及保护级别下的古建筑分布。
* **智能问答**：通过 Neo4j 检索图谱事实，并结合 DeepSeek 生成有知识依据的自然语言回答。

## 技术栈

### 前端

* Vue 3
* Vite
* Vue Router
* ECharts / 图谱可视化组件

### 后端

* Python 3.14
* FastAPI
* Uvicorn
* Neo4j Python Driver
* DeepSeek API

### 数据存储

* Neo4j Community 2026.08.1
* Cypher 图查询语言

## 项目结构

```text
yunfang-ancient-architecture/
├─ backend/                 # FastAPI后端程序
│  ├─ main.py
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/                # Vue 3前端程序
│  ├─ src/
│  ├─ public/
│  ├─ package.json
│  └─ .env.example
├─ .gitignore
└─ README.md
```

## 环境配置

### 后端配置

复制 `backend/.env.example` 并重命名为 `backend/.env`，填写本机配置：

```env
NEO4J\_URI=bolt://127.0.0.1:7687
NEO4J\_USER=neo4j
NEO4J\_PASSWORD=你的Neo4j密码
NEO4J\_DATABASE=neo4j

DEEPSEEK\_API\_KEY=你的DeepSeek\_API\_Key
DEEPSEEK\_BASE\_URL=https://api.deepseek.com
```

安装后端依赖：

```powershell
cd backend
py -3.14 -m pip install -r requirements.txt
```

### 前端配置

复制 `frontend/.env.example` 并重命名为 `frontend/.env`：

```env
VITE\_API\_BASE\_URL=http://127.0.0.1:8000
```

安装前端依赖：

```powershell
cd frontend
npm install
```

## 运行步骤

电脑重启后，需要依次启动 Neo4j、后端和前端，共使用三个 PowerShell 窗口。以下命令中的路径为本项目开发环境路径，其他计算机运行时请替换为实际安装路径。

### 1\. 启动 Neo4j

打开第一个 PowerShell：

```powershell
$env:NEO4J\_HOME = "E:\\neo4j-community-2026.08.1-windows\\neo4j-community-2026.08.1"
Remove-Item Env:NEO4J\_CONF -ErrorAction SilentlyContinue
cd "$env:NEO4J\_HOME\\bin"
.\\neo4j console
```

出现以下信息表示启动成功：

```text
Started.
HTTP enabled on localhost:7474
Bolt enabled on localhost:7687
```

Neo4j 浏览器地址：[http://localhost:7474/](http://localhost:7474/)

> 该 PowerShell 窗口需要保持运行，不要关闭。

### 2\. 启动后端

打开第二个 PowerShell：

```powershell
cd "E:\\study\\大三上\\知识图谱\\中华古建筑智能旅游推荐系统\\backend"
py -3.14 -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

出现以下信息表示启动成功：

```text
Uvicorn running on http://127.0.0.1:8000
```

后端接口文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

该 PowerShell 窗口同样需要保持运行。

### 3\. 启动前端

打开第三个 PowerShell：

```powershell
cd "E:\\study\\大三上\\知识图谱\\中华古建筑智能旅游推荐系统\\frontend"
npm run dev
```

终端显示 `Local` 地址后，在浏览器打开：[http://localhost:5173/](http://localhost:5173/)

## 注意事项

* 首次运行前需完成 Neo4j 数据导入，否则前端无法查询图谱数据。
* 启动后端前应先启动 Neo4j，启动前端前应确保后端服务正常运行。
* 当前项目默认使用本地开发地址，不同计算机运行时需要修改相应路径和环境变量。

## 项目说明

本项目为《知识图谱技术及应用》课程实验作品，主要用于知识图谱构建、查询、推理与应用程序设计的学习和展示。

