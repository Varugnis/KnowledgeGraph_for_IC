"""
大模型增强问答模块（GraphRAG）
支持：
  1. 真实API调用（DeepSeek / OpenAI 兼容接口）
  2. 模板模拟模式（无API时的降级方案）
对比"直接大模型回答"与"知识图谱增强后回答"的效果
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "cp936", "gb2312"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from build_kg import load_graph_from_json
from graph_retrieval import retrieve_for_question, format_kg_context

# ===========================================================================
# API 调用封装（支持 DeepSeek/OpenAI 兼容格式）
# ===========================================================================

def call_llm_api(prompt: str, system_prompt: str = "",
                 model: str = "deepseek-chat",
                 api_key: Optional[str] = None,
                 base_url: str = "https://api.deepseek.com") -> str:
    """
    调用LLM API（DeepSeek/OpenAI兼容接口）
    若API_KEY未设置，返回None（由调用者决定使用模拟模式）
    """
    if api_key is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")

    if not api_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1024,
            temperature=0.1,
        )
        return response.choices[0].message.content

    except ImportError:
        print("  [提示] 未安装 openai 库，请运行: pip install openai")
        return None
    except Exception as e:
        print(f"  [API错误] {e}")
        return None


# ===========================================================================
# 模拟模式（无API时的规则模板答案）
# ===========================================================================

def simulate_direct_answer(question: str) -> str:
    """模拟纯大模型（无KG增强）的回答——展示可能的幻觉和不确定性"""
    templates = {
        "H100": "NVIDIA H100是一款高性能GPU，主要用于AI训练和数据中心计算。它采用Hopper架构，性能非常强大。（注：以上为模拟回答，可能缺少具体细节）",
        "TSMC": "台积电(TSMC)是全球领先的晶圆代工厂，为多家芯片设计公司提供代工服务，包括Apple、AMD等。（注：模拟回答）",
        "Kirin": "华为麒麟系列芯片由海思设计。麒麟9000S的代工厂与具体工艺在公开资料中存在多种说法，难以给出确定结论。（注：模拟回答，可能不准确）",
        "麒麟": "华为麒麟9000S reportedly由中芯国际代工，工艺约为7nm级别，但细节存在争议。（注：模拟回答）",
        "default": f"关于[{question}]，根据我的训练知识：这是一个专业的半导体领域问题。相关芯片/技术在业界有广泛应用。（注：模拟回答，可能存在事实错误，缺乏具体来源）",
    }

    for key in templates:
        if key.lower() in question.lower():
            return templates[key]
    return templates["default"]


def simulate_kg_augmented_answer(question: str, kg_context: str,
                                  matched_entities: list) -> str:
    """模拟KG增强后的回答——基于图谱事实构建有依据的回答"""
    entity_names = [e["name"] for e in matched_entities[:3]]

    answer_lines = [
        f"【直接答案】基于知识图谱，针对问题[{question}]：",
        "",
    ]

    if kg_context and kg_context != "未在知识图谱中找到相关实体。":
        answer_lines.append("【KG事实依据】以下为从知识图谱中检索到的相关三元组：")
        context_lines = kg_context.split("\n")
        relevant_lines = [l for l in context_lines if any(
            name.lower() in l.lower() for name in entity_names
        )][:8]
        answer_lines.extend(f"  {l}" for l in relevant_lines[:8])
        answer_lines.append("")
        answer_lines.append("【推理过程】根据以上知识图谱事实：")
        if entity_names:
            answer_lines.append(f"  - 检索到关键实体：{', '.join(entity_names)}")
        answer_lines.append("  - 通过图谱关系链推导出答案")
        answer_lines.append("")
        answer_lines.append("【置信度】高（基于知识图谱直接证据）")
    else:
        answer_lines.append("【注意】知识图谱中未找到与该问题直接相关的证据。")
        answer_lines.append("【置信度】低（无KG证据支持）")

    return "\n".join(answer_lines)


# ===========================================================================
# GraphRAG 核心流程
# ===========================================================================

SYSTEM_PROMPT = """你是半导体领域专业知识助手。请基于提供的知识图谱上下文回答问题。
回答要求：
1. 优先使用【KG事实】标注知识图谱中的信息
2. 用【背景知识】标注训练数据中的一般知识
3. 给出证据链和置信度
4. 如实说明信息不足之处"""


def answer_with_kg(G, question: str, keywords: Optional[list] = None,
                    api_key: Optional[str] = None,
                    use_simulation: bool = False) -> dict:
    """
    GraphRAG流程：检索子图 -> 构建Prompt -> 调用LLM -> 返回增强答案

    Returns:
        {
            "question": str,
            "retrieval": dict,        # 检索结果
            "kg_context": str,        # 格式化后的KG上下文
            "direct_answer": str,     # 无KG的直接回答
            "kg_augmented_answer": str, # KG增强后的回答
            "using_api": bool,
        }
    """
    print(f"\n[llm_qa] 处理问题: {question}")

    # Step 1: 图谱检索
    retrieval = retrieve_for_question(G, question, keywords=keywords, hops=2)
    kg_context = format_kg_context(retrieval)
    print(f"  检索到 {retrieval['subgraph_nodes']} 个节点, {retrieval['subgraph_edges']} 条关系")

    # Step 2: 加载Prompt模板
    prompt_template_path = ROOT_DIR / "prompts" / "kg_augmented_prompt.txt"
    with open(prompt_template_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Step 3: 调用LLM（或使用模拟）
    using_api = False
    direct_answer = None
    kg_augmented_answer = None

    if not use_simulation:
        # 尝试调用真实API
        # 无KG的直接问答
        direct_prompt = f"请回答关于半导体领域的问题：{question}\n请直接基于你的训练知识回答，不要使用任何外部工具。"
        direct_answer = call_llm_api(direct_prompt, SYSTEM_PROMPT, api_key=api_key)

        # KG增强问答
        kg_prompt = prompt_template.replace("{kg_context}", kg_context).replace("{question}", question)
        kg_augmented_answer = call_llm_api(kg_prompt, SYSTEM_PROMPT, api_key=api_key)

        if direct_answer and kg_augmented_answer:
            using_api = True
            print("  [API] 使用真实API回答成功")

    if not using_api:
        # 降级到模拟模式
        print("  [模拟] 使用规则模板生成回答（未配置API）")
        direct_answer = simulate_direct_answer(question)
        kg_augmented_answer = simulate_kg_augmented_answer(
            question, retrieval["context_text"], retrieval["matched_entities"]
        )

    return {
        "question": question,
        "retrieval": {
            "matched_entities": retrieval["matched_entities"],
            "subgraph_nodes": retrieval["subgraph_nodes"],
            "subgraph_edges": retrieval["subgraph_edges"],
        },
        "kg_context": kg_context,
        "direct_answer": direct_answer,
        "kg_augmented_answer": kg_augmented_answer,
        "using_api": using_api,
    }


# ===========================================================================
# 测试问题集（10个）
# ===========================================================================

TEST_QUESTIONS = [
    {
        "question": "NVIDIA H100 AI加速卡采用什么制造工艺？由谁代工？",
        "keywords": ["H100", "NVIDIA", "TSMC"],
        "expected_entities": ["CH011", "C003", "C004", "P002"],
        "category": "事实查询",
    },
    {
        "question": "台积电掌握哪些先进制程工艺，这些工艺分别用于哪些芯片？",
        "keywords": ["台积电", "TSMC", "制程"],
        "expected_entities": ["C004", "P001", "P002", "P003"],
        "category": "一对多关系查询",
    },
    {
        "question": "苹果A17 Pro芯片与高通骁龙8 Gen 3相比，谁的制造工艺更先进？",
        "keywords": ["A17 Pro", "骁龙8 Gen 3", "工艺"],
        "expected_entities": ["CH017", "CH019", "P001"],
        "category": "比较推理",
    },
    {
        "question": "华为麒麟9000S是由哪家工厂生产的？采用了什么工艺？",
        "keywords": ["麒麟9000S", "Kirin 9000S", "SMIC"],
        "expected_entities": ["CH024", "P009", "C016", "C010"],
        "category": "事实查询",
    },
    {
        "question": "EUV光刻技术对半导体制造有什么影响？哪家公司是EUV设备的唯一供应商？",
        "keywords": ["EUV", "光刻", "ASML"],
        "expected_entities": ["T001", "C015", "P001", "P002"],
        "category": "技术影响分析",
    },
    {
        "question": "AI训练任务（如训练大型语言模型）需要使用什么类型的芯片？",
        "keywords": ["AI训练", "GPU", "H100", "A100"],
        "expected_entities": ["AP003", "CH011", "CH013", "D008"],
        "category": "应用场景推理",
    },
    {
        "question": "AMD Ryzen 9 7950X和Intel Core i9-14900K分别采用什么架构和工艺？",
        "keywords": ["Ryzen 9 7950X", "Core i9-14900K", "架构"],
        "expected_entities": ["CH006", "CH001", "A004", "A005"],
        "category": "多实体对比",
    },
    {
        "question": "氮化镓（GaN）材料在半导体领域有什么应用？",
        "keywords": ["GaN", "氮化镓", "功率器件"],
        "expected_entities": ["M003", "AP009"],
        "category": "材料应用查询",
    },
    {
        "question": "Snapdragon 888到骁龙8 Gen 3经历了哪些代际演进？",
        "keywords": ["Snapdragon 888", "骁龙8 Gen 3", "骁龙8 Gen 2"],
        "expected_entities": ["CH021", "CH020", "CH019"],
        "category": "历史演进多跳推理",
    },
    {
        "question": "台积电3nm工艺使用了哪些关键材料和技术？",
        "keywords": ["3nm", "台积电", "EUV", "材料"],
        "expected_entities": ["P001", "M001", "M007", "T001"],
        "category": "工艺技术深度查询",
    },
]


def run_qa_evaluation(G, api_key: Optional[str] = None,
                       use_simulation: bool = True) -> list:
    """
    运行全部测试问题，返回问答结果列表
    """
    print("\n" + "=" * 70)
    print("       GraphRAG 问答评估（半导体知识图谱增强）")
    print("=" * 70)
    print(f"  模式: {'模拟模式（无API）' if use_simulation else 'API模式（' + ('DeepSeek' if api_key else '自动检测') + '）'}")
    print(f"  测试问题数: {len(TEST_QUESTIONS)}")

    results = []
    for i, tq in enumerate(TEST_QUESTIONS):
        print(f"\n--- 问题 {i+1}/{len(TEST_QUESTIONS)} [{tq['category']}] ---")
        result = answer_with_kg(
            G,
            question=tq["question"],
            keywords=tq["keywords"],
            api_key=api_key,
            use_simulation=use_simulation,
        )
        result["category"] = tq["category"]
        result["expected_entities"] = tq["expected_entities"]
        results.append(result)

        # 简要打印结果
        print(f"\n  【无KG直接回答】")
        print(f"  {result['direct_answer'][:200]}...")
        print(f"\n  【KG增强回答】")
        print(f"  {result['kg_augmented_answer'][:300]}...")
        time.sleep(0.5)  # 避免API限流

    return results


def save_qa_results(results: list, output_path: str):
    """保存问答结果到JSON文件"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n问答结果已保存至: {output_path}")


def print_comparison_table(results: list):
    """打印对比摘要表格"""
    print("\n" + "=" * 70)
    print("                   问答结果对比摘要")
    print("=" * 70)
    print(f"{'#':3} {'类别':16} {'KG实体':5} {'KG边':5} {'API':5}")
    print("-" * 70)
    for i, r in enumerate(results):
        n_entities = r["retrieval"]["matched_entities"].__len__()
        n_edges = r["retrieval"]["subgraph_edges"]
        api_str = "✓" if r["using_api"] else "模拟"
        cat = r.get("category", "")[:14]
        print(f"{i+1:3} {cat:16} {n_entities:5} {n_edges:5} {api_str:5}")
    print("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GraphRAG 问答系统")
    parser.add_argument("--api-key", type=str, help="DeepSeek或OpenAI API密钥")
    parser.add_argument("--simulate", action="store_true", default=False,
                        help="强制使用模拟模式（不调用API）")
    args = parser.parse_args()

    # 加载图谱
    kg_json = ROOT_DIR / "data" / "processed" / "kg_data.json"
    if kg_json.exists():
        G, entities = load_graph_from_json(str(kg_json))
    else:
        from build_kg import build_knowledge_graph
        G, entities, _ = build_knowledge_graph()

    # 确定API密钥
    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY")
    use_simulation = args.simulate or (api_key is None)

    # 运行评估
    results = run_qa_evaluation(G, api_key=api_key, use_simulation=use_simulation)
    print_comparison_table(results)

    # 保存结果
    output_path = str(ROOT_DIR / "results" / "qa_results.json")
    save_qa_results(results, output_path)
