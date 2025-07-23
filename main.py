#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -*- version 1.0 -*-
# -*- AI times -*-
"""
Oracle OCI 对象存储 GUI 管理工具
1.需预先安装并配置 OCI CLI
2.配置~/.oci/config文件
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import subprocess
import json
import os
import threading
from datetime import datetime
import time
import tempfile

class ProgressDialog:
    def __init__(self, parent, title, operation_type):
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("400x150")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        # 居中显示
        self.window.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

        self.operation_type = operation_type
        self.cancelled = False

        # 创建界面
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 文件名显示
        self.file_label = ttk.Label(main_frame, text="准备中...", wraplength=350)
        self.file_label.pack(pady=(0, 10))

        # 进度条
        self.progress = ttk.Progressbar(main_frame, length=350, mode='determinate')
        self.progress.pack(pady=(0, 10))

        # 进度信息
        self.info_label = ttk.Label(main_frame, text="0%")
        self.info_label.pack(pady=(0, 10))

        # 取消按钮
        self.cancel_btn = ttk.Button(main_frame, text="取消", command=self.cancel)
        self.cancel_btn.pack()

        # 协议关闭窗口
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)

    def update_progress(self, filename, progress_percent, speed_info=""):
        if not self.cancelled:
            self.file_label.config(text=f"{self.operation_type}: {os.path.basename(filename)}")
            self.progress['value'] = progress_percent
            info_text = f"{progress_percent:.1f}%"
            if speed_info:
                info_text += f" - {speed_info}"
            self.info_label.config(text=info_text)
            self.window.update()

    def cancel(self):
        self.cancelled = True
        self.window.destroy()

    def close(self):
        if not self.cancelled:
            self.window.destroy()

class OCIStorageGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Oracle OCI 对象存储管理工具")
        self.root.geometry("1000x750")

        # 配置变量
        self.current_profile = tk.StringVar()
        self.current_compartment = tk.StringVar()
        self.current_namespace = tk.StringVar()
        self.current_bucket = tk.StringVar()
        self.current_path = ""  # 当前路径
        self.is_navigating = False  # 新增：导航锁

        # 创建界面
        self.create_widgets()

        # 初始化配置
        self.load_profiles()

    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置区域
        config_frame = ttk.LabelFrame(main_frame, text="配置", padding="5")
        config_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Profile选择
        ttk.Label(config_frame, text="Profile:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.profile_combo = ttk.Combobox(config_frame, textvariable=self.current_profile, width=15)
        self.profile_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.profile_combo.bind('<<ComboboxSelected>>', self.on_profile_changed)

        # Compartment输入
        ttk.Label(config_frame, text="Compartment:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.compartment_entry = ttk.Entry(config_frame, textvariable=self.current_compartment, width=20)
        self.compartment_entry.grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(0, 10))

        # Namespace输入
        ttk.Label(config_frame, text="Namespace:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        self.namespace_entry = ttk.Entry(config_frame, textvariable=self.current_namespace, width=15)
        self.namespace_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10))

        # Bucket输入
        ttk.Label(config_frame, text="Bucket:").grid(row=1, column=2, sticky=tk.W, padx=(0, 5))
        self.bucket_entry = ttk.Entry(config_frame, textvariable=self.current_bucket, width=20)
        self.bucket_entry.grid(row=1, column=3, sticky=(tk.W, tk.E), padx=(0, 10))

        # 刷新按钮
        ttk.Button(config_frame, text="连接", command=self.connect_to_bucket).grid(row=1, column=4, padx=(10, 0))

        # 路径导航区域
        nav_frame = ttk.Frame(main_frame)
        nav_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(nav_frame, text="当前路径:").pack(side=tk.LEFT, padx=(0, 5))
        self.path_var = tk.StringVar()
        self.path_var.set("/")
        self.path_label = ttk.Label(nav_frame, textvariable=self.path_var, relief=tk.SUNKEN, anchor=tk.W)
        self.path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        ttk.Button(nav_frame, text="返回上级", command=self.go_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(nav_frame, text="根目录", command=self.go_root).pack(side=tk.LEFT)

        # 操作按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Button(button_frame, text="上传文件", command=self.upload_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="上传文件夹", command=self.upload_folder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="创建文件夹", command=self.create_folder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="刷新", command=self.refresh_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="下载", command=self.download_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="重命名", command=self.rename_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="删除", command=self.delete_file).pack(side=tk.LEFT, padx=(0, 5))

        # 文件列表区域
        list_frame = ttk.LabelFrame(main_frame, text="文件列表", padding="5")
        list_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # 创建Treeview，支持多选
        columns = ('名称', '大小', '修改时间', '类型')
        self.file_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15, selectmode='extended')

        # 设置列宽
        self.file_tree.column('#0', width=0, stretch=False)  # 隐藏第一列
        self.file_tree.column('名称', width=350)
        self.file_tree.column('大小', width=100)
        self.file_tree.column('修改时间', width=150)
        self.file_tree.column('类型', width=80)

        # 设置列标题
        for col in columns:
            self.file_tree.heading(col, text=col)

        # 绑定双击事件
        self.file_tree.bind('<Double-1>', self.on_double_click)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)

        self.file_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E))

        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        config_frame.columnconfigure(3, weight=1)
        nav_frame.columnconfigure(1, weight=1)

    def run_oci_command(self, command):
        """执行OCI CLI命令"""
        try:
            # Suppress API key warning
            env = os.environ.copy()
            env["SUPPRESS_LABEL_WARNING"] = "True"
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=300, env=env)
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)

    def run_oci_command_with_progress(self, command, progress_dialog, file_path):
        """执行带进度的OCI CLI命令"""
        try:
            # 启动子进程
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)

            # 获取文件大小用于计算进度
            file_size = 0
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)

            start_time = time.time()

            # 模拟进度更新（因为OCI CLI没有内置进度输出）
            while process.poll() is None:
                if progress_dialog.cancelled:
                    process.terminate()
                    return False, "操作已取消"

                elapsed_time = time.time() - start_time
                # 估算进度（基于时间的粗略估计）
                estimated_progress = min(90, elapsed_time * 10)  # 每秒增加10%，最多90%

                speed_info = ""
                if file_size > 0 and elapsed_time > 0:
                    estimated_speed = (file_size * estimated_progress / 100) / elapsed_time / 1024 / 1024  # MB/s
                    speed_info = f"{estimated_speed:.1f} MB/s"

                progress_dialog.update_progress(file_path, estimated_progress, speed_info)
                time.sleep(0.5)

            # 获取结果
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                progress_dialog.update_progress(file_path, 100, "完成")
                time.sleep(0.5)  # 让用户看到100%
                return True, stdout
            else:
                return False, stderr

        except Exception as e:
            return False, str(e)

    def _set_status_with_timeout(self, message):
        """设置状态栏消息并在3秒后恢复为'就绪'"""
        self.status_var.set(message)
        self.root.after(3000, lambda: self.status_var.set("就绪"))

    def load_profiles(self):
        """加载OCI配置文件中的profiles"""
        try:
            # 尝试读取OCI配置文件
            config_file = os.path.expanduser("~/.oci/config")
            if os.path.exists(config_file):
                profiles = []
                with open(config_file, 'r') as f:
                    for line in f:
                        if line.strip().startswith('[') and line.strip().endswith(']'):
                            profile = line.strip()[1:-1]
                            if profile != 'DEFAULT':
                                profiles.append(profile)
                            else:
                                profiles.insert(0, 'DEFAULT')

                self.profile_combo['values'] = profiles
                if profiles:
                    self.current_profile.set(profiles[0])
        except Exception as e:
            messagebox.showerror("错误", f"加载配置文件失败: {str(e)}")

    def on_profile_changed(self, event=None):
        """Profile变更事件"""
        self.status_var.set(f"已选择Profile: {self.current_profile.get()}")

    def connect_to_bucket(self):
        """连接到指定的bucket"""
        if not all([self.current_compartment.get(), self.current_namespace.get(), self.current_bucket.get()]):
            messagebox.showwarning("警告", "请填写完整的配置信息")
            return

        self.status_var.set("正在连接...")
        threading.Thread(target=self._connect_to_bucket_thread, daemon=True).start()

    def _connect_to_bucket_thread(self):
        """在后台线程中连接bucket"""
        profile_arg = f"--profile {self.current_profile.get()}" if self.current_profile.get() != 'DEFAULT' else ""

        # 验证bucket是否存在
        command = f"oci os bucket get --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} {profile_arg}"
        success, output = self.run_oci_command(command)

        if success:
            self.current_path = ""
            self.root.after(0, lambda: self.path_var.set("/"))
            self.root.after(0, lambda: self.status_var.set("连接成功"))
            self.root.after(0, self.refresh_files)
        else:
            self.root.after(0, lambda: messagebox.showerror("连接失败", f"无法连接到bucket: {output}"))
            self.root.after(0, lambda: self.status_var.set("连接失败"))

    def go_up(self):
        """返回上级目录"""
        if self.current_path:
            # 移除最后一个路径分隔符，然后找到上一个分隔符
            path_parts = self.current_path.rstrip('/').split('/')
            if len(path_parts) > 1:
                self.current_path = '/'.join(path_parts[:-1]) + '/'  # Ensure trailing slash
            else:
                self.current_path = ""  # Root path

            self.update_path_display()
            self.refresh_files()

    def go_root(self):
        """返回根目录"""
        self.current_path = ""
        self.update_path_display()
        self.refresh_files()

    def update_path_display(self):
        """更新路径显示"""
        display_path = "/" + self.current_path if self.current_path else "/"
        self.path_var.set(display_path)

    def on_double_click(self, event):
        """双击事件处理"""
        if self.is_navigating:  # 防止快速双击
            return

        selected = self.file_tree.selection()
        if not selected:
            return

        self.is_navigating = True  # 设置导航锁
        try:
            item = self.file_tree.item(selected[0])
            object_name = item['values'][0]
            object_type = item['values'][3]

            # 如果是".."，返回上级目录
            if object_name == "..":
                self.go_up()
            # 如果是文件夹，进入文件夹
            elif object_type == "文件夹":
                new_path = self.current_path + object_name
                # 规范化路径以防止重复文件夹名称
                self.current_path = self._normalize_path(new_path)
                self.update_path_display()
                self.refresh_files()
        finally:
            self.is_navigating = False  # 释放导航锁

    def refresh_files(self):
        """刷新文件列表"""
        if not self.current_bucket.get():
            messagebox.showwarning("警告", "请先连接到bucket")
            return

        self.status_var.set("正在刷新文件列表...")
        threading.Thread(target=self._refresh_files_thread, daemon=True).start()
        self.status_var.set("就绪")

    def _refresh_files_thread(self):
        """在后台线程中刷新文件列表"""
        profile_arg = f"--profile {self.current_profile.get()}" if self.current_profile.get() != 'DEFAULT' else ""

        # 添加前缀参数来获取特定路径下的文件
        prefix_arg = f"--prefix {self.current_path}" if self.current_path else ""

        command = f"oci os object list --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} {prefix_arg} --output json {profile_arg}"
        success, output = self.run_oci_command(command)

        if success:
            try:
                data = json.loads(output)
                self.root.after(0, lambda: self._update_file_list(data.get('data', [])))
            except json.JSONDecodeError:
                self.root.after(0, lambda: self._set_status_with_timeout(f"解析文件列表失败"))
        else:
            self.root.after(0, lambda: self._set_status_with_timeout(f"获取文件列表失败: {output}"))

        ### self.root.after(0, lambda: self.status_var.set("就绪"))

    def _normalize_path(self, path):
        """规范化路径，移除多余的斜杠和重复的文件夹名称"""
        if not path:
            return ""

        # 分割路径并移除空段
        parts = [part for part in path.split('/') if part]
        # 移除重复的文件夹名称，保留最后一个
        unique_parts = []
        for part in parts:
            if not unique_parts or unique_parts[-1] != part:
                unique_parts.append(part)

        # 重新构建路径，确保以斜杠结尾（如果非空）
        normalized = '/'.join(unique_parts)
        if normalized:
            normalized += '/'
        return normalized

    def _update_file_list(self, objects):
        """更新文件列表显示"""
        # 清空现有项目
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        # 如果不在根目录，添加".."项
        if self.current_path:
            self.file_tree.insert('', 'end', values=("..", "", "", "文件夹"))

        # 处理文件和文件夹
        folders = set()
        files = []

        current_level = len(self.current_path.split('/')) if self.current_path else 1

        for obj in objects:
            name = obj.get('name', '')

            # 移除当前路径前缀
            if self.current_path and name.startswith(self.current_path):
                relative_name = name[len(self.current_path):]
            else:
                relative_name = name

            # 跳过空名称
            if not relative_name:
                continue

            # 判断是否为当前目录的直接子项
            name_parts = relative_name.split('/')
            if len(name_parts) > 1:
                # 这是一个子文件夹
                folder_name = name_parts[0] + '/'
                folders.add(folder_name)
            else:
                # 这是一个文件
                if not relative_name.endswith('/'):
                    files.append((relative_name, obj))

        # 添加文件夹项目
        for folder in sorted(folders):
            self.file_tree.insert('', 'end', values=(folder, "", "", "文件夹"))

        # 添加文件项目
        for filename, obj in sorted(files, key=lambda x: x[0]):
            size = self._format_size(obj.get('size', 0))
            time_modified = obj.get('time-modified', '')
            if time_modified:
                try:
                    dt = datetime.fromisoformat(time_modified.replace('Z', '+00:00'))
                    time_modified = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass

            self.file_tree.insert('', 'end', values=(filename, size, time_modified, "文件"))

    def _format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"

        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def upload_file(self):
        """上传多个文件"""
        if not self.current_bucket.get():
            messagebox.showwarning("警告", "请先连接到bucket")
            return

        # 选择多个文件
        file_paths = filedialog.askopenfilenames(title="选择要上传的文件")
        if not file_paths:
            return

        # 构建文件列表
        files_to_upload = []
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            full_object_name = self.current_path + file_name
            files_to_upload.append((file_path, full_object_name))

        if not files_to_upload:
            messagebox.showwarning("警告", "未选择任何文件")
            return

        # 创建进度对话框
        progress_dialog = ProgressDialog(self.root, "上传文件", "上传")

        self.status_var.set("正在准备上传...")
        threading.Thread(target=self._upload_file_thread, args=(files_to_upload, progress_dialog), daemon=True).start()

    def _upload_file_thread(self, files, progress_dialog):
        """在后台线程中上传多个文件"""
        profile_arg = f"--profile {self.current_profile.get()}" if self.current_profile.get() != 'DEFAULT' else ""

        total_files = len(files)
        success_count = 0

        for index, (file_path, full_object_name) in enumerate(files, 1):
            if progress_dialog.cancelled:
                self.root.after(0, lambda: self._set_status_with_timeout("上传已取消"))
                self.root.after(0, progress_dialog.close)
                return

            file_name = os.path.basename(file_path)
            self.root.after(0, lambda: self.status_var.set(f"正在上传 {file_name} ({index}/{total_files})"))

            command = f'oci os object put --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} --file "{file_path}" --name "{full_object_name}" {profile_arg}'
            success, output = self.run_oci_command_with_progress(command, progress_dialog, file_path)

            if success and not progress_dialog.cancelled:
                success_count += 1
            elif not progress_dialog.cancelled:
                self.root.after(0, lambda: self._set_status_with_timeout(f"上传文件 {file_name} 失败: {output}"))
                self.root.after(0, progress_dialog.close)
                return

        self.root.after(0, lambda: self._set_status_with_timeout(f"上传完成: {success_count}/{total_files} 文件成功"))
        self.root.after(0, progress_dialog.close)
        self.root.after(0, self.refresh_files)

    def upload_folder(self):
        """上传文件夹"""
        if not self.current_bucket.get():
            messagebox.showwarning("警告", "请先连接到bucket")
            return

        folder_path = filedialog.askdirectory(title="选择要上传的文件夹")
        if not folder_path:
            return

        # 询问目标文件夹名称
        folder_name = os.path.basename(folder_path)
        target_folder = simpledialog.askstring("目标文件夹名称", "请输入目标文件夹名称:", initialvalue=folder_name)
        if not target_folder:
            return

        if not target_folder.endswith('/'):
            target_folder += '/'

        # 添加当前路径前缀
        full_target_path = self.current_path + target_folder

        self.status_var.set("正在上传文件夹...")
        threading.Thread(target=self._upload_folder_thread, args=(folder_path, full_target_path),
                         daemon=True).start()

    def _upload_folder_thread(self, folder_path, target_path):
        """在后台线程中上传文件夹"""
        profile_arg = f"--profile {self.current_profile.get()}" if self.current_profile.get() != 'DEFAULT' else ""

        try:
            # 收集所有文件
            all_files = []
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, folder_path)
                    # 将Windows路径分隔符转换为Unix格式
                    relative_path = relative_path.replace('\\', '/')
                    all_files.append((file_path, relative_path))

            total_files = len(all_files)
            success_count = 0

            for i, (file_path, relative_path) in enumerate(all_files):
                object_name = target_path + relative_path

                # 更新状态
                self.root.after(0, lambda f=relative_path, c=i + 1, t=total_files:
                self.status_var.set(f"上传 {f} ({c}/{t})"))

                command = f'oci os object put --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} --file "{file_path}" --name "{object_name}" {profile_arg}'
                success, output = self.run_oci_command(command)

                if success:
                    success_count += 1
                else:
                    print(f"上传失败: {relative_path} - {output}")

            # 显示结果
            self.root.after(0, lambda: self._set_status_with_timeout(f"文件夹上传完成\n成功: {success_count}/{total_files}"))
            self.root.after(0, self.refresh_files)

        except Exception as e:
            self.root.after(0, lambda: self._set_status_with_timeout(f"文件夹上传失败: {str(e)}"))

        self.root.after(0, lambda: self.status_var.set("就绪"))

    def download_file(self):
        """下载选中的多个文件"""
        if not self.current_bucket.get():
            messagebox.showwarning("警告", "请先连接到bucket")
            return

        selected = self.file_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请选择要下载的文件")
            return

        # 收集选中的文件
        files_to_download = []
        for item_id in selected:
            item = self.file_tree.item(item_id)
            object_name = item['values'][0]
            object_type = item['values'][3]
            if object_type == "文件夹" or object_name == "..":
                messagebox.showwarning("警告", f"无法下载文件夹或'..'，请仅选择文件")
                return
            full_object_name = self.current_path + object_name
            files_to_download.append((object_name, full_object_name))

        if not files_to_download:
            messagebox.showwarning("警告", "未选择任何文件")
            return

        # 选择保存目录
        save_dir = filedialog.askdirectory(title="选择保存目录")
        if not save_dir:
            return

        # 创建进度对话框
        progress_dialog = ProgressDialog(self.root, "下载文件", "下载")

        threading.Thread(target=self._download_file_thread, args=(files_to_download, save_dir, progress_dialog),
                         daemon=True).start()

    def _download_file_thread(self, files, save_dir, progress_dialog):
        """在后台线程中下载多个文件"""
        profile_arg = f"--profile {self.current_profile.get()}" if self.current_profile.get() != 'DEFAULT' else ""

        total_files = len(files)
        success_count = 0

        for index, (object_name, full_object_name) in enumerate(files, 1):
            if progress_dialog.cancelled:
                self.root.after(0, lambda: self._set_status_with_timeout("下载已取消"))
                self.root.after(0, progress_dialog.close)
                self.root.after(0, lambda: self.status_var.set("就绪"))
                return

            # 构建保存路径
            save_path = os.path.join(save_dir, object_name).replace('\\', '/')

            # 更新状态
            self.root.after(0, lambda: self.status_var.set(f"正在下载 {object_name} ({index}/{total_files})"))

            # 执行下载命令
            command = f'oci os object get --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} --name "{full_object_name}" --file "{save_path}" {profile_arg}'
            success, output = self.run_oci_command_with_progress(command, progress_dialog, save_path)

            if success and not progress_dialog.cancelled:
                success_count += 1
            elif not progress_dialog.cancelled:
                self.root.after(0, lambda: self._set_status_with_timeout( f"下载文件 {object_name} 失败: {output}"))
                self.root.after(0, progress_dialog.close)
                self.root.after(0, lambda: self.status_var.set("就绪"))
                return

        self.root.after(0, lambda: self._set_status_with_timeout(f"下载完成: {success_count}/{total_files} 文件成功"))
        self.root.after(0, progress_dialog.close)
        self.root.after(0, lambda: self.status_var.set("就绪"))

    def delete_file(self):
        """删除选中的多个文件或文件夹"""
        if not self.current_bucket.get():
            messagebox.showwarning("警告", "请先连接到bucket")
            return

        selected = self.file_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请选择要删除的文件或文件夹")
            return

        # 收集选中的文件和文件夹
        items_to_delete = []
        for item_id in selected:
            item = self.file_tree.item(item_id)
            object_name = item['values'][0]
            object_type = item['values'][3]
            if object_name == "..":
                messagebox.showwarning("警告", "无法删除'..'")
                return
            full_object_name = self.current_path + object_name
            items_to_delete.append((object_name, full_object_name, object_type))

        if not items_to_delete:
            messagebox.showwarning("警告", "未选择任何文件或文件夹")
            return

        # 构建确认消息
        confirm_message = "确定要删除以下项目吗？\n\n" + "\n".join([name for name, _, _ in items_to_delete])
        if not messagebox.askyesno("确认删除", confirm_message):
            return

        self.status_var.set("正在删除...")
        threading.Thread(target=self._delete_file_thread, args=(items_to_delete,), daemon=True).start()

    def _delete_file_thread(self, items):
        """在后台线程中删除多个文件或文件夹"""
        profile_arg = f"--profile {self.current_profile.get()}" if self.current_profile.get() != 'DEFAULT' else ""

        total_items = len(items)
        success_count = 0

        for index, (object_name, full_object_name, object_type) in enumerate(items, 1):
            self.root.after(0, lambda: self.status_var.set(f"正在删除 {object_name} ({index}/{total_items})"))

            if object_type == "文件夹":
                # 删除文件夹需要删除所有以该前缀开头的对象
                prefix_arg = f"--prefix {full_object_name}"
                command = f"oci os object list --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} {prefix_arg} --output json {profile_arg}"
                success, output = self.run_oci_command(command)

                if not success:
                    self.root.after(0, lambda: self._set_status_with_timeout(f"获取文件夹内容 {object_name} 失败: {output}"))
                    return

                try:
                    data = json.loads(output)
                    objects = data.get('data', [])
                    for obj in objects:
                        obj_name = obj.get('name', '')
                        if obj_name:
                            delete_command = f'oci os object delete --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} --name "{obj_name}" --force {profile_arg}'
                            success, output = self.run_oci_command(delete_command)
                            if not success:
                                self.root.after(0, lambda: self._set_status_with_timeout(f"删除对象 {obj_name} 失败: {output}"))
                                return
                except json.JSONDecodeError:
                    self.root.after(0, lambda: self._set_status_with_timeout(f"解析文件夹内容 {object_name} 失败"))
                    return
            else:
                # 删除单个文件
                command = f'oci os object delete --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} --name "{full_object_name}" --force {profile_arg}'
                success, output = self.run_oci_command(command)

                if not success:
                    self.root.after(0,
                                    lambda: self._set_status_with_timeout(f"删除文件 {object_name} 失败: {output}"))
                    return

            success_count += 1

        self.root.after(0, lambda: self._set_status_with_timeout( f"删除完成: {success_count}/{total_items} 项目成功"))
        self.root.after(0, self.refresh_files)

    def rename_file(self):
        """重命名文件或文件夹"""
        if not self.current_bucket.get():
            messagebox.showwarning("警告", "请先连接到bucket")
            return

        selected = self.file_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请选择要重命名的文件或文件夹")
            return

        item = self.file_tree.item(selected[0])
        old_name = item['values'][0]
        object_type = item['values'][3]

        new_name = simpledialog.askstring("重命名", f"请输入新的{object_type}名称:", initialvalue=old_name)
        if not new_name or new_name == old_name:
            return

        # 对于文件夹，确保新名称以'/'结尾
        if object_type == "文件夹" and not new_name.endswith('/'):
            new_name += '/'

        # 构建完整路径
        full_old_name = self.current_path + old_name
        full_new_name = self.current_path + new_name

        self.status_var.set(f"正在重命名{object_type}...")
        threading.Thread(target=self._rename_file_thread, args=(full_old_name, full_new_name, object_type),
                         daemon=True).start()

    def _rename_file_thread(self, old_name, new_name, object_type):
        """在后台线程中重命名文件或文件夹"""
        profile_arg = f"--profile {self.current_profile.get()}" if self.current_profile.get() != 'DEFAULT' else ""

        if object_type == "文件夹":
            # 重命名文件夹：复制所有以旧前缀开头的对象到新前缀
            prefix_arg = f"--prefix {old_name}"
            command = f"oci os object list --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} {prefix_arg} --output json {profile_arg}"
            success, output = self.run_oci_command(command)

            if not success:
                self.root.after(0, lambda: self._set_status_with_timeout( f"获取文件夹内容失败: {output}"))
                return

            try:
                data = json.loads(output)
                objects = data.get('data', [])
                success_count = 0
                total_objects = len(objects)

                for obj in objects:
                    obj_name = obj.get('name', '')
                    if obj_name:
                        # 计算新对象名称
                        relative_name = obj_name[len(old_name):] if obj_name.startswith(old_name) else obj_name
                        new_obj_name = new_name + relative_name

                        copy_command = f'oci os object copy --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} --source-object-name "{obj_name}" --destination-bucket {self.current_bucket.get()} --destination-object-name "{new_obj_name}" {profile_arg}'
                        success, output = self.run_oci_command(copy_command)

                        if not success:
                            self.root.after(0, lambda: self._set_status_with_timeout(f"复制对象 {obj_name} 失败: {output}"))
                            return

                        success_count += 1
                        self.root.after(0, lambda: self.status_var.set(
                            f"正在重命名文件夹 ({success_count}/{total_objects})"))

                # 删除旧对象
                for obj in objects:
                    obj_name = obj.get('name', '')
                    if obj_name:
                        delete_command = f'oci os object delete --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} --name "{obj_name}" --force {profile_arg}'
                        success, output = self.run_oci_command(delete_command)
                        if not success:
                            self.root.after(0, lambda: self._set_status_with_timeout(f"删除旧对象 {obj_name} 失败: {output}"))
                            return

            except json.JSONDecodeError:
                self.root.after(0, lambda: self._set_status_with_timeout("重命名失败 - 解析文件夹内容失败"))
                return
        else:
            # 重命名单个文件
            copy_command = f'oci os object copy --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} --source-object-name "{old_name}" --destination-bucket {self.current_bucket.get()} --destination-object-name "{new_name}" {profile_arg}'
            success, output = self.run_oci_command(copy_command)

            if success:
                # 删除原文件
                delete_command = f'oci os object delete --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} --name "{old_name}" --force {profile_arg}'
                success, output = self.run_oci_command(delete_command)

                if not success:
                    self.root.after(0, lambda: self._set_status_with_timeout(f"重命名失败 - 删除原文件失败: {output}"))
                    return
            else:
                self.root.after(0, lambda: self._set_status_with_timeout(f"重命名失败 - 复制文件失败: {output}"))
                return

        self.root.after(0, lambda: self._set_status_with_timeout(f"{object_type}重命名成功"))
        self.root.after(0, self.refresh_files)
        self.root.after(0, lambda: self.status_var.set("就绪"))

    def create_folder(self):
        """创建文件夹"""
        if not self.current_bucket.get():
            messagebox.showwarning("警告", "请先连接到bucket")
            return

        folder_name = simpledialog.askstring("创建文件夹", "请输入文件夹名称:")
        if not folder_name:
            return

        if not folder_name.endswith('/'):
            folder_name += '/'

        # 添加当前路径前缀
        full_folder_name = self.current_path + folder_name

        self.status_var.set("正在创建文件夹...")
        threading.Thread(target=self._create_folder_thread, args=(full_folder_name,), daemon=True).start()

    def _create_folder_thread(self, folder_name):
        """在后台线程中创建文件夹"""
        profile_arg = f"--profile {self.current_profile.get()}" if self.current_profile.get() != 'DEFAULT' else ""

        # 创建一个空对象作为文件夹
        tmp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(b'')
                tmp_file_path = tmp_file.name

            command = f'oci os object put --namespace {self.current_namespace.get()} --bucket-name {self.current_bucket.get()} --file "{tmp_file_path}" --name "{folder_name}" {profile_arg}'
            success, output = self.run_oci_command(command)

            if success:
                self.root.after(0, lambda: self._set_status_with_timeout("文件夹创建成功"))
                self.root.after(0, self.refresh_files)
            else:
                self.root.after(0, lambda: self._set_status_with_timeout(f"文件夹创建失败: {output}"))
        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

        self.root.after(0, lambda: self.status_var.set("就绪"))

def main():
    root = tk.Tk()
    app = OCIStorageGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()