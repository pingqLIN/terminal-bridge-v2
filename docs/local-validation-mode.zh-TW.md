# 暫時採用本地驗收

GitHub Actions 無法執行期間，TB2 經明確授權，暫時不以 hosted CI 作為開發交付前提，
改採本地驗收與 PR 審核。**這不是修復 GitHub 帳戶 billing，也不是將未跑檢查標成綠燈。**

## Repository 設定

2026-09-24 已套用下列伺服器端設定：

- 將 `CI`、`CodeQL` workflow 設為 `disabled_manually`；保留 YAML 原檔以便回復。
- 解除 `main` 的三項 required status checks：`test (ubuntu-latest, 3.11)`、
  `test (windows-latest, 3.11)`、`analyze`，原本均綁定 GitHub Actions app `15368`。
- 保留一位 PR reviewer、舊審核失效、對話解決、禁止 force-push 與禁止刪除分支等保護。
  原有管理員 enforcement 設定不變；這項調整不授權略過 PR 審核。

其他 workflow、Dependabot／安全設定、repository-wide Actions 權限均不變。
獨立自動化仍可能遇到 billing 問題，但不屬於本次解除的三項必要檢查。
歷史失敗紀錄保留不動，不建立同名 commit status 假冒 Actions 結果。

workflow 停用是 repository 設定，不是 YAML 變更，也不會自動套用到 fork。

## 正常 PR 合併前的本地驗收

使用已安裝開發依賴及平台 extras 的專案虛擬環境，在 repository 根目錄執行：

```bash
python tools/release_check.py --pytest-args -q -m "not e2e" -p no:cacheprovider -o addopts=""
```

此工具檢查 diff、doctor JSON、client profile metadata 及測試。
若範圍僅為文件，也可以記錄以下完整非 E2E suite：

```bash
git diff --check
python -m pytest -q -m "not e2e" -p no:cacheprovider -o addopts=""
```

PR 摘要須列出受測 commit／tree、平台、指令、真正 exit code 與測試數量。
原始 evidence 留在私有位置，僅分享去敏感化摘要；reviewer 須確認證據對應送審 tree。
不得因 hosted CI 不可用就使用管理員 bypass 合併。

Native Windows 測試不代表 hosted Linux 測試；pytest 也不能取代 CodeQL 安全分析、
真實 provider 協作或 tmux E2E。未執行項目須明列，不能宣稱本地驗收與 CI 等價。

## 回復 hosted CI

帳戶擁有者處理 billing 後，由 maintainer 啟用原 workflow 並還原備份的 required checks。
保留私有 API 設定快照；只還原 status-check 欄位，避免覆蓋其他後續保護設定。

```bash
gh api --method PUT repos/pingqLIN/terminal-bridge-v2/actions/workflows/244512559/enable
gh api --method PUT repos/pingqLIN/terminal-bridge-v2/actions/workflows/244512560/enable
gh api --method PATCH repos/pingqLIN/terminal-bridge-v2/branches/main/protection/required_status_checks --input restore-required-status-checks.json
```

restore payload 應包含 `strict: true`，以及原先三項帶有 `app_id: 15368` 的 `checks`。
回讀 workflow 與完整 branch protection，確認其餘欄位未變；取得精確候選 commit 的
hosted checks 成功結果後，才能宣稱 CI 恢復，再透過正常審核移除此暫時政策。

API 說明：[workflow 停用／啟用](https://docs.github.com/en/rest/actions/workflows)、
[status-check protection](https://docs.github.com/en/rest/branches/branch-protection)。
