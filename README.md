# LeetCode 刷题档案

这个文件夹用于按“刷题计划 -> 题目类别 -> 单题档案”管理 LeetCode 题解。你的需求可以梳理为：

1. 每个 LeetCode 刷题计划独立成一个文件夹。
2. 每个计划下面按题目类别继续分文件夹，例如哈希、双指针、滑动窗口、子串、矩阵等。
3. 每道题单独建一个题目文件夹，放题解代码、简短解析和元数据。
4. 每道题必须记录 LeetCode 编号、标题、难度、实际标签、所属计划、主分类和本地路径。
5. 根目录提供本地查询工具，可以按编号、标签、类别、计划或关键词查找，并可打开对应题目文件夹。

## 当前结构

```text
.
├── README.md
├── data/
│   ├── categories.json
│   ├── plans.json
│   └── problems.json
├── plans/
│   ├── README.md
│   └── _template/
│       ├── _plan.md
│       ├── array/
│       ├── hash/
│       ├── two-pointers/
│       ├── sliding-window/
│       ├── substring/
│       ├── matrix/
│       └── ...
├── templates/
│   ├── explanation.md
│   ├── metadata.json
│   └── solution.py
└── tools/
    ├── new_problem.py
    └── search.py
```

## 命名规则

- 计划目录：`plans/<plan-slug>/`，例如 `plans/leetcode-75/`、`plans/top-interview-150/`。
- 类别目录：统一使用英文 slug，例如 `hash`、`two-pointers`、`sliding-window`。
- 题目目录：`<4位编号>-<英文题名slug>`，例如 `0001-two-sum`、`0049-group-anagrams`。
- 单题文件：
  - `metadata.json`：本题本地元数据。
  - `solution.py`：默认 Python 题解代码，也可以通过脚本指定其他语言。
  - `explanation.md`：简短题解文本。
  - `cases.txt`：可选，用于记录样例、边界用例或手动测试。

## 新增题目

优先使用脚本创建题目，避免漏改索引：

```powershell
python tools/new_problem.py --id 1 --title "Two Sum" --plan leetcode-75 --category hash --difficulty Easy --tags "Array,Hash Table"
```

常用参数：

```powershell
python tools/new_problem.py --id 49 --title "Group Anagrams" --plan top-interview-150 --category hash --difficulty Medium --tags "Array,Hash Table,String,Sorting" --url "https://leetcode.com/problems/group-anagrams/"
```

脚本会自动：

- 创建计划目录和类别目录。
- 创建单题目录。
- 生成 `metadata.json`、`solution.py`、`explanation.md`、`cases.txt`。
- 更新 `data/problems.json` 和 `data/plans.json`。

## 查询题目

按编号查：

```powershell
python tools/search.py --id 1
```

按 LeetCode 标签查：

```powershell
python tools/search.py --tag "Hash Table"
```

按本地类别查：

```powershell
python tools/search.py --category hash
python tools/search.py --category 哈希
```

按计划查：

```powershell
python tools/search.py --plan leetcode-75
```

按关键词查：

```powershell
python tools/search.py --query anagram
```

打开匹配到的第一个题目文件夹：

```powershell
python tools/search.py --category sliding-window --open
```

查看已定义类别：

```powershell
python tools/search.py --list-categories
```

## 图形化界面

如果不想每次输入命令，可以启动本地 GUI：

```powershell
python tools/gui.py
```

在 Windows 上也可以双击：

```text
tools/launch_gui.bat
```

GUI 支持：

- 按编号、关键词、计划、类别、标签查询题目。
- 新增或更新题目档案。
- 查看每道题在本地的计划/类别记录。
- 打开题目文件夹、题解代码、解析文本。
- 复制题目文件夹路径。
- 同步本地档案到 GitHub 仓库。

## 同步到 GitHub

本项目提供命令行和 GUI 两种同步方式。同步功能依赖本机已安装并登录的 GitHub CLI `gh`。

命令行同步到一个 public 仓库：

```powershell
python tools/github_sync.py --repo leetcode-practice --public
```

常用参数：

```powershell
python tools/github_sync.py --repo MuzeAnisichael/leetcode-practice --public --branch main --message "Update LeetCode archive"
```

脚本会自动：

- 初始化本地 Git 仓库。
- 提交当前变更。
- 如果远端仓库不存在，则创建 public GitHub 仓库。
- 设置 `origin` 远端。
- 推送到指定分支。
- 在 `data/github.json` 中记录最近一次同步配置。

## 后续对话中的协作规则

在任何基于本文件夹的后续对话中，写题解或整理题目时按以下规则执行：

1. 先读取本 README 和 `data/problems.json`，确认是否已有同编号题目。
2. 新题必须放在 `plans/<plan-slug>/<category-slug>/<0000-title-slug>/`。
3. 本地类别使用 `data/categories.json` 中的 slug；如果没有合适类别，先放入 `other`，必要时再扩展类别表。
4. 题目的 LeetCode 实际标签写入 `metadata.json` 和 `data/problems.json` 的 `tags` 字段。
5. 题解文本写入 `explanation.md`，至少包括：题目信息、核心思路、算法步骤、复杂度、易错点。
6. 代码文件保持可直接复制到 LeetCode；不要把解释性长文本写进代码。
7. 修改或新增题目后，必须同步更新全局索引 `data/problems.json`。
8. 如果题号、标题、标签或官方链接不确定，先让用户提供，或在用户允许联网时再核对。

## 数据字段约定

`data/problems.json` 是全局题目索引，结构为列表，每个元素表示一道题：

```json
{
  "id": 1,
  "title": "Two Sum",
  "slug": "two-sum",
  "difficulty": "Easy",
  "url": "https://leetcode.com/problems/two-sum/",
  "plans": ["leetcode-75"],
  "categories": ["hash"],
  "tags": ["Array", "Hash Table"],
  "records": [
    {
      "plan": "leetcode-75",
      "category": "hash",
      "folder": "plans/leetcode-75/hash/0001-two-sum",
      "solution": "solution.py",
      "explanation": "explanation.md",
      "status": "draft"
    }
  ],
  "notes": ""
}
```

`records` 用于记录同一道题在不同计划、不同分类下的本地位置。
