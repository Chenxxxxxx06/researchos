# A 块交付文档：文献知识库 & RAG 检索

> 分支：`blockA-rag-dev`
> 验收依据：`TEACHER_REQUIREMENTS_ACCEPTANCE_MATRIX_ZH.md` T1 + D3 行
> 设计依据：`TEACHER_REQUIREMENTS_INCREMENTAL_PRODUCT_DESIGN_ZH.md` §7（RAG 规格）、§7.4（引用体验）、§15（不做清单）
> 范围：论文入库/解析、索引、混合检索、引用定位、删除保护；不含阅读卡内容逻辑（B）、Agent 编排（C）、前端（D）。

---

## 1. 知识库架构（我方部分）

### 1.1 分层模型与不变量

```text
Paper（论文）          ← 业务不变量：入库即确定，对外可持久化引用
  └─ PaperSection（章节，带 kind/heading/seq）  ← 业务不变量：下游锚定键
       └─ PaperChunk（检索片段）               ← 纯内部层：随 embedding profile 重建
```

- **对外锚定 = `section_id` + 逐字 quote**。阅读卡、锚定笔记、综述主张等下游产物只引用 section 层；`chunk_id` / `char_start` / `char_end` 是检索时返回的定位信息，**不被下游持久化**。
- **chunk 的合法性由 embedding profile 决定**。每条 chunk 记录 `embedding_model`（= profile 名）；查询前校验索引 profile 与当前查询 profile 一致，不一致即触发该项目全量重建（`ensure_project_chunks` 自动完成，对调用方透明）。
- **profile 变更 = 全量重建**。embedding 模型、维度、切分参数任何一项变化都视为新 profile，不存在"部分旧索引"状态。

### 1.2 数据流

```text
arXiv 导入（ar5iv HTML）
  → ingest：正文清洗（空白/引用标记规整，LaTeX alttext 逐字保留）+ section kind 分类
  → PaperSection 落库
  → 句子对齐切分为 PaperChunk（含精确 char 偏移）
  → 两路索引：tsv（PostgreSQL FTS）+ embedding（pgvector HNSW）
  → POST /rag/search：向量 Top40 + 关键词 Top40 → RRF 融合 → 多样性限产 → Top-k 引用片段
```

PDF 上传（inbox）目前**不入索引**，见 §5 已知边界。

---

## 2. RAG 实现说明（设计内容 3 五件套）

### 2.1 解析（`research/ingest.py`）

- 唯一正文来源是 arXiv 的 **ar5iv HTML**（`https://ar5iv.labs.arxiv.org/html/{arxiv_id}`），不解析排版 PDF，因此正文干净、结构完整。
- section 自动提取：按 HTML 标题层级切分，`kind` 自动分类（method / results / introduction / experiments / training / dataset / other 等）。
- 清洗口径（保守原则）：只规整多余空白/换行、规整引用标记（`[5, 2, 35]` → `[5,2,35]`）；**LaTeX 公式 alttext 逐字保留**——公式是语义不是噪声，保留后关键词路可精确匹配公式片段，也为未来正则检索留地基。
- 已修上游 bug：arxiv provider 原用裸 `http://` 且不跟随 301 重定向导致真实导入失败，现改 https 默认 + `follow_redirects=True`。

### 2.2 切分（`knowledge/indexing.py`）

- **句子对齐切分**：目标 600 token / 上限 800 / overlap 100（token 以 `chars_per_token=4.0` 近似换算），chunk 边界一定落在句子上，不会硬切断句。
- **精确偏移不变量**：`section.body[char_start:char_end] == chunk.content`，有专门测试保证。这就是可溯源的地基——返回的片段能逐字回贴到原文。
- chunk 落库带 `text_hash`、`embedding_model`（profile 名）、`indexed_at`，对应设计 §7.2 建议表结构。

### 2.3 向量（`knowledge/embeddings.py` + `knowledge/profiles.py`）

- **双 profile，统一 1024 维**，共用同一 `Vector(1024)` 列（迁移 0020，含 HNSW 索引重建）：

  | profile | 用途 | 说明 |
  |---|---|---|
  | `qwen-text-embedding-v4-1024` | 开发 / 演示（在线） | 阿里云百炼 text-embedding-v4，OpenAI 兼容接口，批次 10 条/次、自动重试、返回维度校验 |
  | `hashing-1024-v2` | CI / 离线兜底 | 确定性 hashing embedding，无网可复现，全套测试的默认 profile |

- `profiles.py` 是**唯一事实源**：索引与查询从同一 profile 对象取模型/维度/归一化参数，从机制上保证"索引用什么、搜就用什么"。
- API Key 只存 `apps/api/.env`（已 gitignore），仅出现在请求 Header，不进代码、不进日志。
- 选型记录：百炼 v4 支持自定义维度（与 hashing 兜底统一 1024）、OpenAI 兼容（迁移成本低）、免费额度 100 万 token 覆盖 demo 规模（100 篇论文全量索引实测约消耗大半额度）。

### 2.4 关键词（PostgreSQL FTS）

- `websearch_to_tsquery`（OR 语义）+ `ts_rank`，阈值 > 1e-10。
- 这里修了一个隐蔽 bug：原实现用 `ts_rank_cd` + AND 语义 tsquery，要求查询全部词项在同一 chunk 共现才给分，长查询下 keyword_score **恒为 0**（等于关键词路形同虚设）。已在 PG16 实测验证修复。

### 2.5 引用片段 + 融合（`knowledge/service.py`）

- **RRF 融合**：向量 Top40 与关键词 Top40 两个独立 SQL 查同一候选池，`score = Σ 1/(60 + rank)`（k=60 标准值），Python 合并。两路分数量纲不同（余弦相似度 vs ts_rank），RRF 只看名次不看分数，无需调权重。
- **多样性限产**：每篇论文最多 3 个 hit，不足时放宽补齐，避免结果全来自一篇。
- 响应模式 `mode = hybrid-vector-keyword-v2`，每个 hit 含设计 §7.3 要求的全部定位字段：

```json
{
  "chunk_id": "…", "paper_id": "…", "section_id": "…",
  "title": "Attention Is All You Need", "heading": "Introduction", "kind": "introduction",
  "snippet": "…原文片段（LaTeX 保留）…",
  "score": 0.0305, "vector_score": 0.6921, "keyword_score": 0.0556,
  "match_reasons": ["vector", "keyword"],
  "char_start": 8268, "char_end": 11236,
  "citation_key": "arxiv:1706.03762"
}
```

- `match_reasons` 标明该 hit 由哪一路召回（`vector` / `keyword`，可双中），对应 §7.4 "展示匹配原因"。
- 规格 §7.3 第 5 步的"可选 reranker 取 Top 12"**未实现**：RRF 直连 Top-k（默认 limit=8）已满足演示与验收，reranker 会引入新的外部依赖与延迟，留作后续增强项。

---

## 3. API 变更清单

| 端点 | 变更 | 说明 |
|---|---|---|
| `POST /projects/{id}/rag/search` | 行为升级 v1→v2 | 新增 `match_reasons`、`embedding_model` 字段；关键词路修复；RRF 融合 + 多样性；`mission_id` / `kinds` 过滤不变 |
| `GET /projects/{id}/papers/{pid}/references` | **新增** | 删除预检：五类下游引用计数（reading_cards / reading_notes / review_sections / experiment_plans / missions）+ `blocked` 标志，VIEWER 可调 |
| `DELETE /projects/{id}/papers/{pid}` | 行为变更 | 默认有引用时返回 **409**（`error.code="paper_has_references"`，`details.references` 为五类明细）；`?force=true` 强删 |

**给 D 块前端的提示**：`apps/web/lib/api/papers.ts:216` 的 `deletePaper()` 目前裸调 DELETE，需改为：先调 references 预检展示提示 → 用户确认后带 `?force=true` 删除。

---

## 4. 验收证据（T1 / D3）

### 4.1 测试

```bash
cd apps/api
POSTGRES_DSN='postgresql+asyncpg://researchos:researchos@localhost:5432/researchos_test' \
REDIS_URL='redis://localhost:6379/15' DB_USE_NULLPOOL='true' \
uv run pytest tests -q
# 结果：435 passed, 1 skipped（skip = 在线测试按开关跳过）
```

- CI 无网全绿：conftest 强制 hashing profile，无任何外部调用。
- 真实 API 在线测试（不省额度）：`tests/online/` 4 用例，`RUN_ONLINE_TESTS=1` + 有效 Key 时启用，真实调百验验证语义判别（margin 0.55）；CI 自动 skip。
- 新增套件：`test_rag_search.py`（8 用例：融合/过滤/空索引/偏移回切闭环）、`test_paper_delete_references.py`（4 用例：409/force/预检）、`test_embeddings_dashscope.py`、`test_vector_indexing.py` 扩充（句子边界/偏移不变量/profile 一致性）。
- `ruff check researchos tests` 绿；`mypy researchos` 无新增错误（残留 7 个在 `common/paths.py`、`runtime/ssh/provider.py`，分支既有问题）。

### 4.2 Golden set 命中率（设计 §7.3 的验收方式）

```bash
# 栈运行中（docker compose up），demo 账号可登录
cd apps/api && uv run python scripts/golden_rag_eval.py
```

- 题库：`apps/api/scripts/golden_rag_set.json`，14 个人工标注问题（direct / paraphrase 各半）。
- **实测（Docker 栈内、100 篇真实 arXiv 论文语料）**：Top-3 命中率 **85.7%**（12/14），Top-5 **92.9%**（13/14）。
- 栈内冒烟实测样例：意译查询 "how does the transformer avoid recurrence in sequence modeling" 命中 Transformer-XL 与 Attention Is All You Need，`match_reasons` 双中，LaTeX 片段完整。

### 4.3 演示操作路径

1. `pnpm stack:full` 起栈，demo@researchos.dev / demo-password-123 登录。
2. 打开 Demo 项目 → 文献（100 篇真实 arXiv 论文，93 篇 sections ≥ 5）。
3. 文献页做跨论文证据检索，展开 method/results 原文片段（`match_reasons` 可见）。
4. 删除一篇被引用的论文 → 409 + 五类引用明细（预检端点可先看）。

---

## 5. 已知边界（明确不做 / 遗留）

- **图表 / 跨模态 RAG、PDF 页码定位**：设计 §15 明文不做项。`locator` 只到 section + char 偏移，不猜页码。
- **inbox PDF 不入索引**：上传 PDF 目前仅存原文不入 RAG 索引，索引正文唯一来源是 ar5iv HTML；扩展 PDF 解析属于产品边界扩张，留给后续决策。
- **`indexed_papers` 口径**：`rag/search` 响应里的 `indexed_papers` / `indexed_chunks` 是"本次调用补索引的数量"（诊断值），不是项目总量，通常为 0；命名易误读，后续可考虑改名。
- **`ResearchCritique.citations_json`**（critic 评审）也引用论文，未计入删除预检的五类；如需覆盖可加第六类，本期不动。
- **section 重建后 quote 重校验 / stale 标记**：未实现（低频，不阻塞主线）；重新 ingest 会换 section UUID，下游 quote 可能失配，列为后续项。
- **demo 库内 1 篇 `arxiv_id=None` 的 pending 论文**：早期 seed 残留，来源未核实，不影响检索。
- **规模性能未实测**：检索正确性已在 100 篇真实语料上验证（golden set），但未测几百篇以上规模的延迟；架构上 HNSW 向量索引 + 两条独立 SQL 无已知性能隐患，数据大了以后应补一次延迟实测。
- **ar5iv `\cite` key 泄漏（保留不修，已确认）**：14 篇论文、65 个章节的正文中混有裸引用键（如 `krizhevsky2012imagenet`），原因是 ar5iv 源站对这些论文未解析出参考文献、把 `\cite{key}` 原样输出，非我方解析 bug。经评估**决定保留**：这类 key 是"作者+年份"的可读英文 token，本身携带语义（可被关键词路命中、可顺藤摸瓜找被引论文），不是无意义哈希噪声，剥离的损失大于收益。

---

## 6. 运维规则（给后续维护者）

1. **换 embedding 模型/维度/切分参数** → 在 `profiles.py` 注册新 profile 并切换 `EMBEDDING_PROFILE`；各项目索引会在下次检索/摄入时自动全量重建，无需手工清表。
2. **不要把 hashing 当质量底线**：hashing profile 只为离线可复现，演示/验收必须切 qwen profile。
3. **百炼批次上限 10 条/次、单条 8K token**，adapter 已内建分批与重试
