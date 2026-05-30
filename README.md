# 半导体知识图谱：构建、推理与大模型增强

> 电子信息研究生课程作业 · 知识图谱 · GraphRAG 实践

---

## 项目简介

本项目围绕**半导体与芯片技术**领域，构建了一个完整的知识图谱系统，包含三个核心模块：

| 模块 | 说明 |
|------|------|
| **图谱构建** | 111 个实体、318 条三元组、8 类实体类型、16 类关系类型 |
| **知识推理** | 规则推理（7条 Horn 规则）+ 路径推理（双向 BFS 多跳）|
| **GraphRAG** | 图谱子图检索 → Prompt 注入 → 有/无 KG 问答对比 + 幻觉检测 |

覆盖 Intel、AMD、NVIDIA、TSMC、Apple、高通等主流厂商，H100、A17 Pro、骁龙 8 Gen 3 等旗舰芯片，以及 3nm/4nm/5nm 等关键制造工艺。

---

## 项目结构

```
KnowledgeGraph/
├── README.md                    # 本文件
├── requirements.txt             # Python 依赖
├── run_all.py                   # 一键运行所有模块
├── .gitignore
│
├── data/
│   └── raw/
│       ├── entities.csv         # 111 个实体（人工整理）
│       └── triples.csv          # 318 条三元组（人工整理）
│
├── src/
│   ├── build_kg.py              # 图谱构建与存储
│   ├── reasoning.py             # 规则推理 + 路径推理
│   ├── graph_retrieval.py       # 子图检索（GraphRAG 基础）
│   ├── llm_qa.py                # 大模型增强问答
│   ├── evaluate.py              # 综合评估（检索/推理/幻觉）
│   └── visualize.py             # pyvis 交互式可视化
│
├── prompts/
│   └── kg_augmented_prompt.txt  # GraphRAG Prompt 模板
│
├── results/
│   └── cases.md                 # 问答案例对比分析（手写）
│   # 以下文件运行后自动生成，不在仓库中：
│   # kg_full.html / kg_static.png / metrics.json / qa_results.json ...
│
└── docs/
    ├── 课程报告.md               # 课程报告正文
    ├── 课程PPT.pptx              # 课程汇报幻灯片（12页）
    ├── 项目答疑纪要.md           # 常见问题整理
    └── gen_ppt.py               # PPT 生成脚本
```

---

## 生成提交材料（PPT / PDF）

```bash
pip install python-pptx
python -X utf8 docs/gen_ppt.py              # 生成 docs/课程PPT.pptx（12页）
python -X utf8 docs/export_submission.py  # 可选：复制 slides.pptx，尝试导出 report.pdf
```

报告 PDF 若自动导出失败，请用 Word/WPS 打开 `docs/课程报告.md` 另存为根目录 `report.pdf`。

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Varugnis/KnowledgeGraph_for_IC.git
cd KnowledgeGraph_for_IC
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行（无需 API Key）

```bash
# Windows
python -X utf8 run_all.py --simulate

# macOS / Linux
python run_all.py --simulate
```

运行完成后查看生成文件：

- **`results/kg_full.html`** — 在浏览器中打开，交互式拖拽查看知识图谱
- **`results/kg_static.png`** — 静态图谱图片
- **`results/metrics.json`** — 评估指标（幻觉检测、路径推理准确率等）
- **`results/qa_results.json`** — 10 个测试问题的有/无 KG 双路回答

---

## 使用 DeepSeek API（可选）

配置后可获得真实的"有 KG vs 无 KG"大模型问答对比效果。

1. 注册 [platform.deepseek.com](https://platform.deepseek.com/)，充值 1 元并创建 API Key。
2. 设置环境变量后运行：

```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-你的key"
python -X utf8 run_all.py

# macOS / Linux
export DEEPSEEK_API_KEY="sk-你的key"
python run_all.py
```

> 未配置 API Key 时系统自动使用**规则模拟模式**，图谱构建、推理、评估模块不受影响。

---

## 分模块运行

```bash
# 仅构建图谱
python -X utf8 src/build_kg.py

# 仅运行推理（规则 + 路径）
python -X utf8 src/reasoning.py

# 仅问答对比
python -X utf8 src/llm_qa.py --simulate

# 仅综合评估
python -X utf8 src/evaluate.py

# 仅生成可视化
python -X utf8 src/visualize.py
```

---

## 主要实验结果

### 图谱质量

| 指标 | 数值 | 作业要求 |
|------|------|---------|
| 实体数量 | 111 | ≥ 100 ✅ |
| 三元组数量 | 318 | ≥ 300 ✅ |
| 实体类型 | 8 类 | ≥ 3 ✅ |
| 关系类型 | 16 类 | ≥ 3 ✅ |
| 最大连通分量覆盖率 | 95.5% | — |

### 推理效果

| 方法 | 结果 |
|------|------|
| 规则推理（7 条 Horn 规则）| 推导出 104 条新知识三元组 |
| 路径推理（BFS，最多 4 跳）| 准确率 85.7%（6/7 测试用例）|

### GraphRAG 问答对比（示例）

**问题**：苹果 A17 Pro 和骁龙 8 Gen 3，谁的制造工艺更先进？

| | 无 KG 直接回答 | KG 增强回答 |
|--|--------------|------------|
| 工艺描述 | "都在 4nm 左右" | A17 Pro: TSMC N3；骁龙 8 Gen 3: TSMC N4P |
| 证据来源 | 无 | 3 条知识图谱三元组 |
| 推理链 | 无 | `A17Pro→TSMC 3nm` / `骁龙→TSMC 4nm` / `3nm successor_of 4nm` |
| 置信度 | 低（模糊） | 高（有据可查）|

**幻觉检测准确率：100%（8/8 声明正确核查）**

---

## 依赖说明

| 库 | 版本要求 | 用途 |
|----|---------|------|
| networkx | ≥ 3.1 | 图谱存储与图算法 |
| pyvis | ≥ 0.3.2 | 交互式 HTML 可视化 |
| matplotlib | ≥ 3.7 | 静态图表 |
| pandas | ≥ 2.0 | 数据处理 |
| openai | ≥ 1.0 | DeepSeek API 调用（可选）|
| python-pptx | ≥ 0.6 | PPT 生成脚本 |

---

## 学术规范声明

本项目在以下环节使用了 AI 辅助（Cursor AI，底层为 Claude Sonnet）：

- **代码辅助生成**：各模块初始框架由 AI 辅助生成，经小组成员逐行阅读、调试验证，修正了 BFS 双向遍历、Windows 编码兼容等问题。
- **文档辅助撰写**：报告和 README 初稿由 AI 辅助生成，小组成员核对所有数据与结论后修改定稿。
- **未使用 AI 的部分**：`entities.csv` 与 `triples.csv` 由小组成员参考公开技术资料人工整理；推理规则语义设计、测试问题选取、案例分析判断均由小组成员独立完成。

数据来源：Intel ARK、AMD 官网、TSMC 官网、AnandTech、IEEE Spectrum、TechPowerUp 等公开资料。

---

## 参考文献

- Bordes et al., *Translating Embeddings for Modeling Multi-relational Data*, NeurIPS 2013
- Edge et al., *From Local to Global: A Graph RAG Approach*, arXiv:2404.16130, 2024
- Ji et al., *A Survey on Knowledge Graphs*, IEEE TNNLS 2022
- Pan et al., *Unifying Large Language Models and Knowledge Graphs: A Roadmap*, IEEE TKDE 2024
- [NetworkX Docs](https://networkx.org/) · [pyvis Docs](https://pyvis.readthedocs.io/) · [DeepSeek API](https://platform.deepseek.com/api-docs/)

---

## 小组成员

| 成员 | 主要分工 |
|------|---------|
| 蒋航 | 数据收集整理、Schema 设计、entities.csv / triples.csv、报告第二章 |
| 漆宇杰 | build_kg.py、reasoning.py、visualize.py、图谱质量分析、报告第三章 |
| 李嘉辉 | graph_retrieval.py、llm_qa.py、evaluate.py、报告与 PPT |
