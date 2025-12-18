# Copyright (c) 2025 Moveshelf
# See LICENSE file for details. 

# install required packages: pip install -r ../requirements.txt
import os, sys
parentFolder = os.path.dirname(os.path.dirname(__file__))
sys.path.append(parentFolder)

import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox

import batchUpload

'''
## Readme - General
The datastructure of Moveshelf is organized as follows:
* Project: Projects are the highest level and associated to a single organization in Moveshelf.
* Subjects: Each project contains a list of subjects. At project level, access to the Electronic Health Record (EHR) of a subject can be made.
* Sessions: A session contains the relevant information for a specific measurement session and is typically defined by the date of the measurement.
* Conditions: Conditions specify a group of trials that were performed within a session.
* Trials: Trials, aka clips, are containers used to store our data. It consists of metadata and 'Additional Data', where the actual data of a trial is stored.

## Instructions for this GUI example
This is a GUI script to handle the batchUpload module. It asks for a project name and a batch upload root folder,
where all subjects' datafolders should be. 
NOTE: Please refer to the batchUpload module for more detailed instructions.
NOTE: Defaults can be changed below. The placeholder text reflects this default setting.
If these defaults are set and you want to use them as inputs, you can Run the program immediately (also if they appear grey).

The GUI will give prompts when errors occur, as well as when the program has ended succesfully.
'''

# DEFAULTS to CHANGE
default_initialdir = './'  # Where the directory selector starts when clicking the 'Browse' button

default_subjectsfolder = '<yourRootFolderPath>'  # Batch root folder housing all subject folders
default_project = '<organizationName/projectName>'  # Moveshelf project name


# FUNCTIONS
def centerWindow(window):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (window.winfo_reqwidth() // 2)
    y = (screen_height // 2) - (window.winfo_reqheight() // 2)
    window.geometry(f"+{x}+{y}")

class PlaceholderEntry(tk.Entry):
    """Entry widget with placeholder text support"""
    def __init__(self, master=None, placeholder="PLACEHOLDER", default=None, color='grey', *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.placeholder = placeholder
        self.default = default if default is not None else placeholder
        self.placeholder_color = color
        self.default_fg_color = self['fg']

        self.bind("<FocusIn>", self._clear_placeholder)
        self.bind("<FocusOut>", self._add_placeholder)

        self._add_placeholder()

    def _clear_placeholder(self, event=None):
        if self['fg'] == self.placeholder_color:
            self.delete(0, tk.END)
            self['fg'] = self.default_fg_color

    def _add_placeholder(self, event=None):
        if not self.get():
            self.insert(0, self.placeholder)
            self['fg'] = self.placeholder_color

    def get_value(self):
        """Return actual value (default if placeholder shown)"""
        if self['fg'] == self.placeholder_color:
            return self.default
        return self.get()

class App:
    def __init__(self, root):
        self.root = root
        root.title("Batch Upload Subjects' data to Moveshelf")

        # Validation command bindings
        self.vcmd = (root.register(self.validate_entry), '%P')
        self.ivcmd = (root.register(self.on_invalid),)

        self.create_widgets()

    # --- BUILD GUI ---
    def create_widgets(self):
        # Moveshelf section
        self.upload_info_frame = tk.LabelFrame(self.root, text="Moveshelf options", bd=1)
        self.upload_info_frame.grid(row=0, column=0, columnspan=3, padx=20, pady=10)

        tk.Label(self.upload_info_frame, text="Project:").grid(row=0, column=0, sticky="e", padx=8, pady=5)
        self.project_entry = PlaceholderEntry(self.upload_info_frame, placeholder=default_project, default=default_project, width=40)
        self.project_entry.grid(row=0, column=1, sticky="w", padx=8, pady=5)

        # Input frame
        self.input_frame = tk.LabelFrame(self.root, text="Input", bd=1)
        self.input_frame.grid(row=1, column=0, sticky="w", padx=20, pady=10)

        placeholder_text = self.shorten_path(default_subjectsfolder) if os.path.isdir(default_subjectsfolder) else "Folder of subjects..."
        tk.Label(self.input_frame, text="Location of All Subjects' data folder to upload to Moveshelf:").grid(row=0, column=0, sticky="w", padx=8, pady=5)

        self.subjectsfolder_entry = PlaceholderEntry(
            self.input_frame,
            placeholder=placeholder_text,
            default=default_subjectsfolder,
            width=45
        )
        self.subjectsfolder_entry.config(validate='focusout', validatecommand=self.vcmd, invalidcommand=self.ivcmd)
        self.subjectsfolder_entry.grid(row=1, column=0, columnspan=2, padx=8, pady=5)

        tk.Button(self.input_frame, text="Browse", command=self.browse_subjectsfolder).grid(row=1, column=3, padx=8)

        self.label_error = tk.Label(self.input_frame, foreground='red')
        self.label_error.grid(row=2, column=0, sticky='w', padx=5, pady=3)

        # Run button
        self.run_button = tk.Button(self.root, text="Run", command=self.run_program)
        self.run_button.grid(row=3, column=0, columnspan=2, padx=5, pady=10)

    # --- UTILITIES ---
    def shorten_path(self, path, depth=3):
        if not path:
            return ""
        parts = os.path.normpath(path).split(os.sep)
        if len(parts) <= depth:
            return path
        return f"...{os.sep}{os.sep.join(parts[-depth:])}"

    def show_message(self, error=''):
        """Show or hide error message and highlight"""
        self.label_error['text'] = error
        if error:
            self.subjectsfolder_entry.config(highlightthickness=2, highlightbackground='red', highlightcolor='red')
        else:
            self.subjectsfolder_entry.config(highlightthickness=0)

    # --- VALIDATION ---
    def validate_entry(self, value):
        """Triggered when entry loses focus or after Browse"""
        fullpath = value.strip()
        # Handle shortened path case: get full path if stored
        if hasattr(self, 'subjectsfolder_path'):
            fullpath = self.subjectsfolder_path

        if os.path.isdir(fullpath):
            self.show_message('')
            return True
        else:
            self.show_message('Please enter a valid directory')
            return False

    def on_invalid(self):
        """Fallback visual when invalid input"""
        self.show_message('Please enter a valid directory')

    # --- ACTIONS ---
    def browse_subjectsfolder(self):
        path = filedialog.askdirectory(initialdir=default_initialdir)
        if path:
            self.subjectsfolder_path = path
            display_text = self.shorten_path(path)
            self.subjectsfolder_entry.delete(0, tk.END)
            self.subjectsfolder_entry.insert(0, display_text)
            self.subjectsfolder_entry['fg'] = self.subjectsfolder_entry.default_fg_color
            self.validate_entry(path)  # Trigger immediate validation

    def process_complete(self, error=False, error_msg=""):
        self.run_button.config(state="normal")
        self.spinner.stop()
        self.spinner.destroy()
        if error:
            messagebox.showerror("Error", f"\n{error_msg}")
        else:
            messagebox.showinfo("Success", "All data is successfully uploaded to Moveshelf")
    
    def run_program(self):
        self.show_message('') # Clear previous errors
        self.run_button.config(state="disabled")
        self.spinner = ttk.Progressbar(root, mode="indeterminate")
        self.spinner.grid(row=4, column=0, columnspan=2, padx=5, pady=10)       
        self.spinner.start()
        threading.Thread(target=self.run_upload, daemon=True).start()
 
    def run_upload(self):
        try:
            subjectsfolder_path = getattr(self, 'subjectsfolder_path', self.subjectsfolder_entry.get_value())
            project = self.project_entry.get_value()

            if not self.validate_entry(subjectsfolder_path) or subjectsfolder_path is None:
                NoValidDirError = "No valid input directory is given. Try again with a valid directory."
                print(f"\nWarning: {NoValidDirError}")
                self.root.after(0, lambda: self.process_complete(error=True, error_msg=NoValidDirError))
                raise Exception(NoValidDirError)

            # Prepare files for upload
            all_subject_files = batchUpload.batchPrepare(subjectsfolder_path)
        
            if isinstance(all_subject_files, str):  # Check for error message
                self.root.after(0, lambda: self.process_complete(error=True, error_msg=all_subject_files))
                raise Exception(all_subject_files)
        
            print('\nPrepared all subject files for upload...\n')
            print('\n--------------------------------------------------------------------------------------')
            print(f"Uploading files in given subjects' data folder ({subjectsfolder_path}) to project {project} on Moveshelf...")
            print('--------------------------------------------------------------------------------------\n')
            
            # Upload subjects to Moveshelf
            success = batchUpload.uploadSubjectstoMoveshelf(project, all_subject_files)
            
            if success:
                self.root.after(0, lambda: self.process_complete(error=False))
            else:
                self.root.after(0, lambda: self.process_complete(error=True, error_msg="Something went wrong during upload. Check console for details."))
                return
        except Exception as e:
            error_msg = str(e)  # Capture the value now
            self.root.after(0, lambda msg=error_msg: self.process_complete(error=True, error_msg=msg))
            return
                

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.update_idletasks()
    centerWindow(root)
    root.mainloop()