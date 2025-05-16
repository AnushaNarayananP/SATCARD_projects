import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from PIL import Image, ImageTk
import os
import csv
import shutil

class ImageAnnotationTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Annotation Tool")
        self.root.geometry("1200x800")
        self.setup_ui()
        self.image_list = []
        self.current_image_index = 0
        self.annotations = []
        self.target_folders = []
        self.annotation_csv = None
        self.annotation_index = 0
        self.tk_img = None
        self.drawn_boxes = []
        self.annotation_folder = None
        self.image_filenames = []
        self.current_bbox = None
        self.bbox_data = {}

    def setup_ui(self):
        self.left_frame = tk.Frame(self.root, width=900, height=800, bg='gray')
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.filename_label = tk.Label(self.left_frame, text="", bg='lightgray')
        self.filename_label.pack(fill=tk.X)

        self.canvas = tk.Canvas(self.left_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.start_bbox)
        self.canvas.bind("<B1-Motion>", self.draw_bbox)
        self.canvas.bind("<ButtonRelease-1>", self.end_bbox)

        self.right_frame = tk.Frame(self.root, width=300)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.folder_label = tk.Label(self.right_frame, text="Upload Target Folders")
        self.folder_label.pack()

        self.upload_btn = tk.Button(self.right_frame, text="Upload Folder", command=self.upload_folders)
        self.upload_btn.pack()

        self.remove_target_btn = tk.Button(self.right_frame, text="Remove Selected Folder", command=self.remove_selected_target_folder)
        self.remove_target_btn.pack()

        self.target_listbox = tk.Listbox(self.right_frame)
        self.target_listbox.pack()

        self.annotation_folder_label = tk.Label(self.right_frame, text="Upload Annotation Folder")
        self.annotation_folder_label.pack()

        self.annotation_btn = tk.Button(self.right_frame, text="Upload Annotation Folder", command=self.upload_annotation_folder)
        self.annotation_btn.pack()

        self.remove_annotation_btn = tk.Button(self.right_frame, text="Remove Annotation Folder", command=self.remove_annotation_folder)
        self.remove_annotation_btn.pack()

        self.upload_img_label = tk.Label(self.right_frame, text="Upload Multiple Images")
        self.upload_img_label.pack()

        self.image_select_btn = tk.Button(self.right_frame, text="Upload Images", command=self.select_images)
        self.image_select_btn.pack()

        self.image_listbox = tk.Listbox(self.right_frame)
        self.image_listbox.pack()

        self.csv_label = tk.Label(self.right_frame, text="Upload CSV")
        self.csv_label.pack()

        self.upload_csv_btn = tk.Button(self.right_frame, text="Upload CSV", command=self.upload_csv)
        self.upload_csv_btn.pack()

        self.csv_filename_label = tk.Label(self.right_frame, text="")
        self.csv_filename_label.pack()

        self.remove_csv_btn = tk.Button(self.right_frame, text="Remove CSV", command=self.remove_csv)
        self.remove_csv_btn.pack()

        self.delete_icon = tk.Button(self.canvas, text="X", command=self.delete_image)
        self.delete_icon.place(relx=0.95, rely=0.01)

        self.prev_btn = tk.Button(self.canvas, text="<", command=self.prev_image)
        self.prev_btn.place(relx=0.01, rely=0.5)

        self.next_btn = tk.Button(self.canvas, text=">", command=self.next_image)
        self.next_btn.place(relx=0.98, rely=0.5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def upload_folders(self):
        folder_path = filedialog.askdirectory(mustexist=True, title="Select Target Folder")
        if folder_path and folder_path not in self.target_folders:
            self.target_folders.append(folder_path)
            self.target_listbox.insert(tk.END, folder_path)
            os.makedirs(os.path.join(folder_path, "images"), exist_ok=True)
            os.makedirs(os.path.join(folder_path, "text_files"), exist_ok=True)

    def remove_selected_target_folder(self):
        selected = self.target_listbox.curselection()
        if selected:
            index = selected[0]
            folder = self.target_folders[index]
            self.target_folders.remove(folder)
            self.target_listbox.delete(index)

    def upload_annotation_folder(self):
        folder_path = filedialog.askdirectory(mustexist=True, title="Select Annotation Folder")
        if folder_path:
            self.annotation_folder = folder_path
            self.image_list = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                               if f.lower().endswith((".jpg", ".jpeg", ".png"))]
            self.image_filenames = [os.path.basename(path) for path in self.image_list]
            self.image_listbox.delete(0, tk.END)
            for name in self.image_filenames:
                self.image_listbox.insert(tk.END, name)
            self.current_image_index = 0
            self.display_image()

    def remove_annotation_folder(self):
        self.annotation_folder = None
        self.image_list = []
        self.image_filenames = []
        self.image_listbox.delete(0, tk.END)
        self.canvas.delete("all")

    def select_images(self):
        image_paths = filedialog.askopenfilenames(filetypes=[("Image files", "*.png;*.jpg;*.jpeg")])
        if image_paths:
            self.image_list.extend(image_paths)
            self.image_filenames.extend([os.path.basename(p) for p in image_paths])
            for name in [os.path.basename(p) for p in image_paths]:
                self.image_listbox.insert(tk.END, name)
            self.current_image_index = 0
            self.display_image()

    def upload_csv(self):
        csv_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if csv_path:
            self.annotation_csv = csv_path
            self.csv_filename_label.config(text=os.path.basename(csv_path))
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                self.annotation_index = sum(1 for _ in reader)

    def remove_csv(self):
        self.annotation_csv = None
        self.csv_filename_label.config(text="")

    def display_image(self):
        self.canvas.delete("all")
        self.drawn_boxes.clear()
        if self.image_list:
            image_path = self.image_list[self.current_image_index]
            self.filename_label.config(text=os.path.basename(image_path))
            image = Image.open(image_path)
            image = image.resize((900, 800))
            self.tk_img = ImageTk.PhotoImage(image)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
            filename = self.image_filenames[self.current_image_index]
            if filename in self.bbox_data:
                for bbox in self.bbox_data[filename]:
                    x0, y0, x1, y1, _ = bbox
                    box_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline="red", width=2)
                    self.drawn_boxes.append(box_id)
            self.delete_icon.lift()
            self.prev_btn.lift()
            self.next_btn.lift()

    def start_bbox(self, event):
        self.bbox_start = (event.x, event.y)
        self.current_bbox = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2)

    def draw_bbox(self, event):
        if self.current_bbox:
            self.canvas.coords(self.current_bbox, self.bbox_start[0], self.bbox_start[1], event.x, event.y)

    def end_bbox(self, event):
        x0, y0 = self.bbox_start
        x1, y1 = event.x, event.y
        if self.target_folders:
            dropdown = tk.Toplevel(self.root)
            dropdown.title("Select Target Folder Label")
            tk.Label(dropdown, text="Select target folder label:").pack()
            label_var = tk.StringVar(value=self.target_folders[0])
            combo = ttk.Combobox(dropdown, textvariable=label_var, values=self.target_folders)
            combo.pack()
            def on_submit():
                selection = label_var.get()
                response = messagebox.askyesnocancel("Save Bounding Box", f"Save this bounding box in: {selection}?")
                dropdown.destroy()
                if response is None:
                    self.canvas.delete(self.current_bbox)
                    self.current_bbox = None
                    return
                elif response:
                    filename = self.image_filenames[self.current_image_index]
                    if filename not in self.bbox_data:
                        self.bbox_data[filename] = []
                    self.bbox_data[filename].append((x0, y0, x1, y1, selection))
                    # Save text file
                    target_path = selection
                    text_folder = os.path.join(target_path, "text_files")
                    image_folder = os.path.join(target_path, "images")
                    idx = len(os.listdir(text_folder))
                    with open(os.path.join(text_folder, f"{idx}.txt"), 'w') as f:
                        f.write(f"{x0},{y0},{x1},{y1}\n")
                    image_src = self.image_list[self.current_image_index]
                    shutil.copy(image_src, os.path.join(image_folder, f"{idx}.jpg"))
                self.canvas.delete(self.current_bbox)
                self.current_bbox = None
            tk.Button(dropdown, text="OK", command=on_submit).pack()

    def next_image(self):
        if self.current_image_index < len(self.image_list) - 1:
            self.current_image_index += 1
            self.display_image()

    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.display_image()

    def delete_image(self):
        if self.image_list:
            del self.image_list[self.current_image_index]
            del self.image_filenames[self.current_image_index]
            self.image_listbox.delete(self.current_image_index)
            if self.current_image_index >= len(self.image_list):
                self.current_image_index = max(0, len(self.image_list) - 1)
            self.display_image()

    def on_close(self):
        if self.bbox_data:
            result = messagebox.askyesnocancel("Exit", "Do you want to download the CSV before closing?")
            if result is None:
                return
            elif result:
                dest_folder = filedialog.askdirectory(title="Select folder to save CSV")
                if dest_folder:
                    csv_path = os.path.join(dest_folder, "annotations.csv")
                    with open(csv_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(["path", "object name", "top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"])
                        for filename, boxes in self.bbox_data.items():
                            for box in boxes:
                                x0, y0, x1, y1, label = box
                                writer.writerow([filename, label, x0, y0, x1, y1])
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageAnnotationTool(root)
    root.mainloop()


