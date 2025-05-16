from tkinter import filedialog, messagebox, ttk
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import shutil
import csv
import os
import numpy as np
import json
from tkinter import messagebox
class AutoCompleteEntry(tk.Entry):
    def __init__(self, master, suggestion_list, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master = master
        self.suggestion_list = sorted(suggestion_list)
        self.var = self["textvariable"] = tk.StringVar()
        self.var.trace_add("write", self.changed)
        self.bind("<Down>", self.move_down)
        self.bind("<Return>", self.select_item)
        self.bind("<Right>", self.select_item)
        self.bind("<FocusOut>", lambda e: self.hide_listbox())
        

        self.listbox = None

    def changed(self, *args):
        pattern = self.var.get().lower()
        matches = [item for item in self.suggestion_list if pattern in item.lower()]
        self.show_matches(matches)

    def show_matches(self, matches):
        if self.listbox:
            self.listbox.destroy()

        if not matches:
            return

        self.listbox = tk.Listbox(self.master, height=min(5, len(matches)))
        self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)

        for match in matches:
            self.listbox.insert(tk.END, match)

        self.listbox.place(x=self.winfo_rootx() - self.master.winfo_rootx(),
                           y=self.winfo_rooty() - self.master.winfo_rooty() + self.winfo_height(),
                           width=self.winfo_width())

    def hide_listbox(self):
        if self.listbox:
            self.listbox.destroy()
            self.listbox = None

    def on_listbox_select(self, event):
        if self.listbox:
            index = self.listbox.curselection()
            if index:
                self.var.set(self.listbox.get(index))
                self.hide_listbox()

    def select_item(self, event):
        if self.listbox:
            index = self.listbox.curselection()
            if index:
                self.var.set(self.listbox.get(index))
        self.hide_listbox()

    def move_down(self, event):
        if self.listbox:
            self.listbox.focus_set()
            self.listbox.selection_set(0)


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
        self.selected_source_folder=None
        
        self.selected_target_folder=None

        self.last_crop = ""
        self.last_category = ""
        self.last_name = ""
        self.source_folder = None
        self.target_folder = None
        self.undo_stack = []  # List of (filename, annotation) tuples
        self.redo_stack = []

        self.image_list = []
        self.display_image_list = []
        self.current_image_index = 0
        self.annotations = {}
        self.csv_data = []
        self.categories = []
        self.names = []
        self.last_drawn_rect = None
        self.setup_page1()
        self.annotation_labels = []
        self.root.bind("<Control-z>", self.undo_callback)
        self.root.bind("<Control-y>", self.redo_callback)
        
        
    def setup_page1(self):
        self.clear_root()

        frame = tk.Frame(self.root, bg="#ffffff", bd=2, relief=tk.RIDGE)
        frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        ttk.Label(frame, text="📁 Source Folder:").pack(pady=5)
        self.src_label = ttk.Label(frame, text=self.selected_source_folder or "Not Selected", foreground="gray")
        self.src_label.pack(pady=5)
        ttk.Button(frame, text="Select Source Folder", command=self.select_source_folder).pack(pady=5)
        ttk.Button(frame, text="Remove Source Folder", command=self.remove_source_folder).pack(pady=5)

        ttk.Label(frame, text="📂 Target Folder:").pack(pady=15)
        self.tgt_label = ttk.Label(frame, text=self.selected_target_folder or "Not Selected", foreground="gray" )
        self.tgt_label.pack(pady=5)
        ttk.Button(frame, text="Select Target Folder", command=self.select_target_folder).pack(pady=5)
        ttk.Button(frame, text="Remove Target Folder", command=self.remove_target_folder).pack(pady=5)

        ttk.Button(frame, text="✅ Done", command=self.on_done).pack(pady=30)

    def setup_page2(self):
        self.clear_root()

        back_btn = ttk.Button(self.root, text="🔙 Back", command=self.setup_page1)
        back_btn.pack(anchor='nw', padx=10, pady=10)
        # Preserve paths in case user returns
        self.selected_source_folder = self.source_folder
        self.selected_target_folder = self.target_folder
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
        self.canvas.bind("<Button-3>", self.delete_annotation)

        self.rect_start = None
        self.current_rect = None

        nav_frame = tk.Frame(self.root, bg="#d9ecff")
        nav_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)

        # Left-side controls
        left_frame = tk.Frame(nav_frame, bg="#d9ecff")
        left_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(left_frame, text="◀ Previous", command=self.prev_image).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_frame, text="🧹 Clear", command=self.clear_current_annotations).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_frame, text="Undo", command=self.undo_callback).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_frame, text="Redo", command=self.redo_callback).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_frame, text="Next ▶", command=self.next_image).pack(side=tk.LEFT, padx=(5, 0))

        # Center: filename
        self.file_name_label = ttk.Label(nav_frame, text="")
        self.file_name_label.pack(side=tk.LEFT, expand=True)

        # Right-side: stats
        self.stats_label = ttk.Label(nav_frame, text="", font=('Helvetica', 10, 'italic'))
        self.stats_label.pack(side=tk.RIGHT, padx=10)
        self.root.bind("<Control-z>", self.undo_callback)
        self.root.bind("<Control-y>", self.redo_callback)

        self.display_image()
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.root.after(100, self.display_image)
    def delete_annotation(self, event):
        x_click, y_click = event.x, event.y
        filename = self.display_image_list[self.current_image_index]
        if filename in self.annotations:
            updated_annots = []
            deleted = False
            for annot in self.annotations[filename]:
                x0, y0, x1, y1, crop, category, name, stage = annot
                
                if x0 <= x_click <= x1 and y0 <= y_click <= y1 and not deleted:
                    deleted = True
                    continue  # skip this one
                updated_annots.append(annot)
            if deleted:
                self.annotations[filename] = updated_annots
                self.display_image()

    def clear_current_annotations(self):
        if not self.display_image_list:
            return

        filename = self.display_image_list[self.current_image_index]

        # Delete image and text files from all known category/name/stage folders
        for crop in getattr(self, 'crops', []):
            crop_path = os.path.join(self.target_folder, crop)
            if not os.path.exists(crop_path):
                continue

            for category in os.listdir(crop_path):
                category_path = os.path.join(crop_path, category)
                if not os.path.isdir(category_path):
                    continue

                for name in os.listdir(category_path):
                    name_path = os.path.join(category_path, name)
                    if not os.path.isdir(name_path):
                        continue

                    for stage in os.listdir(name_path):
                        stage_path = os.path.join(name_path, stage)
                        images_path = os.path.join(stage_path, 'images')
                        texts_path = os.path.join(stage_path, 'text_files')

                        # Remove the image file
                        if os.path.exists(images_path):
                            img_file_path = os.path.join(images_path, filename)
                            if os.path.exists(img_file_path):
                                os.remove(img_file_path)

                        # Remove the text file
                        if os.path.exists(texts_path):
                            txt_file_path = os.path.join(texts_path, os.path.splitext(filename)[0] + ".txt")
                            if os.path.exists(txt_file_path):
                                os.remove(txt_file_path)

        # Remove annotations from memory
        if filename in self.annotations:
            del self.annotations[filename]

        # Remove associated CSV entries
        self.csv_data = [row for row in self.csv_data if not row[0].endswith(filename)]

        self.display_image()


    def clear_root(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def select_source_folder(self):
        
        folder = filedialog.askdirectory()
        if folder:
            self.selected_source_folder = folder
            self.source_folder = folder
            self.src_label.config(text=folder)

    def remove_source_folder(self):
        self.selected_source_folder = None
        self.source_folder = None
        self.src_label.config(text="Not Selected")

    def select_target_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_target_folder = folder
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
        self.selected_target_folder = None
        self.target_folder = None
        self.tgt_label.config(text="Not Selected")

    def on_done(self):
        if not self.selected_source_folder or not self.selected_target_folder:
            messagebox.showerror("Error", "Please select both source and target folders.")
            return
        self.source_folder = self.selected_source_folder
        self.target_folder = self.selected_target_folder
        self.setup_page2()
        
    def display_image(self):
        self.canvas.delete("all")
        for label in self.annotation_labels:
            self.canvas.delete(label)
        self.annotation_labels.clear()

        if not self.display_image_list:
            self.file_name_label.config(text="No images to display")
            return

        image_path = os.path.join(self.source_folder, self.display_image_list[self.current_image_index])
        self.current_image = Image.open(image_path)

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width, canvas_height = 800, 600  # Default fallback
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
                x0, y0, x1, y1, crop, category, name, stage = ann
                label_str = f"{crop} | {category} | {name} | {stage}"
                rect_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline='red', width=2)
                text_id = self.canvas.create_text(x0 + 5, y0 - 15, anchor="nw", fill="red", text=label_str, font=('Arial', 10, 'bold'))
                self.annotation_labels.extend([rect_id, text_id])

    
        self.update_stats()


    def update_stats(self):
        total_images = len(self.image_list)
        remaining = len(self.display_image_list)
        completed = total_images - remaining

        label_count = {}
        for anns in self.annotations.values():
            for ann in anns:
                label = f"{ann[4]}:{ann[5]}"
                label_count[label] = label_count.get(label, 0) + 1

        stats = f"✔ {completed}/{total_images} | Labels: {len(label_count)}"
        self.stats_label.config(text=stats)

    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.display_image()

    def next_image(self):
        if self.current_image_index < len(self.display_image_list) - 1:
            self.current_image_index += 1
            self.display_image()

    def on_press(self, event):
        self.rect_start = (event.x, event.y)
        self.current_rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red')
        self.last_drawn_rect = self.current_rect

    def on_drag(self, event):
        if self.current_rect:
            self.canvas.coords(self.current_rect, self.rect_start[0], self.rect_start[1], event.x, event.y)

    def on_release(self, event):
        x0, y0 = self.rect_start
        x1, y1 = event.x, event.y
        self.show_popup(min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1))
        
    def update_folder_options_from_target(self):
        crops, names = set(), set()
        category_stage_map = {}
        user_categories = set()

        if not os.path.exists(self.target_folder):
            return

        for crop in os.listdir(self.target_folder):
            crop_path = os.path.join(self.target_folder, crop)
            if not os.path.isdir(crop_path):
                continue
            crops.add(crop)

            for category in os.listdir(crop_path):
                category_path = os.path.join(crop_path, category)
                if not os.path.isdir(category_path):
                    continue

                user_categories.add(category.lower())  # Save all found categories

                for name in os.listdir(category_path):
                    name_path = os.path.join(category_path, name)
                    if not os.path.isdir(name_path):
                        continue
                    names.add(name)

                    for stage in os.listdir(name_path):
                        if not os.path.isdir(os.path.join(name_path, stage)):
                            continue
                        if category.lower() not in category_stage_map:
                            category_stage_map[category.lower()] = set()
                        category_stage_map[category.lower()].add(stage)

        # Save unique values
        self.crops = sorted(set(getattr(self, 'crops', [])) | crops)
        self.names = sorted(set(getattr(self, 'names', [])) | names)

        self.category_stage_map = {
            k.lower(): sorted(v) for k, v in category_stage_map.items()
        }

        # Define default categories
        default_categories = {'pest', 'disease', 'deficiency', 'weed'}
        self.categories_from_folders = sorted(default_categories | user_categories)
    


    def show_popup(self, x0, y0, x1, y1):
        self.update_folder_options_from_target()

        stage_options = {
            'pest': ['Larvae or instar', 'Egg', 'Adult', 'Other'],
            'disease': ['Leaf', 'Stem', 'Fruit', 'Root', 'Seed', 'Other'],
            'deficiency': ['Nitrogen', 'Phosphorus', 'Potassium', 'Calcium', 'Magnesium', 'Sulfur', 'Chloride', 'Iron',
                        'Boron', 'Manganese', 'Zinc', 'Copper', 'Molybdenum', 'Nickel', 'Other'],
            'weed': ['Broad leaf', 'Narrow leaf', 'Other'],
            'others': ['Other']
        }

        # Popup Step 1: Crop, Category, Name
        popup1 = tk.Toplevel(self.root)
        popup1.title("📝 Annotation - Step 1")
        popup1.configure(bg="#f7fbff")

        ttk.Label(popup1, text="Crop:", background="#f7fbff", font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
        crop_entry = AutoCompleteEntry(popup1, getattr(self, 'crops', []))
        crop_entry.insert(0, self.last_crop)
        crop_entry.pack(padx=10, pady=(0, 10))

        category_var = tk.StringVar(value=self.last_category)
        other_category_var = tk.StringVar()

        ttk.Label(popup1, text="Category:", background="#f7fbff", font=('Arial', 10, 'bold')).pack(anchor='w', padx=10)
        categories = self.categories_from_folders or ['pest', 'disease', 'deficiency', 'weed', 'others']
        sorted_categories = sorted([cat for cat in categories if cat.lower() != 'others']) + ['others']

        category_frame = tk.Frame(popup1, bg="#f7fbff")
        category_frame.pack(anchor='w', padx=20)

        other_category_entry = ttk.Entry(category_frame, textvariable=other_category_var)
        other_category_entry.pack_forget()  # Hide initially

        def update_category_input(*args):
            if category_var.get() == 'others':
                other_category_entry.pack(pady=(5,0), padx=30, anchor='w')
            else:
                other_category_entry.pack_forget()

        category_var.trace_add('write', update_category_input)

        for cat in sorted_categories:
            ttk.Radiobutton(category_frame, text=cat.capitalize(), variable=category_var, value=cat.lower()).pack(anchor='w')
        
        ttk.Label(popup1, text="Name:", background="#f7fbff", font=('Arial', 10, 'bold')).pack(anchor='w', padx=10)
        name_entry = AutoCompleteEntry(popup1, self.names)
        name_entry.insert(0, self.last_name)
        name_entry.pack(padx=10, pady=(0, 10))

        def next_step():
            
            
            
            crop = crop_entry.get().strip()
            category = category_var.get().strip()
            if category == 'others':
                category = other_category_var.get().strip()
            name = name_entry.get().strip()
      

            if not crop or not category or not name:
                messagebox.showerror("Error", "Please fill all fields before continuing.")
                return
            
            self.last_crop = crop
            self.last_category = category
            self.last_name = name

            popup1.destroy()

            # Popup Step 2: Stage
            popup2 = tk.Toplevel(self.root)
            popup2.title("📝 Annotation - Step 2: Stage")
            popup2.configure(bg="#f7fbff")
            def go_back_to_popup1():
                popup2.destroy()
                self.show_popup(x0, y0, x1, y1)  # Reopen from scratch with preserved bounding box

            ttk.Button(popup2, text="🔙 Back", command=go_back_to_popup1).pack(anchor='nw', padx=10, pady=10)


            
            ttk.Label(popup2, text="Stage:", background="#f7fbff", font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

            stage_var = tk.StringVar()
            other_stage_var = tk.StringVar()
            stage_frame = tk.Frame(popup2, bg="#f7fbff")
            stage_frame.pack()

            def render_stage_options():
                for widget in stage_frame.winfo_children():
                    widget.destroy()

                defaults = {
                    'pest': ['Larvae|instar', 'Egg', 'Adult', 'Other'],
                    'disease': ['Leaf', 'Stem', 'Fruit', 'Root', 'Seed', 'Other'],
                    'deficiency': ['Nitrogen', 'Phosphorus', 'Potassium', 'Calcium', 'Magnesium', 'Sulfur', 'Chloride',
                                'Iron', 'Boron', 'Manganese', 'Zinc', 'Copper', 'Molybdenum', 'Nickel', 'Other'],
                    'weed': ['Broad leaf', 'Narrow leaf', 'Other'],
                    'others': ['Other']
                }

                default_opts = defaults.get(category.lower(), ['Other'])
                scanned_opts = self.category_stage_map.get(category.lower(), set())
                options = list(set(default_opts) | set(scanned_opts))

                options_sorted = sorted([opt for opt in options if opt.lower() != 'other']) + ['Other']

                other_stage_entry = ttk.Entry(stage_frame, textvariable=other_stage_var)
                other_stage_entry.pack_forget()

                def update_stage_input(*args):
                    if stage_var.get() == 'other':
                        other_stage_entry.pack(pady=5, padx=10, anchor='w')
                    else:
                        other_stage_entry.pack_forget()

                stage_var.trace_add('write', update_stage_input)

                for opt in options_sorted:
                    ttk.Radiobutton(stage_frame, text=opt, variable=stage_var, value=opt.lower()).pack(anchor='w')

            render_stage_options()

            def save_annotation():
                stage = other_stage_var.get().strip() if stage_var.get() == 'other' else stage_var.get().strip()
                if not stage:
                    messagebox.showerror("Error", "Please specify a stage.")
                    return

                img_path = os.path.join(self.target_folder, crop, category, name, stage, 'images')
                txt_path = os.path.join(self.target_folder, crop, category, name, stage, 'text_files')
                os.makedirs(img_path, exist_ok=True)
                os.makedirs(txt_path, exist_ok=True)

                filename = self.display_image_list[self.current_image_index]
                if filename not in self.annotations:
                    self.annotations[filename] = []

                self.annotations[filename].append((x0, y0, x1, y1, crop, category, name, stage))
                

                img_name = f"{len(os.listdir(img_path)):04d}.jpg"
                img_save_path = os.path.join(img_path, img_name)
                self.current_image.load()
                cv2_img = cv2.cvtColor(np.array(self.current_image), cv2.COLOR_RGB2BGR)
                cv2.imwrite(img_save_path, cv2_img)

                txt_name = img_name.replace('.jpg', '.txt')
                txt_save_path = os.path.join(txt_path, txt_name)
                with open(txt_save_path, 'a') as f:
                    f.write(f"{x0},{y0},{x1},{y1}\n")
                
                

                self.csv_data.append([
                    os.path.join(self.source_folder, filename),
                    img_save_path, crop, category, name, stage, x0, y0, x1, y1
                ])
                action = {
                    "filename": filename,
                    "annotation": (x0, y0, x1, y1, crop, category, name, stage),
                    "img_path": img_save_path,
                    "txt_path": txt_save_path,
                    "csv_index": len(self.csv_data) - 1  # Last added row
                }
                self.undo_stack.append(action)
                self.redo_stack.clear()

                popup2.destroy()
                self.display_image()

            btn_frame = tk.Frame(popup2, bg="#f7fbff")
            btn_frame.pack(pady=10)
            ttk.Button(btn_frame, text="OK", command=save_annotation).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text="Cancel", command=lambda: popup2.destroy()).pack(side=tk.RIGHT, padx=10)

        ttk.Button(popup1, text="Next", command=next_step).pack(pady=10)

    def undo_callback(self, event=None):
        if not self.undo_stack:
            return

        action = self.undo_stack.pop()
        self.redo_stack.append(action)

        filename = action["filename"]
        ann = action["annotation"]
        img_path = action["img_path"]
        txt_path = action["txt_path"]
        csv_index = action["csv_index"]

        # Remove annotation from self.annotations
        if filename in self.annotations:
            if ann in self.annotations[filename]:
                self.annotations[filename].remove(ann)

        # Remove saved image
        if os.path.exists(img_path):
            os.remove(img_path)

        # Remove corresponding text line
        if os.path.exists(txt_path):
            with open(txt_path, 'r') as f:
                lines = f.readlines()
            with open(txt_path, 'w') as f:
                for line in lines:
                    if line.strip() != f"{ann[0]},{ann[1]},{ann[2]},{ann[3]}":
                        f.write(line)

        # Remove row from CSV
        if 0 <= csv_index < len(self.csv_data):
            self.csv_data[csv_index] = None  # Mark for removal
        self.csv_data = [row for row in self.csv_data if row is not None]

        self.display_image()
    def redo_callback(self, event=None):
        if not self.redo_stack:
            return

        action = self.redo_stack.pop()
        self.undo_stack.append(action)

        filename = action["filename"]
        ann = action["annotation"]
        img_path = action["img_path"]
        txt_path = action["txt_path"]
        csv_index = action["csv_index"]
        crop, category, name, stage = ann[4], ann[5], ann[6], ann[7]

        # Reinsert annotation
        if filename not in self.annotations:
            self.annotations[filename] = []
        self.annotations[filename].append(ann)

        # Redraw image and re-save it
        self.current_image.load()
        cv2_img = cv2.cvtColor(np.array(self.current_image), cv2.COLOR_RGB2BGR)
        os.makedirs(os.path.dirname(img_path), exist_ok=True)
        cv2.imwrite(img_path, cv2_img)

        # Re-add bounding box to text file
        os.makedirs(os.path.dirname(txt_path), exist_ok=True)
        with open(txt_path, 'a') as f:
            f.write(f"{ann[0]},{ann[1]},{ann[2]},{ann[3]}\n")

        # Re-add CSV row
        self.csv_data.append([
            os.path.join(self.source_folder, filename),
            img_path, crop, category, name, stage, ann[0], ann[1], ann[2], ann[3]
        ])

        self.display_image()


    def update_autocomplete(self, combobox, options):
        value = combobox.get()
        cursor_pos = combobox.index(tk.INSERT)
        filtered = [item for item in options if value.lower() in item.lower()]
        combobox['values'] = filtered
        combobox.delete(0, tk.END)
        combobox.insert(0, value)
        combobox.icursor(cursor_pos)

    def on_exit(self): 
        cleaned_csv = [row for row in self.csv_data if row is not None]
        if cleaned_csv:
            csv_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                title="Save CSV File As",
                initialfile="annotations.csv"
            )
            if csv_path:
                with open(csv_path, "w", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["Source Path", "Saved Image Path", "Crop", "Category", "Name", "Stage", "x0", "y0", "x1", "y1"])
                    writer.writerows(cleaned_csv)
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = AnnotationTool(root)
    root.mainloop()

