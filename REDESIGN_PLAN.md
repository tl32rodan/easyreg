# RegressionX-CLI Redesign Plan

## 問題本質

團隊無法自信地重構或開發新功能，因為缺乏回歸安全網。
Legacy 程式碼持續累積，因為沒有人敢動「能跑的東西」。

**RegressionX 的定位**：不只是比較工具，而是一個 **regression platform**，
讓 flow owner 能輕鬆搭建成百上千套回歸測試，形成團隊重構的信心來源。

---

## 設計約束

| 約束 | 決定 |
|------|------|
| 依賴 | 零外部依賴，純 Python stdlib |
| Python 版本 | 3.8+ |
| 設定檔格式 | JSON |
| Golden 儲存 | 檔案系統目錄 |
| 比較邏輯 | 可配置過濾規則（忽略時間戳、PID 等） |
| 目標用戶 | 內部 EE 背景團隊 |
| 使用場景 | CI/CD pipeline |
| 版本比較 | A/B 為主，偶爾多版 |

---

## 核心概念重新定義

### 術語表

| 術語 | 定義 |
|------|------|
| **Suite** | 一組回歸測試的集合，由一個 JSON 設定檔定義 |
| **Case** | 一個獨立的測試案例：一個 script + input → output |
| **Golden** | 已驗證的預期輸出，存在檔案系統中作為 reference |
| **Run** | 一次執行，產生實際輸出 |
| **Diff Rule** | 比對時的過濾/轉換規則（忽略時間戳等） |
| **Verdict** | 比對結果：PASS / FAIL / NEW（無 golden）|
| **Promotion** | 將本次 run 的輸出升級為新的 golden |

### 核心工作流

```
                    ┌─────────────┐
                    │  Suite JSON  │  ← flow owner 定義
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   Runner     │  ← 執行每個 case 的 script
                    │  (可擴展:    │     目前: subprocess
                    │   LSF/並行)  │     未來: LSF job dispatch
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Comparator  │  ← 比對 run output vs golden
                    │  + DiffRules │     支援可配置過濾規則
                    └──────┬──────┘
                           │
                ┌──────────┼──────────┐
                ▼          ▼          ▼
             PASS        FAIL       NEW
              │           │          │
              │      ┌────▼────┐     │
              │      │ Report  │     │
              │      │ Details │     │
              │      └─────────┘     │
              │                      │
              └──────────┬───────────┘
                         ▼
                ┌────────────────┐
                │   Promotion    │  ← 可選：將結果升級為新 golden
                │  (手動/自動)    │
                └────────────────┘
```

---

## Suite JSON 設定檔格式

```jsonc
{
  "suite": "my_flow_regression",
  "version": "1",

  // Golden reference 根目錄
  "golden_dir": "/path/to/golden/{case}",

  // 執行輸出根目錄
  "output_dir": "/path/to/runs/{run_id}/{case}",

  // 全域 diff rules（可被 case 覆寫）
  "diff_rules": [
    {"type": "ignore_line", "pattern": "^#.*timestamp.*"},
    {"type": "ignore_line", "pattern": "^# Generated at"},
    {"type": "ignore_regex", "pattern": "PID=\\d+", "replace": "PID=XXX"},
    {"type": "ignore_file", "pattern": "*.log"},
    {"type": "ignore_folder", "pattern": "tmp/"},
    {"type": "ignore_folder", "pattern": "__pycache__/"}
  ],

  // 全域環境變數
  "env": {
    "TOOL_ROOT": "/path/to/tool/{version}"
  },

  // 版本定義（支援多版本）
  "versions": {
    "baseline": {"TOOL_ROOT": "/path/to/tool/v1.0"},
    "candidate": {"TOOL_ROOT": "/path/to/tool/v2.0"}
  },

  // 測試案例
  "cases": [
    {
      "name": "case_a",
      "command": "run_flow.sh {input} {output_dir}",
      "input": "/data/inputs/case_a",
      "timeout": 3600,
      "diff_rules_mode": "append",
      "diff_rules": [
        {"type": "ignore_line", "pattern": "^DEBUG:"}
      ]
    },
    {
      "name": "case_b",
      "command": "run_flow.sh {input} {output_dir}",
      "input": "/data/inputs/case_b"
    }
  ]
}
```

**設計要點：**
- `{case}`, `{run_id}`, `{version}`, `{input}`, `{output_dir}` 為內建 placeholder
- `diff_rules` 支援全域和 per-case
- `diff_rules_mode`：預設 `"append"`（case 規則追加在全域之後），可設為 `"override"`（case 規則完全取代全域規則）
- `versions` 讓同一套 case 跑不同版本，實現 A/B 比較
- 如果只有一個版本，就跟 golden 比對

---

## Diff Rules 設計

```
ignore_line    → 整行匹配 regex 就跳過該行
ignore_regex   → 行內匹配 regex 替換後再比較
ignore_file    → 忽略特定檔名 pattern 的檔案（glob，如 *.log）
ignore_folder  → 忽略特定目錄 pattern（glob，如 tmp/、__pycache__/）
tolerance      → 數值容差（未來擴展）
sort_lines     → 比較前先排序（處理不穩定輸出順序）
```

規則從上到下依序應用，先過濾再比對。

---

## 模組架構

```
regressionx/
├── __init__.py          # 公開 API
├── __main__.py          # python -m regressionx
├── cli.py               # CLI 入口，指令分派
│
├── model.py             # 資料模型：Suite, Case, DiffRule, Verdict, RunResult
├── config.py            # JSON 設定檔載入、驗證、placeholder 展開
│
├── runner/              # 執行引擎（可擴展）
│   ├── __init__.py      # RunnerBase 抽象介面
│   ├── subprocess.py    # 預設：本地 subprocess 執行
│   └── lsf.py           # 未來：LSF job dispatch (stub)
│
├── comparator/          # 比對引擎
│   ├── __init__.py      # 比對入口
│   ├── diff_rules.py    # DiffRule 實作：過濾、轉換
│   ├── directory.py     # 目錄結構比對
│   └── content.py       # 檔案內容比對（套用 diff rules）
│
├── golden.py            # Golden reference 管理：讀取、更新(promotion)、備份
│
└── reporter/            # 報告產生（可擴展）
    ├── __init__.py      # ReporterBase 抽象介面
    ├── markdown.py      # Markdown 報告
    └── json_report.py   # JSON 報告（CI 整合用）
```

**擴展點：**
- `runner/` 目錄：新增 runner 只需實作 `RunnerBase` 介面
- `reporter/` 目錄：新增報告格式只需實作 `ReporterBase`
- `comparator/diff_rules.py`：新增 diff rule type 只需加一個 class

---

## CLI 指令設計

```bash
# 核心流程
regressionx run    --config suite.json                  # 執行所有 case，比對 golden
regressionx run    --config suite.json --case case_a    # 只執行指定 case
regressionx run    --config suite.json --version candidate  # 只跑特定版本

# 比對（不執行）
regressionx compare --config suite.json                 # 用已有 output 比對 golden
regressionx compare --left /path/a --right /path/b      # 直接比對兩個目錄

# Golden 管理
regressionx promote --config suite.json                 # 將最新 run 結果升級為 golden
regressionx promote --config suite.json --case case_a   # 只升級指定 case
regressionx golden  --config suite.json --status        # 查看 golden 狀態

# 報告
regressionx report  --config suite.json --format md     # 產生報告
regressionx report  --config suite.json --format json   # JSON 格式（CI 用）
```

---

## 實作階段

### Phase 1：核心骨架（本次實作）
1. **model.py** — 定義所有資料模型（dataclass）
2. **config.py** — JSON 載入 + placeholder 展開 + 驗證
3. **comparator/** — 目錄比對 + diff rules 引擎
4. **golden.py** — Golden reference 讀取 + promotion
5. **runner/subprocess.py** — 本地 subprocess 執行
6. **reporter/markdown.py** — Markdown 報告
7. **cli.py** — `run`, `compare`, `promote` 指令

### Phase 2：完善體驗（後續）
- JSON 報告輸出（CI 整合）
- `--parallel N` 本地多進程並行
- diff rule: `tolerance`（數值容差）
- diff rule: `sort_lines`（不穩定順序）
- Golden 備份與版本歷史

### Phase 3：分散式（未來）
- LSF runner 整合
- 分散式 job 狀態追蹤
- Web dashboard（可選）

---

## 與現有程式碼的關係

| 現有模組 | 處理方式 |
|---------|---------|
| `domain.py` (Case) | → 重寫為 `model.py`，擴展資料模型 |
| `factory.py` (Template) | → 移除，由 JSON config 的 cases 陣列取代 |
| `config.py` (load_config) | → 重寫，改為 JSON 載入 + placeholder 展開 |
| `executor.py` (run_case) | → 重構為 `runner/subprocess.py`，支援可擴展 |
| `comparator.py` | → 拆分為 `comparator/` 子套件，加入 diff rules |
| `reporter.py` | → 重構為 `reporter/` 子套件，支援多格式 |
| `cli.py` | → 重寫，新增 promote/golden 指令 |

現有的測試和範例將全部重寫以對應新架構。
