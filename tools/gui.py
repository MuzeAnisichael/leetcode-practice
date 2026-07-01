"""Tkinter GUI for the local LeetCode archive."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.dont_write_bytecode = True

import tkinter as tk
from tkinter import messagebox, ttk

import github_sync
import new_problem
import search as search_tools


ROOT = new_problem.ROOT


def load_json(path: Path, default: Any) -> Any:
    return new_problem.load_json(path, default)


def shorten(value: Any, limit: int = 80) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def category_option(item: dict[str, Any]) -> str:
    label = item.get("label", "")
    slug = item.get("slug", "")
    return f"{slug} - {label}" if label else slug


def option_slug(value: str) -> str:
    value = value.strip()
    if not value or value == "全部":
        return ""
    return value.split(" - ", 1)[0].strip()


def open_path(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if hasattr(os, "startfile"):
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        webbrowser.open(path.resolve().as_uri())


class LeetCodeArchiveApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("LeetCode 刷题档案管理")
        self.geometry("1180x760")
        self.minsize(980, 640)

        self.categories: list[dict[str, Any]] = []
        self.plans: list[dict[str, Any]] = []
        self.problems: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []
        self.selected_problem: dict[str, Any] | None = None

        self._build_vars()
        self._build_widgets()
        self.reload_data(run_search=False)
        self.run_search()

    def _build_vars(self) -> None:
        self.filter_id_var = tk.StringVar()
        self.filter_query_var = tk.StringVar()
        self.filter_plan_var = tk.StringVar(value="全部")
        self.filter_category_var = tk.StringVar(value="全部")
        self.filter_tag_var = tk.StringVar()

        self.form_id_var = tk.StringVar()
        self.form_title_var = tk.StringVar()
        self.form_plan_var = tk.StringVar()
        self.form_category_var = tk.StringVar()
        self.form_difficulty_var = tk.StringVar()
        self.form_tags_var = tk.StringVar()
        self.form_url_var = tk.StringVar()
        self.form_language_var = tk.StringVar(value="python")
        self.form_status_var = tk.StringVar(value="draft")

        self.github_repo_var = tk.StringVar(value=github_sync.default_repo_name())
        self.github_branch_var = tk.StringVar(value="main")
        self.github_message_var = tk.StringVar(value="Sync LeetCode archive")
        self.github_public_var = tk.BooleanVar(value=True)

        self.status_var = tk.StringVar(value="就绪")

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        search_frame = ttk.LabelFrame(self, text="查询")
        search_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        search_frame.columnconfigure(3, weight=1)

        ttk.Label(search_frame, text="编号").grid(row=0, column=0, sticky="w", padx=(8, 4), pady=8)
        ttk.Entry(search_frame, width=10, textvariable=self.filter_id_var).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=8)

        ttk.Label(search_frame, text="关键词").grid(row=0, column=2, sticky="w", padx=(0, 4), pady=8)
        query_entry = ttk.Entry(search_frame, textvariable=self.filter_query_var)
        query_entry.grid(row=0, column=3, sticky="ew", padx=(0, 12), pady=8)
        query_entry.bind("<Return>", lambda _event: self.run_search())

        ttk.Label(search_frame, text="计划").grid(row=0, column=4, sticky="w", padx=(0, 4), pady=8)
        self.filter_plan_combo = ttk.Combobox(search_frame, width=20, textvariable=self.filter_plan_var)
        self.filter_plan_combo.grid(row=0, column=5, sticky="w", padx=(0, 12), pady=8)

        ttk.Label(search_frame, text="类别").grid(row=0, column=6, sticky="w", padx=(0, 4), pady=8)
        self.filter_category_combo = ttk.Combobox(search_frame, width=22, textvariable=self.filter_category_var, state="readonly")
        self.filter_category_combo.grid(row=0, column=7, sticky="w", padx=(0, 12), pady=8)

        ttk.Label(search_frame, text="标签").grid(row=1, column=0, sticky="w", padx=(8, 4), pady=(0, 8))
        tag_entry = ttk.Entry(search_frame, textvariable=self.filter_tag_var)
        tag_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(0, 12), pady=(0, 8))
        tag_entry.bind("<Return>", lambda _event: self.run_search())

        ttk.Button(search_frame, text="搜索", command=self.run_search).grid(row=1, column=5, sticky="ew", padx=(0, 8), pady=(0, 8))
        ttk.Button(search_frame, text="重置", command=self.reset_filters).grid(row=1, column=6, sticky="ew", padx=(0, 8), pady=(0, 8))
        ttk.Button(search_frame, text="刷新", command=self.reload_data).grid(row=1, column=7, sticky="ew", padx=(0, 12), pady=(0, 8))

        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)

        results_frame = ttk.Frame(main_pane)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        main_pane.add(results_frame, weight=3)

        columns = ("id", "title", "difficulty", "plans", "categories", "tags")
        self.problem_tree = ttk.Treeview(results_frame, columns=columns, show="headings", selectmode="browse")
        self.problem_tree.heading("id", text="编号")
        self.problem_tree.heading("title", text="标题")
        self.problem_tree.heading("difficulty", text="难度")
        self.problem_tree.heading("plans", text="计划")
        self.problem_tree.heading("categories", text="类别")
        self.problem_tree.heading("tags", text="标签")
        self.problem_tree.column("id", width=64, anchor="center", stretch=False)
        self.problem_tree.column("title", width=180)
        self.problem_tree.column("difficulty", width=70, anchor="center", stretch=False)
        self.problem_tree.column("plans", width=150)
        self.problem_tree.column("categories", width=120)
        self.problem_tree.column("tags", width=260)
        self.problem_tree.grid(row=0, column=0, sticky="nsew")
        self.problem_tree.bind("<<TreeviewSelect>>", self.on_problem_select)
        self.problem_tree.bind("<Double-1>", lambda _event: self.open_selected_folder())

        results_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.problem_tree.yview)
        self.problem_tree.configure(yscrollcommand=results_scroll.set)
        results_scroll.grid(row=0, column=1, sticky="ns")

        detail_frame = ttk.Frame(main_pane)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(2, weight=1)
        main_pane.add(detail_frame, weight=2)

        self.detail_title = ttk.Label(detail_frame, text="未选择题目", font=("", 13, "bold"), wraplength=420)
        self.detail_title.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.detail_text = tk.Text(detail_frame, height=9, wrap="word", state="disabled")
        self.detail_text.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        record_frame = ttk.LabelFrame(detail_frame, text="本地记录")
        record_frame.columnconfigure(0, weight=1)
        record_frame.rowconfigure(0, weight=1)
        record_frame.grid(row=2, column=0, sticky="nsew")

        record_columns = ("plan", "category", "status", "folder")
        self.record_tree = ttk.Treeview(record_frame, columns=record_columns, show="headings", height=8, selectmode="browse")
        self.record_tree.heading("plan", text="计划")
        self.record_tree.heading("category", text="类别")
        self.record_tree.heading("status", text="状态")
        self.record_tree.heading("folder", text="路径")
        self.record_tree.column("plan", width=120)
        self.record_tree.column("category", width=120)
        self.record_tree.column("status", width=70, anchor="center")
        self.record_tree.column("folder", width=260)
        self.record_tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        self.record_tree.bind("<Double-1>", lambda _event: self.open_selected_folder())

        record_scroll = ttk.Scrollbar(record_frame, orient=tk.VERTICAL, command=self.record_tree.yview)
        self.record_tree.configure(yscrollcommand=record_scroll.set)
        record_scroll.grid(row=0, column=1, sticky="ns", pady=8)

        button_frame = ttk.Frame(detail_frame)
        button_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        for col in range(4):
            button_frame.columnconfigure(col, weight=1)
        ttk.Button(button_frame, text="打开文件夹", command=self.open_selected_folder).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(button_frame, text="打开代码", command=lambda: self.open_selected_file("solution")).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(button_frame, text="打开解析", command=lambda: self.open_selected_file("explanation")).grid(row=0, column=2, sticky="ew", padx=6)
        ttk.Button(button_frame, text="复制路径", command=self.copy_selected_folder).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        form_frame = ttk.LabelFrame(self, text="新增或更新题目")
        form_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(6, 10))
        for col in (1, 3, 5, 7):
            form_frame.columnconfigure(col, weight=1)

        ttk.Label(form_frame, text="编号").grid(row=0, column=0, sticky="w", padx=(8, 4), pady=8)
        ttk.Entry(form_frame, width=10, textvariable=self.form_id_var).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=8)

        ttk.Label(form_frame, text="标题").grid(row=0, column=2, sticky="w", padx=(0, 4), pady=8)
        ttk.Entry(form_frame, textvariable=self.form_title_var).grid(row=0, column=3, sticky="ew", padx=(0, 10), pady=8)

        ttk.Label(form_frame, text="计划").grid(row=0, column=4, sticky="w", padx=(0, 4), pady=8)
        self.form_plan_combo = ttk.Combobox(form_frame, textvariable=self.form_plan_var)
        self.form_plan_combo.grid(row=0, column=5, sticky="ew", padx=(0, 10), pady=8)

        ttk.Label(form_frame, text="类别").grid(row=0, column=6, sticky="w", padx=(0, 4), pady=8)
        self.form_category_combo = ttk.Combobox(form_frame, textvariable=self.form_category_var, state="readonly")
        self.form_category_combo.grid(row=0, column=7, sticky="ew", padx=(0, 10), pady=8)

        ttk.Label(form_frame, text="难度").grid(row=1, column=0, sticky="w", padx=(8, 4), pady=(0, 8))
        ttk.Combobox(
            form_frame,
            width=10,
            textvariable=self.form_difficulty_var,
            values=("", "Easy", "Medium", "Hard"),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 8))

        ttk.Label(form_frame, text="标签").grid(row=1, column=2, sticky="w", padx=(0, 4), pady=(0, 8))
        ttk.Entry(form_frame, textvariable=self.form_tags_var).grid(row=1, column=3, sticky="ew", padx=(0, 10), pady=(0, 8))

        ttk.Label(form_frame, text="链接").grid(row=1, column=4, sticky="w", padx=(0, 4), pady=(0, 8))
        ttk.Entry(form_frame, textvariable=self.form_url_var).grid(row=1, column=5, sticky="ew", padx=(0, 10), pady=(0, 8))

        ttk.Label(form_frame, text="语言").grid(row=1, column=6, sticky="w", padx=(0, 4), pady=(0, 8))
        ttk.Combobox(
            form_frame,
            textvariable=self.form_language_var,
            values=("python", "cpp", "java", "javascript", "typescript", "go", "rust"),
        ).grid(row=1, column=7, sticky="ew", padx=(0, 10), pady=(0, 8))

        ttk.Label(form_frame, text="状态").grid(row=2, column=0, sticky="w", padx=(8, 4), pady=(0, 8))
        ttk.Combobox(
            form_frame,
            width=12,
            textvariable=self.form_status_var,
            values=("draft", "solved", "reviewing", "done"),
        ).grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=(0, 8))

        action_frame = ttk.Frame(form_frame)
        action_frame.grid(row=2, column=3, columnspan=5, sticky="e", padx=(0, 10), pady=(0, 8))
        ttk.Button(action_frame, text="创建/更新", command=self.create_or_update_problem).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(action_frame, text="用选中题目填充", command=self.fill_form_from_selection).grid(row=0, column=1, padx=8)
        ttk.Button(action_frame, text="清空表单", command=self.clear_form).grid(row=0, column=2, padx=(8, 0))

        github_frame = ttk.LabelFrame(self, text="GitHub 同步")
        github_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 8))
        github_frame.columnconfigure(1, weight=1)
        github_frame.columnconfigure(3, weight=1)
        github_frame.columnconfigure(5, weight=1)

        ttk.Label(github_frame, text="仓库").grid(row=0, column=0, sticky="w", padx=(8, 4), pady=8)
        ttk.Entry(github_frame, textvariable=self.github_repo_var).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=8)

        ttk.Label(github_frame, text="分支").grid(row=0, column=2, sticky="w", padx=(0, 4), pady=8)
        ttk.Entry(github_frame, width=12, textvariable=self.github_branch_var).grid(row=0, column=3, sticky="ew", padx=(0, 10), pady=8)

        ttk.Label(github_frame, text="提交信息").grid(row=0, column=4, sticky="w", padx=(0, 4), pady=8)
        ttk.Entry(github_frame, textvariable=self.github_message_var).grid(row=0, column=5, sticky="ew", padx=(0, 10), pady=8)

        ttk.Checkbutton(github_frame, text="Public", variable=self.github_public_var).grid(row=0, column=6, sticky="w", padx=(0, 10), pady=8)
        self.github_sync_button = ttk.Button(github_frame, text="同步到 GitHub", command=self.sync_to_github)
        self.github_sync_button.grid(row=0, column=7, sticky="ew", padx=(0, 10), pady=8)

        status_label = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status_label.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 8))

    def reload_data(self, run_search: bool = True) -> None:
        self.categories = load_json(new_problem.CATEGORIES_PATH, [])
        self.plans = load_json(new_problem.PLANS_PATH, [])
        self.problems = load_json(new_problem.PROBLEMS_PATH, [])
        self._load_github_config()
        self._refresh_combo_values()
        self.status_var.set(f"已加载 {len(self.problems)} 道题")
        if run_search:
            self.run_search()

    def _load_github_config(self) -> None:
        config = load_json(github_sync.GITHUB_CONFIG_PATH, {})
        if config.get("repo"):
            self.github_repo_var.set(config["repo"])
        if config.get("branch"):
            self.github_branch_var.set(config["branch"])
        if config.get("visibility"):
            self.github_public_var.set(config["visibility"] != "private")

    def _refresh_combo_values(self) -> None:
        plan_values = ["全部", *self._plan_slugs()]
        category_values = ["全部", *[category_option(item) for item in self.categories]]
        form_category_values = [category_option(item) for item in self.categories]

        self.filter_plan_combo.configure(values=plan_values)
        self.filter_category_combo.configure(values=category_values)
        self.form_plan_combo.configure(values=self._plan_slugs())
        self.form_category_combo.configure(values=form_category_values)

        if self.filter_plan_var.get() not in plan_values:
            self.filter_plan_var.set("全部")
        if self.filter_category_var.get() not in category_values:
            self.filter_category_var.set("全部")
        if not self.form_category_var.get() and form_category_values:
            self.form_category_var.set(form_category_values[0])

    def _plan_slugs(self) -> list[str]:
        slugs = {item.get("slug", "") for item in self.plans if item.get("slug") and item.get("slug") != "_template"}
        plans_dir = ROOT / "plans"
        if plans_dir.exists():
            for child in plans_dir.iterdir():
                if child.is_dir() and child.name != "_template":
                    slugs.add(child.name)
        return sorted(slugs)

    def run_search(self) -> None:
        problem_id: int | None = None
        raw_id = self.filter_id_var.get().strip()
        if raw_id:
            try:
                problem_id = int(raw_id)
            except ValueError:
                messagebox.showerror("编号格式错误", "编号必须是整数。")
                return

        tags = new_problem.parse_csv(self.filter_tag_var.get())
        args = SimpleNamespace(
            id=problem_id,
            plan="" if self.filter_plan_var.get() == "全部" else self.filter_plan_var.get().strip(),
            category=option_slug(self.filter_category_var.get()),
            tag=tags,
            query=self.filter_query_var.get().strip(),
        )

        self.results = [entry for entry in self.problems if search_tools.matches(entry, args, self.categories)]
        self._populate_results()
        self.status_var.set(f"找到 {len(self.results)} 道题，共 {len(self.problems)} 道题")

    def reset_filters(self) -> None:
        self.filter_id_var.set("")
        self.filter_query_var.set("")
        self.filter_plan_var.set("全部")
        self.filter_category_var.set("全部")
        self.filter_tag_var.set("")
        self.run_search()

    def _populate_results(self) -> None:
        self.problem_tree.delete(*self.problem_tree.get_children())
        self.record_tree.delete(*self.record_tree.get_children())
        self.selected_problem = None
        self._set_detail_text("")
        self.detail_title.configure(text="未选择题目")

        for index, entry in enumerate(self.results):
            values = (
                f"#{int(entry.get('id', 0)):04d}",
                entry.get("title", ""),
                entry.get("difficulty", ""),
                shorten(", ".join(entry.get("plans", [])), 30),
                shorten(", ".join(entry.get("categories", [])), 30),
                shorten(", ".join(entry.get("tags", [])), 55),
            )
            self.problem_tree.insert("", "end", iid=str(index), values=values)

    def on_problem_select(self, _event: tk.Event[tk.Misc]) -> None:
        selection = self.problem_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        self.selected_problem = self.results[index]
        self._show_problem_detail(self.selected_problem)

    def _show_problem_detail(self, entry: dict[str, Any]) -> None:
        problem_id = int(entry.get("id", 0))
        title = entry.get("title", "")
        self.detail_title.configure(text=f"#{problem_id:04d} {title}")

        lines = [
            f"难度：{entry.get('difficulty') or '-'}",
            f"计划：{', '.join(entry.get('plans', [])) or '-'}",
            f"类别：{', '.join(entry.get('categories', [])) or '-'}",
            f"标签：{', '.join(entry.get('tags', [])) or '-'}",
            f"链接：{entry.get('url') or '-'}",
            f"备注：{entry.get('notes') or '-'}",
        ]
        self._set_detail_text("\n".join(lines))

        self.record_tree.delete(*self.record_tree.get_children())
        for index, record in enumerate(entry.get("records", [])):
            self.record_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    record.get("plan", ""),
                    record.get("category", ""),
                    record.get("status", ""),
                    record.get("folder", ""),
                ),
            )
        children = self.record_tree.get_children()
        if children:
            self.record_tree.selection_set(children[0])

    def _set_detail_text(self, text: str) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, text)
        self.detail_text.configure(state="disabled")

    def _selected_record(self) -> dict[str, Any] | None:
        if not self.selected_problem:
            return None
        records = self.selected_problem.get("records", [])
        if not records:
            return None
        selection = self.record_tree.selection()
        if selection:
            index = int(selection[0])
            if 0 <= index < len(records):
                return records[index]
        return records[0]

    def _selected_folder(self) -> Path | None:
        record = self._selected_record()
        if not record:
            return None
        folder = record.get("folder")
        return ROOT / folder if folder else None

    def open_selected_folder(self) -> None:
        folder = self._selected_folder()
        if folder is None:
            messagebox.showinfo("没有可打开的目录", "请先选择一道已有本地记录的题目。")
            return
        try:
            open_path(folder)
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def open_selected_file(self, file_key: str) -> None:
        record = self._selected_record()
        folder = self._selected_folder()
        if record is None or folder is None:
            messagebox.showinfo("没有可打开的文件", "请先选择一道已有本地记录的题目。")
            return

        filename = record.get(file_key)
        if not filename:
            messagebox.showinfo("缺少文件记录", f"当前记录没有 {file_key} 文件。")
            return

        try:
            open_path(folder / filename)
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))

    def copy_selected_folder(self) -> None:
        folder = self._selected_folder()
        if folder is None:
            messagebox.showinfo("没有可复制的路径", "请先选择一道已有本地记录的题目。")
            return
        self.clipboard_clear()
        self.clipboard_append(str(folder))
        self.status_var.set(f"已复制路径：{folder}")

    def create_or_update_problem(self) -> None:
        raw_id = self.form_id_var.get().strip()
        try:
            problem_id = int(raw_id)
        except ValueError:
            messagebox.showerror("编号格式错误", "编号必须是整数。")
            return

        title = self.form_title_var.get().strip()
        plan = self.form_plan_var.get().strip()
        category = option_slug(self.form_category_var.get())
        if not title:
            messagebox.showerror("缺少标题", "请填写题目标题。")
            return
        if not plan:
            messagebox.showerror("缺少计划", "请填写或选择刷题计划。")
            return
        if not category:
            messagebox.showerror("缺少类别", "请选择题目类别。")
            return

        args = SimpleNamespace(
            id=problem_id,
            title=title,
            plan=plan,
            category=category,
            difficulty=self.form_difficulty_var.get().strip(),
            tags=self.form_tags_var.get().strip(),
            url=self.form_url_var.get().strip(),
            language=self.form_language_var.get().strip() or "python",
            status=self.form_status_var.get().strip() or "draft",
        )

        try:
            folder = new_problem.create_problem(args)
        except Exception as exc:
            messagebox.showerror("创建失败", str(exc))
            return

        self.reload_data(run_search=False)
        self.filter_id_var.set(str(problem_id))
        self.filter_plan_var.set("全部")
        self.filter_category_var.set("全部")
        self.filter_query_var.set("")
        self.filter_tag_var.set("")
        self.run_search()
        self._select_problem_by_id(problem_id)
        self.status_var.set(f"已创建/更新：{folder}")
        messagebox.showinfo("完成", f"已创建/更新：\n{folder}")

    def _select_problem_by_id(self, problem_id: int) -> None:
        for index, entry in enumerate(self.results):
            if int(entry.get("id", -1)) == problem_id:
                iid = str(index)
                self.problem_tree.selection_set(iid)
                self.problem_tree.focus(iid)
                self.problem_tree.see(iid)
                self.selected_problem = entry
                self._show_problem_detail(entry)
                return

    def clear_form(self) -> None:
        self.form_id_var.set("")
        self.form_title_var.set("")
        self.form_plan_var.set("")
        self.form_difficulty_var.set("")
        self.form_tags_var.set("")
        self.form_url_var.set("")
        self.form_language_var.set("python")
        self.form_status_var.set("draft")
        values = list(self.form_category_combo.cget("values"))
        self.form_category_var.set(values[0] if values else "")

    def fill_form_from_selection(self) -> None:
        if not self.selected_problem:
            messagebox.showinfo("未选择题目", "请先在上方列表中选择题目。")
            return

        entry = self.selected_problem
        self.form_id_var.set(str(entry.get("id", "")))
        self.form_title_var.set(str(entry.get("title", "")))
        self.form_difficulty_var.set(str(entry.get("difficulty", "")))
        self.form_tags_var.set(", ".join(entry.get("tags", [])))
        self.form_url_var.set(str(entry.get("url", "")))

        record = self._selected_record()
        if record:
            self.form_plan_var.set(str(record.get("plan", "")))
            category = str(record.get("category", ""))
            for item in self.categories:
                if item.get("slug") == category:
                    self.form_category_var.set(category_option(item))
                    break

    def sync_to_github(self) -> None:
        repo = self.github_repo_var.get().strip() or github_sync.default_repo_name()
        branch = self.github_branch_var.get().strip() or "main"
        message = self.github_message_var.get().strip() or "Sync LeetCode archive"
        visibility = "public" if self.github_public_var.get() else "private"

        self.github_sync_button.configure(state="disabled")
        self.status_var.set("正在同步到 GitHub...")

        thread = threading.Thread(
            target=self._sync_to_github_worker,
            args=(repo, visibility, branch, message),
            daemon=True,
        )
        thread.start()

    def _sync_to_github_worker(self, repo: str, visibility: str, branch: str, message: str) -> None:
        try:
            result = github_sync.sync_to_github(
                repo=repo,
                visibility=visibility,
                branch=branch,
                message=message,
            )
        except Exception as exc:
            self.after(0, lambda: self._sync_to_github_failed(exc))
            return

        self.after(0, lambda: self._sync_to_github_done(result))

    def _sync_to_github_done(self, result: github_sync.SyncResult) -> None:
        self.github_sync_button.configure(state="normal")
        self.github_repo_var.set(result.repo)
        self.github_branch_var.set(result.branch)
        self.status_var.set(f"GitHub 同步完成：{result.repo_url}")
        messagebox.showinfo("GitHub 同步完成", github_sync.result_summary(result))

    def _sync_to_github_failed(self, exc: Exception) -> None:
        self.github_sync_button.configure(state="normal")
        self.status_var.set("GitHub 同步失败")
        messagebox.showerror("GitHub 同步失败", str(exc))


def run_check() -> int:
    categories = load_json(new_problem.CATEGORIES_PATH, [])
    plans = load_json(new_problem.PLANS_PATH, [])
    problems = load_json(new_problem.PROBLEMS_PATH, [])
    repo_name = github_sync.default_repo_name()
    print(f"GUI check ok: {len(categories)} categories, {len(plans)} plans, {len(problems)} problems, repo {repo_name}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the LeetCode archive GUI.")
    parser.add_argument("--check", action="store_true", help="Validate imports and data files without opening the GUI.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.check:
        return run_check()

    app = LeetCodeArchiveApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
