# 專案結構

依用途找檔案；程式套件與既有公開文件路徑維持穩定。

```text
terminal-bridge-v2/
├── README.md / README.zh-TW.md
├── tb2/                 # Python runtime and CLI
├── tests/               # Regression and integration tests
├── schemas/             # Machine-readable contracts
├── examples/            # Example configurations and fixtures
├── tools/               # Diagnostics and development utilities
├── deploy/              # Deployment templates
├── docs/
│   ├── README.md / README.zh-TW.md
│   ├── getting-started*.md
│   ├── role-guides*.md
│   ├── validation-status*.md
│   ├── platforms/
│   └── images/
│       └── kindergarten/
└── .github/             # CI and community templates
```

## 維護原則

- 使用者指南放在 docs，從文件入口連結；英文與繁體中文同步。
- 平台細節集中 platforms，圖片集中 images 的系列子目錄。
- schema 與可重用範例保留各自根目錄，避免文件搬遷改變程式載入路徑。
- 已有外部引用的文件先更新內容與導航，不直接更名。
- 本機測試證據、備份、內部規劃與原始提示詞存於 Git 忽略範圍；不得用 git add . 一次納入。
- 公開 push 前按明確檔案清單檢查 diff、連結、敏感內容與測試。已被 Git 追蹤的檔案不會因新增 ignore 規則而自動排除。

[返回文件入口](README.zh-TW.md)
