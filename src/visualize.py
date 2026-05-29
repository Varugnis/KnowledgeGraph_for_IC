"""
知识图谱可视化模块
生成交互式HTML可视化（pyvis）和静态图片（matplotlib）
"""

import sys
import json
import os
from pathlib import Path
from collections import defaultdict

import networkx as nx

if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "cp936", "gb2312"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from build_kg import load_graph_from_json

# 实体类型颜色方案
ENTITY_COLORS = {
    "Company":     "#4A90D9",   # 蓝色
    "Chip":        "#E67E22",   # 橙色
    "ProcessNode": "#27AE60",   # 绿色
    "Architecture":"#8E44AD",   # 紫色
    "Material":    "#E74C3C",   # 红色
    "Device":      "#1ABC9C",   # 青色
    "Application": "#F39C12",   # 黄色
    "Technology":  "#95A5A6",   # 灰色
}

ENTITY_SIZES = {
    "Company":     30,
    "Chip":        20,
    "ProcessNode": 25,
    "Architecture":18,
    "Material":    15,
    "Device":      18,
    "Application": 22,
    "Technology":  18,
}

# 关系类型颜色（用于边）
PREDICATE_COLORS = {
    "designs":       "#2980B9",
    "fabricates":    "#16A085",
    "uses_process":  "#8E44AD",
    "based_on_arch": "#D35400",
    "used_for":      "#27AE60",
    "competes_with": "#E74C3C",
    "successor_of":  "#F39C12",
    "developed_by":  "#1ABC9C",
}


def build_pyvis_html(G: nx.MultiDiGraph, output_path: str,
                      title: str = "半导体知识图谱",
                      max_nodes: int = 80):
    """
    使用 pyvis 生成交互式知识图谱HTML可视化
    支持鼠标拖拽、缩放、点击查看节点信息
    """
    try:
        from pyvis.network import Network
    except ImportError:
        print("  [错误] 请安装 pyvis: pip install pyvis")
        return False

    print(f"  生成pyvis交互式可视化（最多{max_nodes}个节点）...")

    # 如果图过大，只取关键子图
    if G.number_of_nodes() > max_nodes:
        degree_sorted = sorted(G.degree(), key=lambda x: -x[1])
        top_nodes = [n for n, _ in degree_sorted[:max_nodes]]
        subG = G.subgraph(top_nodes).copy()
    else:
        subG = G

    # 创建pyvis网络
    net = Network(
        height="800px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="#ffffff",
        heading=title,
    )
    net.set_options("""
    {
      "nodes": {
        "borderWidth": 2,
        "borderWidthSelected": 4,
        "font": {"size": 12, "face": "Microsoft YaHei, SimHei, Arial"},
        "shadow": true
      },
      "edges": {
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.8}},
        "color": {"inherit": false},
        "smooth": {"type": "continuous"},
        "font": {"size": 10, "face": "Microsoft YaHei, Arial"},
        "shadow": true
      },
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -8000,
          "centralGravity": 0.3,
          "springLength": 120,
          "damping": 0.09
        },
        "stabilization": {"iterations": 200}
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 200,
        "hideEdgesOnDrag": true
      }
    }
    """)

    # 添加节点
    for nid, data in subG.nodes(data=True):
        etype = data.get("entity_type", "Unknown")
        color = ENTITY_COLORS.get(etype, "#95A5A6")
        size = ENTITY_SIZES.get(etype, 20)
        name_cn = data.get("name_cn", data.get("name", nid))
        desc = data.get("description", "")[:100]
        title_text = f"<b>{name_cn}</b><br>类型: {etype}<br>ID: {nid}<br>{desc}"

        net.add_node(
            nid,
            label=name_cn,
            title=title_text,
            color=color,
            size=size,
            group=etype,
        )

    # 添加边
    for u, v, data in subG.edges(data=True):
        pred = data.get("predicate", "?")
        conf = data.get("confidence", 1.0)
        inferred = data.get("inferred", False)

        from graph_retrieval import PREDICATE_NAMES
        pred_cn = PREDICATE_NAMES.get(pred, pred)

        color = PREDICATE_COLORS.get(pred, "#7f8c8d")
        width = max(1, int(conf * 3))
        dashes = inferred

        title_text = f"{pred_cn}<br>置信度: {conf:.2f}"

        net.add_edge(
            u, v,
            title=title_text,
            label=pred_cn,
            color={"color": color, "opacity": min(1.0, conf + 0.2)},
            width=width,
            dashes=dashes,
        )

    # 保存
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    net.save_graph(output_path)
    print(f"  ✅ 交互式可视化已保存: {output_path}")
    return True


def build_subgraph_html(G: nx.MultiDiGraph, center_entity: str,
                         output_path: str, hops: int = 2):
    """生成以特定实体为中心的子图可视化"""
    from graph_retrieval import retrieve_subgraph
    subgraph = retrieve_subgraph(G, [center_entity], hops=hops, max_nodes=40)
    entity_name = G.nodes[center_entity].get("name_cn", center_entity) if center_entity in G.nodes else center_entity
    return build_pyvis_html(subgraph, output_path,
                             title=f"以 {entity_name} 为中心的知识子图",
                             max_nodes=40)


def _setup_chinese_font():
    """配置matplotlib中文字体"""
    import matplotlib
    import matplotlib.font_manager as fm
    # Windows中文字体候选列表
    candidates = ["Microsoft YaHei", "SimHei", "FangSong", "KaiTi",
                  "STSong", "Noto Sans CJK SC", "WenQuanYi Micro Hei"]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            matplotlib.rcParams["font.family"] = font
            return font
    # 如果找不到中文字体，使用ASCII标签
    return None


def build_matplotlib_static(G: nx.MultiDiGraph, output_path: str,
                              max_nodes: int = 50):
    """
    使用 matplotlib + networkx 生成静态图谱图片
    用于报告和不支持HTML的环境
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("  [错误] 请安装 matplotlib: pip install matplotlib")
        return False

    cn_font = _setup_chinese_font()

    print(f"  生成静态图谱图片（最多{max_nodes}个节点）...")

    # 取度数最高的子图
    if G.number_of_nodes() > max_nodes:
        degree_sorted = sorted(G.degree(), key=lambda x: -x[1])
        top_nodes = [n for n, _ in degree_sorted[:max_nodes]]
        subG = G.subgraph(top_nodes).copy()
    else:
        subG = G.copy()

    # 转为无向图用于布局
    undirected = subG.to_undirected()

    # 布局
    try:
        pos = nx.spring_layout(undirected, k=2.0, iterations=50, seed=42)
    except Exception:
        pos = nx.random_layout(undirected, seed=42)

    fig, ax = plt.subplots(figsize=(18, 14))
    ax.set_facecolor("#1a1a2e")
    fig.patch.set_facecolor("#1a1a2e")

    # 按类型分组绘制节点
    for etype, color in ENTITY_COLORS.items():
        nodes_of_type = [n for n, d in subG.nodes(data=True)
                         if d.get("entity_type") == etype]
        if nodes_of_type:
            size = ENTITY_SIZES.get(etype, 20) * 15
            nx.draw_networkx_nodes(undirected, pos,
                                   nodelist=nodes_of_type,
                                   node_color=color,
                                   node_size=size,
                                   alpha=0.9,
                                   ax=ax)

    # 绘制边
    nx.draw_networkx_edges(undirected, pos,
                           edge_color="#4a4a6a",
                           width=0.8,
                           alpha=0.6,
                           arrows=True,
                           ax=ax)

    # 绘制标签（如果没有中文字体则截短使用ASCII）
    labels = {}
    for n in subG.nodes():
        name = subG.nodes[n].get("name_cn", n)
        if cn_font is None:
            name = subG.nodes[n].get("name", n)[:10]  # 使用英文名
        else:
            name = name[:8]
        labels[n] = name

    label_kwargs = {"font_size": 7, "font_color": "white", "ax": ax}
    if cn_font:
        label_kwargs["font_family"] = cn_font
    nx.draw_networkx_labels(undirected, pos, labels=labels, **label_kwargs)

    # 图例
    patches = [mpatches.Patch(color=c, label=t) for t, c in ENTITY_COLORS.items()]
    ax.legend(handles=patches, loc="upper left",
              facecolor="#2c2c4e", edgecolor="white",
              labelcolor="white", fontsize=9)

    ax.set_title(f"半导体知识图谱 (显示{subG.number_of_nodes()}个节点, "
                 f"{subG.number_of_edges()}条关系)",
                 color="white", fontsize=14, pad=20)
    ax.axis("off")

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ 静态图片已保存: {output_path}")
    return True


def generate_entity_type_chart(G: nx.MultiDiGraph, output_path: str):
    """生成实体类型分布饼图"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    cn_font = _setup_chinese_font()

    type_count = defaultdict(int)
    for _, data in G.nodes(data=True):
        type_count[data.get("entity_type", "Unknown")] += 1

    labels = list(type_count.keys())
    sizes = [type_count[l] for l in labels]
    colors = [ENTITY_COLORS.get(l, "#95A5A6") for l in labels]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor("#1a1a2e")

    # 饼图
    ax1.set_facecolor("#1a1a2e")
    wedges, texts, autotexts = ax1.pie(
        sizes, labels=labels, colors=colors,
        autopct="%1.1f%%", startangle=90,
        textprops={"color": "white", "fontsize": 10}
    )
    ax1.set_title("实体类型分布", color="white", fontsize=13)

    # 关系类型分布条形图
    pred_count = defaultdict(int)
    for _, _, data in G.edges(data=True):
        pred_count[data.get("predicate", "unknown")] += 1

    pred_items = sorted(pred_count.items(), key=lambda x: -x[1])[:12]
    pred_names = [p[:20] for p, _ in pred_items]
    pred_vals = [v for _, v in pred_items]

    ax2.set_facecolor("#1a1a2e")
    bars = ax2.barh(range(len(pred_names)), pred_vals,
                    color=[PREDICATE_COLORS.get(p, "#7f8c8d") for p, _ in pred_items],
                    alpha=0.85)
    ax2.set_yticks(range(len(pred_names)))
    ax2.set_yticklabels(pred_names, color="white", fontsize=9)
    ax2.set_xlabel("三元组数量", color="white")
    ax2.set_title("关系类型分布（Top-12）", color="white", fontsize=13)
    ax2.tick_params(colors="white")
    ax2.spines["bottom"].set_color("white")
    ax2.spines["left"].set_color("white")
    for spine in ["top", "right"]:
        ax2.spines[spine].set_visible(False)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ 统计图表已保存: {output_path}")
    return True


def run_all_visualization():
    """生成所有可视化文件"""
    print("\n[visualize] 开始生成知识图谱可视化...")

    kg_json = ROOT_DIR / "data" / "processed" / "kg_data.json"
    if kg_json.exists():
        G, entities = load_graph_from_json(str(kg_json))
    else:
        from build_kg import build_knowledge_graph
        G, entities, _ = build_knowledge_graph()

    results_dir = ROOT_DIR / "results"
    results_dir.mkdir(exist_ok=True)

    # 1. 全图交互式可视化
    build_pyvis_html(G,
                     str(results_dir / "kg_full.html"),
                     title="半导体知识图谱 - 全图视图")

    # 2. NVIDIA子图
    build_subgraph_html(G, "C003",
                         str(results_dir / "kg_nvidia_subgraph.html"))

    # 3. TSMC子图
    build_subgraph_html(G, "C004",
                         str(results_dir / "kg_tsmc_subgraph.html"))

    # 4. 静态图谱
    build_matplotlib_static(G, str(results_dir / "kg_static.png"))

    # 5. 统计图表
    generate_entity_type_chart(G, str(results_dir / "kg_statistics.png"))

    print("\n[visualize] 可视化生成完成！")


if __name__ == "__main__":
    run_all_visualization()
