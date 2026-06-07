import base64
import json
import math
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.parse import quote
from urllib.request import Request, urlopen


SEARCH_URL = "https://api.kivo.wiki/api/v1/data/students/?name={name}"
DETAIL_URL = "https://api.kivo.wiki/api/v1/data/students/{student_id}"
IMAGE_MAX_SIZE = 96
REQUEST_TIMEOUT = 15


def resource_path(filename):
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / filename
    return Path(__file__).with_name(filename)


FAVOR_FILE = resource_path("character_favor_levels.json")


def api_get_json(url):
    request = Request(url, headers={"User-Agent": "BlueArchiveFavorLevelLookup/1.0"})
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def normalize_url(url):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return url


def display_name(student):
    name = student.get("given_name_cn") or student.get("given_name") or ""
    skin = student.get("skin_cn") or student.get("skin") or ""
    if skin:
        return f"{name}（{skin}）"
    return name


def find_key(data, key):
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for value in data.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_key(item, key)
            if found is not None:
                return found
    return None


def load_favor_index():
    with FAVOR_FILE.open("r", encoding="utf-8") as file:
        rows = json.load(file)
    return {
        int(row["character_id"]): row.get("favor_level", [])
        for row in rows
        if "character_id" in row
    }


def format_level(level):
    text = str(level)
    if text.isdigit():
        return str(int(text))
    return text


class FavorLookupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("好感剧情解锁等级查询")
        self.geometry("760x620")
        self.minsize(640, 480)

        self.favor_index = load_favor_index()
        self.images = []

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.create_search_bar()
        self.create_results_area()
        self.create_output_area()

    def create_search_bar(self):
        frame = ttk.Frame(self, padding=(12, 12, 12, 8))
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.search_var)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        entry.bind("<Return>", lambda _event: self.search())
        entry.focus_set()

        self.search_button = ttk.Button(frame, text="查询", command=self.search)
        self.search_button.grid(row=0, column=1)

        self.status_var = tk.StringVar(value="请输入学生名后查询。")
        status = ttk.Label(frame, textvariable=self.status_var)
        status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def create_results_area(self):
        wrapper = ttk.Frame(self, padding=(12, 0, 12, 8))
        wrapper.grid(row=1, column=0, sticky="nsew")
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(wrapper, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=self.canvas.yview)
        self.results_frame = ttk.Frame(self.canvas)
        self.results_window = self.canvas.create_window((0, 0), window=self.results_frame, anchor="nw")

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.results_frame.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(self.results_window, width=event.width),
        )

    def create_output_area(self):
        frame = ttk.Frame(self, padding=(12, 0, 12, 12))
        frame.grid(row=2, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        self.output = tk.Text(frame, height=5, wrap="word")
        self.output.grid(row=0, column=0, sticky="ew")
        self.output.configure(state="disabled")

        copy_button = ttk.Button(frame, text="复制结果", command=self.copy_result)
        copy_button.grid(row=0, column=1, sticky="ns", padx=(8, 0))

    def run_background(self, task, on_success):
        def worker():
            try:
                result = task()
            except Exception as exc:
                self.after(0, lambda: self.show_error(exc))
            else:
                self.after(0, lambda: on_success(result))

        threading.Thread(target=worker, daemon=True).start()

    def search(self):
        name = self.search_var.get().strip()
        if not name:
            messagebox.showinfo("提示", "请输入查询名。")
            return

        self.clear_results()
        self.set_output("")
        self.search_button.configure(state="disabled")
        self.status_var.set("正在查询...")

        def task():
            url = SEARCH_URL.format(name=quote(name))
            payload = api_get_json(url)
            return payload.get("data", {}).get("students") or []

        self.run_background(task, self.show_students)

    def show_students(self, students):
        self.search_button.configure(state="normal")
        if not students:
            self.status_var.set("没有找到匹配结果。")
            return

        self.status_var.set(f"找到 {len(students)} 个结果，请选择一个。")
        self.images.clear()

        for index, student in enumerate(students):
            self.add_student_option(index, student)

    def add_student_option(self, index, student):
        frame = ttk.Frame(self.results_frame, padding=(8, 8))
        frame.grid(row=index, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)

        photo = self.load_avatar(student.get("avatar"))
        self.images.append(photo)

        image_label = ttk.Label(frame, image=photo)
        image_label.grid(row=0, column=0, sticky="w", padx=(0, 12))

        button = ttk.Button(
            frame,
            text=display_name(student),
            command=lambda selected=student: self.choose_student(selected),
        )
        button.grid(row=0, column=1, sticky="ew")

    def load_avatar(self, url):
        try:
            image_url = normalize_url(url)
            if not image_url:
                raise ValueError("empty avatar url")
            request = Request(image_url, headers={"User-Agent": "BlueArchiveFavorLevelLookup/1.0"})
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                data = response.read()
            photo = tk.PhotoImage(data=base64.b64encode(data))
            scale = max(1, math.ceil(max(photo.width(), photo.height()) / IMAGE_MAX_SIZE))
            if scale > 1:
                photo = photo.subsample(scale, scale)
            return photo
        except Exception:
            return tk.PhotoImage(width=IMAGE_MAX_SIZE, height=IMAGE_MAX_SIZE)

    def choose_student(self, student):
        student_id = student.get("id")
        if student_id is None:
            messagebox.showerror("错误", "该结果缺少 id 字段。")
            return

        self.status_var.set("正在查询角色详情...")
        self.set_output("")

        def task():
            detail = api_get_json(DETAIL_URL.format(student_id=student_id))
            character_id = find_key(detail, "character_id")
            if character_id is None:
                raise KeyError("详情接口返回结果中没有 character_id 字段。")
            return int(character_id)

        self.run_background(task, lambda character_id: self.show_favor_levels(student, character_id))

    def show_favor_levels(self, student, character_id):
        favor_levels = self.favor_index.get(character_id)
        if not favor_levels:
            self.status_var.set(f"本地文件中没有 character_id={character_id} 的好感剧情数据。")
            return

        levels = ", ".join(format_level(level) for level in favor_levels)
        result = f'{display_name(student)}\n的好感剧情于好感等级\n{levels}\n时解锁。'
        self.status_var.set(f"已找到 {display_name(student)} 的好感剧情解锁等级。")
        self.set_output(result)
        print(result)

    def clear_results(self):
        for child in self.results_frame.winfo_children():
            child.destroy()
        self.images.clear()

    def set_output(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def copy_result(self):
        text = self.output.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("结果已复制。")

    def show_error(self, exc):
        self.search_button.configure(state="normal")
        self.status_var.set("查询失败。")
        messagebox.showerror("错误", str(exc))


if __name__ == "__main__":
    FavorLookupApp().mainloop()
