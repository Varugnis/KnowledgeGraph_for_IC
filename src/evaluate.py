"""
评估模块
对知识图谱质量、推理效果和LLM增强效果进行量化评估
输出评估指标和案例分析
"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict

import networkx as nx

# 兼容Windows控制台编码
if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "cp936", "gb2312"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from build_kg import load_graph_from_json, build_knowledge_graph, get_graph_statistics
from reasoning import rule_based_reasoning, path_based_reasoning, DEFAULT_PATH_QUERIES
from graph_retrieval import retrieve_for_question


# ===========================================================================
# 1. 图谱质量评估
# ===========================================================================

def evaluate_kg_quality(G: nx.MultiDiGraph) -> dict:
    """评估知识图谱的结构质量"""
    stats = get_graph_statistics(G, {})

    # 连通性分析
    undirected = G.to_undirected()
    components = list(nx.connected_components(undirected))
    largest_cc = max(components, key=len)
    connectivity_ratio = len(largest_cc) / G.number_of_nodes()

    # 度分布
    in_degrees = [d for _, d in G.in_degree()]
    out_degrees = [d for _, d in G.out_degree()]
    avg_in = sum(in_degrees) / len(in_degrees) if in_degrees else 0
    avg_out = sum(out_degrees) / len(out_degrees) if out_degrees else 0
    max_in = max(in_degrees) if in_degrees else 0
    max_out = max(out_degrees) if out_degrees else 0

    # 孤立节点
    isolated = [n for n in G.nodes() if G.degree(n) == 0]

    # 高中心性节点（按度中心性）
    degree_centrality = nx.degree_centrality(undirected)
    top_central = sorted(degree_centrality.items(), key=lambda x: -x[1])[:5]
    top_central_names = [
        (G.nodes[n].get("name_cn", n), round(c, 4))
        for n, c in top_central
    ]

    metrics = {
        "total_entities": stats["total_entities"],
        "total_triples": stats["total_triples"],
        "entity_types": stats["num_entity_types"],
        "relation_types": stats["num_relation_types"],
        "connectivity_ratio": round(connectivity_ratio, 4),
        "num_connected_components": len(components),
        "largest_component_size": len(largest_cc),
        "avg_in_degree": round(avg_in, 3),
        "avg_out_degree": round(avg_out, 3),
        "max_in_degree": max_in,
        "max_out_degree": max_out,
        "isolated_nodes": len(isolated),
        "density": round(stats["density"], 8),
        "top_central_nodes": top_central_names,
        "entity_type_distribution": stats["entity_types"],
        "relation_type_distribution": stats["relation_types"],
    }

    return metrics


def print_kg_quality_report(metrics: dict):
    """打印图谱质量报告"""
    print("\n" + "=" * 65)
    print("               知识图谱质量评估报告")
    print("=" * 65)
    print(f"  实体总数:          {metrics['total_entities']:4d}  (要求: ≥100)")
    print(f"  三元组总数:        {metrics['total_triples']:4d}  (要求: ≥300)")
    print(f"  实体类型数:        {metrics['entity_types']:4d}  (要求: ≥3)")
    print(f"  关系类型数:        {metrics['relation_types']:4d}  (要求: ≥3)")
    print(f"  连通度:            {metrics['connectivity_ratio']:.4f}  (最大连通分量占比)")
    print(f"  连通分量数:        {metrics['num_connected_components']:4d}")
    print(f"  最大连通分量规模:  {metrics['largest_component_size']:4d}")
    print(f"  平均入度:          {metrics['avg_in_degree']:.3f}")
    print(f"  平均出度:          {metrics['avg_out_degree']:.3f}")
    print(f"  最大入度:          {metrics['max_in_degree']:4d}")
    print(f"  最大出度:          {metrics['max_out_degree']:4d}")
    print(f"  孤立节点数:        {metrics['isolated_nodes']:4d}")
    print(f"  图密度:            {metrics['density']:.8f}")

    print("\n  中心性最高节点 (度中心性):")
    for name, score in metrics["top_central_nodes"]:
        print(f"    {name:25s}: {score:.4f}")
    print("=" * 65)

    # 满足作业要求检查
    print("\n  ✅ 作业要求达标检查:")
    checks = [
        ("实体数 ≥ 100", metrics["total_entities"] >= 100),
        ("三元组数 ≥ 300", metrics["total_triples"] >= 300),
        ("实体类型 ≥ 3", metrics["entity_types"] >= 3),
        ("关系类型 ≥ 3", metrics["relation_types"] >= 3),
    ]
    for desc, passed in checks:
        status = "✅ 通过" if passed else "❌ 未达标"
        print(f"    {status}: {desc}")


# ===========================================================================
# 2. 推理效果评估
# ===========================================================================

REASONING_TEST_CASES = [
    # (source, target, expected_path_exists, description)
    ("C002", "T001", True, "AMD产品关联EUV光刻技术（多跳）"),
    ("C007", "C004", True, "苹果与台积电的合作关系"),
    ("CH011", "M001", True, "H100到硅材料的关联路径"),
    ("C001", "AP003", True, "Intel产品应用于AI训练"),
    ("CH024", "P009", True, "麒麟9000S采用SMIC工艺"),
    ("C003", "T001", True, "NVIDIA产品关联EUV技术"),
    ("C001", "C002", False, "Intel与AMD直接路径（不直接相连）"),
]

RULE_REASONING_EVAL = [
    # (rule_name, min_expected_triples, description)
    ("company_uses_process", 5, "公司产品采用特定工艺（间接关系）"),
    ("fab_masters_process", 3, "代工厂掌握工艺能力"),
    ("inherits_competition", 2, "继代产品的竞争关系继承"),
    ("process_requires_material", 3, "工艺节点对材料的依赖"),
]


def evaluate_path_reasoning(G: nx.MultiDiGraph) -> dict:
    """评估路径推理的准确性"""
    from reasoning import bfs_paths

    correct = 0
    total = len(REASONING_TEST_CASES)
    results = []

    for src, tgt, expected, desc in REASONING_TEST_CASES:
        paths = bfs_paths(G, src, tgt, max_hops=4)
        found = len(paths) > 0
        is_correct = found == expected
        if is_correct:
            correct += 1
        results.append({
            "source": src,
            "target": tgt,
            "description": desc,
            "expected_path_exists": expected,
            "found_path": found,
            "num_paths": len(paths),
            "correct": is_correct,
        })

    accuracy = correct / total if total > 0 else 0
    return {
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "total": total,
        "details": results,
    }


def evaluate_rule_reasoning(G: nx.MultiDiGraph) -> dict:
    """评估规则推理推导的新知识质量"""
    from reasoning import rule_based_reasoning

    inferred = rule_based_reasoning(G, verbose=False)
    results = []

    for rule_name, min_count, desc in RULE_REASONING_EVAL:
        count = len(inferred.get(rule_name, []))
        results.append({
            "rule": rule_name,
            "description": desc,
            "inferred_count": count,
            "meets_expectation": count >= min_count,
        })

    total_inferred = sum(len(v) for v in inferred.values())
    return {
        "total_inferred_triples": total_inferred,
        "rule_results": results,
        "rules_evaluated": len(RULE_REASONING_EVAL),
    }


# ===========================================================================
# 3. GraphRAG 效果评估
# ===========================================================================

def evaluate_retrieval(G: nx.MultiDiGraph, test_questions: list) -> dict:
    """评估图谱检索对每个问题的覆盖效果"""
    results = []
    total_precision = 0
    total_recall = 0

    for tq in test_questions:
        question = tq["question"]
        keywords = tq.get("keywords", [])
        expected_entities = set(tq.get("expected_entities", []))

        retrieval = retrieve_for_question(G, question, keywords=keywords)
        retrieved_entities = set(e["id"] for e in retrieval["matched_entities"])

        # 精确率和召回率（基于期望实体）
        if retrieved_entities:
            precision = len(retrieved_entities & expected_entities) / len(retrieved_entities)
        else:
            precision = 0.0

        if expected_entities:
            recall = len(retrieved_entities & expected_entities) / len(expected_entities)
        else:
            recall = 1.0

        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        total_precision += precision
        total_recall += recall

        results.append({
            "question": question[:50] + "..." if len(question) > 50 else question,
            "retrieved_entities": list(retrieved_entities),
            "expected_entities": list(expected_entities),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "subgraph_nodes": retrieval["subgraph_nodes"],
            "subgraph_edges": retrieval["subgraph_edges"],
        })

    n = len(test_questions)
    return {
        "macro_precision": round(total_precision / n, 4) if n > 0 else 0,
        "macro_recall": round(total_recall / n, 4) if n > 0 else 0,
        "num_questions": n,
        "details": results,
    }


def simulate_hallucination_check(G: nx.MultiDiGraph) -> dict:
    """
    幻觉检测模拟：
    给出几个"大模型可能编造的"事实，用知识图谱验证
    """
    # 模拟LLM输出的声明（一些正确，一些错误）
    claims = [
        {
            "claim": "NVIDIA H100采用TSMC 4nm工艺",
            "subject": "CH011",
            "predicate": "uses_process",
            "object": "P002",
            "ground_truth": True,
        },
        {
            "claim": "Apple M3 Ultra采用Samsung 3nm工艺",
            "subject": "CH015",
            "predicate": "uses_process",
            "object": "P008",
            "ground_truth": False,
        },
        {
            "claim": "AMD Ryzen 9 7950X基于Zen4架构",
            "subject": "CH006",
            "predicate": "based_on_arch",
            "object": "A004",
            "ground_truth": True,
        },
        {
            "claim": "Intel设计了Snapdragon 8 Gen 3",
            "subject": "C001",
            "predicate": "designs",
            "object": "CH019",
            "ground_truth": False,
        },
        {
            "claim": "TSMC代工生产了苹果A17 Pro",
            "subject": "C004",
            "predicate": "fabricates",
            "object": "CH017",
            "ground_truth": True,
        },
        {
            "claim": "麒麟9000S是麒麟9000的继代产品",
            "subject": "CH024",
            "predicate": "successor_of",
            "object": "CH025",
            "ground_truth": True,
        },
        {
            "claim": "ASML是EUV光刻机的唯一供应商",
            "subject": "C015",
            "predicate": "manufactures_tool",
            "object": "T001",
            "ground_truth": True,
        },
        {
            "claim": "AMD Ryzen 9 7950X由Intel代工制造",
            "subject": "C001",
            "predicate": "fabricates",
            "object": "CH006",
            "ground_truth": False,
        },
    ]

    results = []
    correct_detections = 0

    for claim_data in claims:
        s = claim_data["subject"]
        p = claim_data["predicate"]
        o = claim_data["object"]
        gt = claim_data["ground_truth"]

        # 在图谱中查找该三元组
        kg_verified = False
        for u, v, data in G.edges(data=True):
            if u == s and v == o and data.get("predicate") == p:
                kg_verified = True
                break

        is_correctly_detected = (kg_verified == gt)
        if is_correctly_detected:
            correct_detections += 1

        results.append({
            "claim": claim_data["claim"],
            "kg_verified": kg_verified,
            "ground_truth": gt,
            "correctly_detected": is_correctly_detected,
            "verdict": "✅ 事实正确" if kg_verified else "❌ 无法验证/可能错误",
        })

    accuracy = correct_detections / len(claims)
    return {
        "hallucination_detection_accuracy": round(accuracy, 4),
        "total_claims": len(claims),
        "correctly_detected": correct_detections,
        "details": results,
    }


def print_hallucination_report(hall_results: dict):
    """打印幻觉检测报告"""
    print("\n" + "=" * 65)
    print("               幻觉检测评估报告")
    print("=" * 65)
    print(f"  检测准确率: {hall_results['hallucination_detection_accuracy']:.2%}")
    print(f"  正确检测: {hall_results['correctly_detected']}/{hall_results['total_claims']}")
    print("\n  逐条分析:")
    for r in hall_results["details"]:
        status = "✅" if r["correctly_detected"] else "❌"
        print(f"  {status} [{r['verdict']}] {r['claim']}")
    print("=" * 65)


# ===========================================================================
# 综合评估主程序
# ===========================================================================

def run_full_evaluation():
    """运行完整评估流程并保存结果"""
    print("\n" + "=" * 70)
    print("              半导体知识图谱系统 - 综合评估")
    print("=" * 70)

    # 加载图谱
    kg_json = ROOT_DIR / "data" / "processed" / "kg_data.json"
    if kg_json.exists():
        print("[evaluate] 从缓存加载知识图谱...")
        G, entities = load_graph_from_json(str(kg_json))
    else:
        G, entities, _ = build_knowledge_graph()

    all_metrics = {}

    # 1. 图谱质量
    print("\n[1/4] 评估知识图谱质量...")
    kg_metrics = evaluate_kg_quality(G)
    print_kg_quality_report(kg_metrics)
    all_metrics["kg_quality"] = kg_metrics

    # 2. 路径推理
    print("\n[2/4] 评估路径推理...")
    path_eval = evaluate_path_reasoning(G)
    print(f"  路径推理准确率: {path_eval['accuracy']:.2%} ({path_eval['correct']}/{path_eval['total']})")
    for d in path_eval["details"]:
        status = "✅" if d["correct"] else "❌"
        print(f"  {status} {d['description']}: 找到{d['num_paths']}条路径")
    all_metrics["path_reasoning"] = path_eval

    # 3. 规则推理
    print("\n[3/4] 评估规则推理...")
    rule_eval = evaluate_rule_reasoning(G)
    print(f"  规则推理总新增三元组: {rule_eval['total_inferred_triples']}")
    for r in rule_eval["rule_results"]:
        status = "✅" if r["meets_expectation"] else "⚠️"
        print(f"  {status} {r['rule']}: 推导出 {r['inferred_count']} 条 | {r['description']}")
    all_metrics["rule_reasoning"] = rule_eval

    # 4. 幻觉检测
    print("\n[4/4] 幻觉检测评估...")
    from llm_qa import TEST_QUESTIONS
    hall_eval = simulate_hallucination_check(G)
    print_hallucination_report(hall_eval)
    all_metrics["hallucination_check"] = hall_eval

    # 5. 检索评估
    print("\n[bonus] 图谱检索评估...")
    retrieval_eval = evaluate_retrieval(G, TEST_QUESTIONS)
    print(f"  宏平均精确率: {retrieval_eval['macro_precision']:.4f}")
    print(f"  宏平均召回率: {retrieval_eval['macro_recall']:.4f}")
    all_metrics["retrieval_evaluation"] = retrieval_eval

    # 保存结果
    metrics_path = ROOT_DIR / "results" / "metrics.json"
    metrics_path.parent.mkdir(exist_ok=True)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 综合评估完成！结果已保存至: {metrics_path}")

    return all_metrics


if __name__ == "__main__":
    run_full_evaluation()
