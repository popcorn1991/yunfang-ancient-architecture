import json
import os
import re
import time
import urllib.request
from contextlib import asynccontextmanager
from typing import Annotated, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from pydantic import BaseModel


load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# DeepSeek 仅负责理解问题与组织语言，事实一律来自 Neo4j
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"
)
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
DEEPSEEK_TIMEOUT = 10

# DeepSeek 服务熔断：连续失败若干次后进入短冷却期，期内直接回退规则模板，
# 避免上游过载时每次问答都空等到超时，让 /api/qa 始终秒级响应；
# 冷却期保持较短，保证上游恢复后能尽快重新启用大模型作答。
DEEPSEEK_FAILURE_LIMIT = 2
DEEPSEEK_COOLDOWN_SECONDS = 60
_deepseek_failures = 0
_deepseek_cooldown_until = 0.0

driver = None


def query(cypher: str, **parameters):
    records, _, _ = driver.execute_query(
        cypher,
        parameters_=parameters,
        database_=NEO4J_DATABASE,
    )
    return [record.data() for record in records]


@asynccontextmanager
async def lifespan(_: FastAPI):
    global driver
    if not NEO4J_PASSWORD:
        raise RuntimeError("请在.env文件中设置NEO4J_PASSWORD")
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )
    driver.verify_connectivity()
    yield
    driver.close()


app = FastAPI(
    title="中华古建筑知识图谱智能旅游推荐系统",
    description="提供知识图谱检索、图谱探索、统计分析和可解释旅游推荐接口",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str
    # 多轮对话上下文：上一轮推荐的基准建筑与答案代表建筑
    last_seed: Optional[str] = None
    last_building: Optional[str] = None


def administrative_alias(name: str) -> str:
    """生成省级行政区常用简称，用于自然语言问题中的宽松匹配。"""
    return re.sub(r"(壮族自治区|回族自治区|维吾尔自治区|特别行政区|自治区|省|市)$", "", name)


@app.get("/")
def root():
    return {
        "system": "中华古建筑知识图谱智能旅游推荐系统",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    result = query("RETURN 1 AS ok")
    return {
        "status": "ok",
        "neo4j": result[0]["ok"] == 1,
        # 供排查用：DeepSeek 密钥是否已从 .env 载入（不返回密钥本身）
        "deepseek_configured": bool(DEEPSEEK_API_KEY),
    }


@app.get("/api/stats")
def stats():
    result = query(
        """
        MATCH (n)
        WITH count(n) AS node_count
        MATCH ()-[r]->()
        WITH node_count, count(r) AS relationship_count
        OPTIONAL MATCH (b:古建筑)
        WITH node_count, relationship_count, count(b) AS building_count
        OPTIONAL MATCH (p:省级行政区)
        WITH node_count, relationship_count, building_count, count(p) AS province_count
        OPTIONAL MATCH (h:历史时期)
        RETURN node_count, relationship_count, building_count,
               province_count, count(h) AS period_count
        """
    )[0]
    result["recommendation_count"] = query(
        "MATCH ()-[r:旅游推荐]->() RETURN count(r) AS c"
    )[0]["c"]
    return result


@app.get("/api/filters")
def filters():
    provinces = query(
        "MATCH (p:省级行政区) RETURN p.name AS name ORDER BY name"
    )
    locations = query(
        "MATCH (l:具体地点) RETURN DISTINCT l.name AS name ORDER BY name"
    )
    periods = query(
        "MATCH (h:历史时期) RETURN h.name AS name ORDER BY name"
    )
    eras = query(
        "MATCH (e:时代)<-[:建造时代]-(:古建筑) "
        "RETURN DISTINCT e.name AS name ORDER BY name"
    )
    types = query(
        "MATCH (t:建筑类型)<-[:建筑类型]-(:古建筑) "
        "RETURN DISTINCT t.name AS name ORDER BY name"
    )
    components = query(
        "MATCH (c:建筑构件)<-[:具有构件]-(:古建筑) "
        "RETURN DISTINCT c.name AS name ORDER BY name"
    )
    materials = query(
        "MATCH (m:建筑材料)<-[:使用材料]-(:古建筑) "
        "RETURN DISTINCT m.name AS name ORDER BY name"
    )
    persons = query(
        "MATCH (n:人物)<-[:相关人物]-(:古建筑) "
        "RETURN DISTINCT n.name AS name ORDER BY name"
    )
    protections = query(
        "MATCH (p:保护级别)<-[:保护级别]-(:古建筑) "
        "RETURN DISTINCT p.name AS name ORDER BY name"
    )
    return {
        "provinces": [x["name"] for x in provinces],
        "locations": [x["name"] for x in locations],
        "periods": [x["name"] for x in periods],
        "eras": [x["name"] for x in eras],
        "types": [x["name"] for x in types],
        "components": [x["name"] for x in components],
        "materials": [x["name"] for x in materials],
        "persons": [x["name"] for x in persons],
        "protections": [x["name"] for x in protections],
    }


@app.get("/api/buildings")
def search_buildings(
    keyword: Optional[str] = None,
    province: Optional[str] = None,
    period: Optional[str] = None,
    era: Optional[str] = None,
    protection: Optional[str] = None,
    building_type: Optional[str] = None,
    type_any: Annotated[Optional[list[str]], Query()] = None,
    location: Optional[str] = None,
    component: Optional[str] = None,
    material: Optional[str] = None,
    material_any: Annotated[Optional[list[str]], Query()] = None,
    person: Optional[str] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 12,
):
    skip = (page - 1) * page_size
    rows = query(
        """
        MATCH (b:古建筑)
        WITH b,
             [(b)-[:位于]->(p:省级行政区) | p.name] AS provinces,
             [(b)-[:建造时代]->(e:时代) | e.name] AS eras,
             [(b)-[:属于时期]->(h:历史时期) | h.name] AS periods,
             [(b)-[:保护级别]->(pl:保护级别) | pl.name] AS protections,
             [(b)-[:建筑类型]->(t:建筑类型) | t.name] AS types,
             [(b)-[:具体地点]->(s:具体地点) | s.name] AS locations,
             [(b)-[:具有构件]->(c:建筑构件) | c.name] AS components,
             [(b)-[:使用材料]->(m:建筑材料) | m.name] AS materials,
             [(b)-[:相关人物]->(n:人物) | n.name] AS persons
        WHERE ($keyword IS NULL OR $keyword = '' OR
               toLower(b.name) CONTAINS toLower($keyword) OR
               toLower(coalesce(b.summary_text, '')) CONTAINS toLower($keyword))
          AND ($province IS NULL OR $province = '' OR $province IN provinces)
          AND ($period IS NULL OR $period = '' OR $period IN periods)
          AND ($era IS NULL OR $era = '' OR $era IN eras)
          AND ($protection IS NULL OR $protection = '' OR $protection IN protections)
          AND ($building_type IS NULL OR $building_type = '' OR $building_type IN types)
          AND ($type_any IS NULL OR size($type_any) = 0 OR
               any(one IN types WHERE one IN $type_any))
          AND ($location IS NULL OR $location = '' OR $location IN locations)
          AND ($component IS NULL OR $component = '' OR $component IN components)
          AND ($material IS NULL OR $material = '' OR $material IN materials)
          AND ($material_any IS NULL OR size($material_any) = 0 OR
               any(one IN materials WHERE one IN $material_any))
          AND ($person IS NULL OR $person = '' OR $person IN persons)
        WITH b, provinces, eras, periods, protections,
             types, locations, components, materials, persons
        ORDER BY b.name
        WITH collect({
            record_id: b.record_id,
            name: b.name,
            province: head(provinces),
            location: b.location,
            era: head(eras),
            period: head(periods),
            type: head(types),
            protection_level: head(protections),
            locations: locations,
            types: types,
            components: components,
            materials: materials,
            persons: persons,
            image_url: b.image_url,
            summary_text: b.summary_text
        }) AS all_items
        RETURN size(all_items) AS total,
               all_items[$skip..$skip + $page_size] AS items
        """,
        keyword=keyword,
        province=province,
        period=period,
        era=era,
        protection=protection,
        building_type=building_type,
        type_any=type_any or [],
        location=location,
        component=component,
        material=material,
        material_any=material_any or [],
        person=person,
        skip=skip,
        page_size=page_size,
    )[0]
    return {"page": page, "page_size": page_size, **rows}


@app.get("/api/buildings/{record_id}")
def building_detail(record_id: str):
    rows = query(
        """
        MATCH (b:古建筑 {record_id: $record_id})
        OPTIONAL MATCH (b)-[r]->(n)
        RETURN properties(b) AS building,
               collect(DISTINCT {
                   relation: type(r),
                   target: coalesce(n.name, n.record_id),
                   target_labels: labels(n)
               }) AS knowledge
        """,
        record_id=record_id,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="未找到该古建筑")
    return rows[0]


def add_graph_node(nodes: dict, node_id, name, node_type: str):
    """按 id 去重地登记一个图谱节点。"""
    key = str(node_id)
    if key not in nodes:
        nodes[key] = {
            "id": key,
            "name": name or key,
            "node_type": node_type or "其他",
        }


@app.get("/api/graph/overview")
def overview_graph(
    include_recommend: bool = False,
    limit: int = Query(20000, ge=100, le=40000),
):
    """全库总图谱：1604 座古建筑 + 全部共享实体节点。

    默认排除建筑之间的 4033 条 :旅游推荐 推理边，否则总图谱无法清晰渲染。
    """
    nodes: dict = {}
    links = []

    for row in query(
        "MATCH (b:古建筑) RETURN b.record_id AS id, b.name AS name ORDER BY name"
    ):
        add_graph_node(nodes, row["id"], row["name"], "古建筑")

    for row in query(
        """
        MATCH (b:古建筑)-[r]->(n)
        WHERE NOT n:古建筑
        RETURN b.record_id AS source_id,
               elementId(n) AS target_id,
               coalesce(n.name, n.record_id) AS target_name,
               labels(n) AS target_labels,
               type(r) AS relation
        """
    ):
        add_graph_node(
            nodes, row["target_id"], row["target_name"], row["target_labels"][0]
        )
        links.append(
            {
                "source": row["source_id"],
                "target": str(row["target_id"]),
                "relation": row["relation"],
            }
        )

    if include_recommend:
        for row in query(
            """
            MATCH (a:古建筑)-[r:旅游推荐]->(b:古建筑)
            RETURN a.record_id AS source_id,
                   b.record_id AS target_id,
                   type(r) AS relation
            """
        ):
            links.append(
                {
                    "source": row["source_id"],
                    "target": row["target_id"],
                    "relation": row["relation"],
                }
            )

    return {
        "mode": "overview",
        "nodes": list(nodes.values()),
        "links": links[:limit],
        "node_count": len(nodes),
        "link_count": len(links[:limit]),
        "include_recommend": include_recommend,
    }


@app.get("/api/graph/province/{name}")
def province_graph(name: str, limit: int = Query(20000, ge=100, le=40000)):
    """省份图谱：省份枢纽 + 省内全部古建筑 + 这些建筑关联的共享实体。"""
    province = query(
        "MATCH (p:省级行政区 {name: $name}) "
        "RETURN elementId(p) AS id, p.name AS name",
        name=name,
    )
    if not province:
        raise HTTPException(status_code=404, detail=f"未收录省级行政区：{name}")

    nodes: dict = {}
    links = []
    center_id = str(province[0]["id"])
    add_graph_node(nodes, center_id, province[0]["name"], "省级行政区")

    rows = query(
        """
        MATCH (b:古建筑)-[loc:位于]->(p:省级行政区 {name: $name})
        MATCH (b)-[r]->(n)
        WHERE NOT n:古建筑
        RETURN b.record_id AS building_id,
               b.name AS building_name,
               elementId(n) AS entity_id,
               coalesce(n.name, n.record_id) AS entity_name,
               labels(n) AS entity_labels,
               type(r) AS relation
        """,
        name=name,
    )
    for row in rows:
        add_graph_node(nodes, row["building_id"], row["building_name"], "古建筑")
        add_graph_node(
            nodes, row["entity_id"], row["entity_name"], row["entity_labels"][0]
        )
        links.append(
            {
                "source": row["building_id"],
                "target": str(row["entity_id"]),
                "relation": row["relation"],
            }
        )

    return {
        "mode": "province",
        "province": name,
        "nodes": list(nodes.values()),
        "links": links[:limit],
        "node_count": len(nodes),
        "link_count": len(links[:limit]),
    }


@app.get("/api/graph/relations")
def relation_graph(
    names: Optional[str] = None,
    ids: Optional[str] = None,
    max_seeds: int = Query(40, ge=2, le=60),
    max_bridges: int = Query(80, ge=0, le=200),
):
    """多实体关系图谱：所选实体互相关联，并展开被其中两个以上共享的桥接实体。"""
    name_list = [x.strip() for x in (names or "").split(",") if x.strip()]
    id_list = [x.strip() for x in (ids or "").split(",") if x.strip()]
    if not name_list and not id_list:
        raise HTTPException(status_code=400, detail="请至少提供两个实体名称或编号")

    seeds = []
    seen = set()

    def push_seed(row):
        if row["id"] in seen:
            return
        seen.add(row["id"])
        seeds.append(row)

    if id_list:
        for row in query(
            """
            MATCH (n)
            WHERE n.record_id IN $ids
            RETURN coalesce(n.record_id, elementId(n)) AS id,
                   coalesce(n.name, n.record_id) AS name,
                   labels(n)[0] AS node_type
            ORDER BY name
            LIMIT $limit
            """,
            ids=id_list,
            limit=max_seeds,
        ):
            push_seed(row)

    if name_list:
        for entry in name_list[:max_seeds]:
            # 每条输入只取一个最佳匹配：完全相同 → 名称包含该输入（取最短，最具体）
            # → 该输入包含名称（取最长）。避免“唐”这类短词泛化出大量无关实体。
            rows = query(
                """
                MATCH (n)
                WHERE coalesce(n.name, '') <> ''
                  AND (toLower(n.name) CONTAINS toLower($q)
                       OR toLower($q) CONTAINS toLower(n.name))
                WITH n, size(n.name) AS name_len,
                     CASE
                       WHEN toLower(n.name) = toLower($q) THEN 0
                       WHEN toLower(n.name) CONTAINS toLower($q) THEN 1
                       ELSE 2
                     END AS match_rank
                RETURN coalesce(n.record_id, elementId(n)) AS id,
                       n.name AS name,
                       labels(n)[0] AS node_type
                ORDER BY match_rank,
                         CASE WHEN match_rank = 2 THEN -name_len ELSE name_len END
                LIMIT 1
                """,
                q=entry,
            )
            for row in rows:
                push_seed(row)

    if len(seeds) < 2:
        raise HTTPException(
            status_code=404,
            detail="未能匹配到两个以上实体，请检查名称是否存在于知识图谱中",
        )

    seed_ids = [row["id"] for row in seeds]
    neighbor_rows = query(
        """
        UNWIND $ids AS sid
        MATCH (n)
        WHERE coalesce(n.record_id, elementId(n)) = sid
        MATCH (n)-[r]-(m)
        WHERE NOT coalesce(m.record_id, elementId(m)) IN $ids
        RETURN sid AS seed_id,
               coalesce(m.record_id, elementId(m)) AS other_id,
               coalesce(m.name, m.record_id) AS other_name,
               labels(m)[0] AS other_labels,
               type(r) AS relation
        """,
        ids=seed_ids,
    )

    shared = {}
    neighbors = {}
    for row in neighbor_rows:
        key = str(row["other_id"])
        neighbors.setdefault(key, row)
        shared.setdefault(key, set()).add(row["seed_id"])

    # 邻域节点：被多个所选实体共享的（桥接实体）排在前，其余按名称排列；
    # 两者同时存在时能直观看出所选实体之间的共同语境。
    neighbor_keys = sorted(
        shared,
        key=lambda key: (-len(shared[key]), neighbors[key]["other_name"] or ""),
    )[:max_bridges]
    node_set = set(neighbor_keys) | {str(x) for x in seed_ids}

    nodes: dict = {}
    for row in seeds:
        add_graph_node(nodes, row["id"], row["name"], row["node_type"])
    for key in neighbor_keys:
        row = neighbors[key]
        add_graph_node(nodes, key, row["other_name"], row["other_labels"])

    links = []
    for row in neighbor_rows:
        source = str(row["seed_id"])
        target = str(row["other_id"])
        if target in node_set:
            links.append(
                {"source": source, "target": target, "relation": row["relation"]}
            )

    direct_rows = query(
        """
        UNWIND $ids AS sid
        MATCH (n)-[r]-(m)
        WHERE coalesce(n.record_id, elementId(n)) = sid
          AND NOT coalesce(m.record_id, elementId(m)) = sid
        RETURN DISTINCT coalesce(n.record_id, elementId(n)) AS source_id,
               coalesce(m.record_id, elementId(m)) AS target_id,
               type(r) AS relation
        """,
        ids=seed_ids,
    )
    existing = {(link["source"], link["target"], link["relation"]) for link in links}
    for row in direct_rows:
        source = str(row["source_id"])
        target = str(row["target_id"])
        if target not in node_set:
            continue
        edge = (source, target, row["relation"])
        if edge not in existing:
            existing.add(edge)
            links.append(
                {"source": source, "target": target, "relation": row["relation"]}
            )

    # 种子节点排在前，前端据此标记所选实体（matched_seeds）
    ordered = [nodes[str(row["id"])] for row in seeds] + [
        nodes[key] for key in neighbor_keys
    ]
    return {
        "mode": "relations",
        "nodes": ordered,
        "links": links,
        "matched_seeds": len(seeds),
        "matched_names": [row["name"] for row in seeds],
        "bridge_count": sum(1 for key in neighbor_keys if len(shared[key]) >= 2),
        "node_count": len(ordered),
        "link_count": len(links),
    }


@app.get("/api/graph/{record_id}")
def local_graph(record_id: str, limit: int = Query(80, ge=1, le=200)):
    rows = query(
        """
        MATCH (b:古建筑 {record_id: $record_id})-[r]-(n)
        RETURN b.record_id AS source_id,
               b.name AS source_name,
               labels(b) AS source_labels,
               type(r) AS relation,
               coalesce(n.record_id, n.node_id, elementId(n)) AS target_id,
               coalesce(n.name, n.record_id) AS target_name,
               labels(n) AS target_labels,
               properties(r) AS relation_properties
        LIMIT $limit
        """,
        record_id=record_id,
        limit=limit,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="未找到局部图谱")

    nodes = {}
    links = []
    for row in rows:
        nodes[row["source_id"]] = {
            "id": row["source_id"],
            "name": row["source_name"],
            "category": row["source_labels"][0],
        }
        nodes[row["target_id"]] = {
            "id": row["target_id"],
            "name": row["target_name"],
            "category": row["target_labels"][0],
        }
        links.append(
            {
                "source": row["source_id"],
                "target": row["target_id"],
                "name": row["relation"],
                "properties": row["relation_properties"],
            }
        )
    return {"nodes": list(nodes.values()), "links": links}


@app.get("/api/recommendations/{record_id}")
def recommendations(record_id: str, limit: int = Query(5, ge=1, le=20)):
    rows = query(
        """
        MATCH (b:古建筑 {record_id: $record_id})-[r:旅游推荐]->(target:古建筑)
        OPTIONAL MATCH (target)-[:位于]->(p:省级行政区)
        OPTIONAL MATCH (target)-[:属于时期]->(h:历史时期)
        RETURN target.record_id AS record_id,
               target.name AS name,
               target.location AS location,
               target.image_url AS image_url,
               target.summary_text AS summary_text,
               p.name AS province,
               h.name AS period,
               r.confidence AS confidence,
               r.reason AS reason,
               r.rule_id AS rule_id
        ORDER BY confidence DESC, name
        LIMIT $limit
        """,
        record_id=record_id,
        limit=limit,
    )
    return {"record_id": record_id, "items": rows}


@app.get("/api/analysis/periods")
def period_analysis(province: Optional[str] = None):
    return query(
        """
        MATCH (b:古建筑)-[:属于时期]->(h:历史时期)
        OPTIONAL MATCH (b)-[:位于]->(p:省级行政区)
        WITH h, b, p
        WHERE $province IS NULL OR $province = '' OR p.name = $province
        RETURN h.name AS period, count(DISTINCT b) AS count
        ORDER BY count DESC, period
        """,
        province=province,
    )


@app.get("/api/analysis/overview")
def overview_analysis():
    """首页总览聚合：省级行政区与建筑类型的古建筑数量排行，服务端聚合。"""
    provinces = query(
        """
        MATCH (b:古建筑)-[:位于]->(p:省级行政区)
        RETURN p.name AS name, count(DISTINCT b) AS count
        ORDER BY count DESC, name
        """
    )
    building_types = query(
        """
        MATCH (b:古建筑)-[:建筑类型]->(t:建筑类型)
        RETURN t.name AS name, count(DISTINCT b) AS count
        ORDER BY count DESC, name
        """
    )
    return {
        "provinces": provinces,
        "types": building_types,
    }


QA_SYSTEM_PROMPT = """你是“云访古建”系统的问答助手。

只能根据下方Neo4j知识图谱查询结果回答，
不得使用模型自身知识补充建筑数量、时代、地点或保护级别，
不得虚构查询结果中不存在的信息。

如果查询结果为空，请回答：
“当前知识图谱中暂未收录相关信息。”"""

EMPTY_ANSWER = "当前知识图谱中暂未收录相关信息。"

# 口语类型词 → 图谱中真实存在的建筑类型集合（用于同义扩展检索）
TYPE_GROUPS = {
    "寺庙": ["寺庙", "佛寺", "道观"],
    "寺院": ["寺庙", "佛寺", "道观"],
    "庙": ["寺庙", "佛寺"],
    "塔": ["古塔", "佛塔", "石塔", "砖塔", "木塔"],
    "古塔": ["古塔", "佛塔", "石塔", "砖塔", "木塔"],
    "佛塔": ["佛塔", "古塔", "石塔", "砖塔", "木塔"],
    "桥": ["古桥", "石桥", "廊桥"],
    "祠堂": ["祠堂", "宗祠"],
    "祠": ["祠堂", "宗祠"],
    "园林": ["园林"],
    "宫殿": ["宫殿"],
    "民居": ["民居"],
    "城墙": ["城墙"],
    "书院": ["书院"],
    "牌坊": ["牌坊"],
    "陵墓": ["陵墓", "古墓"],
    "墓": ["陵墓", "古墓"],
    "清真寺": ["清真寺"],
    "文庙": ["文庙"],
    "会馆": ["会馆"],
}

REFERENCE_WORDS = (
    "这个",
    "这座",
    "这处",
    "它",
    "该建筑",
    "该塔",
    "该寺",
    "此建筑",
    "上述",
    "这里",
)

DETAIL_KEYWORDS = (
    "建于",
    "建造",
    "修建",
    "始建于",
    "什么时候",
    "哪年",
    "哪一年",
    "哪一朝",
    "什么时代",
    "哪个时代",
    "什么朝代",
    "哪个朝代",
    "时代",
    "朝代",
    "位于",
    "在哪",
    "哪里",
    "地址",
    "什么位置",
    "保护级别",
    "保护等级",
    "简介",
    "介绍",
    "概况",
    "建筑构件",
    "构件",
    "使用材料",
    "材料",
    "相关人物",
    "谁",
    "详细",
)


def call_deepseek(question: str, graph_context: str) -> Optional[str]:
    """把 Neo4j 查询结果交给 DeepSeek 组织语言；任何异常都返回 None 由调用方回退。"""
    global _deepseek_failures, _deepseek_cooldown_until
    if not DEEPSEEK_API_KEY:
        return None
    if time.monotonic() < _deepseek_cooldown_until:
        # 熔断冷却期内不再尝试上游，直接走规则模板
        return None
    body = json.dumps(
        {
            "model": DEEPSEEK_MODEL,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": QA_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"用户问题：\n{question}\n\nNeo4j查询结果：\n{graph_context}",
                },
            ],
        }
    ).encode("utf-8")
    api_request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(api_request, timeout=DEEPSEEK_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        answer = payload["choices"][0]["message"]["content"].strip()
        _deepseek_failures = 0
        return answer or None
    except Exception:
        # 超时、网络错误、鉴权失败、返回体异常：一律回退规则模板，保证问答不崩
        _deepseek_failures += 1
        if _deepseek_failures >= DEEPSEEK_FAILURE_LIMIT:
            _deepseek_cooldown_until = time.monotonic() + DEEPSEEK_COOLDOWN_SECONDS
            _deepseek_failures = 0
        return None


def deepseek_answer(question: str, graph_context: str, fallback: str) -> str:
    return call_deepseek(question, graph_context) or fallback


def format_context(rows, fields, limit: int = 60) -> str:
    """把查询结果整理为可读事实清单，作为 DeepSeek 的唯一事实依据。"""
    lines = []
    for row in rows[:limit]:
        parts = []
        for field in fields:
            value = row.get(field)
            if value in (None, "", []):
                continue
            if isinstance(value, (list, tuple)):
                value = "、".join(str(item) for item in value)
            parts.append(f"{field}={value}")
        lines.append("- " + "；".join(parts))
    return "\n".join(lines) if lines else "（查询结果为空）"


def evidence_of(rows, limit: int = 20) -> list:
    return [
        {"record_id": row.get("record_id"), "name": row.get("name")}
        for row in rows[:limit]
        if row.get("record_id") and row.get("name")
    ]


def detect_region(question: str, provinces: list) -> Optional[str]:
    for name in provinces:
        if name in question:
            return name
        alias = administrative_alias(name)
        if len(alias) >= 2 and alias in question:
            return name
    return None


def detect_era(question: str, eras: list) -> Optional[str]:
    for era in sorted(eras, key=len, reverse=True):
        if len(era) >= 2 and era in question:
            return era
    for era in eras:
        if len(era) == 1 and re.search(era + r"(代|朝|时期)", question):
            return era
    return None


def detect_types(question: str, types: list) -> list:
    for key in sorted(TYPE_GROUPS, key=len, reverse=True):
        if key in question:
            return TYPE_GROUPS[key]
    for name in sorted(types, key=len, reverse=True):
        if name in question:
            return [name]
    return []


def detect_protection(question: str, protections: list) -> Optional[str]:
    for name in protections:
        if name in question:
            return name
    return None


# 口语材料词 → 图谱中真实存在的建筑材料集合
MATERIAL_GROUPS = {
    "木材": ["木构", "木结构"],
    "木头": ["木构", "木结构"],
    "木": ["木构", "木结构"],
    "青砖": ["青砖"],
    "砖瓦": ["砖瓦"],
    "砖石": ["砖石"],
    "砖": ["青砖", "砖瓦", "砖石"],
    "石材": ["石材"],
    "石构": ["石构", "石结构"],
    "石": ["石材", "石构", "石结构", "砖石"],
    "琉璃": ["琉璃"],
    "灰瓦": ["灰瓦"],
    "瓦": ["灰瓦", "砖瓦"],
    "夯土": ["夯土"],
    "土": ["夯土"],
}

# 触发材料检索的问题用词（避免“石桥/木塔”这类类型词被误判为材料）
MATERIAL_CUES = ("材料", "材质", "用了", "使用", "砌", "结构", "建造")

# 触发构件检索的问题用词 / 需要显式“构件”提示的通用构件词
COMPONENT_CUES = ("构件", "部件", "斗拱", "藻井", "飞檐", "梁架", "檐柱", "照壁", "影壁", "牌楼")
GENERIC_COMPONENTS = {
    "大殿",
    "正殿",
    "配殿",
    "山门",
    "台基",
    "屋顶",
    "院落",
    "围墙",
    "城门",
    "城楼",
    "钟楼",
    "鼓楼",
    "戏台",
}

# 触发人物检索的问题用词
PERSON_CUES = ("谁", "人物", "参与", "建造者", "设计者", "主持", "出自")


def detect_material(question: str, materials: list) -> list:
    if not any(cue in question for cue in MATERIAL_CUES):
        return []
    for key in sorted(MATERIAL_GROUPS, key=len, reverse=True):
        if key in question:
            hit = [name for name in MATERIAL_GROUPS[key] if name in materials]
            if hit:
                return hit
    return []


def detect_component(question: str, components: list) -> Optional[str]:
    has_cue = any(cue in question for cue in COMPONENT_CUES)
    if not has_cue:
        return None
    for name in sorted(components, key=len, reverse=True):
        if name in question and (name not in GENERIC_COMPONENTS or "构件" in question):
            return name
    return None


def detect_person(question: str, persons: list) -> Optional[str]:
    for name in sorted(persons, key=len, reverse=True):
        if name in question:
            return name
    return None


def asks_for_person(question: str) -> bool:
    return any(cue in question for cue in PERSON_CUES)


SIMILAR_REL_LABELS = {
    "建筑类型": "建筑类型",
    "属于时期": "历史时期",
    "建造时代": "建造时代",
    "使用材料": "建筑材料",
    "具有构件": "建筑构件",
    "位于": "所属省份",
}


def similar_buildings(record_id: str, limit: int = 5) -> list:
    """没有 :旅游推荐 推理边时，用共享实体特征给出可追溯的相似建筑。

    评分权重：建筑类型 > 构件/材料 > 时期/时代/省份，全部来自 Neo4j 中的真实关系。
    """
    rows = query(
        """
        MATCH (b:古建筑 {record_id: $record_id})
        MATCH (b)-[r1]->(f)<-[r2]-(c:古建筑)
        WHERE c.record_id <> $record_id
          AND type(r1) = type(r2)
          AND type(r1) IN ['建筑类型', '属于时期', '建造时代',
                           '使用材料', '位于', '具有构件']
        WITH c, f, type(r1) AS rel_type,
             CASE type(r1)
               WHEN '建筑类型' THEN 3
               WHEN '具有构件' THEN 2
               WHEN '使用材料' THEN 2
               ELSE 1 END AS weight
        WITH c,
             collect(DISTINCT rel_type) AS dims,
             sum(weight) AS score,
             count(DISTINCT f) AS shared
        RETURN c.record_id AS record_id,
               c.name AS name,
               c.location AS location,
               c.image_url AS image_url,
               c.summary_text AS summary_text,
               head([(c)-[:位于]->(p:省级行政区) | p.name]) AS province,
               head([(c)-[:属于时期]->(h:历史时期) | h.name]) AS period,
               head([(c)-[:建筑类型]->(t:建筑类型) | t.name]) AS type,
               dims,
               shared,
               'attribute_similarity' AS rule_id,
               null AS confidence
        ORDER BY score DESC, shared DESC, name
        LIMIT $limit
        """,
        record_id=record_id,
        limit=limit,
    )
    for row in rows:
        dims = row.pop("dims", None) or []
        labels = "、".join(SIMILAR_REL_LABELS.get(dim, dim) for dim in dims)
        row["reason"] = f"与基准建筑共享{labels}（共{row['shared']}项实体特征）"
    return rows


def fuzzy_match_entity(question: str) -> Optional[dict]:
    """兜底：在全库节点名中做包含式匹配，取最长命中作为问题指向的实体。"""
    rows = query(
        """
        MATCH (n)
        WHERE coalesce(n.name, '') <> '' AND size(n.name) >= 2
          AND toLower($question) CONTAINS toLower(n.name)
        RETURN coalesce(n.record_id, elementId(n)) AS node_id,
               coalesce(n.name, elementId(n)) AS name,
               labels(n)[0] AS node_type,
               size(n.name) AS name_len
        ORDER BY name_len DESC
        LIMIT 1
        """,
        question=question,
    )
    return rows[0] if rows else None


_BUILDING_NAME_INDEX = None


def building_name_index() -> list:
    """全库古建筑名称索引（进程内缓存），供自然语言问句做名称匹配。"""
    global _BUILDING_NAME_INDEX
    if _BUILDING_NAME_INDEX is None:
        _BUILDING_NAME_INDEX = query(
            "MATCH (b:古建筑) RETURN b.record_id AS record_id, b.name AS name"
        )
    return _BUILDING_NAME_INDEX


def name_aliases(name: str) -> list:
    """拆分建筑名中的括号/连接符，得到“佛宫寺释迦塔（应县木塔）”这类别名。"""
    parts = re.split(r"[（）()\[\]【】<>《》\-—~～·、,，/／|]", name)
    return [part.strip() for part in parts if len(part.strip()) >= 2]


def find_building_by_name(text: str) -> Optional[dict]:
    """三级匹配：问题含建筑全名 → 问题含建筑名的别名片段 → 建筑名含问题片段。"""
    lowered = text.lower()
    best = None
    best_score = -1
    for row in building_name_index():
        name = row.get("name") or ""
        if not name:
            continue
        if name.lower() in lowered:
            score = 1000 + len(name)
        else:
            score = max(
                (len(alias) for alias in name_aliases(name) if alias.lower() in lowered),
                default=-1,
            )
        if score > best_score:
            best_score = score
            best = row
    if best is not None and best_score >= 2:
        return {"record_id": best["record_id"], "name": best["name"]}
    # 兜底：建筑名包含问题片段（兼容更短的简称）
    rows = query(
        """
        MATCH (b:古建筑)
        WHERE size($q) >= 2 AND toLower(b.name) CONTAINS toLower($q)
        RETURN b.record_id AS record_id, b.name AS name, size(b.name) AS name_len
        ORDER BY name_len
        LIMIT 1
        """,
        q=text,
    )
    return rows[0] if rows else None


def extract_recommend_target(question: str) -> Optional[str]:
    """从“与XX相似”这类表述中抽出基准建筑名。"""
    match = re.search(
        r"([\u4e00-\u9fa5A-Za-z0-9（）()·]{2,30}?)(?:相似|类似|相近|相仿)",
        question,
    )
    if not match:
        return None
    candidate = re.sub(
        r"^(?:推荐|查找|查一下|找|看看|有没有|请|帮我|列出|查询|显示|与|和|跟|、|的|给|一些|几个|古建筑)+",
        "",
        match.group(1),
    )
    return candidate.strip() or None


def building_facts(record_id: str) -> Optional[dict]:
    rows = query(
        """
        MATCH (b:古建筑 {record_id: $record_id})
        RETURN b.record_id AS record_id,
               b.name AS name,
               b.location AS location,
               b.image_url AS image_url,
               b.summary_text AS summary_text,
               [(b)-[:位于]->(p:省级行政区) | p.name] AS provinces,
               [(b)-[:建造时代]->(e:时代) | e.name] AS eras,
               [(b)-[:属于时期]->(h:历史时期) | h.name] AS periods,
               [(b)-[:保护级别]->(pl:保护级别) | pl.name] AS protections,
               [(b)-[:建筑类型]->(t:建筑类型) | t.name] AS types,
               [(b)-[:具体地点]->(s:具体地点) | s.name] AS locations,
               [(b)-[:具有构件]->(c:建筑构件) | c.name] AS components,
               [(b)-[:使用材料]->(m:建筑材料) | m.name] AS materials,
               [(b)-[:相关人物]->(n:人物) | n.name] AS persons
        """,
        record_id=record_id,
    )
    return rows[0] if rows else None


def describe_building(facts: dict) -> str:
    parts = []
    for label, key in (
        ("位于", "provinces"),
        ("具体地点", "locations"),
        ("建造时代", "eras"),
        ("所属时期", "periods"),
        ("建筑类型", "types"),
        ("保护级别", "protections"),
        ("主要构件", "components"),
        ("使用材料", "materials"),
        ("相关人物", "persons"),
    ):
        value = facts.get(key)
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            value = "、".join(value)
        parts.append(f"{label}{value}")
    return "；".join(parts)


BUILDING_CONTEXT_FIELDS = (
    "record_id",
    "name",
    "location",
    "provinces",
    "locations",
    "eras",
    "periods",
    "types",
    "protections",
    "components",
    "materials",
    "persons",
    "summary_text",
)

RESULT_CONTEXT_FIELDS = (
    "record_id",
    "name",
    "province",
    "location",
    "era",
    "period",
    "type",
    "protection_level",
    "components",
    "materials",
    "persons",
)


@app.post("/api/qa")
def question_answer(request: QuestionRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    provinces = [x["name"] for x in query("MATCH (p:省级行政区) RETURN p.name AS name")]
    periods = [x["name"] for x in query("MATCH (h:历史时期) RETURN h.name AS name")]
    eras = [
        x["name"]
        for x in query(
            "MATCH (e:时代)<-[:建造时代]-(:古建筑) RETURN DISTINCT e.name AS name"
        )
    ]
    types = [
        x["name"]
        for x in query(
            "MATCH (t:建筑类型)<-[:建筑类型]-(:古建筑) RETURN DISTINCT t.name AS name"
        )
    ]
    protections = [
        x["name"]
        for x in query(
            "MATCH (pl:保护级别)<-[:保护级别]-(:古建筑) RETURN DISTINCT pl.name AS name"
        )
    ]
    materials = [
        x["name"]
        for x in query(
            "MATCH (m:建筑材料)<-[:使用材料]-(:古建筑) RETURN DISTINCT m.name AS name"
        )
    ]
    components = [
        x["name"]
        for x in query(
            "MATCH (c:建筑构件)<-[:具有构件]-(:古建筑) RETURN DISTINCT c.name AS name"
        )
    ]
    persons = [
        x["name"]
        for x in query(
            "MATCH (n:人物)<-[:相关人物]-(:古建筑) RETURN DISTINCT n.name AS name"
        )
    ]

    province = detect_region(question, provinces)
    period = next((name for name in periods if name in question), None)
    era = detect_era(question, eras)
    type_group = detect_types(question, types)
    protection = detect_protection(question, protections)
    material_group = detect_material(question, materials)
    component = detect_component(question, components)
    person = detect_person(question, persons)
    uses_reference = any(word in question for word in REFERENCE_WORDS)

    # 1) 推荐解释：结合上一轮上下文，说明推理边给出的推荐理由
    if re.search(r"为什么|为何|原因|理由|依据|怎么推荐|凭什么", question):
        seed_id = request.last_seed
        if not seed_id:
            seed = find_building_by_name(extract_recommend_target(question) or question)
            seed_id = seed["record_id"] if seed else None
        if seed_id:
            rows = query(
                """
                MATCH (a:古建筑 {record_id: $seed})-[r:旅游推荐]->(b:古建筑)
                WHERE $target IS NULL OR b.record_id = $target
                RETURN b.record_id AS record_id,
                       b.name AS name,
                       r.reason AS reason,
                       r.confidence AS confidence,
                       r.rule_id AS rule_id
                ORDER BY confidence DESC, name
                LIMIT 3
                """,
                seed=seed_id,
                target=request.last_building,
            )
            seed_facts = building_facts(seed_id)
            if rows and seed_facts:
                context = (
                    f"基准建筑：{seed_facts['name']}（{seed_facts['record_id']}）\n"
                    + format_context(rows, ("name", "record_id", "reason", "confidence", "rule_id"))
                )
                fallback = (
                    f"推荐关系来自知识图谱中的旅游推荐推理边："
                    + "；".join(
                        f"{row['name']} —— {row.get('reason') or '综合特征相似'}"
                        f"（置信度{row.get('confidence')}）"
                        for row in rows
                    )
                )
                return {
                    "intent": "推荐解释",
                    "answer": deepseek_answer(question, context, fallback),
                    "source": "Neo4j知识图谱",
                    "evidence_count": len(rows),
                    "evidence": evidence_of(rows),
                    "data": rows,
                    "seed": seed_id,
                    "representative": rows[0]["record_id"],
                }

    # 2) 建筑详情：按建筑名或“它/这个”指代查询完整档案
    if any(word in question for word in DETAIL_KEYWORDS):
        building = find_building_by_name(question)
        if not building and uses_reference and request.last_building:
            building = {
                "record_id": request.last_building,
                "name": request.last_building,
            }
        if building:
            facts = building_facts(building["record_id"])
            if facts:
                # 具名建筑 + 人物提问：直接回答图谱中记录的相关人物
                if asks_for_person(question):
                    related = facts.get("persons") or []
                    if related:
                        return {
                            "intent": "建筑人物",
                            "answer": deepseek_answer(
                                question,
                                format_context(
                                    [{**facts, "persons": related}],
                                    BUILDING_CONTEXT_FIELDS,
                                ),
                                f"知识图谱中与{facts['name']}相关的人物有："
                                + "、".join(related)
                                + "。",
                            ),
                            "source": "Neo4j知识图谱",
                            "evidence_count": 1,
                            "evidence": evidence_of([facts]),
                            "data": [facts],
                            "seed": request.last_seed,
                            "representative": facts["record_id"],
                        }
                    return {
                        "intent": "建筑人物",
                        "answer": (
                            f"当前知识图谱中暂未收录与{facts['name']}相关的建造人物信息。"
                        ),
                        "source": "Neo4j知识图谱",
                        "evidence_count": 1,
                        "evidence": evidence_of([facts]),
                        "data": [facts],
                        "representative": facts["record_id"],
                    }
                describe = describe_building(facts) or "图谱中暂无该建筑的实体关联信息"
                extra = (
                    f"；简介：{facts['summary_text'][:160]}"
                    if facts.get("summary_text")
                    else ""
                )
                return {
                    "intent": "建筑详情",
                    "answer": deepseek_answer(
                        question,
                        format_context([facts], BUILDING_CONTEXT_FIELDS),
                        f"{facts['name']}（{facts['record_id']}）：{describe}{extra}。",
                    ),
                    "source": "Neo4j知识图谱",
                    "evidence_count": 1,
                    "evidence": evidence_of([facts]),
                    "data": [facts],
                    "seed": request.last_seed,
                    "representative": facts["record_id"],
                }
        if uses_reference and not request.last_building:
            return {
                "intent": "建筑详情",
                "answer": "请先说明要查询的古建筑名称，或先发起一次推荐/检索后再用“它”指代。",
                "source": "Neo4j知识图谱",
                "evidence_count": 0,
                "evidence": [],
                "data": [],
            }

    # 2.5) 构件 / 材料 / 人物检索：图谱中的实体维度的计数与列举
    if material_group or component or person:
        data = search_buildings(
            material_any=material_group,
            component=component,
            person=person,
            page=1,
            page_size=20,
        )
        items = data["items"]
        labels = []
        if material_group:
            labels.append("使用材料：" + "、".join(material_group))
        if component:
            labels.append("具有构件：" + component)
        if person:
            labels.append("相关人物：" + person)
        conditions = "；".join(labels)
        intent_label = (
            "人物检索" if person else ("构件检索" if component else "材料检索")
        )
        if not items:
            return {
                "intent": intent_label,
                "answer": f"当前知识图谱中暂未收录相关信息（已检索条件：{conditions}）。",
                "source": "Neo4j知识图谱",
                "evidence_count": 0,
                "evidence": [],
                "data": [],
            }
        context = (
            f"检索条件：{conditions}；命中总数：{data['total']}\n"
            + format_context(items, RESULT_CONTEXT_FIELDS)
        )
        return {
            "intent": intent_label,
            "answer": deepseek_answer(
                question,
                context,
                f"{conditions}的古建筑共{data['total']}座："
                + "、".join(item["name"] for item in items)
                + "。",
            ),
            "source": "Neo4j知识图谱",
            "evidence_count": data["total"],
            "evidence": evidence_of(items),
            "data": items,
        }

    # 3) 旅游推荐：优先 :旅游推荐 推理边，缺失时用共享实体特征做相似度兜底
    if re.search(r"推荐|相似|类似|周边|值得去", question):
        target = extract_recommend_target(question)
        seed = find_building_by_name(target or question)
        if seed:
            items = recommendations(seed["record_id"], 5)["items"]
            used_similarity = False
            if not items:
                # 1604 座古建筑中有 763 座没有 :旅游推荐 出边，改用实体特征相似度
                items = similar_buildings(seed["record_id"], 5)
                used_similarity = bool(items)
            if items:
                context = format_context(
                    items,
                    ("name", "record_id", "province", "period", "type", "reason", "shared"),
                )
                if used_similarity:
                    fallback = (
                        f"知识图谱中未收录{seed['name']}的旅游推荐推理边，"
                        f"改以共享实体特征推理出{len(items)}座相似古建筑："
                        + "、".join(item["name"] for item in items)
                        + "。"
                    )
                else:
                    fallback = (
                        f"为{seed['name']}推理出{len(items)}座相似古建筑："
                        + "、".join(item["name"] for item in items)
                        + "。"
                    )
                return {
                    "intent": "相似推荐" if used_similarity else "旅游推荐",
                    "answer": deepseek_answer(question, context, fallback),
                    "source": "Neo4j知识图谱",
                    "evidence_count": len(items),
                    "evidence": evidence_of(items),
                    "data": items,
                    "seed": seed["record_id"],
                    "representative": items[0]["record_id"],
                }
            return {
                "intent": "旅游推荐",
                "answer": f"知识图谱中暂未为{seed['name']}推理出推荐结果。",
                "source": "Neo4j知识图谱",
                "evidence_count": 0,
                "evidence": [],
                "data": [],
                "seed": seed["record_id"],
            }

    # 4) 条件检索：省份/时期/时代/类型/保护级别任一命中
    if province or period or era or type_group or protection:
        data = search_buildings(
            province=province,
            period=period,
            era=era,
            type_any=type_group,
            protection=protection,
            page=1,
            page_size=20,
        )
        items = data["items"]
        condition_parts = []
        for value in (province, period, era, protection):
            if value and value not in condition_parts:
                condition_parts.append(value)
        if type_group:
            type_label = "、".join(type_group)
            if type_label not in condition_parts:
                condition_parts.append(type_label)
        conditions = "、".join(condition_parts) or "当前条件"
        if not items:
            return {
                "intent": "条件检索",
                "answer": f"当前知识图谱中暂未收录相关信息（已检索条件：{conditions}）。",
                "source": "Neo4j知识图谱",
                "evidence_count": 0,
                "evidence": [],
                "data": [],
            }
        context = f"条件：{conditions}；命中总数：{data['total']}\n" + format_context(
            items, RESULT_CONTEXT_FIELDS
        )
        return {
            "intent": "条件检索",
            "answer": deepseek_answer(
                question,
                context,
                f"{conditions}共收录{data['total']}座古建筑："
                + "、".join(item["name"] for item in items)
                + "。",
            ),
            "source": "Neo4j知识图谱",
            "evidence_count": data["total"],
            "evidence": evidence_of(items),
            "data": items,
        }

    # 5) 提到行政区但图谱未收录
    mentioned_region = re.search(
        r"([\u4e00-\u9fa5]{2,10}(?:省|市|自治区|特别行政区))", question
    )
    if mentioned_region:
        region_name = mentioned_region.group(1)
        return {
            "intent": "地域检索",
            "answer": f"当前知识图谱中未收录{region_name}对应的古建筑记录。",
            "source": "Neo4j知识图谱",
            "evidence_count": 0,
            "evidence": [],
            "data": [],
        }

    # 6) 兜底：在全库实体名中做包含式匹配，命中后转为对应检索或建筑档案
    entity = fuzzy_match_entity(question)
    if entity:
        node_type = entity["node_type"]
        node_id = entity["node_id"]
        if node_type == "古建筑":
            facts = building_facts(node_id)
            if facts:
                describe = describe_building(facts) or "图谱中暂无该建筑的实体关联信息"
                return {
                    "intent": "建筑详情",
                    "answer": deepseek_answer(
                        question,
                        format_context([facts], BUILDING_CONTEXT_FIELDS),
                        f"{facts['name']}（{facts['record_id']}）：{describe}。",
                    ),
                    "source": "Neo4j知识图谱",
                    "evidence_count": 1,
                    "evidence": evidence_of([facts]),
                    "data": [facts],
                    "representative": facts["record_id"],
                }
        entity_params = {
            "省级行政区": {"province": entity["name"]},
            "建筑类型": {"type_any": [entity["name"]]},
            "历史时期": {"period": entity["name"]},
            "时代": {"era": entity["name"]},
            "建筑材料": {"material": entity["name"]},
            "建筑构件": {"component": entity["name"]},
            "人物": {"person": entity["name"]},
            "具体地点": {"location": entity["name"]},
        }.get(node_type)
        if entity_params:
            data = search_buildings(page=1, page_size=20, **entity_params)
            items = data["items"]
            if items:
                return {
                    "intent": "实体检索",
                    "answer": deepseek_answer(
                        question,
                        f"关联实体：{entity['name']}（{node_type}）；命中总数：{data['total']}\n"
                        + format_context(items, RESULT_CONTEXT_FIELDS),
                        f"与{entity['name']}相关的古建筑共{data['total']}座："
                        + "、".join(item["name"] for item in items)
                        + "。",
                    ),
                    "source": "Neo4j知识图谱",
                    "evidence_count": data["total"],
                    "evidence": evidence_of(items),
                    "data": items,
                }

    return {
        "intent": "未识别",
        "answer": EMPTY_ANSWER
        + " 你可以尝试询问：某省份有多少古建筑、某时代或某类型的古建筑有哪些、"
        "使用某材料或具有某构件的古建筑有哪些、推荐与某座建筑相似的古建筑，"
        "或某座建筑的时代、位置与保护级别。",
        "source": "Neo4j知识图谱",
        "evidence_count": 0,
        "evidence": [],
        "data": [],
    }

