import os 
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import cv2
import shutil
import csv
import numpy as np

class AnnotationTool:
    def __init__(self, root):
        self.root = root
        self.root.title("📸 Image Annotation Tool")
        self.root.geometry("1280x860+100+50")
        self.root.configure(bg="#e6f2ff")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=8, relief="flat", background="#007acc", foreground="white", font=('Helvetica', 10, 'bold'))
        style.configure("TLabel", background="#e6f2ff", font=('Helvetica', 11))
        style.configure("TCombobox", padding=5, font=('Helvetica', 10))

        self.source_folder = None
        self.target_folder = None
        self.image_list = []
        self.display_image_list = []
        self.current_image_index = 0
        self.annotations = {}
        self.csv_data = []
        self.categories = []
        self.names = []
        self.setup_page1()

    def setup_page1(self):
        self.clear_root()

        frame = tk.Frame(self.root, bg="#ffffff", bd=2, relief=tk.RIDGE)
        frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        ttk.Label(frame, text="📁 Source Folder:").pack(pady=5)
        self.src_label = ttk.Label(frame, text="Not Selected", foreground="gray")
        self.src_label.pack(pady=5)
        ttk.Button(frame, text="Select Source Folder", command=self.select_source_folder).pack(pady=5)
        ttk.Button(frame, text="Remove Source Folder", command=self.remove_source_folder).pack(pady=5)

        ttk.Label(frame, text="📂 Target Folder:").pack(pady=15)
        self.tgt_label = ttk.Label(frame, text="Not Selected", foreground="gray")
        self.tgt_label.pack(pady=5)
        ttk.Button(frame, text="Select Target Folder", command=self.select_target_folder).pack(pady=5)
        ttk.Button(frame, text="Remove Target Folder", command=self.remove_target_folder).pack(pady=5)

        ttk.Button(frame, text="✅ Done", command=self.on_done).pack(pady=30)

    def setup_page2(self):
        self.clear_root()
        self.image_list = sorted([f for f in os.listdir(self.source_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))])

        annotated_images = set()
        for category in self.categories:
            for name in self.names:
                img_dir = os.path.join(self.target_folder, category, name, 'images')
                if os.path.exists(img_dir):
                    annotated_images.update(os.listdir(img_dir))

        self.display_image_list = [img for img in self.image_list if img not in annotated_images]

        if not self.display_image_list:
            messagebox.showinfo("Info", "All images in the source folder have already been annotated.")
            return

        self.canvas = tk.Canvas(self.root, cursor="cross", bg="#ffffff")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.rect_start = None
        self.current_rect = None

        nav_frame = tk.Frame(self.root, bg="#d9ecff")
        nav_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)

        ttk.Button(nav_frame, text="◀ Previous", command=self.prev_image).pack(side=tk.LEFT, padx=10)
        self.file_name_label = ttk.Label(nav_frame, text="")
        self.file_name_label.pack(side=tk.LEFT, expand=True)
        ttk.Button(nav_frame, text="Next ▶", command=self.next_image).pack(side=tk.RIGHT, padx=10)
        ttk.Button(nav_frame, text="🗑️ Delete Image", command=self.remove_image_from_display).pack(side=tk.RIGHT, padx=10)

        self.display_image()
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

    def clear_root(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def select_source_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_folder = folder
            self.src_label.config(text=folder)

    def remove_source_folder(self):
        self.source_folder = None
        self.src_label.config(text="Not Selected")

    def select_target_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.target_folder = folder
            self.tgt_label.config(text=folder)
            self.load_categories_and_names()

    def load_categories_and_names(self):
        self.categories = []
        self.names = []
        if os.path.isdir(self.target_folder):
            for cat in os.listdir(self.target_folder):
                cat_path = os.path.join(self.target_folder, cat)
                if os.path.isdir(cat_path):
                    self.categories.append(cat)
                    for name in os.listdir(cat_path):
                        name_path = os.path.join(cat_path, name)
                        if os.path.isdir(name_path) and name not in self.names:
                            self.names.append(name)

    def remove_target_folder(self):
        self.target_folder = None
        self.tgt_label.config(text="Not Selected")

    def on_done(self):
        if self.source_folder and self.target_folder:
            self.setup_page2()
        else:
            messagebox.showwarning("Warning", "Both source and target folders must be selected.")

    def display_image(self):
        self.canvas.delete("all")
        if not self.display_image_list:
            self.file_name_label.config(text="No images to display")
            return
        image_path = os.path.join(self.source_folder, self.display_image_list[self.current_image_index])
        self.current_image = Image.open(image_path)

        canvas_width = self.canvas.winfo_width() or 800
        canvas_height = self.canvas.winfo_height() or 600
        img_width, img_height = self.current_image.size

        scale = min(canvas_width / img_width, canvas_height / img_height, 1.0)
        new_width = max(1, int(img_width * scale))
        new_height = max(1, int(img_height * scale))
        resized_image = self.current_image.resize((new_width, new_height), Image.LANCZOS)

        self.tk_image = ImageTk.PhotoImage(resized_image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        self.file_name_label.config(text=self.display_image_list[self.current_image_index])

        filename = self.display_image_list[self.current_image_index]
        if filename in self.annotations:
            for ann in self.annotations[filename]:
                rect = self.canvas.create_rectangle(*ann[:4], outline='red')
                label = f"{ann[4]}:{ann[5]}"
                self.canvas.create_text(ann[0]+5, ann[1]-10, anchor="nw", fill="red", text=label)

    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.display_image()

    def next_image(self):
        if self.current_image_index < len(self.display_image_list) - 1:
            self.current_image_index += 1
            self.display_image()

    def remove_image_from_display(self):
        if self.display_image_list:
            del self.display_image_list[self.current_image_index]
            if not self.display_image_list:
                self.canvas.delete("all")
                self.file_name_label.config(text="No images to display")
                return
            if self.current_image_index >= len(self.display_image_list):
                self.current_image_index = max(0, len(self.display_image_list) - 1)
            self.display_image()

    def on_press(self, event):
        self.rect_start = (event.x, event.y)
        self.current_rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red')

    def on_drag(self, event):
        if self.current_rect:
            self.canvas.coords(self.current_rect, self.rect_start[0], self.rect_start[1], event.x, event.y)

    def on_release(self, event):
        x0, y0 = self.rect_start
        x1, y1 = event.x, event.y
        self.show_popup(min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1))

    def show_popup(self, x0, y0, x1, y1):
        popup = tk.Toplevel(self.root)
        popup.title("📝 Annotation")
        popup.configure(bg="#f7fbff")

        ttk.Label(popup, text="Category").pack(pady=5)
        category_var = tk.StringVar()
        category_cb = ttk.Combobox(popup, textvariable=category_var)
        category_cb.pack()
        category_cb['values'] = self.categories
        category_cb.bind('<KeyRelease>', lambda e: self.update_autocomplete(category_cb, self.categories))

        ttk.Label(popup, text="Name").pack(pady=5)
        name_var = tk.StringVar()
        name_cb = ttk.Combobox(popup, textvariable=name_var)
        name_cb.pack()
        name_cb['values'] = self.names
        name_cb.bind('<KeyRelease>', lambda e: self.update_autocomplete(name_cb, self.names))

        def on_ok():
            category = category_var.get()
            name = name_var.get()

            if not category or not name:
                messagebox.showerror("Error", "Both category and name must be selected.")
                return

            if category not in self.categories:
                self.categories.append(category)
            if name not in self.names:
                self.names.append(name)

            img_path = os.path.join(self.target_folder, category, name, 'images')
            txt_path = os.path.join(self.target_folder, category, name, 'text_files')
            os.makedirs(img_path, exist_ok=True)
            os.makedirs(txt_path, exist_ok=True)

            filename = self.display_image_list[self.current_image_index]
            if filename not in self.annotations:
                self.annotations[filename] = []
            self.annotations[filename].append((x0, y0, x1, y1, category, name))

            img_name = f"{len(os.listdir(img_path)):04d}.jpg"
            txt_name = img_name.replace('.jpg', '.txt')

            save_img_path = os.path.join(img_path, img_name)
            save_txt_path = os.path.join(txt_path, txt_name)

            cv2_img = cv2.cvtColor(np.array(self.current_image), cv2.COLOR_RGB2BGR)
            cv2.imwrite(save_img_path, cv2_img)

            with open(save_txt_path, 'a') as f:
                f.write(f"{x0},{y0},{x1},{y1}\n")

            self.csv_data.append([
                os.path.join(self.source_folder, filename),
                save_img_path, category, name, x0, y0, x1, y1
            ])

            popup.destroy()
            self.display_image()

        def on_cancel():
            popup.destroy()

        btn_frame = tk.Frame(popup, bg="#f7fbff")
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT, padx=10)

    def update_autocomplete(self, combobox, options):
        value = combobox.get().lower()
        filtered = [item for item in options if value in item.lower()]
        combobox['values'] = filtered
        if value:
            combobox.event_generate('<Down>')

    def on_exit(self):
        csv_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if csv_path:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['source_path', 'target_path', 'category', 'name', 'x0', 'y0', 'x1', 'y1'])
                writer.writerows(self.csv_data)
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = AnnotationTool(root)
    root.mainloop()

