"""
图谱检索模块
为GraphRAG大模型增强提供子图检索、实体搜索和上下文构建功能
"""

import re
import sys
import json
from pathlib import Path
from collections import defaultdict
from typing import Optional

import networkx as nx

if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "cp936", "gb2312"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from build_kg import load_graph_from_json


# 关系类型中文映射
PREDICATE_NAMES = {
    "designs": "设计研发",
    "fabricates": "代工制造",
    "uses_process": "采用工艺",
    "based_on_arch": "基于架构",
    "used_for": "应用于",
    "uses_device": "包含/使用器件",
    "uses_material": "使用材料",
    "competes_with": "竞争对手",
    "successor_of": "后继产品",
    "developed_by": "开发者",
    "enables_process": "支撑工艺",
    "manufactures_tool": "生产设备",
    "masters_technology": "掌握技术",
    "uses_technology": "使用技术",
    "company_uses_process": "[推理]产品采用工艺",
    "fab_masters_process": "[推理]代工厂掌握工艺",
    "inherits_competition": "[推理]继代竞争关系",
    "process_requires_material": "[推理]工艺依赖材料",
    "supports_memory": "支持内存类型",
    "requires_device": "需要器件",
    "company_competition_inferred": "[推理]厂商竞争",
    "fab_advanced_process": "[推理]工艺进步",
}


def search_entity(G: nx.MultiDiGraph, query: str, top_k: int = 5) -> list:
    """
    在图谱中搜索与查询字符串匹配的实体
    支持英文名、中文名、实体ID的模糊匹配
    
    Returns:
        list of (entity_id, entity_data, match_score)
    """
    query_lower = query.lower().strip()
    results = []

    for nid, data in G.nodes(data=True):
        score = 0.0
        name = data.get("name", "").lower()
        name_cn = data.get("name_cn", "").lower()
        desc = data.get("description", "").lower()

        # 精确匹配得分最高
        if query_lower == name or query_lower == name_cn:
            score = 1.0
        elif query_lower in name or query_lower in name_cn:
            score = 0.8
        elif query_lower in desc:
            score = 0.5
        elif query_lower in nid.lower():
            score = 0.6

        if score > 0:
            results.append((nid, data, score))

    # 按分数降序排序
    results.sort(key=lambda x: -x[2])
    return results[:top_k]


def get_entity_neighbors(G: nx.MultiDiGraph, entity_id: str,
                         direction: str = "both", max_items: int = 20) -> dict:
    """
    获取实体的直接邻居及关系

    Args:
        direction: "out" (出边), "in" (入边), "both" (双向)
    
    Returns:
        {"out": [(pred, neighbor_id, neighbor_data)], "in": [...]}
    """
    result = {"out": [], "in": []}

    if entity_id not in G.nodes:
        return result

    if direction in ("out", "both"):
        for _, v, data in G.out_edges(entity_id, data=True):
            pred = data.get("predicate", "?")
            pred_cn = PREDICATE_NAMES.get(pred, pred)
            result["out"].append({
                "predicate": pred,
                "predicate_cn": pred_cn,
                "neighbor_id": v,
                "neighbor_name": G.nodes[v].get("name_cn", G.nodes[v].get("name", v)),
                "neighbor_type": G.nodes[v].get("entity_type", "?"),
                "confidence": data.get("confidence", 1.0),
            })

    if direction in ("in", "both"):
        for u, _, data in G.in_edges(entity_id, data=True):
            pred = data.get("predicate", "?")
            pred_cn = PREDICATE_NAMES.get(pred, pred)
            result["in"].append({
                "predicate": pred,
                "predicate_cn": pred_cn,
                "neighbor_id": u,
                "neighbor_name": G.nodes[u].get("name_cn", G.nodes[u].get("name", u)),
                "neighbor_type": G.nodes[u].get("entity_type", "?"),
                "confidence": data.get("confidence", 1.0),
            })

    # 截断
    result["out"] = result["out"][:max_items]
    result["in"] = result["in"][:max_items]
    return result


def retrieve_subgraph(G: nx.MultiDiGraph, entity_ids: list,
                      hops: int = 2, max_nodes: int = 50) -> nx.MultiDiGraph:
    """
    以给定实体为种子，通过BFS扩展提取子图（用于RAG上下文）
    
    Args:
        entity_ids: 种子实体ID列表
        hops: 扩展跳数
        max_nodes: 最大节点数限制
    
    Returns:
        子图（NetworkX MultiDiGraph）
    """
    visited = set(entity_ids)
    frontier = set(entity_ids)

    for _ in range(hops):
        new_frontier = set()
        for nid in frontier:
            if nid not in G.nodes:
                continue
            for neighbor in list(G.successors(nid)) + list(G.predecessors(nid)):
                if neighbor not in visited:
                    new_frontier.add(neighbor)
                    visited.add(neighbor)
            if len(visited) >= max_nodes:
                break
        frontier = new_frontier
        if len(visited) >= max_nodes:
            break

    return G.subgraph(visited).copy()


def subgraph_to_text(G: nx.MultiDiGraph, subgraph: nx.MultiDiGraph,
                     max_triples: int = 40) -> str:
    """
    将子图转化为自然语言文本描述，用于LLM的上下文输入
    格式：(主体名称, 关系, 客体名称)
    """
    lines = []
    count = 0

    for u, v, data in subgraph.edges(data=True):
        if count >= max_triples:
            break
        pred = data.get("predicate", "?")
        pred_cn = PREDICATE_NAMES.get(pred, pred)
        conf = data.get("confidence", 1.0)
        inferred = data.get("inferred", False)

        u_name = subgraph.nodes[u].get("name_cn", subgraph.nodes[u].get("name", u))
        v_name = subgraph.nodes[v].get("name_cn", subgraph.nodes[v].get("name", v))

        prefix = "[推理] " if inferred else ""
        conf_str = f" (置信度:{conf:.2f})" if conf < 1.0 else ""
        lines.append(f"{prefix}({u_name}) --[{pred_cn}]--> ({v_name}){conf_str}")
        count += 1

    return "\n".join(lines)


def retrieve_for_question(G: nx.MultiDiGraph, question: str,
                          keywords: Optional[list] = None,
                          top_k_entities: int = 5,
                          hops: int = 2) -> dict:
    """
    面向问题的图谱检索流程：
    1. 从问题中提取关键词
    2. 在图谱中搜索相关实体
    3. 提取以这些实体为中心的子图
    4. 将子图转化为文本上下文

    Args:
        question: 用户问题
        keywords: 额外的关键词列表（可选）
    
    Returns:
        {
            "matched_entities": [...],
            "subgraph_nodes": int,
            "subgraph_edges": int,
            "context_text": str,
            "entity_descriptions": [...]
        }
    """
    # 合并关键词
    search_terms = [question]
    if keywords:
        search_terms.extend(keywords)

    # 搜索实体
    matched = {}
    for term in search_terms:
        found = search_entity(G, term, top_k=top_k_entities)
        for eid, edata, score in found:
            if eid not in matched or matched[eid]["score"] < score:
                matched[eid] = {"data": edata, "score": score, "matched_by": term}

    matched_list = sorted(matched.items(), key=lambda x: -x[1]["score"])[:top_k_entities]

    if not matched_list:
        return {
            "matched_entities": [],
            "subgraph_nodes": 0,
            "subgraph_edges": 0,
            "context_text": "未在知识图谱中找到相关实体。",
            "entity_descriptions": [],
        }

    # 提取子图
    seed_ids = [eid for eid, _ in matched_list]
    subgraph = retrieve_subgraph(G, seed_ids, hops=hops, max_nodes=60)
    context_text = subgraph_to_text(G, subgraph)

    # 实体描述
    entity_descs = []
    for eid, info in matched_list:
        edata = info["data"]
        entity_descs.append(
            f"[{edata.get('entity_type', '?')}] {edata.get('name_cn', '')} ({edata.get('name', eid)}): "
            f"{edata.get('description', '')}"
        )

    return {
        "matched_entities": [
            {"id": eid, "name": info["data"].get("name_cn", eid), "score": info["score"]}
            for eid, info in matched_list
        ],
        "subgraph_nodes": subgraph.number_of_nodes(),
        "subgraph_edges": subgraph.number_of_edges(),
        "context_text": context_text,
        "entity_descriptions": entity_descs,
    }


def format_kg_context(retrieval_result: dict) -> str:
    """将检索结果格式化为结构化的LLM上下文字符串"""
    lines = ["【知识图谱检索结果】"]

    if retrieval_result["matched_entities"]:
        lines.append("\n匹配到的关键实体:")
        for e in retrieval_result["matched_entities"]:
            lines.append(f"  - {e['name']} (匹配度: {e['score']:.2f})")

    if retrieval_result["entity_descriptions"]:
        lines.append("\n实体详细描述:")
        for desc in retrieval_result["entity_descriptions"]:
            lines.append(f"  {desc}")

    if retrieval_result["context_text"]:
        lines.append(f"\n相关知识三元组 (子图: {retrieval_result['subgraph_nodes']}节点, "
                     f"{retrieval_result['subgraph_edges']}条关系):")
        lines.append(retrieval_result["context_text"])

    return "\n".join(lines)


def demo_retrieval(G: nx.MultiDiGraph):
    """演示图谱检索功能"""
    test_questions = [
        ("NVIDIA H100用于什么应用？", ["H100", "NVIDIA"]),
        ("台积电掌握哪些制程工艺？", ["TSMC", "台积电"]),
        ("苹果A17 Pro和骁龙8 Gen 3谁更先进？", ["A17 Pro", "骁龙8 Gen 3"]),
        ("EUV光刻技术由谁提供？", ["EUV", "ASML"]),
    ]

    for question, keywords in test_questions:
        print(f"\n{'='*60}")
        print(f"问题: {question}")
        result = retrieve_for_question(G, question, keywords)
        context = format_kg_context(result)
        print(context[:800])


if __name__ == "__main__":
    kg_json = ROOT_DIR / "data" / "processed" / "kg_data.json"
    if kg_json.exists():
        G, entities = load_graph_from_json(str(kg_json))
    else:
        from build_kg import build_knowledge_graph
        G, entities, _ = build_knowledge_graph()

    demo_retrieval(G)
