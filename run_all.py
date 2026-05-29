"""
一键运行脚本：依次执行所有模块
用法：python run_all.py [--api-key YOUR_KEY] [--simulate]
"""

import sys
import os
import argparse
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR / "src"))


def step(n: int, title: str):
    print(f"\n{'='*70}")
    print(f"  步骤 {n}: {title}")
    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(description="半导体知识图谱系统 - 一键运行")
    parser.add_argument("--api-key", type=str, default=None,
                        help="DeepSeek/OpenAI API密钥（可选）")
    parser.add_argument("--simulate", action="store_true", default=False,
                        help="强制使用模拟模式（不调用API）")
    parser.add_argument("--skip-viz", action="store_true", default=False,
                        help="跳过可视化步骤（节省时间）")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY")
    use_simulation = args.simulate or (api_key is None)

    print("\n" + "=" * 70)
    print("       半导体知识图谱系统 - 完整运行")
    print("       （知识图谱构建 + 推理 + GraphRAG大模型增强）")
    print("=" * 70)
    print(f"  API模式: {'模拟（无API）' if use_simulation else f'真实API ({api_key[:8]}...)'}")
    print(f"  可视化: {'跳过' if args.skip_viz else '生成'}")

    start_time = time.time()

    # ===== 步骤1：构建知识图谱 =====
    step(1, "构建半导体知识图谱")
    from build_kg import build_knowledge_graph
    G, entities, stats = build_knowledge_graph()

    # ===== 步骤2：知识推理 =====
    step(2, "执行知识推理（规则推理 + 路径推理）")
    from reasoning import run_all_reasoning
    G_aug, reasoning_results = run_all_reasoning()

    # ===== 步骤3：大模型增强问答 =====
    step(3, f"GraphRAG大模型增强问答（{'模拟模式' if use_simulation else 'API模式'}）")
    from llm_qa import run_qa_evaluation, save_qa_results, print_comparison_table, TEST_QUESTIONS
    from build_kg import load_graph_from_json

    kg_json = ROOT_DIR / "data" / "processed" / "kg_data.json"
    G_qa, _ = load_graph_from_json(str(kg_json))

    qa_results = run_qa_evaluation(G_qa, api_key=api_key, use_simulation=use_simulation)
    print_comparison_table(qa_results)
    save_qa_results(qa_results, str(ROOT_DIR / "results" / "qa_results.json"))

    # ===== 步骤4：综合评估 =====
    step(4, "综合评估（图谱质量 + 推理效果 + 幻觉检测）")
    from evaluate import run_full_evaluation
    metrics = run_full_evaluation()

    # ===== 步骤5：可视化 =====
    if not args.skip_viz:
        step(5, "生成知识图谱可视化")
        try:
            from visualize import run_all_visualization
            run_all_visualization()
        except Exception as e:
            print(f"  [警告] 可视化生成出错（可能缺少依赖）: {e}")
            print("  请手动运行: python src/visualize.py")
    else:
        print("\n[步骤5] 跳过可视化（--skip-viz）")

    # ===== 完成 =====
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"  ✅ 所有步骤完成！总耗时: {elapsed:.1f}秒")
    print("=" * 70)
    print("\n  生成的文件：")
    output_files = [
        ("data/processed/kg_data.json", "知识图谱数据"),
        ("data/triples.csv", "三元组CSV"),
        ("results/reasoning_results.json", "推理结果"),
        ("results/qa_results.json", "问答结果"),
        ("results/metrics.json", "评估指标"),
        ("results/cases.md", "案例分析"),
        ("results/kg_full.html", "交互式图谱可视化"),
        ("results/kg_static.png", "静态图谱图片"),
        ("results/kg_statistics.png", "统计图表"),
    ]
    for fpath, desc in output_files:
        full_path = ROOT_DIR / fpath
        status = "✅" if full_path.exists() else "⚠️ 未生成"
        print(f"  {status} {fpath:45s} ({desc})")

    print("\n  快速开始查看：")
    print("  - 打开 results/kg_full.html 查看交互式知识图谱")
    print("  - 查看 results/cases.md 了解问答案例对比分析")
    print("  - 查看 results/metrics.json 了解量化评估指标")


if __name__ == "__main__":
    main()
