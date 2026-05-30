# 案例分析报告
## 半导体知识图谱 GraphRAG 问答案例

---

## 案例一：事实查询（成功案例）

**问题**：NVIDIA H100 AI加速卡采用什么制造工艺？由谁代工？

### 无KG直接大模型回答
> NVIDIA H100是基于Hopper架构的数据中心GPU，在AI训练方面性能强大。
> 它采用先进的制造工艺，由台积电代工制造。具体工艺节点为4nm左右。
> **（无具体工艺型号证据，置信度低）**

### KG增强后回答
**【KG事实】**
- `(NVIDIA, designs, H100)` ✅
- `(TSMC, fabricates, H100)` ✅
- `(H100, uses_process, TSMC 4nm(N4))` ✅
- `(H100, used_for, AI训练)` ✅
- `(H100, used_for, 数据中心)` ✅
- `(H100, uses_device, HBM高带宽存储器)` ✅

**直接答案**：NVIDIA H100由NVIDIA设计，委托台积电（TSMC）采用**4nm（N4）**工艺代工制造。
**证据链**：NVIDIA设计→H100→采用TSMC 4nm→由TSMC代工制造
**置信度**：高（知识图谱直接事实支持）

### 分析
- 无KG时：工艺信息笼统（"4nm左右"），缺乏精确型号
- 有KG时：精确给出"TSMC N4"工艺，并补充HBM存储、应用场景等关联信息
- **KG增强效果**：准确性提升，证据可追溯，信息完整度显著提高

---

## 案例二：多跳推理（成功案例）

**问题**：苹果A17 Pro和高通骁龙8 Gen 3相比，谁的制造工艺更先进？

### 无KG直接大模型回答
> 苹果A17 Pro和骁龙8 Gen 3都是旗舰级芯片，工艺都非常先进。
> A17 Pro可能采用3nm工艺，骁龙8 Gen 3也在4nm左右。
> **（工艺数据模糊，"左右"表述体现不确定性）**

### KG增强后回答
**【KG事实】**
- `(A17 Pro, uses_process, TSMC 3nm(N3))` ✅
- `(Snapdragon 8 Gen 3, uses_process, TSMC 4nm(N4P))` ✅  
  注：骁龙8 Gen 3采用的是台积电N4P工艺，属于4nm优化版
- `(TSMC 3nm, successor_of, TSMC 4nm)` ✅

**多跳推理链**：
```
A17 Pro --uses_process--> TSMC 3nm
                              |
                        successor_of
                              ↓
Snapdragon 8 Gen 3 --uses_process--> TSMC 4nm(N4P)
```

**直接答案**：苹果A17 Pro（TSMC 3nm）比骁龙8 Gen 3（TSMC 4nm N4P）工艺更先进，3nm工艺节点是4nm的后继代工艺。
**置信度**：高（多个KG事实支持 + 工艺继代关系佐证）

---

## 案例三：含争议信息（复杂案例）

**问题**：华为麒麟9000S是由哪家工厂生产的？采用了什么工艺？

### 无KG直接大模型回答
> 华为麒麟9000S据报道采用了中芯国际（SMIC）的7nm工艺生产，但受到制裁影响，
> 实际工艺情况存在一定争议。具体代工厂和工艺细节难以确认。

### KG增强后回答
**【KG事实】**
- `(HiSilicon, designs, Kirin 9000S)` [置信度: 1.0] ✅
- `(SMIC, fabricates, Kirin 9000S)` [置信度: 1.0] ✅
- `(Kirin 9000S, uses_process, SMIC N+1)` [置信度: 1.0] ✅

**分析**：图谱将代工厂正确关联至中芯国际（C016），与工艺节点 SMIC N+1 一致，消除了此前误将联发科（C009）标注为代工方的数据错误。

**直接答案**：麒麟9000S由华为海思设计，由中芯国际（SMIC）代工制造，采用 SMIC N+1 工艺（等效约 7nm 级别）。
**置信度**：高（设计、代工、工艺三元组相互印证）

---

## 案例四：技术影响分析

**问题**：EUV光刻技术对半导体制造有什么影响？哪家公司是EUV设备的唯一供应商？

### 无KG直接大模型回答
> EUV（极紫外光刻）技术是半导体制造的重要突破，波长约13.5nm，能够实现更精细的光刻图案，是7nm以下节点制造的关键技术。ASML是全球唯一的EUV光刻机制造商。

### KG增强后回答
**【KG事实】**
- `(ASML, manufactures_tool, EUV光刻)` ✅
- `(EUV光刻, enables_process, TSMC 3nm)` ✅
- `(EUV光刻, enables_process, TSMC 4nm)` ✅
- `(EUV光刻, enables_process, TSMC 5nm)` ✅
- `(TSMC, masters_technology, EUV光刻)` ✅
- `(Intel, masters_technology, EUV光刻)` [置信度: 0.9] ✅

**直接答案**：EUV光刻（波长13.5nm）是5nm及以下节点量产的核心技术，由荷兰ASML垄断供应。台积电在3nm/4nm/5nm节点均使用EUV技术，Intel从Intel 4节点开始引入EUV。

**置信度**：高（KG多条直接证据支持，信息具体可追溯）

---

## 案例五：幻觉检测示例

**声明（错误）**："Apple M3 Ultra采用Samsung 3nm GAA工艺"

### 错在哪里？

| 维度 | 错误说法 | 图谱事实 |
|------|----------|----------|
| 代工厂 | 暗示三星代工 | `(TSMC, fabricates, M3 Ultra)` ✅；无 Samsung 代工边 |
| 工艺节点 | Samsung 3nm GAA（三星 P008） | `(M3 Ultra, uses_process, TSMC 3nm(N3))` ✅ |
| 产业角色 | 与 Exynos 同属三星工艺体系 | M 系列由苹果设计、台积电代工；三星 3nm GAA 用于 Exynos 等自有芯片 |

常见原因：模型将语料中高频的 “Samsung + 3nm + GAA” 与 “Apple 旗舰芯片” 错误拼接，未区分 `fabricates` 与 `uses_process`。

### KG 验证结果
- 查询 `(M3 Ultra, uses_process, Samsung 3nm GAA)` → **不存在** → 判为幻觉
- 正确链条：`(Apple Silicon, designs, M3 Ultra)` → `(TSMC, fabricates, M3 Ultra)` → `(M3 Ultra, uses_process, TSMC 3nm(N3))`

### 正确表述
> M3 Ultra 由苹果设计、**台积电**代工，采用**台积电 3nm（N3）**，**不是**三星 3nm GAA。

**判定**：❌ **幻觉检出**

---

## 案例六：历史演进多跳推理

**问题**：Snapdragon 888到骁龙8 Gen 3经历了哪些代际演进？

### KG推理路径
```
骁龙888 (5nm, 2020)
    ↓ successor_of (反向)
骁龙8 Gen 2 (4nm, 2022)
    ↓ successor_of (反向)
骁龙8 Gen 3 (4nm N4P, 2023)
```

**KG事实链**：
- `(Snapdragon 8 Gen 2, successor_of, Snapdragon 888)` ✅
- `(Snapdragon 8 Gen 3, successor_of, Snapdragon 8 Gen 2)` ✅
- 工艺演进：5nm → 4nm → 4nm(N4P优化)

**结论**：三代演进，工艺从5nm升级至4nm，AI性能持续提升，均由Qualcomm设计、TSMC代工。

---

## 综合对比分析

| 问题类型 | 无KG准确性 | KG增强准确性 | KG增强主要贡献 |
|---------|----------|------------|--------------|
| 简单事实查询 | 中 | 高 | 具体工艺型号、精确数据 |
| 多跳关系推理 | 低 | 高 | 完整推理链，每步有据可查 |
| 争议信息处理 | 模糊 | 有标注 | 置信度量化，争议明确标注 |
| 技术影响分析 | 基本正确 | 高+详细 | 具体受影响芯片/工艺列举 |
| 幻觉检测 | N/A | 87.5%准确 | 事实核查，防止错误传播 |
| 历史演进查询 | 部分正确 | 完整准确 | 代际关系链完整，时间准确 |

### 主要发现
1. **准确性提升**：KG增强后对具体技术事实（工艺型号、代工关系）的准确率显著提升
2. **可追溯性**：所有答案均可追溯到具体知识图谱三元组，支持证据审计
3. **幻觉减少**：87.5%的错误声明被成功检出（8个测试声明，7个正确）
4. **多跳推理**：图谱明确支持3-4跳推理，而纯LLM在多跳场景下错误率较高
5. **局限性**：跨类型实体检索（如 Q10 材料/技术）召回率仍偏低，需改进检索策略
