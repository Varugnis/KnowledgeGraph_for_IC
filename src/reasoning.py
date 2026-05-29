"""
知识推理模块
实现两种推理方法：
  1. 规则推理（Rule-based Reasoning）：前向链式规则推理，知识补全
  2. 路径推理（Path-based Reasoning）：BFS多跳路径发现，证据链检索
"""

import json
import sys
from pathlib import Path
from collections import defaultdict, deque
from typing import Optional

import networkx as nx

if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "cp936", "gb2312"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from build_kg import build_knowledge_graph, load_graph_from_json


# ===========================================================================
# 1. 规则推理（Rule-based Reasoning）
# ===========================================================================

# 推理规则定义：(前提关系1, 前提关系2) -> (推导关系, 置信度衰减因子, 描述)
INFERENCE_RULES = [
    # 规则1：如果公司A设计了芯片B，芯片B采用了工艺C，则公司A的产品使用了工艺C
    ("designs", "uses_process", "company_uses_process", 0.95,
     "{A}的产品{B}采用了{C}工艺"),

    # 规则2：如果公司A代工制造了芯片B，芯片B采用了工艺C，则公司A掌握工艺C
    ("fabricates", "uses_process", "fab_masters_process", 0.90,
     "{A}通过代工{B}掌握{C}工艺"),

    # 规则3：如果芯片A是芯片B的继代，且B竞争对手是C，则A的竞争对手也是C
    ("successor_of", "competes_with", "inherits_competition", 0.85,
     "{A}作为{B}的继代产品，也与{C}形成竞争关系"),

    # 规则4：如果公司A设计了芯片B，且B与C竞争，则A与设计C的公司竞争
    ("designs", "competes_with", "company_competition_inferred", 0.80,
     "{A}设计的{B}与{C}竞争，可推断厂商间存在竞争"),

    # 规则5：如果工艺节点P采用器件D，器件D使用材料M，则工艺P依赖材料M
    ("uses_device", "uses_material", "process_requires_material", 0.90,
     "{A}工艺通过{B}器件依赖{C}材料"),

    # 规则6：如果芯片A用于应用域X，且X需要器件D，则A包含器件D
    ("used_for", "requires_device", "chip_contains_required_device", 0.75,
     "{A}用于{X}领域，该领域需要{D}，故{A}可能包含{D}"),

    # 规则7：如果公司A的芯片B是C的继代，工艺升级关系
    ("fabricates", "successor_of", "fab_advanced_process", 0.85,
     "{A}代工的{B}是{C}的升级版，体现代工厂工艺进步"),
]


def apply_rule(G: nx.MultiDiGraph, rule: tuple) -> list:
    """
    应用单条规则进行前向推理
    rule格式: (rel1, rel2, new_rel, confidence_factor, description_template)
    返回新推导出的三元组列表 [(subject, new_rel, object, confidence, description)]
    """
    rel1, rel2, new_rel, conf_factor, desc_template = rule
    new_triples = []
    seen = set()

    # 构建关系索引
    rel1_edges = defaultdict(list)  # subject -> [(object, confidence)]
    rel2_edges = defaultdict(list)

    for u, v, data in G.edges(data=True):
        pred = data.get("predicate", "")
        conf = data.get("confidence", 1.0)
        if pred == rel1:
            rel1_edges[u].append((v, conf))
        if pred == rel2:
            rel2_edges[u].append((v, conf))

    # 链式推理: A -rel1-> B -rel2-> C => A -new_rel-> C
    for A, b_list in rel1_edges.items():
        for B, conf1 in b_list:
            if B in rel2_edges:
                for C, conf2 in rel2_edges[B]:
                    if A == C:  # 避免自环
                        continue
                    key = (A, new_rel, C)
                    if key in seen:
                        continue
                    seen.add(key)
                    new_conf = round(conf1 * conf2 * conf_factor, 3)
                    desc = desc_template.replace("{A}", A).replace(
                        "{B}", B).replace("{C}", C).replace(
                        "{X}", B).replace("{D}", C)
                    new_triples.append((A, new_rel, C, new_conf, desc, B))

    return new_triples


def rule_based_reasoning(G: nx.MultiDiGraph, verbose: bool = True) -> dict:
    """
    执行规则推理，返回推导出的新知识
    
    Returns:
        dict: {rule_name: [(subject, predicate, object, confidence, desc, bridge)]}
    """
    print("\n[reasoning] 开始规则推理...")
    results = {}
    total_new = 0

    for rule in INFERENCE_RULES:
        rule_name = rule[2]
        new_triples = apply_rule(G, rule)
        results[rule_name] = new_triples
        total_new += len(new_triples)

        if verbose:
            print(f"  规则 '{rule_name}': 推导出 {len(new_triples)} 条新三元组")
            for t in new_triples[:3]:  # 展示前3条示例
                s_name = G.nodes[t[0]].get("name_cn", t[0]) if t[0] in G.nodes else t[0]
                o_name = G.nodes[t[2]].get("name_cn", t[2]) if t[2] in G.nodes else t[2]
                print(f"    -> ({s_name}, {t[1]}, {o_name}) [置信度: {t[3]}]")
            if len(new_triples) > 3:
                print(f"    ... 共 {len(new_triples)} 条")

    print(f"\n  规则推理共推导出 {total_new} 条新知识三元组")
    return results


def add_inferred_triples(G: nx.MultiDiGraph, inferred: dict, min_confidence: float = 0.7) -> nx.MultiDiGraph:
    """将推导出的高置信度三元组加入图谱，扩充知识"""
    added = 0
    for rule_name, triples in inferred.items():
        for t in triples:
            s, pred, o, conf, desc, bridge = t
            if conf >= min_confidence:
                if s in G.nodes and o in G.nodes:
                    G.add_edge(s, o,
                               predicate=pred,
                               confidence=conf,
                               description=f"[推理] {desc}",
                               inferred=True,
                               rule=rule_name)
                    added += 1
    print(f"  已向图谱中添加 {added} 条推理知识（置信度 >= {min_confidence}）")
    return G


# ===========================================================================
# 2. 路径推理（Path-based Reasoning）
# ===========================================================================

def bfs_paths(G: nx.MultiDiGraph, source: str, target: str,
              max_hops: int = 4, max_paths: int = 5) -> list:
    """
    BFS多跳路径发现：在有向图中走双向边（出边+入边），找到从source到target的路径
    路径语义：同时支持正向和反向关系的多跳推理
    
    Returns:
        list of paths, each path is [(node1, edge_pred, node2), ...]
        node2为实际终点方向，pred前缀"-"表示反向关系
    """
    if source not in G.nodes:
        return []
    if target not in G.nodes:
        return []

    paths = []
    queue = deque([(source, [])])
    visited_in_path = deque([{source}])

    while queue and len(paths) < max_paths:
        current, path = queue.popleft()
        visited = visited_in_path.popleft()

        if current == target and len(path) > 0:
            paths.append(path)
            continue

        if len(path) >= max_hops:
            continue

        # 出边（正向关系）
        for _, neighbor, data in G.out_edges(current, data=True):
            if neighbor not in visited:
                new_path = path + [(current, data.get("predicate", "?"), neighbor)]
                queue.append((neighbor, new_path))
                visited_in_path.append(visited | {neighbor})

        # 入边（反向关系，用 "inv_" 前缀标注）
        for neighbor, _, data in G.in_edges(current, data=True):
            if neighbor not in visited:
                pred = "inv_" + data.get("predicate", "?")
                new_path = path + [(current, pred, neighbor)]
                queue.append((neighbor, new_path))
                visited_in_path.append(visited | {neighbor})

    return paths


def format_path(G: nx.MultiDiGraph, path: list) -> str:
    """将路径格式化为可读字符串"""
    if not path:
        return "(空路径)"

    parts = []
    for i, (s, pred, o) in enumerate(path):
        s_name = G.nodes[s].get("name_cn", G.nodes[s].get("name", s)) if s in G.nodes else s
        o_name = G.nodes[o].get("name_cn", G.nodes[o].get("name", o)) if o in G.nodes else o
        if i == 0:
            parts.append(f"[{s_name}]")
        parts.append(f"--{pred}-->")
        parts.append(f"[{o_name}]")

    return " ".join(parts)


def path_based_reasoning(G: nx.MultiDiGraph, queries: list) -> list:
    """
    路径推理：针对一组问题，寻找实体间的推理路径
    
    Args:
        G: 知识图谱
        queries: [(source_id, target_id, question_desc), ...]
    
    Returns:
        list of result dicts
    """
    print("\n[reasoning] 开始路径推理...")
    results = []

    for source_id, target_id, question in queries:
        print(f"\n  问题: {question}")
        print(f"  查找路径: {source_id} -> {target_id}")

        paths = bfs_paths(G, source_id, target_id, max_hops=4, max_paths=5)

        result = {
            "question": question,
            "source": source_id,
            "target": target_id,
            "paths": [],
            "path_count": len(paths),
        }

        if paths:
            print(f"  找到 {len(paths)} 条路径:")
            for i, path in enumerate(paths):
                path_str = format_path(G, path)
                print(f"    路径{i+1}: {path_str}")
                result["paths"].append({
                    "hops": len(path),
                    "path_str": path_str,
                    "nodes": [s for s, _, _ in path] + [path[-1][2]],
                    "predicates": [p for _, p, _ in path],
                })
        else:
            print(f"  未找到路径（在4跳范围内）")

        results.append(result)

    return results


def find_common_neighbors(G: nx.MultiDiGraph, entity1: str, entity2: str) -> dict:
    """找到两个实体的共同邻居（共同关联的节点），用于关系预测"""
    neighbors1 = set(G.successors(entity1)) | set(G.predecessors(entity1))
    neighbors2 = set(G.successors(entity2)) | set(G.predecessors(entity2))
    common = neighbors1 & neighbors2

    result = {}
    for n in common:
        n_name = G.nodes[n].get("name_cn", G.nodes[n].get("name", n))
        n_type = G.nodes[n].get("entity_type", "?")
        result[n] = {"name": n_name, "type": n_type}

    return result


def link_prediction_heuristic(G: nx.MultiDiGraph, entity1: str, entity2: str) -> float:
    """
    基于路径的启发式链接预测：
    - 判断两个实体之间是否可能存在关系
    - 使用公共邻居数 + 路径距离作为特征
    """
    common = find_common_neighbors(G, entity1, entity2)
    n_common = len(common)

    # 尝试找最短路径
    try:
        undirected = G.to_undirected()
        dist = nx.shortest_path_length(undirected, entity1, entity2)
        dist_score = 1.0 / dist if dist > 0 else 1.0
    except nx.NetworkXNoPath:
        dist_score = 0.0
        dist = float("inf")

    # Jaccard系数近似
    neighbors1 = set(G.successors(entity1)) | set(G.predecessors(entity1))
    neighbors2 = set(G.successors(entity2)) | set(G.predecessors(entity2))
    union = neighbors1 | neighbors2
    jaccard = len(common) / len(union) if union else 0.0

    score = 0.4 * dist_score + 0.4 * jaccard + 0.2 * min(n_common / 10.0, 1.0)
    return round(score, 4), n_common, dist


def run_link_prediction_demo(G: nx.MultiDiGraph, pairs: list) -> list:
    """对一组实体对进行链接预测评分"""
    print("\n[reasoning] 链接预测演示（基于路径启发式）:")
    results = []

    for e1, e2, desc in pairs:
        if e1 not in G.nodes or e2 not in G.nodes:
            print(f"  实体不存在: {e1} 或 {e2}")
            continue

        score, n_common, dist = link_prediction_heuristic(G, e1, e2)
        common = find_common_neighbors(G, e1, e2)

        e1_name = G.nodes[e1].get("name_cn", e1)
        e2_name = G.nodes[e2].get("name_cn", e2)

        print(f"\n  [{desc}]")
        print(f"  实体1: {e1_name}  实体2: {e2_name}")
        print(f"  关联分数: {score:.4f}  共同邻居: {n_common}  最短距离: {dist}")
        if common:
            cn_names = [v["name"] for v in list(common.values())[:5]]
            print(f"  共同邻居示例: {', '.join(cn_names)}")

        results.append({
            "entity1": e1, "entity1_name": e1_name,
            "entity2": e2, "entity2_name": e2_name,
            "description": desc,
            "score": score,
            "common_neighbors": n_common,
            "shortest_path": dist,
        })

    return results


# ===========================================================================
# 主程序
# ===========================================================================

DEFAULT_PATH_QUERIES = [
    ("C002", "T001", "AMD的芯片产品与EUV光刻技术有何关联？"),
    ("C007", "C004", "苹果公司与台积电之间的关系链是什么？"),
    ("CH011", "M001", "H100 AI加速卡与硅材料的关联路径"),
    ("C001", "AP003", "Intel的产品与AI训练应用的关联"),
    ("CH017", "AP003", "苹果A17 Pro与AI训练的关联路径"),
    ("C002", "C004", "AMD与台积电的合作关系链"),
]

DEFAULT_LINK_PAIRS = [
    ("C001", "C002", "Intel与AMD的关系预测"),
    ("CH011", "CH013", "H100与A100的关系预测"),
    ("C007", "C004", "Apple与TSMC的关系预测"),
    ("CH019", "CH022", "Snapdragon 8 Gen 3与Dimensity 9300"),
    ("C001", "T001", "Intel与EUV光刻的关系"),
    ("CH024", "P009", "Kirin 9000S与SMIC N+1工艺"),
]


def run_all_reasoning():
    """执行所有推理任务并保存结果"""
    from pathlib import Path
    import json

    # 构建图谱
    kg_json = ROOT_DIR / "data" / "processed" / "kg_data.json"
    if kg_json.exists():
        print("[reasoning] 从缓存加载知识图谱...")
        G, entities = load_graph_from_json(str(kg_json))
    else:
        G, entities, _ = build_knowledge_graph()

    all_results = {}

    # 1. 规则推理
    inferred = rule_based_reasoning(G, verbose=True)
    G_augmented = add_inferred_triples(G.copy(), inferred, min_confidence=0.7)
    all_results["rule_reasoning"] = {
        k: [(t[0], t[1], t[2], t[3], t[4]) for t in v]
        for k, v in inferred.items()
    }

    # 2. 路径推理
    path_results = path_based_reasoning(G, DEFAULT_PATH_QUERIES)
    all_results["path_reasoning"] = path_results

    # 3. 链接预测
    link_results = run_link_prediction_demo(G, DEFAULT_LINK_PAIRS)
    all_results["link_prediction"] = link_results

    # 保存推理结果
    output_path = ROOT_DIR / "results" / "reasoning_results.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n推理结果已保存至: {output_path}")

    return G_augmented, all_results


if __name__ == "__main__":
    G_aug, results = run_all_reasoning()
    print("\n[reasoning] 推理模块执行完成！")
