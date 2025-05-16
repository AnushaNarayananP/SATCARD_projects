import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
from PIL import Image, ImageTk
import shutil
import csv

class AnnotationTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Annotation Tool")

        self.image_folder = ""
        self.image_files = []
        self.current_image_index = 0
        self.annotations = {}  # image_filename: [ (x1, y1, x2, y2, crop, category, name, stage) ]

        self.crop_options = set()
        self.name_options = set()
        self.stage_options = {"Pest": ["Egg", "Larva", "Adult"],
                              "Disease": ["Early", "Mid", "Late"],
                              "Deficiency": ["Mild", "Moderate", "Severe"],
                              "Weed": ["Seedling", "Mature", "Flowering"],
                              "Others": []}

        self.initialize_ui()

    def initialize_ui(self):
        self.page1 = tk.Frame(self.root)
        self.page1.pack()

        tk.Label(self.page1, text="Select Image Folder").pack(pady=10)
        tk.Button(self.page1, text="Browse", command=self.browse_folder).pack()
        self.folder_label = tk.Label(self.page1, text="")
        self.folder_label.pack(pady=10)
        tk.Button(self.page1, text="Continue", command=self.load_images).pack()

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.image_folder = folder
            self.folder_label.config(text=self.image_folder)

    def load_images(self):
        if not self.image_folder:
            messagebox.showerror("Error", "Please select a folder first.")
            return

        for root_dir, dirs, files in os.walk(self.image_folder):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    full_path = os.path.join(root_dir, file)
                    self.image_files.append(full_path)

        if not self.image_files:
            messagebox.showerror("Error", "No images found in the selected folder.")
            return

        self.extract_existing_folders()
        self.show_annotation_page()

    def extract_existing_folders(self):
        for root_dir, dirs, files in os.walk(self.image_folder):
            parts = root_dir.replace(self.image_folder, "").strip(os.sep).split(os.sep)
            if len(parts) == 4:  # crop/category/name/stage
                crop, category, name, stage = parts
                self.crop_options.add(crop)
                self.name_options.add(name)

    def show_annotation_page(self):
        self.page1.pack_forget()
        self.page2 = tk.Frame(self.root)
        self.page2.pack()

        self.canvas = tk.Canvas(self.page2, width=800, height=600)
        self.canvas.grid(row=0, column=0, columnspan=4)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.prev_button = tk.Button(self.page2, text="Previous", command=self.show_previous_image)
        self.prev_button.grid(row=1, column=0)

        self.next_button = tk.Button(self.page2, text="Next", command=self.show_next_image)
        self.next_button.grid(row=1, column=1)

        self.clear_button = tk.Button(self.page2, text="Clear", command=self.clear_annotations)
        self.clear_button.grid(row=1, column=2)

        self.exit_button = tk.Button(self.page2, text="Exit", command=self.exit_tool)
        self.exit_button.grid(row=1, column=3)

        self.display_image()

    def display_image(self):
        self.canvas.delete("all")
        image_path = self.image_files[self.current_image_index]
        self.current_image = Image.open(image_path)
        self.tk_image = ImageTk.PhotoImage(self.current_image.resize((800, 600)))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        filename = os.path.basename(image_path)
        if filename in self.annotations:
            for box in self.annotations[filename]:
                x1, y1, x2, y2, crop, category, name, stage = box
                self.canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2)
                self.canvas.create_text(x1 + 5, y1 - 10, anchor="nw",
                                        text=f"{crop}/{category}/{name}/{stage}", fill="red")

    def on_canvas_click(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

    def on_canvas_release(self, event):
        end_x, end_y = event.x, event.y
        if abs(end_x - self.start_x) < 5 or abs(end_y - self.start_y) < 5:
            return
        self.show_annotation_popup(self.start_x, self.start_y, end_x, end_y)

    def show_annotation_popup(self, x1, y1, x2, y2):
        popup = tk.Toplevel(self.root)
        popup.title("Annotation Details")

        tk.Label(popup, text="Crop:").grid(row=0, column=0)
        crop_var = tk.StringVar()
        crop_entry = ttk.Combobox(popup, textvariable=crop_var)
        crop_entry['values'] = list(self.crop_options)
        crop_entry.grid(row=0, column=1)

        tk.Label(popup, text="Category:").grid(row=1, column=0)
        category_var = tk.StringVar(value="Pest")
        for i, val in enumerate(["Pest", "Disease", "Deficiency", "Weed", "Others"]):
            tk.Radiobutton(popup, text=val, variable=category_var, value=val).grid(row=1, column=i+1)

        tk.Label(popup, text="Name:").grid(row=2, column=0)
        name_var = tk.StringVar()
        name_entry = ttk.Combobox(popup, textvariable=name_var)
        name_entry['values'] = list(self.name_options)
        name_entry.grid(row=2, column=1)

        def on_next():
            popup.destroy()
            self.show_stage_popup(x1, y1, x2, y2, crop_var.get(), category_var.get(), name_var.get())

        tk.Button(popup, text="Next", command=on_next).grid(row=3, column=0, columnspan=2)

    def show_stage_popup(self, x1, y1, x2, y2, crop, category, name):
        popup = tk.Toplevel(self.root)
        popup.title("Stage")

        tk.Label(popup, text="Stage:").grid(row=0, column=0)
        stage_var = tk.StringVar()
        options = self.stage_options.get(category, [])

        if options:
            for i, val in enumerate(options):
                tk.Radiobutton(popup, text=val, variable=stage_var, value=val).grid(row=0, column=i+1)
        else:
            tk.Entry(popup, textvariable=stage_var).grid(row=0, column=1)

        def on_ok():
            stage = stage_var.get()
            filename = os.path.basename(self.image_files[self.current_image_index])
            self.annotations.setdefault(filename, []).append((x1, y1, x2, y2, crop, category, name, stage))
            self.crop_options.add(crop)
            self.name_options.add(name)
            self.save_annotation_file(filename, x1, y1, x2, y2, crop, category, name, stage)
            popup.destroy()
            self.display_image()

        tk.Button(popup, text="OK", command=on_ok).grid(row=1, column=0, columnspan=2)

    def save_annotation_file(self, filename, x1, y1, x2, y2, crop, category, name, stage):
        base_folder = os.path.join(self.image_folder, crop, category, name, stage)
        image_folder = os.path.join(base_folder, "images")
        text_folder = os.path.join(base_folder, "text_files")
        os.makedirs(image_folder, exist_ok=True)
        os.makedirs(text_folder, exist_ok=True)

        shutil.copy(self.image_files[self.current_image_index], os.path.join(image_folder, filename))

        with open(os.path.join(text_folder, filename + ".txt"), "a") as f:
            f.write(f"{x1},{y1},{x2},{y2},{crop},{category},{name},{stage}\n")

    def clear_annotations(self):
        filename = os.path.basename(self.image_files[self.current_image_index])
        if filename in self.annotations:
            for box in self.annotations[filename]:
                _, _, _, _, crop, category, name, stage = box
                base = os.path.join(self.image_folder, crop, category, name, stage)
                try:
                    os.remove(os.path.join(base, "images", filename))
                    os.remove(os.path.join(base, "text_files", filename + ".txt"))
                except FileNotFoundError:
                    pass
            del self.annotations[filename]
            self.display_image()

    def show_next_image(self):
        self.current_image_index = (self.current_image_index + 1) % len(self.image_files)
        self.display_image()

    def show_previous_image(self):
        self.current_image_index = (self.current_image_index - 1) % len(self.image_files)
        self.display_image()

    def exit_tool(self):
        with open(os.path.join(self.image_folder, "annotations_summary.csv"), "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["filename", "x1", "y1", "x2", "y2", "crop", "category", "name", "stage"])
            for filename, boxes in self.annotations.items():
                for box in boxes:
                    writer.writerow([filename, *box])
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = AnnotationTool(root)
    root.mainloop()
