"""
知识图谱构建模块
构建半导体领域知识图谱，包含实体加载、三元组导入、图谱存储和统计分析
"""

import csv
import json
import os
import sys
import networkx as nx
from pathlib import Path
from collections import defaultdict

if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "cp936", "gb2312"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
DATA_RAW = ROOT_DIR / "data" / "raw"
DATA_PROCESSED = ROOT_DIR / "data" / "processed"
RESULTS_DIR = ROOT_DIR / "results"


def load_entities(filepath: str) -> dict:
    """从CSV文件加载实体数据，返回以实体ID为键的字典"""
    entities = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entities[row["id"]] = {
                "id": row["id"],
                "name": row["name"],
                "name_cn": row["name_cn"],
                "type": row["type"],
                "description": row["description"],
                "founded_year": row.get("founded_year", ""),
                "country": row.get("country", ""),
            }
    return entities


def load_triples(filepath: str) -> list:
    """从CSV文件加载三元组数据"""
    triples = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            triples.append({
                "subject": row["subject_id"],
                "predicate": row["predicate"],
                "object": row["object_id"],
                "confidence": float(row.get("confidence", 1.0)),
                "description": row.get("description", ""),
            })
    return triples


def build_graph(entities: dict, triples: list) -> nx.MultiDiGraph:
    """
    基于实体和三元组构建NetworkX有向多重图
    节点属性：id, name, name_cn, type, description
    边属性：predicate, confidence, description
    """
    G = nx.MultiDiGraph()

    # 添加节点
    for eid, edata in entities.items():
        G.add_node(
            eid,
            name=edata["name"],
            name_cn=edata["name_cn"],
            entity_type=edata["type"],
            description=edata["description"],
            founded_year=edata.get("founded_year", ""),
            country=edata.get("country", ""),
        )

    # 添加边
    skipped = 0
    for triple in triples:
        s, p, o = triple["subject"], triple["predicate"], triple["object"]
        if s not in G.nodes:
            print(f"  [警告] 主体实体不存在: {s}")
            skipped += 1
            continue
        if o not in G.nodes:
            print(f"  [警告] 客体实体不存在: {o}")
            skipped += 1
            continue
        G.add_edge(
            s, o,
            predicate=p,
            confidence=triple["confidence"],
            description=triple["description"],
        )

    print(f"  跳过无效三元组: {skipped} 条")
    return G


def get_graph_statistics(G: nx.MultiDiGraph, entities: dict) -> dict:
    """计算并返回图谱统计信息"""
    type_count = defaultdict(int)
    for _, data in G.nodes(data=True):
        type_count[data.get("entity_type", "Unknown")] += 1

    pred_count = defaultdict(int)
    for _, _, data in G.edges(data=True):
        pred_count[data.get("predicate", "unknown")] += 1

    stats = {
        "total_entities": G.number_of_nodes(),
        "total_triples": G.number_of_edges(),
        "entity_types": dict(type_count),
        "relation_types": dict(pred_count),
        "num_entity_types": len(type_count),
        "num_relation_types": len(pred_count),
        "avg_out_degree": sum(d for _, d in G.out_degree()) / G.number_of_nodes(),
        "density": nx.density(G),
    }
    return stats


def save_graph(G: nx.MultiDiGraph, output_path: str):
    """将图谱保存为JSON格式（节点+边列表）"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    graph_data = {
        "nodes": [
            {"id": n, **data}
            for n, data in G.nodes(data=True)
        ],
        "edges": [
            {
                "source": u,
                "target": v,
                "predicate": data.get("predicate", ""),
                "confidence": data.get("confidence", 1.0),
                "description": data.get("description", ""),
            }
            for u, v, data in G.edges(data=True)
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    print(f"  图谱已保存至: {output_path}")


def export_triples_csv(G: nx.MultiDiGraph, output_path: str):
    """将图谱三元组导出为标准CSV格式（供其他模块使用）"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["subject_id", "subject_name", "predicate", "object_id", "object_name", "confidence"])
        for u, v, data in G.edges(data=True):
            u_name = G.nodes[u].get("name_cn", G.nodes[u].get("name", u))
            v_name = G.nodes[v].get("name_cn", G.nodes[v].get("name", v))
            writer.writerow([u, u_name, data.get("predicate", ""), v, v_name, data.get("confidence", 1.0)])
    print(f"  三元组CSV已导出至: {output_path}")


def print_statistics(stats: dict):
    """打印图谱统计信息"""
    print("\n" + "=" * 60)
    print("           半导体知识图谱统计信息")
    print("=" * 60)
    print(f"  实体总数: {stats['total_entities']}")
    print(f"  三元组总数: {stats['total_triples']}")
    print(f"  实体类型数: {stats['num_entity_types']}")
    print(f"  关系类型数: {stats['num_relation_types']}")
    print(f"  平均出度: {stats['avg_out_degree']:.2f}")
    print(f"  图密度: {stats['density']:.6f}")

    print("\n  实体类型分布:")
    for etype, count in sorted(stats["entity_types"].items(), key=lambda x: -x[1]):
        print(f"    {etype:25s}: {count:3d} 个")

    print("\n  关系类型分布:")
    for pred, count in sorted(stats["relation_types"].items(), key=lambda x: -x[1]):
        print(f"    {pred:30s}: {count:3d} 条")
    print("=" * 60)


def build_knowledge_graph() -> tuple:
    """主函数：构建并返回知识图谱，同时保存到文件"""
    print("\n[build_kg] 开始构建半导体知识图谱...")

    # 加载数据
    entities_path = DATA_RAW / "entities.csv"
    triples_path = DATA_RAW / "triples.csv"

    print(f"  加载实体: {entities_path}")
    entities = load_entities(str(entities_path))
    print(f"  加载了 {len(entities)} 个实体")

    print(f"  加载三元组: {triples_path}")
    triples = load_triples(str(triples_path))
    print(f"  加载了 {len(triples)} 条三元组")

    # 构建图
    print("  构建NetworkX有向图...")
    G = build_graph(entities, triples)

    # 统计信息
    stats = get_graph_statistics(G, entities)
    print_statistics(stats)

    # 保存图谱
    kg_json_path = str(DATA_PROCESSED / "kg_data.json")
    save_graph(G, kg_json_path)

    triples_csv_path = str(ROOT_DIR / "data" / "triples.csv")
    export_triples_csv(G, triples_csv_path)

    # 保存统计信息
    stats_path = str(DATA_PROCESSED / "kg_stats.json")
    os.makedirs(os.path.dirname(stats_path), exist_ok=True)
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  统计信息已保存至: {stats_path}")

    print("\n[build_kg] 知识图谱构建完成！")
    return G, entities, stats


def load_graph_from_json(json_path: str) -> tuple:
    """从JSON文件加载已保存的知识图谱"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    G = nx.MultiDiGraph()
    entities = {}

    for node in data["nodes"]:
        nid = node["id"]
        attrs = {k: v for k, v in node.items() if k != "id"}
        G.add_node(nid, **attrs)
        entities[nid] = {"id": nid, **attrs}

    for edge in data["edges"]:
        G.add_edge(
            edge["source"], edge["target"],
            predicate=edge["predicate"],
            confidence=edge["confidence"],
            description=edge["description"],
        )

    return G, entities


if __name__ == "__main__":
    G, entities, stats = build_knowledge_graph()
    print(f"\n图谱构建成功，可在 data/processed/kg_data.json 中查看图谱数据。")
