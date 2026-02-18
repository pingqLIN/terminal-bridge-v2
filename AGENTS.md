# AGENTS.md

> Guidelines for AI agents operating in any repository.  
> 供 AI Agent 操作任何 Repository 的通用指導方針。

This document defines **universal guidelines** for AI agents—covering execution principles,
coding style, multi-model coordination, and error handling patterns.

此文件定義 **AI Agent 的通用指導方針**——涵蓋執行原則、編碼風格、多 Model 協調與錯誤處理模式。

---

## 1. Execution Principles / 執行原則

> **Efficiency and autonomy without sacrificing safety.**  
> **追求效率與自主，但不犧牲安全性。**

| Principle / 原則 | Guideline / 指導方針 |
|------------------|---------------------|
| **Parallel execution** / 並行執行 | Only parallelize when tasks have no dependencies, overlaps, or contradictions; otherwise, optimize sequential execution / 僅在任務間無先後、主從、競合或矛盾時並行，否則應優化序列執行 |
| **Prefer automation** / 偏好自動化 | Execute actions without confirmation unless blocked by missing info or safety concerns / 除非資訊不足或有安全疑慮，否則直接執行 |
| **Avoid unnecessary prompts** / 避免不必要提問 | Make reasonable defaults, ask only when truly ambiguous / 合理假設，僅在真正模糊時才詢問 |

---

## 2. Guiding Philosophy / 最高指導原則

### AI-First for Code & Inline Comments / 程式碼與行內註解以 AI 為優先

All code, inline comments, and technical descriptions should be written **primarily for AI consumption**:

所有程式碼、行內註解與技術說明的撰寫，都以**提供 AI 使用為最高原則**：

| Aspect / 項目 | Guideline / 指導方針 |
|---------------|---------------------|
| **Variable/function names** / 變數與函式命名 | Descriptive, unambiguous names that AI can parse / 描述性、無歧義的命名 |
| **Code comments** / 程式碼註解 | Explain intent and context for AI reasoning / 說明意圖與脈絡，便於 AI 推理 |
| **Type annotations** / 型別標註 | Always include types for AI static analysis / 必須包含型別，供 AI 靜態分析 |
| **Structured data** / 結構化資料 | Use JSON/YAML with clear schemas / 使用 JSON/YAML 並提供清楚的 schema |

### Human-Readable Documentation / 說明文件以人類可讀為優先

**Exception**: User-facing documentation MUST prioritize human readability:

**例外**：面向使用者的說明文件必須以人類可讀性為優先：

| Requirement / 需求 | Description / 說明 |
|--------------------|-------------------|
| **Bilingual (recommended)** / 雙語（建議） | Provide both **Traditional Chinese (zh-TW)** and **English** when appropriate / 視情況提供繁體中文與英文版本 |
| **Detailed explanations** / 詳細說明 | Comprehensive coverage with examples / 完整涵蓋並附範例 |
| **Easy to read** / 容易閱讀 | Logical structure, clear hierarchy, scannable layout / 邏輯結構、清晰層次、可快速瀏覽 |

---

## 3. Code Style Guidelines / 程式碼風格規範

### General Principles / 通用原則

| Principle / 原則 | Description / 說明 |
|------------------|-------------------|
| **Single responsibility** / 單一職責 | Keep things in one function unless composable or reusable / 除非可組合或重用，否則保持單一函式 |
| **Avoid `try`/`catch`** / 避免 try/catch | Where possible, let errors propagate / 盡量讓錯誤向上傳播 |
| **No `any` type** / 不用 any | Avoid untyped variables / 避免無型別變數 |
| **Simple naming** / 簡潔命名 | Prefer single-word variable names when possible / 變數名稱盡量使用單字 |
| **Type inference** / 型別推斷 | Rely on inference; explicit types only when needed for exports or clarity / 依賴推斷，僅在匯出或需清晰時標註 |
| **Functional methods** / 函數式方法 | Prefer `flatMap`, `filter`, `map` over `for` loops / 優先使用函數式陣列方法 |

### Naming Conventions / 命名規範

Prefer single-word names. Only use multiple words if necessary:
優先使用單字命名，僅在必要時使用多字：

```ts
// Good ✅
const foo = 1
function journal(dir: string) {}

// Bad ❌
const fooBar = 1
function prepareJournal(dir: string) {}
```

Reduce total variable count by inlining when a value is only used once:
只使用一次的值應內聯，減少變數數量：

```ts
// Good ✅
const data = await readFile(path.join(dir, "data.json"))

// Bad ❌
const dataPath = path.join(dir, "data.json")
const data = await readFile(dataPath)
```

### Destructuring / 解構

Avoid unnecessary destructuring. Use dot notation to preserve context:
避免不必要的解構，使用點記法保留上下文：

```ts
// Good ✅
obj.a
obj.b

// Bad ❌
const { a, b } = obj
```

### Variables / 變數

Prefer `const` over `let`. Use ternaries or early returns instead of reassignment:
優先使用 `const`，用三元運算或提前返回代替重新賦值：

```ts
// Good ✅
const foo = condition ? 1 : 2

// Bad ❌
let foo
if (condition) foo = 1
else foo = 2
```

### Control Flow / 控制流程

Avoid `else` statements. Prefer early returns:
避免 `else`，優先使用提前返回：

```ts
// Good ✅
function foo() {
  if (condition) return 1
  return 2
}

// Bad ❌
function foo() {
  if (condition) return 1
  else return 2
}
```

---

## 4. Markdown & Documentation Style / Markdown 與文件風格

| Aspect / 項目 | Convention / 慣例 |
|---------------|-------------------|
| **Language / 語言** | Main content in local language, technical terms in English / 主要內容使用當地語言，技術名詞英文 |
| **Headings / 標題** | Use ATX-style (`#`, `##`, `###`), max depth 4 / 使用 ATX 風格，最多 4 層 |
| **Lists / 列表** | Use `-` for unordered, `1.` for ordered / 無序用 `-`，有序用 `1.` |
| **Code blocks / 程式碼區塊** | Always specify language / 必須標註語言 |
| **Tables / 表格** | Align columns with pipes, use header separator / 使用管線符對齊 |
| **Links / 連結** | Prefer relative paths for internal docs / 內部文件優先使用相對路徑 |

### Frontmatter (for Workflows) / 前置資料（工作流程用）

```yaml
---
description: Brief description of the workflow purpose / 工作流程目的簡述
---
```

### JSON Files / JSON 檔案

| Aspect / 項目 | Convention / 慣例 |
|---------------|-------------------|
| **Indentation / 縮排** | 2 or 4 spaces (be consistent) / 2 或 4 空格（保持一致） |
| **Quotes / 引號** | Double quotes only / 僅使用雙引號 |
| **Trailing commas / 結尾逗號** | Not allowed (strict JSON) / 不允許 |

---

## 5. Multi-Agent Coordination / 多 Agent 協調

### Subagent Types / Subagent 類型

| Subagent Type | Purpose / 用途 | Cost / 成本 |
|---------------|----------------|-------------|
| `explore` | Codebase exploration, pattern matching / 程式碼探索、模式比對 | FREE |
| `librarian` | Documentation, OSS examples, external docs / 文件查詢、OSS 範例 | CHEAP |
| `oracle` | Architecture review, deep reasoning / 架構審查、深度推理 | HIGH |
| `frontend-ui-ux-engineer` | UI/UX visual development / UI/UX 視覺開發 | CHEAP |
| `document-writer` | Technical documentation / 技術文件撰寫 | CHEAP |
| `multimodal-looker` | Visual content analysis (PDF, images) / 視覺內容分析 | CHEAP |
| `general` | General multi-step tasks / 通用多步驟任務 | MEDIUM |

### Workflow Source Convention / 工作流程來源規範

**Single Source of Truth / 單一真相來源**：`.agent/workflows/` is the canonical source for all workflow definitions.

| Location / 位置 | Purpose / 用途 |
|-----------------|----------------|
| `.agent/workflows/*.md` | **Canonical source** - edit here / **正式來源** |
| Root `*.md` (workflow docs) | Reference/extended docs / 參考文件 |

---

## 6. Checkpoint & Execution Modes / 檢查點與執行模式

### Checkpoint Syntax / 檢查點語法

```markdown
📍 **CHECKPOINT**: taskAnalysis
├── Verification item 1 / 驗證項目 1
├── Verification item 2 / 驗證項目 2
└── Final verification / 最終驗證

[supervised] Action in supervised mode / 監控模式下的動作
[yolo] Action in YOLO mode / YOLO 模式下的動作
```

### Available Checkpoints / 可用檢查點

- `taskAnalysis` - Task analysis complete / 任務分析完成
- `resourceAllocation` - Resource allocation confirmed / 資源分配確認
- `preExecution` - Pre-execution confirmation / 執行前確認
- `phaseComplete` - Phase complete / 階段完成
- `finalReview` - Final review / 最終審核

### Execution Modes / 執行模式

| Mode / 模式 | Behavior / 行為 |
|-------------|----------------|
| **supervised / 監控模式** | Pause at checkpoints, require user confirmation / 檢查點暫停，需確認 |
| **yolo / YOLO 模式** | Auto-continue, pause only on errors / 自動繼續，僅錯誤時暫停 |

---

## 7. Error Handling Patterns / 錯誤處理模式

| Error Type / 錯誤類型 | Action / 處理方式 |
|-----------------------|-------------------|
| `RATE_LIMIT_EXCEEDED` | Auto retry / 自動重試 |
| `TIMEOUT` | Auto retry / 自動重試 |
| `TEMPORARY_FAILURE` | Auto retry / 自動重試 |
| `AUTHENTICATION_FAILED` | Escalate to user / 升級給使用者 |
| `QUOTA_EXHAUSTED` | Escalate to user / 升級給使用者 |

---

## 8. Testing Guidelines / 測試指導

| Principle / 原則 | Description / 說明 |
|------------------|-------------------|
| **Avoid mocks** / 避免 mock | Test with real implementations when possible / 盡量使用真實實現測試 |
| **No logic duplication** / 不重複邏輯 | Test actual implementation, don't duplicate logic into tests / 測試實際實現，不在測試裡複製邏輯 |
| **Integration over unit** / 整合優於單元 | Prefer integration tests that exercise real paths / 偏好整合測試 |

---

## 9. Important Constraints / 重要限制

### DO ✅ / 應該做

- Use parallel tool execution when tasks are independent / 任務獨立時並行執行
- Keep role/subagent names consistent across documents / 維持角色名稱一致性
- Include type annotations for all exports / 所有匯出都要有型別標註
- Use YAML frontmatter in workflow documents / 工作流程文件使用 YAML 前置資料

### DO NOT ❌ / 不應該做

- Use `any` type / 使用 any 型別
- Create new role names without updating inventory / 未更新 inventory 就建立新角色
- Hard-code model names in workflows (use role aliases) / 在工作流程中硬編碼 Model 名稱
- Remove checkpoint markers from supervised workflows / 移除監控模式的檢查點標記

---

## Quick Reference / 快速參考

| What / 項目 | Location / 位置 |
|-------------|----------------|
| Role definitions / 角色定義 | `resources/inventory.md` (if available) |
| Execution config / 執行設定 | `config.json` (if available) |
| Workflow templates / 工作流程範本 | `.agent/workflows/` |
| UI design rules / UI 設計規則 | `resources/ui-design-guidelines.md` (if available) |

---

> [!NOTE]
> This document is a **merged version** combining the best practices from:
> - opencode/AGENTS.md (TypeScript/execution efficiency focus)
> - global_workflows/AGENTS.md (multi-model coordination focus)
> 
> 此文件為**合併版本**，整合自兩份來源的最佳實踐。
