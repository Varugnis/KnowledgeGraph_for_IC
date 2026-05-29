# 半导体知识图谱：构建、推理与大模型增强

> 电子信息研究生课程作业 | 知识图谱领域 | GraphRAG 实践

---

## 项目简介

本项目构建了一个**半导体与芯片技术**领域的知识图谱系统，包含：
- **知识图谱构建**：110个实体、318条三元组、8类实体、16类关系
- **知识推理**：规则推理（7条Horn规则）+ 路径推理（BFS多跳）+ 链接预测
- **大模型增强（GraphRAG）**：图谱检索 → Prompt增强 → 对比问答 + 幻觉检测

覆盖全球主流芯片厂商（Intel/AMD/NVIDIA/TSMC/Apple/高通等）、旗舰芯片、制造工艺、材料、架构等核心知识。

---

## 环境要求

- Python 3.9 及以上
- 操作系统：Windows / macOS / Linux

---

## 快速开始

### 第一步：克隆项目

```bash
git clone https://github.com/你的用户名/你的仓库名.git
cd KnowledgeGraph_for_IC
```

### 第二步：安装依赖

```bash
pip install -r requirements.txt
```

依赖项说明：

| 库 | 用途 |
|----|------|
| `networkx` | 知识图谱存储与图算法 |
| `pyvis` | 交互式HTML图谱可视化 |
| `matplotlib` | 静态图表生成 |
| `pandas` | 数据处理 |
| `openai` | DeepSeek / OpenAI API调用（可选）|

### 第三步：运行项目

**方式A：一键运行所有模块（推荐）**

```bash
# 模拟模式（无需API，直接运行）
python -X utf8 run_all.py --simulate

# 真实大模型模式（需要DeepSeek API Key）
python -X utf8 run_all.py --api-key sk-你的key

# 跳过可视化（更快）
python -X utf8 run_all.py --simulate --skip-viz
```

**方式B：分步骤运行**

```bash
# 1. 构建知识图谱
python -X utf8 src/build_kg.py

# 2. 知识推理（规则 + 路径）
python -X utf8 src/reasoning.py

# 3. 大模型增强问答
python -X utf8 src/llm_qa.py --simulate        # 模拟模式
python -X utf8 src/llm_qa.py --api-key sk-xxx  # 真实API

# 4. 综合评估
python -X utf8 src/evaluate.py

# 5. 生成可视化
python -X utf8 src/visualize.py
```

---

## 配置 DeepSeek API（可选但推荐）

1. 注册账号：https://platform.deepseek.com/
2. 充值（1元即可）并创建 API Key
3. 配置环境变量：

**Windows PowerShell：**
```powershell
$env:DEEPSEEK_API_KEY = "sk-你的key"
python -X utf8 run_all.py
```

**macOS / Linux：**
```bash
export DEEPSEEK_API_KEY="sk-你的key"
python -X utf8 run_all.py
```

> 不配置也完全没问题，系统会自动使用模拟模式运行。

---

## 项目结构

```
KnowledgeGraph/
├── README.md                   # 本文件
├── requirements.txt            # Python依赖
├── run_all.py                  # 一键运行脚本
├── .gitignore                  # Git忽略规则
│
├── data/
│   ├── raw/
│   │   ├── entities.csv        # 110个实体定义（手工整理）
│   │   └── triples.csv         # 318条三元组（手工整理）
│   ├── processed/              # 运行后自动生成，已被.gitignore忽略
│   └── triples.csv             # 运行后自动生成，已被.gitignore忽略
│
├── src/
│   ├── build_kg.py             # 知识图谱构建
│   ├── reasoning.py            # 知识推理（规则 + 路径 + 链接预测）
│   ├── graph_retrieval.py      # 子图检索（为GraphRAG提供上下文）
│   ├── llm_qa.py               # 大模型增强问答（GraphRAG）
│   ├── evaluate.py             # 综合评估
│   └── visualize.py            # 图谱可视化
│
├── prompts/
│   └── kg_augmented_prompt.txt # GraphRAG Prompt模板
│
└── results/
    └── cases.md                # 问答案例对比分析（手写）
    # 以下文件在运行后自动生成：
    # kg_full.html              交互式图谱（浏览器打开）
    # kg_static.png             静态图谱图片
    # kg_statistics.png         统计图表
    # metrics.json              评估指标
    # qa_results.json           问答结果
    # reasoning_results.json    推理结果
```

---

## 主要实验结果

### 知识图谱质量

| 指标 | 数值 |
|------|------|
| 实体总数 | 110 |
| 三元组总数 | 318 |
| 实体类型 | 8类 |
| 关系类型 | 16类 |
| 最大连通分量覆盖率 | 95.5% |
| 台积电节点度中心性 | 0.239（最高） |

### 推理效果

| 方法 | 结果 |
|------|------|
| 规则推理（7条规则）| 推导出 104 条新知识三元组 |
| 路径推理（BFS 4跳）| 准确率 85.7% |
| 幻觉检测 | 准确率 100%（8/8） |

### GraphRAG 问答对比示例

**问题**：苹果A17 Pro和骁龙8 Gen 3谁的制造工艺更先进？

| | 无KG直接回答 | KG增强回答 |
|--|------------|-----------|
| 工艺数据 | "都在4nm左右" | A17 Pro: TSMC N3；骁龙8 Gen 3: TSMC N4P |
| 证据来源 | 无 | 3条知识图谱三元组 |
| 置信度 | 低（模糊表述）| 高（有据可查）|

---

## 大模型使用说明

本项目在以下场景使用了大模型（符合学术规范要求说明）：
- **代码辅助生成**：部分模块代码由 AI 辅助编写，经人工审核和调试
- **数据整理**：实体与三元组数据参考公开技术资料人工整理
- **报告撰写**：报告内容由作者独立撰写，AI仅用于润色

---

## 小组成员分工

| 成员 | 贡献 |
|------|------|
| 成员A | 数据收集整理（entities.csv、triples.csv）、图谱Schema设计 |
| 成员B | 图谱构建模块（build_kg.py）、可视化（visualize.py） |
| 成员C | 推理模块（reasoning.py）、评估（evaluate.py） |
| 成员D | 大模型增强（llm_qa.py、graph_retrieval.py）、案例分析 |

---

## 参考资料

- NetworkX 文档：https://networkx.org/
- pyvis 可视化：https://pyvis.readthedocs.io/
- DeepSeek API：https://platform.deepseek.com/
- GraphRAG 论文：Edge et al., 2024, *From Local to Global: A Graph RAG Approach*
- TransE 论文：Bordes et al., 2013, *Translating Embeddings for Modeling Multi-relational Data*
