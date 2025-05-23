from tkinter import filedialog, messagebox, ttk
import tkinter as tk
from PIL import Image, ImageTk
import cv2
import shutil

import os
import numpy as np
import json
from tkinter import messagebox
from copy import deepcopy
import threading
from datetime import datetime
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

        self.listbox.place(x= self.winfo_rootx() - self.master.winfo_rootx(),
                           y= self.winfo_rooty() - self.master.winfo_rooty() + self.winfo_height(),
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
    def add_suggestion(self, new_item):
        if new_item not in self.suggestion_list:
            self.suggestion_list.append(new_item)
            self.suggestion_list.sort()

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
        self.undo_file = os.path.join(os.path.dirname(__file__), "undo_stack.json")
        self.redo_file = os.path.join(os.path.dirname(__file__), "redo_stack.json")
        

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
        self.crops =[]
        self.undo_stack = []
        self.redo_stack = []
        self.box_index_counter = 1
        self.categories = []
        self.names = []
        self.last_drawn_rect = None
        self.annotation_labels = []
        self.image_counter_label = ttk.Label()
        self.category_stage_map = {
            'healthy': set(['Healthy']),
            'pest': set(['Larvae or instar', 'Egg', 'Adult', 'Other']),
            'disease': set(['Leaf', 'Stem', 'Fruit', 'Root', 'Seed', 'Other']),
            'deficiency': set(['Nitrogen', 'Phosphorus', 'Potassium', 'Calcium', 'Magnesium', 'Sulfur', 'Chloride','Iron', 'Boron', 'Manganese', 'Zinc', 'Copper', 'Molybdenum', 'Nickel', 'Other']),
            'weed': set(['Broad leaf', 'Narrow leaf', 'Other']),
            'others': set(['Other'])
        }
        self.categories = ['healthy', 'pest', 'disease', 'deficiency', 'weed', 'others']

        self.setup_page1()
        self.root.bind("<Control-z>", self.undo_action)
        self.root.bind("<Control-y>", self.redo_action)
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)  
    
    def setup_page1(self):
        self.clear_root()
        frame = tk.Frame(self.root, bg="#ffffff", bd=2, relief=tk.RIDGE)
        frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        ttk.Label(frame, text="📁 Source Folder:").pack(pady=5)
        self.src_label = ttk.Label(frame, text=self.selected_source_folder or "Not Selected", foreground="gray")
        self.src_label.pack(pady=5)
        ttk.Button(frame, text="Select Source Folder", command=self.select_source_folder).pack(pady=5)
        ttk.Button(frame, text="Remove Source Folder", command=self.remove_source_folder).pack(pady=5)
        ttk.Button(frame, text="✅ Done", command=self.on_done).pack(pady=30)
        
        
        
    def save_annotations_to_json(self):
        project_folder_path = os.path.join(os.path.dirname(self.source_folder), "annotations.json")

        # Load existing annotations if available
        if os.path.exists(project_folder_path):
            with open(project_folder_path, 'r') as f:
                try:
                    json_data = json.load(f)
                except json.JSONDecodeError:
                    json_data = {}
        else:
            json_data = {}

        # Get the next available image index by checking existing keys
        existing_indices = [int(k) for k in json_data.keys()]
        image_index = max(existing_indices) + 1 if existing_indices else 1
        box_index = 1  # Global box index

        final_folder_name = os.path.basename(self.source_folder)

        for filename in sorted(self.annotations.keys()):
            # Build custom image path
            rel_path = os.path.join("Project_Folder", final_folder_name, filename).replace("\\", "/")
            image_entry = {
                "path": rel_path,
                "bounding_and_label": []
            }

            for ann in self.annotations[filename]:
                x0, y0, x1, y1, crop, category, name, stage = ann
                image_entry["bounding_and_label"].append({
                    "index": box_index,
                    "x0": x0,
                    "y0": y0,
                    "x1": x1,
                    "y1": y1,
                    "crop": crop,
                    "category": category,
                    "name": name,
                    "stage": stage
                })
                box_index += 1

            json_data[str(image_index)] = image_entry
            image_index += 1

        # Save the merged annotations
        with open(project_folder_path, 'w') as f:
            json.dump(json_data, f, indent=4)

            
    def load_stack_file(self, filename):
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}



    def save_stack_file(self, filename, stack_dict):
        with open(filename, 'w') as f:
            json.dump(stack_dict, f, indent=4)


    def load_annotations_from_json(self):
        self.annotations = {}  # Reset current annotations

        if not self.source_folder:
            return

        parent_dir = os.path.dirname(self.source_folder)
        json_path = os.path.join(parent_dir, "annotations.json")

        if not os.path.exists(json_path):
            return  # Nothing to load

        try:
            if os.path.getsize(json_path) == 0:
                print("Empty annotations.json file. Skipping load.")
                return

            with open(json_path, 'r') as f:
                json_data = json.load(f)
            
            # Compare final folder name to ensure it's for the correct project
            final_folder_name = os.path.basename(self.source_folder)

            for entry in json_data.values():
                image_path = entry["path"]
                parts = image_path.split("/")  # Expecting format: Project_Folder/final_folder/filename
                if len(parts) >= 3 and parts[0] == "Project_Folder" and parts[1] == final_folder_name:
                    filename = parts[2]
                    if filename in self.image_list:
                        self.annotations.setdefault(filename, [])
                        for bbox in entry["bounding_and_label"]:
                            self.annotations[filename].append((
                                bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"],
                                bbox["crop"], bbox["category"], bbox["name"], bbox["stage"]
                            ))
        except Exception as e:
            print(f"Error loading annotations: {e}")
    def zoom_in(self):
        self.zoom_level *= 1.2
        self.display_image()

    def zoom_out(self):
        self.zoom_level /= 1.2
        self.display_image()
        
    def setup_page2(self):
        self.clear_root()
        self.image_counter_label = ttk.Label(
        self.root
        )
        self.folder_key = os.path.basename(self.source_folder)

        # Load global stacks from JSON
        self.undo_dict = self.load_stack_file(self.undo_file)
        self.redo_dict = self.load_stack_file(self.redo_file)

        # Load current folder's stack
        self.undo_stack = self.undo_dict.get(self.folder_key, [])
        self.redo_stack = self.redo_dict.get(self.folder_key, [])
        self.image_counter_label.pack(side="top", anchor="ne", pady=5) 
        back_btn = ttk.Button(self.root, text="🔙 Back", command=self.back_to_page1)
        back_btn.pack(anchor='nw', padx=10, pady=10)
        # Preserve paths in case user returns
        self.selected_source_folder = self.source_folder
        self.image_list = sorted([f for f in os.listdir(self.source_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))])
        self.display_image_list = self.image_list.copy()
        self.annotation_labels = []  # Needed to manage canvas labels
    
        self.load_annotations_from_json()
        # Create scrollable canvas frame
        canvas_frame = tk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.h_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.v_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas = tk.Canvas(canvas_frame, cursor="cross", bg="#ffffff",
                                xscrollcommand=self.h_scrollbar.set,
                                yscrollcommand=self.v_scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.h_scrollbar.config(command=self.canvas.xview)
        self.v_scrollbar.config(command=self.canvas.yview)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.delete_annotation)
        self.canvas.bind("<Control-MouseWheel>", self.zoom_with_mousewheel)
        self.rect_start = None
        self.current_rect = None
        self.zoom_level = 1.0
        nav_frame = tk.Frame(self.root, bg="#d9ecff")
        nav_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)

        # Left-side controls
        left_frame = tk.Frame(nav_frame, bg="#d9ecff")
        left_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(left_frame, text="◀ Previous", command=self.prev_image).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_frame, text="🧹 Clear", command=self.clear_current_annotations).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_frame, text="Undo", command=self.undo_action).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_frame, text="Redo", command=self.redo_action).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(left_frame, text="➕ Zoom In", command=self.zoom_in).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_frame, text="➖ Zoom Out", command=self.zoom_out).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_frame, text="Next ▶", command=self.next_image).pack(side=tk.LEFT, padx=(5, 0))

        # Center: filename
        self.file_name_label = ttk.Label(nav_frame, text="")
        self.file_name_label.pack(side=tk.LEFT, expand=True)

        # Right-side: stats
        self.stats_label = ttk.Label(nav_frame, text="", font=('Helvetica', 10, 'italic'))
        self.stats_label.pack(side=tk.RIGHT, padx=10)
        
        self.root.bind("<Control-z>", self.undo_action)
        self.root.bind("<Control-y>", self.redo_action)

        # Load last index if exists
        session_path = os.path.join(".session", "session.json")
        folder_key = os.path.basename(self.source_folder)
        self.current_image_index = 0  # Default

        if os.path.exists(session_path):
            try:
                with open(session_path, "r") as f:
                    session_data = json.load(f)
                    self.current_image_index = session_data.get(folder_key, 0)
            except json.JSONDecodeError:
                self.current_image_index = 0
        
        self.display_image()
                
    def back_to_page1(self):
        self.save_annotations_to_json()  # Save annotations before leaving
        # Save current image index to session file
        folder_key = os.path.basename(self.selected_source_folder)
        session_path = os.path.join(".session", "session.json")
        os.makedirs(".session", exist_ok=True)

        session_data = {}
        if os.path.exists(session_path):
            with open(session_path, "r") as f:
                try:
                    session_data = json.load(f)
                except json.JSONDecodeError:
                    session_data = {}

        session_data[folder_key] = self.current_image_index

        with open(session_path, "w") as f:
            json.dump(session_data, f, indent=2)

        self.setup_page1()

    
    
    def zoom_with_mousewheel(self, event):
        if event.delta > 0:
            self.zoom_level *= 1.1  # Zoom in
        else:
            self.zoom_level /= 1.1  # Zoom out
        self.display_image()

    
    
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
                self.save_annotations_to_json()
                
    def clear_current_annotations(self):
        if not self.display_image_list:
            return
        filename = self.display_image_list[self.current_image_index]
                # Remove annotations from memory
        if filename in self.annotations:
            cleared_annotations = self.annotations[filename]
            source_image_path = os.path.join(self.source_folder, filename)
            box_index = len(self.annotations[filename]) - 1 
            self.redo_stack.append({
                "filename": filename,
                "annotations": cleared_annotations,
                "source_image_path": source_image_path,
                "box_index": box_index# Save entire list
            })
            del self.annotations[filename]
        self.save_annotations_to_json()
        self.display_image()
        
    def clear_root(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def select_source_folder(self):
        new_folder = filedialog.askdirectory()
        self.source_folder = new_folder
        self.selected_source_folder = new_folder
        self.source_folder_path =new_folder# Add this line
        self.src_label.config(text=new_folder)
            

    def remove_source_folder(self):
        self.selected_source_folder = None
        self.source_folder = None
        self.source_folder_path  = None
        self.src_label.config(text="Not Selected")
        
    def on_done(self):
        if not self.selected_source_folder :
            messagebox.showerror("Error", "Please select source  folders.")
            return
        self.source_folder = self.selected_source_folder
        self.folder_key = os.path.basename(self.source_folder)

        # Load undo/redo stacks from JSON file
        self.undo_dict = self.load_stack_file(self.undo_file)
        self.redo_dict = self.load_stack_file(self.redo_file)

        # Get stacks for current folder
        self.undo_stack = self.undo_dict.get(self.folder_key, [])
        self.redo_stack = self.redo_dict.get(self.folder_key, [])

        
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

        img_width, img_height = self.current_image.size
        zoomed_width = int(img_width * self.zoom_level)
        zoomed_height = int(img_height * self.zoom_level)
        resized_image = self.current_image.resize((zoomed_width, zoomed_height), Image.LANCZOS)

        self.tk_image = ImageTk.PhotoImage(resized_image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        self.canvas.config(scrollregion=(0, 0, zoomed_width, zoomed_height))

        self.file_name_label.config(text=self.display_image_list[self.current_image_index])

        filename = self.display_image_list[self.current_image_index]
        if filename in self.annotations:
            for ann in self.annotations[filename]:
                x0, y0, x1, y1, crop, category, name, stage = ann
                zx0, zy0, zx1, zy1 = [coord * self.zoom_level for coord in (x0, y0, x1, y1)]
                label_str = f"{crop} | {category} | {name} | {stage}"
                rect_id = self.canvas.create_rectangle(zx0, zy0, zx1, zy1, outline='red', width=2)
                text_id = self.canvas.create_text(zx0 + 5, zy0 - 15, anchor="nw", fill="red", text=label_str, font=('Arial', 10, 'bold'))
                self.annotation_labels.extend([rect_id, text_id])

        self.update_stats()
    def update_stats(self): 
        total_images = len(self.image_list)
        completed = self.current_image_index + 1  # Number of images already viewed (1-based)
        remaining = total_images - completed

        label_count = {}
        for anns in self.annotations.values():
            for ann in anns:
                label = f"{ann[4]}:{ann[5]}"
                label_count[label] = label_count.get(label, 0) + 1

        # Count bounding boxes in current image
        current_filename = self.display_image_list[self.current_image_index]
        num_boxes = len(self.annotations.get(current_filename, []))

        stats = f"{completed}/{total_images} | Boxes in image: {num_boxes} | Unique Labels: {len(label_count)}"
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
        
        self.unsaved_changes = True
        self.rect_start_canvas = (event.x, event.y)  # Store as-is for drawing
        self.current_rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red')
        self.last_drawn_rect = self.current_rect

    def on_drag(self, event):
        if self.current_rect and self.rect_start_canvas:
            x0, y0 = self.rect_start_canvas
            x1, y1 = event.x, event.y
            self.canvas.coords(self.current_rect, x0, y0, x1, y1)
    def on_release(self, event):
        if self.rect_start_canvas:
            x0_canvas, y0_canvas = self.rect_start_canvas
            x1_canvas, y1_canvas = event.x, event.y

            # Convert back to image coordinates (not canvas)
            x0_img = x0_canvas / self.zoom_level
            y0_img = y0_canvas / self.zoom_level
            x1_img = x1_canvas / self.zoom_level
            y1_img = y1_canvas / self.zoom_level

            # Enforce minimum size in image scale
            if abs(x1_img - x0_img) > 10 / self.zoom_level and abs(y1_img - y0_img) > 10 / self.zoom_level:
                self.show_popup(x0_img, y0_img, x1_img, y1_img, self.current_rect)
            else:
                self.canvas.delete(self.current_rect)
                self.current_rect = None

            self.rect_start_canvas = None
            
            
    def show_popup(self, x0, y0, x1, y1, rect_id=None):
        
        stage_options = {
            "healthy":['Healthy'],
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

        def on_popup_close():
            if rect_id:  # If there's a rectangle ID, delete it
                self.canvas.delete(rect_id)
            popup1.destroy()
        
        popup1.protocol("WM_DELETE_WINDOW", on_popup_close)
        ttk.Label(popup1, text="Crop:", background="#f7fbff", font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
        crop_entry = AutoCompleteEntry(popup1, getattr(self, 'crops', []))
        crop_entry.pack(padx=10, pady=(0, 10))
        category_var = tk.StringVar()
        def update_name_field_visibility(*args):
            
            if category_var.get() == 'healthy':
                # Instead of pack_forget(), disable the widgets
                name_entry.config(state='disabled')  # Make entry non-editable
                name_label.config(state='disabled')  # Make label appear grayed out
            else:
                # Enable the widgets when not healthy
                name_entry.config(state='normal')
                name_label.config(state='normal')
                # Ensure they're properly packed
                name_label.pack(anchor='w', padx=10)
                name_entry.pack(padx=10, pady=(0, 10))


        category_var.trace_add('write', update_name_field_visibility)

        other_category_var = tk.StringVar()

        ttk.Label(popup1, text="Category:", background="#f7fbff", font=('Arial', 10, 'bold')).pack(anchor='w', padx=10)
        sorted_categories = sorted([cat for cat in self.categories if cat.lower() != 'others']) + ['others']

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
        
        name_label = ttk.Label(popup1, text="Name:", background="#f7fbff", font=('Arial', 10, 'bold'))
        name_label.pack(anchor='w', padx=10)
        name_entry = AutoCompleteEntry(popup1, self.names)
        
        name_entry.pack(padx=10, pady=(0, 10))

        def next_step():
            
            crop = crop_entry.get().strip()
            category = category_var.get().strip()
            if category == 'others':
                category = other_category_var.get().strip().lower()
                if category and category not in self.categories:
                    self.categories.append(category)
            if category == 'healthy':
                name= stage = "Healthy"
            else:
                name = name_entry.get().strip()


            if not crop or not category or (category != 'healthy' and not name):
                messagebox.showerror("Error", "Please fill all fields before continuing.")
                return

            # Update crops and names list if new
            if not hasattr(self, 'crops'):
                self.crops = []
            if not hasattr(self, 'names'):
                self.names = []

            if crop not in self.crops:
                self.crops.append(crop)
            if name not in self.names:
                self.names.append(name)

            # Save last used values
            self.last_crop = crop
            self.last_category = category
            self.last_name = name
            if category == 'healthy':
                # Add the annotation directly without second popup
                filename = self.display_image_list[self.current_image_index]
                source_image_path = os.path.join(self.source_folder_path, filename)
                if filename not in self.annotations:
                    self.annotations[filename] = []
                self.annotations[filename].append((x0, y0, x1, y1, crop, category, name, stage))

                action = {
                    "filename": filename,
                    "annotation": (x0, y0, x1, y1, crop, category, name, stage),
                    "source_image_path": source_image_path,
                    "box_index": len(self.annotations[filename]) - 1
                }
                self.undo_stack.append(action)
                self.redo_stack.clear()
                

                self.save_annotations_to_json()
                popup1.destroy()
                self.display_image()
                return
            popup1.destroy()
            
            # Popup Step 2: Stage
            popup2 = tk.Toplevel(self.root)
            popup2.title("📝 Annotation - Step 2: Stage")
            popup2.configure(bg="#f7fbff")
            
            def on_popup2_close():
                if rect_id:  # If there's a rectangle ID, delete it
                    self.canvas.delete(rect_id)
                popup2.destroy()
            
            popup2.protocol("WM_DELETE_WINDOW", on_popup2_close)
            
            
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
                    "healthy":['Healthy'],
                    'pest': ['Larvae or instar', 'Egg', 'Adult', 'Other'],
                    'disease': ['Leaf', 'Stem', 'Fruit', 'Root', 'Seed', 'Other'],
                    'deficiency': ['Nitrogen', 'Phosphorus', 'Potassium', 'Calcium', 'Magnesium', 'Sulfur', 'Chloride',
                                'Iron', 'Boron', 'Manganese', 'Zinc', 'Copper', 'Molybdenum', 'Nickel', 'Other'],
                    'weed': ['Broad leaf', 'Narrow leaf', 'Other'],
                    'others': ['Other']
                }

                default_opts = defaults.get(category.lower(), ['Other'])
                scanned_opts = self.category_stage_map.get(category.lower(), set())
                normalized_defaults = {opt.lower() for opt in default_opts}
                normalized_scanned = {opt.lower() for opt in scanned_opts}
                options = normalized_defaults | normalized_scanned
                sorted_opts = sorted([opt for opt in options if opt != 'other'])
                sorted_opts.append('other')
                
                other_stage_entry = ttk.Entry(stage_frame, textvariable=other_stage_var)
                other_stage_entry.pack_forget()

                def update_stage_input(*args):
                    if stage_var.get() == 'other':
                        other_stage_entry.pack(pady=5, padx=10, anchor='w')
                    else:
                        other_stage_entry.pack_forget()

                stage_var.trace_add('write', update_stage_input)

                for opt in sorted_opts:
                    display_text = opt.capitalize() if opt != 'other' else 'Other'
                    ttk.Radiobutton(stage_frame, text=display_text, variable=stage_var, value=opt).pack(anchor='w')
            render_stage_options()

            def save_annotation():
                if category == 'healthy':
                    stage = "Healthy"
                else:
                    stage = other_stage_var.get().strip().lower() if stage_var.get() == 'other' else stage_var.get().strip().lower()
                
                if category.lower() not in self.category_stage_map:
                    self.category_stage_map[category.lower()] = set()
                self.category_stage_map[category.lower()].add(stage)
                if not stage:
                    messagebox.showerror("Error", "Please specify a stage.")
                    return

                filename = self.display_image_list[self.current_image_index]
                source_image_path = os.path.join(self.source_folder_path, filename)
                if filename not in self.annotations:
                    self.annotations[filename] = []
                    
                self.annotations[filename].append((x0, y0, x1, y1, crop, category, name, stage))
                box_index = len(self.annotations[filename]) - 1 
                action = {
                    "filename": filename,
                    "annotation": (x0, y0, x1, y1, crop, category, name, stage),
                    "source_image_path": source_image_path,
                    "box_index": box_index
                }
                self.undo_stack.append(action)
                self.redo_stack.clear()
                if rect_id:
                    self.canvas.delete(rect_id)

                # Save after modification
                self.undo_dict[self.folder_key] = self.undo_stack
                self.redo_dict[self.folder_key] = self.redo_stack
                self.save_stack_file(self.undo_file, self.undo_dict)
                self.save_stack_file(self.redo_file, self.redo_dict)

                self.save_annotations_to_json()
                popup2.destroy()
                self.display_image()

            btn_frame = tk.Frame(popup2, bg="#f7fbff")
            btn_frame.pack(pady=10)
            ttk.Button(btn_frame, text="OK", command=save_annotation).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text="Cancel", command=on_popup2_close).pack(side=tk.RIGHT, padx=10)

        ttk.Button(popup1, text="Next", command=next_step).pack(pady=10)
        
    def undo_action(self, event=None):
        if not self.undo_stack:
            return

        # Find last undo action for current image
        for i in reversed(range(len(self.undo_stack))):
            if self.undo_stack[i]["filename"] == self.display_image_list[self.current_image_index]:
                last_action = self.undo_stack.pop(i)
                self.redo_stack.append(last_action)

                annotation_to_remove = last_action["annotation"]
                filename = last_action["filename"]

                if filename in self.annotations:
                    try:
                        self.annotations[filename].remove(annotation_to_remove)
                    except ValueError:
                        pass  # Already removed

                self.save_annotations_to_json()
                # Save after modification
                self.undo_dict[self.folder_key] = self.undo_stack
                self.redo_dict[self.folder_key] = self.redo_stack
                self.save_stack_file(self.undo_file, self.undo_dict)
                self.save_stack_file(self.redo_file, self.redo_dict)
                self.display_image()
                break
    
    def redo_action(self, event=None):
        if not self.redo_stack:
            return

        # Find last redo action for current image
        for i in reversed(range(len(self.redo_stack))):
            if self.redo_stack[i]["filename"] == self.display_image_list[self.current_image_index]:
                action = self.redo_stack.pop(i)
                self.undo_stack.append(action)

                filename = action["filename"]
                annotations_to_restore = action.get("annotations") or [action["annotation"]]

                if filename not in self.annotations:
                    self.annotations[filename] = []

                self.annotations[filename].extend(annotations_to_restore)

                self.save_annotations_to_json()
                # Save after modification
                self.undo_dict[self.folder_key] = self.undo_stack
                self.redo_dict[self.folder_key] = self.redo_stack
                self.save_stack_file(self.undo_file, self.undo_dict)
                self.save_stack_file(self.redo_file, self.redo_dict)
                self.display_image()
                break


    def on_exit(self): 
        if not self.selected_source_folder:
            self.root.destroy()
            return

        folder_key = os.path.basename(self.selected_source_folder)
        os.makedirs(".session", exist_ok=True)
        session_path = os.path.join(".session", "session.json")

        session_data = {}
        if os.path.exists(session_path):
            with open(session_path, "r") as f:
                try:
                    session_data = json.load(f)
                except json.JSONDecodeError:
                    session_data = {}

        session_data[folder_key] = self.current_image_index

        with open(session_path, "w") as f:
            json.dump(session_data, f, indent=2)

        self.save_annotations_to_json()

        if messagebox.askyesno("Exit", "Do you want to save and exit the application?"):
            self.save_annotations_to_json()
            self.root.destroy()
        else:
            return

        


if __name__ == '__main__':
    root = tk.Tk()
    app = AnnotationTool(root)
    root.mainloop() 