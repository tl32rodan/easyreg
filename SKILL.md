# RegressionX MCP Skill Guide

> **目標讀者**: AI Agent (尤其是 qwen3-235B 等較舊模型)
> 本文件描述如何正確使用 RegressionX MCP server 提供的 tools。

---

## 什麼是 RegressionX？

RegressionX 是一個 **regression testing platform**，用來：
1. 執行測試案例 (case) 的 command
2. 將執行結果與 golden reference 比對
3. 報告 PASS / FAIL / NEW / ERROR
4. 管理 golden reference 的升級 (promote)

---

## MCP Server 啟動方式

```json
{
  "mcpServers": {
    "regressionx": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "<RegressionX-CLI 根目錄的絕對路徑>"
    }
  }
}
```

---

## 可用 Tools 一覽

| Tool 名稱 | 用途 | 必填參數 | 選填參數 |
|---|---|---|---|
| `regressionx_show_config` | 查看 suite 設定內容 | `config_path` | — |
| `regressionx_run` | 執行 cases 並比對 golden | `config_path` | `case_name`, `parallel` |
| `regressionx_compare` | 只比對（不重新執行） | `config_path` | `case_name` |
| `regressionx_promote` | 把 output 升級為 golden | `config_path` | `case_name` |
| `regressionx_golden_status` | 檢查 golden 是否存在 | `config_path` | — |

---

## ⚠️ 重要：使用順序與判斷時機

### 標準流程（請嚴格按此順序）

```
步驟 1: regressionx_show_config   ← 先看設定，確認 config_path 正確
步驟 2: regressionx_golden_status ← 確認 golden 是否已建立
步驟 3: regressionx_run           ← 執行測試
步驟 4: (如果 verdict=NEW) regressionx_promote ← 首次建立 golden
```

### 什麼時候用哪個 tool？

| 情境 | 應該用的 tool | 不要用的 tool |
|---|---|---|
| 「我想跑回歸測試」 | `regressionx_run` | ~~regressionx_compare~~ |
| 「已經跑過了，只想重新比對」 | `regressionx_compare` | ~~regressionx_run~~ |
| 「測試結果是 NEW，要建立 golden」 | `regressionx_promote` | — |
| 「不確定 config 裡有什麼」 | `regressionx_show_config` | — |
| 「golden 有沒有準備好？」 | `regressionx_golden_status` | — |

---

## ⚠️ 參數填寫提示（防止常見錯誤）

### config_path

- **必須是字串**，指向一個 `.json` 檔案
- 可以是相對路徑或絕對路徑
- **正確範例**: `"examples/simple_suite.json"`
- **錯誤範例**: `examples/simple_suite`（缺少 .json）、`null`、`{}`

```json
// ✅ 正確
{"config_path": "examples/simple_suite.json"}

// ❌ 錯誤 — 不要漏掉 .json 副檔名
{"config_path": "examples/simple_suite"}

// ❌ 錯誤 — 不要傳空物件或 null
{"config_path": null}
```

### case_name

- **選填**，省略表示跑「全部 cases」
- 必須**完全匹配** suite config 中某個 case 的 `name` 欄位
- **先用 `regressionx_show_config` 查看有哪些 case name**，再填入
- **正確範例**: `"hello"`、`"case_a"`
- **錯誤範例**: `"Hello"`（大小寫不對）、`"all"`（不存在的 name）

```json
// ✅ 正確 — 只跑名為 "hello" 的 case
{"config_path": "examples/simple_suite.json", "case_name": "hello"}

// ✅ 正確 — 跑所有 case（不傳 case_name）
{"config_path": "examples/simple_suite.json"}

// ❌ 錯誤 — 不要傳 "*" 或 "all"，直接省略即可
{"config_path": "examples/simple_suite.json", "case_name": "*"}
```

### parallel

- **選填**，僅用於 `regressionx_run`
- 必須是**正整數**，預設為 `1`
- 不要傳 `0` 或負數

```json
// ✅ 正確
{"config_path": "examples/simple_suite.json", "parallel": 4}

// ❌ 錯誤 — 不要傳字串
{"config_path": "examples/simple_suite.json", "parallel": "4"}
```

---

## Verdict 含義

| Verdict | 意思 | 下一步行動 |
|---|---|---|
| `PASS` | 輸出與 golden 完全一致 | 無需動作 |
| `FAIL` | 輸出與 golden 不一致 | 檢查 diffs 欄位，分析差異原因 |
| `NEW` | 沒有 golden reference | 確認輸出正確後呼叫 `regressionx_promote` |
| `ERROR` | 執行 command 失敗 | 檢查 errors 欄位，修正 command 或環境 |

---

## 回傳值結構

### regressionx_run / regressionx_compare

```json
{
  "suite": "suite 名稱",
  "summary": {"PASS": 1, "FAIL": 0, "NEW": 0, "ERROR": 0},
  "results": [
    {
      "case_name": "hello",
      "verdict": "PASS",
      "diffs": [],
      "errors": []
    }
  ]
}
```

- `diffs`: 列出不一致的檔案路徑（verdict=FAIL 時才有內容）
- `errors`: 列出錯誤訊息（verdict=ERROR 時才有內容）

### regressionx_promote

```json
{"promoted": ["hello", "case_a"]}
```

### regressionx_golden_status

```json
{"golden_root": "examples/golden", "cases": {"hello": true}}
```

### regressionx_show_config

回傳完整的 suite 結構化資料，包含所有 cases、diff_rules、env 等。

---

## 常見錯誤與排除

| 錯誤訊息 | 原因 | 解法 |
|---|---|---|
| `Config file not found: xxx` | config_path 路徑不存在 | 確認檔案路徑正確，注意相對路徑的起始目錄 |
| `No case named 'xxx' found` | case_name 拼錯或不存在 | 先用 `regressionx_show_config` 查看正確的 case name |
| `Source directory does not exist` | promote 時 output 目錄不存在 | 先執行 `regressionx_run` 產生 output |
| `Config missing required field` | JSON 設定檔缺少必要欄位 | 確認 JSON 包含 suite, golden_dir, output_dir, cases |

---

## Suite JSON Config 格式速查

一個最小可用的 suite config：

```json
{
  "suite": "my_test",
  "golden_dir": "golden/{case}",
  "output_dir": "runs/{case}",
  "cases": [
    {
      "name": "example",
      "command": "echo hello > output.txt"
    }
  ]
}
```

### Diff Rules 類型

| type | 用途 | pattern 範例 | replace |
|---|---|---|---|
| `ignore_line` | 整行匹配 regex 就跳過 | `"^#.*timestamp"` | 不需要 |
| `ignore_regex` | 行內替換後再比較 | `"PID=\\d+"` | `"PID=XXX"` |
| `ignore_file` | 忽略特定檔案 (glob) | `"*.log"` | 不需要 |
| `ignore_folder` | 忽略特定目錄 (glob) | `"tmp/"` | 不需要 |
| `sort_lines` | 比較前先排序 | `".*"` (任意) | 不需要 |
| `tolerance` | 數值容差比較 | `".*"` (任意) | `"0.001"` (容差值) |

---

## 完整使用範例

### 範例 1：首次建立 golden

```
Agent 思考: 使用者要我對 examples/simple_suite.json 建立回歸測試

1. 呼叫 regressionx_show_config(config_path="examples/simple_suite.json")
   → 確認有 1 個 case: "hello"

2. 呼叫 regressionx_golden_status(config_path="examples/simple_suite.json")
   → golden 不存在

3. 呼叫 regressionx_run(config_path="examples/simple_suite.json")
   → verdict: NEW（沒有 golden 可比對）

4. 確認 output 正確後，呼叫 regressionx_promote(config_path="examples/simple_suite.json")
   → promoted: ["hello"]

5. 再次呼叫 regressionx_run(config_path="examples/simple_suite.json")
   → verdict: PASS（現在有 golden 了）
```

### 範例 2：日常回歸測試

```
Agent 思考: 使用者修改了程式碼，要驗證有沒有 regression

1. 呼叫 regressionx_run(config_path="examples/simple_suite.json")
   → 檢查 summary：如果全部 PASS，回報「無 regression」
   → 如果有 FAIL，查看 diffs 欄位，告知使用者哪些檔案不一致
```
