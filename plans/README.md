# plans 目录

每个子目录代表一个 LeetCode 刷题计划。

推荐结构：

```text
plans/
├── _template/
└── leetcode-75/
    ├── _plan.md
    ├── hash/
    │   └── 0001-two-sum/
    │       ├── metadata.json
    │       ├── solution.py
    │       ├── explanation.md
    │       └── cases.txt
    └── sliding-window/
```

新增题目时优先使用根目录的 `tools/new_problem.py`，让脚本自动创建目录并更新 `data/problems.json`。

