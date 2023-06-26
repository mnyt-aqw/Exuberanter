#!/usr/bin/env python3

'''
NOTE: This script is now deprecated in favor of the `interface.py` script.

A graphical interface for interacting with the data extracted from articles
by `extract.py`.

The program uses the CustomTKinter framwork to create the graphical interface.
It enables the user to load an article and view the different pieces of
information, such as sections, figures and tables.
'''

from datetime import datetime
from PIL import Image
import customtkinter as ctk
import shutil
import json
import os
import uuid

# The path of the extract results file
EXTRACT_FILE = './output/extract/results.json'

# The path of the identifed results file
IDENTIFY_FILE = './output/identify/results.json'

# The export directory path
EXPORT_DIRECTORY = './output/interface'
EXPORT_SUMMARY_PATH = f'{EXPORT_DIRECTORY}/results.json'

# Dynamic global variables
ARTICLE_ID = ''
ARTICLE_CONTENT = {}
ARTICLE_INFOS = []

# Based of https://github.com/TomSchimansky/CustomTkinter/blob/master/examples/scrollable_frame_example.py
class ScrollableLabelButtonFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, command, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self.command = command
        self.label_list = []
        self.button_list = []

    def add_item(self, name, value, image=None, indentation=0, buttons=['Open']):
        label = ctk.CTkLabel(self, text=name, image=image, compound='left', padx=5, anchor='w')
        label.grid(row=len(self.label_list), column=0, padx=(5 + indentation * 20, 5), pady=5, sticky='w')

        # Make sure the value is a list
        if not isinstance(value, list):
            value = [value]

        for i, button in enumerate(buttons):
            button = ctk.CTkButton(self, text=buttons[i], width=50, height=24)
            if self.command is not None:
                button.configure(command=lambda val=value[i]: self.command(val))
            button.grid(row=len(self.label_list), column=1 + i, pady=5, padx=(5, 10))

            self.button_list.append(button)

        self.label_list.append(label)

    def clean(self):
        for label in self.label_list:
            label.grid_forget()

        for button in self.button_list:
            button.grid_forget()

        self.label_list.clear()
        self.button_list.clear()

# The program sidebar with widgeets for changing apperance and loading articles
class Sidebar(ctk.CTkFrame):
    def __init__(self, master, load_relative_article, **kwargs):
        super().__init__(master, width=140, corner_radius=0, **kwargs)

        self.grid_rowconfigure(1, weight=1)
        self.label_title = ctk.CTkLabel(self, text='Litterature Survey',
                                              font=ctk.CTkFont(size=20, weight='bold'))
        self.label_title.grid(row=0, column=0, columnspan=3, padx=20, pady=(20, 10))

        self.textbox_articles = ctk.CTkTextbox(self)
        self.textbox_articles.grid(row=1, columnspan=3, column=0, padx=20, pady=0, sticky='nsew')

        self.var_open_article = ctk.StringVar()
        self.entry_open_article = ctk.CTkEntry(self, textvariable=self.var_open_article,
                                               placeholder_text='The article to open')
        self.entry_open_article.grid(row=2, column=0, columnspan=3, padx=20, pady=(10, 0), sticky='nsew')

        self.button_prev_article = ctk.CTkButton(self, text='Previous',
                                                 width=50, height=24,
                                                 command=lambda: load_relative_article(-1))
        self.button_prev_article.grid(row=3, column=0, padx=(20, 5), pady=10, sticky='nsew')
        self.button_open_article = ctk.CTkButton(self, text='Open article',
                                                 width=50, height=24,
                                                 command=lambda: load_relative_article(0))
        self.button_open_article.grid(row=3, column=1, padx=5, pady=10, sticky='nsew')
        self.button_next_article = ctk.CTkButton(self, text='Next',
                                                 width=50, height=24,
                                                 command=lambda: load_relative_article(1))
        self.button_next_article.grid(row=3, column=2, padx=(5, 20), pady=10, sticky='nsew')

        self.label_apperance_mode = ctk.CTkLabel(self, text='Appearance Mode:', anchor='w')
        self.label_apperance_mode.grid(row=5, column=0, columnspan=3, padx=20, pady=0)
        self.menu_apperance_mode = ctk.CTkOptionMenu(self, values=['Light', 'Dark', 'System'],
                                                     command=self.change_appearance_mode)
        self.menu_apperance_mode.grid(row=6, column=0, columnspan=3, padx=20, pady=0)

        self.label_ui_scaling = ctk.CTkLabel(self, text='UI Scaling:', anchor='w')
        self.label_ui_scaling.grid(row=7, column=0, columnspan=3, padx=20, pady=(10, 0))
        self.menu_ui_scaling = ctk.CTkOptionMenu(self, values=['80%', '90%', '100%', '110%', '120%'],
                                                 command=self.change_ui_scaling)
        self.menu_ui_scaling.grid(row=8, column=0, columnspan=3, padx=20, pady=(0, 20))

        # Default to dark colorscheme with 100$ scaling
        self.menu_apperance_mode.set('Dark')
        self.menu_ui_scaling.set('100%')
        self.change_appearance_mode('Dark')

    # Update the appearance mode
    def change_appearance_mode(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    # Update the scaling factor
    def change_ui_scaling(self, new_scaling: str):
        new_scaling_float = int(new_scaling.replace('%', '')) / 100
        ctk.set_widget_scaling(new_scaling_float)

    # Initialize the articles list with a set of articles
    def set_articles_list(self, articles):
        # Disable read-only mode
        self.textbox_articles.configure(state='normal')

        for article in articles:
            self.textbox_articles.insert(ctk.END, article + '\n')

        # Turn on read-only mode
        self.textbox_articles.configure(state='disabled')

# The selection panel, for selecting which part of the article to view
class SelectionPanel(ctk.CTkFrame):
    def __init__(self, master, set_section, set_figure, set_table, set_metadata, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform='column')
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        # Create headers selection panel
        self.label_headers = ctk.CTkLabel(self, text='Sections',
                                                        font=ctk.CTkFont(weight='bold'))
        self.label_headers.grid(row=0, column=0, padx=10, pady=(10, 0), sticky='w')
        self.list_headers = ScrollableLabelButtonFrame(self, command=set_section,
                                                       width=370, height=400)
        self.list_headers.grid(row=1, column=0, padx=(10, 5), pady=(0, 10), sticky='nswe')

        # Create a figure selection panel
        self.label_figures = ctk.CTkLabel(self, text='Figures',
                                                        font=ctk.CTkFont(weight='bold'))
        self.label_figures.grid(row=0, column=1, padx=10, pady=(10, 0), sticky='w')
        self.list_figures = ScrollableLabelButtonFrame(self, command=set_figure,
                                                       width=250, height=400)
        self.list_figures.grid(row=1, column=1, padx=5, pady=(0, 10), sticky='nswe')

        # Create a table selection panel
        self.label_tables = ctk.CTkLabel(self, text='Tables',
                                                        font=ctk.CTkFont(weight='bold'))
        self.label_tables.grid(row=0, column=2, padx=10, pady=(10, 0), sticky='w')
        self.list_tables = ScrollableLabelButtonFrame(self, command=set_table,
                                                      width=250, height=400)
        self.list_tables.grid(row=1, column=2, padx=5, pady=(0, 10), sticky='nswe')

        # Create a metadata selection panel
        self.label_metadata = ctk.CTkLabel(self, text='Metadata',
                                                        font=ctk.CTkFont(weight='bold'))
        self.label_metadata.grid(row=0, column=3, padx=10, pady=(10, 0), sticky='w')
        self.list_metadata = ScrollableLabelButtonFrame(self, command=set_metadata,
                                                        width=370, height=400)
        self.list_metadata.grid(row=1, column=3, padx=(5, 10), pady=(0, 10), sticky='nswe')

    # Load the article into the selection panels
    def load(self, article):
        # Load header list
        self.list_headers.clean()
        for i in article['section_order']:
            # Calculate depth by finding None grandparent
            depth = 0
            grandparent = article['sections'][i]['parent']
            while grandparent is not None:
                grandparent = article['sections'][grandparent]['parent']
                depth += 1

            self.list_headers.add_item(article['sections'][i]['name'],
                                                  i, indentation=depth)

        # Load figures list
        self.list_figures.clean()
        for i, figure in enumerate(article['figures']):
            image = ctk.CTkImage(Image.open(figure['path']), size=(30, 30))
            self.list_figures.add_item(figure['title'], [(True, i), (False, i)],
                                                  image=image, buttons=['Caption', 'Open'])

        # Load tables list
        self.list_tables.clean()
        for i, table in enumerate(article['tables']):
            self.list_tables.add_item(table['title'], [(True, i), (False, i)],
                                                 buttons=['Caption', 'Open'])

        # Load metadata list
        self.list_metadata.clean()
        for metadata in article['metadata']:
            self.list_metadata.add_item(metadata.capitalize(), metadata)

# The inspection box, used for displaying a part of the article
class InspectBox(ctk.CTkFrame):
    def __init__(self, master, set_result_textbox, set_shown_tab, **kwargs):
        super().__init__(master, **kwargs)

        self.set_result_textbox = set_result_textbox
        self.set_shown_tab = set_shown_tab

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.inspect_textbox = ctk.CTkTextbox(self, wrap=ctk.WORD)
        self.inspect_textbox.grid(row=1, padx=10, pady=(0, 10), sticky='nsew')
        self.inspect_textbox.bind('<<Selection>>', self.on_inspect_select)
        self.ignore_inspect_selection = 0

        self.label_inspect_box = ctk.CTkLabel(self, text='',
                                                font=ctk.CTkFont(weight='bold'))
        self.label_inspect_box.grid(row=0, column=0, padx=10, pady=(10, 0), sticky='w')

    # Highlights and focuses the given span of text
    def focus(self, span):
        self.inspect_textbox.configure(state='normal')
        self.inspect_textbox.tag_add('sel', span['start'], span['end'])
        self.inspect_textbox.configure(state='disabled')

        # Navigate to the highlighted area
        self.inspect_textbox.see(span['start'])

    # When text is selected in the inspect textbox, move the information to
    # the results textbox and update the source accordingly
    def on_inspect_select(self, _=None):
        global ARTICLE_ID

        # The try-block is needed when there is no selection such when a
        # deselection is issued
        try:
            # This is a bit hacky as we access the internal item _textbox, but
            # after multiple hours of digging this seems to be the only way
            # to do what we want
            sel_range = self.inspect_textbox._textbox.tag_ranges(ctk.SEL)
            selection = self.inspect_textbox._textbox.get(*sel_range)
        except:
            return

        # If set to ignore select, do it
        if 0 < self.ignore_inspect_selection:
            self.ignore_inspect_selection -= 1
            return

        # The source of the current item
        source = {
            'article': ARTICLE_ID,
            'kind': self.opened_source['kind'],
            'subtype': self.opened_source['subtype'],
            'location': {
                'start': str(sel_range[0]),
                'end': str(sel_range[1])
            }
        }

        # Update the result
        self.set_result_textbox(selection, source)

    # Load the given text in inspect textbox
    def set_inspect_textbox(self, title, text, monospace=False):
        # Clean the grid
        if 'button_figure_image' in self.__dict__:
            self.button_figure_image.grid_forget()

        # Change wrapping and text font on monospace
        if monospace:
            font = ctk.CTkFont(family='Monospace')
            wrap = ctk.NONE
        else:
            font = ctk.CTkFont()
            wrap = ctk.WORD

        # Disable read-only
        self.inspect_textbox.configure(state='normal')

        # Add text
        self.inspect_textbox.delete('0.0', ctk.END)
        self.inspect_textbox.insert(ctk.END, text)
        self.inspect_textbox.configure(wrap=wrap, font=font)
        self.inspect_textbox.grid()

        # Turn on read-only mode
        self.inspect_textbox.configure(state='disabled')

        # Set title
        self.label_inspect_box.configure(text=title)

    # Set the section to the given section id
    def set_section(self, section_id):
        global ARTICLE_CONTENT

        self.opened_source = {'kind': 'section', 'subtype': section_id}
        self.set_inspect_textbox(ARTICLE_CONTENT['sections'][section_id]['name'],
                                 ARTICLE_CONTENT['sections'][section_id]['content'])

    # Set the inspect textbox to the given metadata id
    def set_metadata(self, metadata):
        self.opened_source = {'kind': 'metadata', 'subtype': metadata}
        self.set_inspect_textbox(metadata.capitalize(), ARTICLE_CONTENT['metadata'][metadata])

    # Show the table or table caption given (caption, table_id)
    def set_table(self, table):
        global ARTICLE_CONTENT

        caption, table_id = table
        table = ARTICLE_CONTENT['tables'][table_id]

        # If the table caption should be loaded instead, do that
        if caption:
            self.opened_source = {'kind': 'table caption', 'subtype': table_id}
            self.set_inspect_textbox(table['title'],
                                     table['caption'])
            return

        self.opened_source = {'kind': 'table', 'subtype': table_id}
        self.set_inspect_textbox(table['title'],
                                 table['content'],
                                 monospace=True)

    # Show the figure or figure caption given (caption, figure_id)
    def set_figure(self, figure):
        global ARTICLE_CONTENT

        caption, figure_id = figure
        figure = ARTICLE_CONTENT['figures'][figure_id]

        # If the figure caption should be loaded instead, do that
        if caption:
            self.opened_source = {'kind': 'figure caption', 'subtype': figure_id}
            self.set_inspect_textbox(figure['title'], figure['caption'])
            return

        # Clean the grid
        self.inspect_textbox.grid_remove()
        if 'button_figure_image' in self.__dict__:
            self.button_figure_image.grid_forget()

        image = Image.open(figure['path'])

        scale = max(image.width, image.height)
        dimensions = (round(image.width / scale * 400),
                      round(image.height / scale * 400))
        image = ctk.CTkImage(image, size=dimensions)

        # Add the image as a button, but hide it
        self.button_figure_image = ctk.CTkButton(self, text='', image=image,
                                                 fg_color='transparent', hover=False,
                                                 command=self.open_figure)
        self.button_figure_image.grid(row=1, padx=10, pady=(0, 10), sticky='nsew')

        # Set title
        self.label_inspect_box.configure(text=figure['title'])
        self.opened_source = {'kind': 'figure', 'subtype': figure_id}

        # We also export the figure to allow access for web plot digitizer.
        # To allow access we copy the figure into the interface export
        # directory. We also output a JSON file containing the path relative
        # to the export directory
        os.makedirs(f'{EXPORT_DIRECTORY}/digitizer', exist_ok=True)
        self.figure_path = f'{EXPORT_DIRECTORY}/digitizer/{figure["path"].split("/")[-1]}'
        shutil.copy(figure['path'], self.figure_path)
        if file := open(file_path:=f'{EXPORT_DIRECTORY}/digitizer/digitizer.json', 'w+'):
            json.dump({'path': os.path.relpath(self.figure_path, EXPORT_DIRECTORY)}, file)
        else:
            print(f'Failed to open file {file_path}')

    # Opens the current figure (and prints path to console)
    def open_figure(self):
        print(f'The current figure is located at {self.figure_path}')
        Image.open(self.figure_path).show()

    # Open the source
    #
    # If no data is specified and the figure is either a figure or table,
    # show the data itself instead of caption
    def view_source(self, source, caption):
        text = True
        match source['kind']:
            case 'section':
                self.set_section(source['subtype'])
            case 'metadata':
                self.set_metadata(source['subtype'])
            case 'figure':
                self.set_figure((False, source['subtype']))
                text = False
            case 'figure caption':
                self.set_figure((caption,  source['subtype']))
            case 'table':
                self.set_table((False, source['subtype']))
            case 'table caption':
                self.set_table((caption, source['subtype']))
            case kind:
                print(f'unrecognized source kind {kind}')
                exit(-1)

        # Add highlight
        if text:
            self.focus(source['location'])

        # Display the general section
        self.set_shown_tab('General');

# The box containing the resulting information
class InformationBox(ctk.CTkFrame):
    def __init__(self, master, information_paths, view_source, **kwargs):
        super().__init__(master, **kwargs)

        self.information_paths = information_paths
        self.view_source = view_source

        # Load the file containg all previous export paths
        if (os.path.isfile(EXPORT_SUMMARY_PATH) and
            (file := open(EXPORT_SUMMARY_PATH, 'r'))):
            self.export_summary = json.load(file)
        else:
            self.export_summary = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure((0, 1, 3), weight=0)
        self.grid_rowconfigure(2, weight=1)

        # Create a label for the inspect and result frame
        self.label_frame_result = ctk.CTkLabel(self, text='Extracted information',
                                                        font=ctk.CTkFont(weight='bold'))
        self.label_frame_result.grid(row=0, column=0, columnspan=6, padx=10, pady=(10, 0), sticky='w')

        # Create a label indicating what information should be written
        self.label_result_datatype = ctk.CTkLabel(self, text='')
        self.label_result_datatype.grid(row=1, column=0, columnspan=6, padx=10, sticky='w')

        # Create the textbox storing the data
        self.result_textbox = ctk.CTkTextbox(self, wrap=ctk.WORD)
        self.result_textbox.grid(row=2, column=0, columnspan=6, padx=10, pady=(0, 10), sticky='nsew')

        # Add label and buttons for result frame
        self.var_result_title = ctk.StringVar()
        self.entry_result_title = ctk.CTkEntry(self, textvariable=self.var_result_title,
                                                         placeholder_text='Information title')
        self.entry_result_title.grid(row=3, column=0, padx=10, pady=(0, 10), sticky='w')

        # Add a sample selection for result frame
        self.var_result_sample = ctk.IntVar()
        self.entry_result_sample = ctk.CTkEntry(self, textvariable=self.var_result_sample,
                                                         placeholder_text='Sample number')
        self.entry_result_sample.grid(row=3, column=1, padx=(0, 10), pady=(0, 10), sticky='w')

        buttons = {
            'Previous': lambda: self.load_information(self.information_index - 1),
            'Store': lambda: self.store_information(),
            'Next': lambda: self.load_information(self.information_index + 1),
        }

        for i, (name, action) in enumerate(buttons.items()):
            button = ctk.CTkButton(self, text=name,
                                             width=50, height=24, command=action)
            button.grid(row=3, column=2+i, padx=(0, 10), pady=(0, 10), sticky='nsew')

    def load(self, id):
        global ARTICLE_INFOS

        # Load previous information, if any
        path =  f'{EXPORT_DIRECTORY}/{id}.json'
        if id in self.export_summary and (file := open(path, 'r')):
            ARTICLE_INFOS = json.load(file)
        else:
            # Create the initial article file
            ARTICLE_INFOS = []
            if file := open(path, 'w+'):
                json.dump(ARTICLE_INFOS, file)
            else:
                print(f'Failed to open file {path}')
                exit(-1)

            # We also add the new file to the index of all output files
            self.export_summary[id] = path
            if file := open(EXPORT_SUMMARY_PATH, 'w+'):
                json.dump(self.export_summary, file)
            else:
                print(f'Failed to open file {EXPORT_SUMMARY_PATH}')
                exit(-1)

        # Load the article identify JSON file
        if id in self.information_paths:
            path = self.information_paths[id]
        else:
            print(f'Failed to load unrecognized article identification data {id}, skipping')
            return

        if file := open(path):
            self.identified_information = json.load(file)

            # Load the first piece of information
            self.information_index = None
            if 0 < len(self.identified_information):
                self.load_information(0)
            else:
                self.load_information(None)
        else:
            print(f'Failed to open file {path}')

    def set(self, text, src):
        self.result_textbox.delete('0.0', ctk.END)
        self.result_textbox.insert(ctk.END, text)

        if self.current_info is None:
            self.current_info = {}

        self.current_info['source'] = src

    # Stores the current information to the export file
    def store_information(self):
        global ARTICLE_INFOS

        # If no information exists, ignore
        if self.current_info is None:
            return

        # Update the information with the most up to date version
        self.current_info['stamp'] = datetime.now().isoformat()
        self.current_info['title'] = self.var_result_title.get()
        self.current_info['data'] = self.result_textbox.get('1.0', ctk.END).strip()
        self.current_info['uuid'] = str(uuid.uuid4())

        if self.current_info['sample'] is not None:
            self.current_info['sample'] = self.var_result_sample.get()

        # Add the information to the article info
        ARTICLE_INFOS.append(self.current_info.copy())

        # Export the information to export file
        path = f'{EXPORT_DIRECTORY}/{self.current_info["source"]["article"]}.json'
        if file := open(path, 'w+'):
            json.dump(ARTICLE_INFOS, file)
        else:
            print(f'Failed to open file {path}')
            exit(-1)

    # Loads the piece of information associated with the given number
    def load_information(self, index):
        # If the index is None, clear
        if index is None:
            self.label_frame_result.configure(text='Extracted information')
            self.label_result_datatype.configure(text='')
            self.var_result_sample.set(1)
            self.var_result_title.set('')
            self.result_textbox.delete('0.0', ctk.END)
            self.current_info = None

        if len(self.identified_information) == 0:
            self.information_index = None
            return

        # Make sure the information is within bounds
        if index < 0:
            self.information_index = 0
        elif len(self.identified_information) <= index:
            self.information_index = len(self.identified_information) - 1
        else:
            self.information_index = index

        self.current_info = self.identified_information[self.information_index].copy()

        # Open the source
        self.view_source(self.current_info['source'], self.current_info['data'] is not None)

        # Update the result frame and it's content
        self.label_frame_result.configure(
            text=f'Extracted information ({self.information_index+1}/{len(self.identified_information)})')
        self.result_textbox.delete('0.0', ctk.END)
        self.var_result_title.set(self.current_info['title'])
        self.ignore_inspect_selection = 2
        self.label_result_datatype.configure(
            text=self.current_info['description']['data']
        )

        if self.current_info['data'] is not None:
            self.result_textbox.insert(ctk.END, self.current_info['data'])

        # Populate the sample number
        if self.current_info['sample'] is None:
            self.entry_result_sample.grid_remove()
        else:
            self.entry_result_sample.grid()
            nr = int(self.current_info['sample'])
            if nr == -1:
                self.var_result_sample.set(1)
            else:
                self.var_result_sample.set(nr)

class InformationEntry(ctk.CTkFrame):
    def __init__(self, master, info, updated_information_callback,
                 delete_callback, view_source, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(2, weight=1)

        # Store the info on itself
        self.info = info
        self.updated_information_callback = updated_information_callback

        # The top row should contain an option to delete the information
        self.button_delete = ctk.CTkButton(self, text='Delete', width=50,
                                           height=24, command=delete_callback)
        self.button_delete.grid(row=0, column=0, pady=(10, 10), padx=10)

        # Add a view source button
        self.button_source = ctk.CTkButton(self, text='View source', width=50,
                                           height=24, command=lambda:
                                           view_source(self.info['source'],
                                                       self.info['data'] is not None)
                                           )
        self.button_source.grid(row=0, column=1, pady=(10, 10), padx=10)

        # Display simple top-level JSON data
        self.items = {}
        for key in ['title', 'data', 'sample', 'stamp']:
            i = len(self.items)
            var = ctk.StringVar(self, self.info[key])
            label = ctk.CTkLabel(self, text=key, justify='left')
            label.grid(row=i+1, column=0, pady=(0, 10), padx=10, sticky='w')
            entry = ctk.CTkEntry(self, textvariable=var, placeholder_text=key)
            entry.grid(row=i+1, column=1, columnspan=2, pady=(0, 10),
                       padx=(0, 10), sticky='nsew')

            # Also associated the field change function with entry to update
            # the info on change
            entry.bind("<KeyRelease>", lambda _, key=key: self.on_field_change(key))

            # Keep track of all items
            self.items[key] = (var, label, entry)

        # Add a "expanding" switch to toggle the "expanding" property
        self.var_expanding = ctk.BooleanVar(value=self.info['expanding'])
        self.label_expanding = ctk.CTkLabel(self, text='expanding', justify='left')
        self.label_expanding.grid(row=len(self.items) + 1, column=0, pady=(0, 10),
                                  padx=10, sticky='w')
        self.switch_expanding = ctk.CTkSwitch(self, onvalue=True, offvalue=False,
                                              variable=self.var_expanding, text='',
                                              command=self.on_expanding_toggle)
        self.switch_expanding.grid(row=len(self.items) + 1, column=1, columnspan=2,
                                   pady=(0, 10), padx=(0, 10), sticky='nsew')

    # Update the expanding status on toggle
    #
    # Is called when expanding switch is toggled
    def on_expanding_toggle(self):
        self.info['expanding'] = self.var_expanding.get()

        # Propagate update
        self.updated_information_callback()

    # Updates the associated information
    #
    # Is called if the value of a field changes
    def on_field_change(self, key):
        value = self.items[key][0].get()

        # Treat blank as None
        if value == "":
            self.info[key] = None
        else:
            self.info[key] = value

        # Propagate update
        self.updated_information_callback()

class ScrollableInfoFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, updated_information_callback, delete_callback,
                 view_source, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self.entries = []
        self.updated_information_callback = updated_information_callback
        self.delete_callback = delete_callback
        self.view_source = view_source

    def load_infos(self, infos):
        # Clean out old info
        for entry in self.entries:
            entry.grid_forget()
        self.entries.clear()

        # Load new info
        for i, info in enumerate(infos):
            entry = InformationEntry(self, info, self.updated_information_callback,
                                     lambda uuid=info['uuid']: self.remove_info(uuid),
                                     self.view_source,
                                     height=50)
            entry.grid(row=i, column=0, pady=5, padx=5, sticky='nsew')

            self.entries.append(entry)

    # Removes the given uuid from the list
    #
    # A uuid is used instead of index to not have to update all references for
    # every time a item is removed
    def remove_info(self, uuid):
        # Remove the uuid from the list
        index = None
        for index, entry in enumerate(self.entries):
            if entry.info['uuid'] == uuid:
                entry.grid_forget()
                self.entries.pop(index)
                break

        # Also remove info from parent
        self.delete_callback(index)

class App(ctk.CTk):
    def __init__(self, extract_data, information_paths):
        # Initialize CTKinter
        super().__init__()

        # Store the data on self
        self.extract_data = extract_data

        # configure window title
        self.title('Litterature Survey Software')
        self.geometry('1420x800')

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # create sidebar populated with articles
        self.sidebar = Sidebar(self, self.load_relative_article)
        self.sidebar.grid(row=0, column=0, sticky='nsew')
        self.sidebar.set_articles_list(self.extract_data.keys())

        # Create a tabview with two different view. One for skimming through
        # articles and extracting data and one for viewing all data currently
        # associated with the current article
        self.main_tabview = ctk.CTkTabview(self, command=self.load_summary)
        self.main_tabview.grid(row=0, column=1, padx=10, pady=10, sticky='nsew')
        self.main_tabview.add('General')
        self.main_tabview.add('Summary')
        self.main_tabview.set('General')

        # configure grid layout (2x2) for general section
        self.main_tabview.tab('General').grid_columnconfigure((0, 1),
                                                              weight=1,
                                                              uniform='column')
        self.main_tabview.tab('General').grid_rowconfigure((0, 1),
                                                           weight=1,
                                                           uniform='row')

        # Create the inspect box displaying parts of the article
        self.inspect_box = InspectBox(self.main_tabview.tab('General'), self.set_info_box,
                                      lambda tab: (self.main_tabview.set(tab) if
                                          self.main_tabview.get() != tab else None))
        self.inspect_box.grid(row=0, column=0, padx=(10, 5), pady=10, sticky='nsew')

        # create a result frame showing info pieces
        self.information_box = InformationBox(self.main_tabview.tab('General'),
                                              information_paths,
                                              self.inspect_box.view_source)
        self.information_box.grid(row=0, column=1, padx=(5, 10), pady=10, sticky='nsew')

        # Create the selection panel section
        self.selection_panels = SelectionPanel(self.main_tabview.tab('General'),
                                               self.inspect_box.set_section,
                                               self.inspect_box.set_figure,
                                               self.inspect_box.set_table,
                                               self.inspect_box.set_metadata)
        self.selection_panels.grid(row=1, column=0, columnspan=2, padx=10,
                                   pady=(0, 10), sticky='nsew')

        # configure grid layout (2x1) for summary section
        self.main_tabview.tab('Summary').grid_columnconfigure(0, weight=1)
        self.main_tabview.tab('Summary').grid_rowconfigure(1, weight=1)

        # Add the two sections (article associated and sample associated info)
        self.label_article_infos = ctk.CTkLabel(self.main_tabview.tab('Summary'),
                                         text='All information assoicated with article')
        self.label_article_infos.grid(row=0, column=0, padx=0, pady=0, sticky='nsew')
        self.info_list = ScrollableInfoFrame(self.main_tabview.tab('Summary'),
                                             self.on_info_change, self.delete_info,
                                             self.inspect_box.view_source)

        self.info_list.grid(row=1, column=0, padx=(10, 5), pady=10, sticky='nsew')

        # Load the initial article
        self.load_article(list(self.extract_data.keys())[0])

    # Deletes the given info index from the current article, updates the output
    # file
    def delete_info(self, index):
        ARTICLE_INFOS.pop(index)
        self.on_info_change()

    # A function called when article_infos needs updating. Outputs the new
    # info to the output file
    #
    # It might be inefficient to write file on every keystroke, but it doesn't
    # seem to slow
    def on_info_change(self):
        path =  f'{EXPORT_DIRECTORY}/{ARTICLE_ID}.json'
        if file := open(path, 'w+'):
            json.dump(ARTICLE_INFOS, file)
        else:
            print(f'Failed to open file {path}')
            exit(-1)

    # A function needed to work around the issue of bidirectional dependence
    # between `information_box` and `inspect_box`
    def set_info_box(self, data, src):
        self.information_box.set(data, src)

    # Load a relative article to the currently open one
    def load_relative_article(self, offset):
        global ARTICLE_ID

        # If the offset is 0, load the currently written article
        if offset == 0:
            self.load_article(self.sidebar.var_open_article.get())

        articles = list(self.extract_data.keys())

        # Find the current article
        for i, id in enumerate(articles):
            if id == ARTICLE_ID:
                # Clamped offset
                new_article_index = min(max(0, i + offset), len(articles)-1)
                self.load_article(articles[new_article_index])
                break

    # Load the given article into view from extract.py output
    def load_article(self, id):
        global ARTICLE_ID, ARTICLE_CONTENT

        ARTICLE_ID = id

        # Load the article JSON file
        if id in self.extract_data:
            path = self.extract_data[id]
        else:
            print(f'Failed to load unrecognized article {id}, skipping')
            return

        if file := open(path):
            ARTICLE_CONTENT = json.load(file)
        else:
            print(f'Failed to load article {id}, skipping')
            return

        # Display the currently opened article
        self.sidebar.var_open_article.set(str(id))

        # Initialize the selection panel
        self.selection_panels.load(ARTICLE_CONTENT)

        # Load the information
        self.information_box.load(id)

        # Initialize the summary tab
        self.load_summary()

    # Loads the current article information preparing the 'Summary' tab
    def load_summary(self):
        # Only run if the 'Summary' tab is open
        if self.main_tabview.get() != 'Summary':
            return

        # Load the information
        self.info_list.load_infos(ARTICLE_INFOS)

# Only run if non-library
if __name__ == '__main__':
    # Load the extract results
    if os.path.isfile(EXTRACT_FILE) and (file := open(EXTRACT_FILE)):
        extract_data = json.load(file)
    else:
        print('Failed to load extract results, are you sure you have ran the `extract.py` script?')
        exit(-1)

    # Load the identify results
    if os.path.isfile(IDENTIFY_FILE) and (file := open(IDENTIFY_FILE)):
        information_paths = json.load(file)
    else:
        print('Failed to load identify results, are you sure you have ran the `identify.py` script?')
        exit(-1)

    # Create the export directory
    os.makedirs(EXPORT_DIRECTORY, exist_ok=True)

    app = App(extract_data, information_paths)
    app.mainloop()
