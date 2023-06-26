#!/usr/bin/env python3

'''
A script for dividing article into parts such as sections, tables and figures.
Works on articles downloaded by `download.py`.

The program interprets the semantic XML articles provided by PubMed Central to
separate an article into sections, figures and tables. These are then exported
to individual JSON files such as `PMC9745798.json`. Finally, the program
exports a list containing the path to all extracted articles to `results.json`.

If no XML file is found, PDF extraction is invoked. For figure identification
adjacent figures are merged, the document is rendered and a "screenshot" is
taken around each figure. This includes data superimposed on the image itself,
such as labels.

The script optionally takes one argument which can be `mix`. If such an argument
is given, all images, including in cases of an existing XML file, is extracted
from the PDF. Note that the rest of the information is still extracted from the
XML file, if available.
'''

from PIL import Image
import xml.etree.ElementTree as ET
import Levenshtein
import html2text
import json
import os
import sys
import fitz

# The path to the articles
ARTICLES_PATH = './output/download'

# The export directory path
EXPORT_DIRECTORY = './output/extract'

# A list of all known headers, used for PDF extraction
KNOWN_HEADERS = ['abstract:', 'abstract', 'introduction', 'materials and methods', 'method',
                 'results', 'results and discussion', 'discussion', 'acknowledgements',
                 'references']

# The (x, y) image margin around images that should be captured for PDF extraction
IMAGE_PX_MARGIN = (30, 30)

# The pixel upscaling used when extracting figures for PDF extraction
IMAGE_PX_MULT = 4

# The Levenshtein distance ratio used for page header similarity
PAGE_HEADER_MIN_RATIO = 0.9

# A list of file extensions in order of priority, from highest to lowest. Is
# used to determine the source of figure images in XML extraction
IMAGE_EXTENSION_PRIORITY = ['eps', 'tif', 'tiff', 'png', 'jpg', 'gif']

# The image format that all extracted images should be in
IMAGE_TARGET_FORMAT = 'png'

# Extracts all figures from a PDF
def extract_pdf_figures(name, doc):
    # To be able to handle images which are overlaid with information
    # we render the region around the images and then extract the images
    # instead of only taking the images
    #
    # The algorithm also de-duplicate images with their hash digest,
    # meaning completely equal images are de-duped
    #
    # An often seen edge case is images split into multiple parts, this is
    # handled by extending adjacent bounding boxes
    figures = []
    figure_hashes = {}
    zoom = fitz.Matrix(IMAGE_PX_MULT, IMAGE_PX_MULT)
    for page in doc.pages():
        images = page.get_image_info(hashes=True)

        # Join adjacent images
        joined_images = []
        for img_a_index, img_a in enumerate(images):
            new_bbox = None
            for img_b in images:
                if img_a == img_b:
                    continue

                # Find all points that match between the two rectangles
                matches = []
                rectangle_points = [[0, 1], [2, 1], [2, 3], [0, 3]]
                for a in range(4):
                    point_a = (img_a['bbox'][rectangle_points[a][0]],
                               img_a['bbox'][rectangle_points[a][1]])

                    for b in range(4):
                        point_b = (img_b['bbox'][rectangle_points[b][0]],
                                   img_b['bbox'][rectangle_points[b][1]])

                        if point_a == point_b:
                            matches.append((rectangle_points[a], rectangle_points[b]))

                # If any side is equal, merge them
                if len(matches) == 2:
                    # Find if x side is touching
                    if matches[0][0][0] == matches[1][0][0] and matches[0][1][0] == matches[1][1][0]:
                        new_bbox = (min(img_a['bbox'][0], img_a['bbox'][2]),
                                    min(img_a['bbox'][1], img_a['bbox'][3]),
                                    max(img_b['bbox'][0], img_b['bbox'][2]),
                                    max(img_a['bbox'][1], img_a['bbox'][3]))

                    # or if y side is touching
                    elif matches[0][0][1] == matches[1][0][1] and matches[0][1][1] == matches[1][1][1]:
                        new_bbox = (min(img_a['bbox'][0], img_a['bbox'][2]),
                                    min(img_a['bbox'][1], img_a['bbox'][3]),
                                    max(img_a['bbox'][0], img_a['bbox'][2]),
                                    max(img_b['bbox'][1], img_b['bbox'][3]))
                    else:
                        continue

                    # Remove the other image
                    images.pop(img_a_index)
                    break

            # If a new bounding box was found, use it
            if new_bbox:
                img_a['bbox'] = new_bbox
            joined_images.append(img_a)

        # Extract each figure
        for image in joined_images:
            # Skip duplicates
            if image['digest'] in figure_hashes:
                continue
            figure_hashes[image['digest']] = None

            # Crop the image region with a slight margin
            clip = fitz.Rect(image['bbox'][0] - IMAGE_PX_MARGIN[0],
                             image['bbox'][1] - IMAGE_PX_MARGIN[0],
                             image['bbox'][2] + IMAGE_PX_MARGIN[1],
                             image['bbox'][3] + IMAGE_PX_MARGIN[1])
            pixmap = page.get_pixmap(matrix=zoom, clip=clip)

            # Save the map to a file, may fail if faulty image, continue anyways
            try:
                path = f'{EXPORT_DIRECTORY}/{name}-figure-{len(figures)}.png'
                pixmap.save(path)
                figures.append({
                    'title': f'Fig {len(figures)} (generated)',
                    'caption': '',
                    'path': path,
                })
            except:
                pass

    return figures

# Extracts information from a given PDF file
def extract_from_pdf(name, path):
    doc = fitz.open(path)

    # Extract figures
    figures = extract_pdf_figures(name, doc)

    # Identify page header
    #
    # This is done by comparing the first line of each page and finding how
    # similar they are. If they are similar enough, below a certain threshold,
    # they are classified as a page header and ignored.
    #
    # The almost equal is important to adjust for page numbers or other
    # discrepancies. We also skip the first page as there is often a custom
    # first page header
    almost_equal_lines = 0
    similar = True
    while similar:
        lines = []
        for page in list(doc.pages())[1:]:
            lines.append(page.get_text('text', flags=0, sort=True)
                            .split('\n')[almost_equal_lines].strip())

        for line in lines:
            if not (PAGE_HEADER_MIN_RATIO < Levenshtein.ratio(lines[0], line)):
                similar = False
                break

        if similar:
            almost_equal_lines += 1

    # Extract all the text in the article, explicitly in the correct reading
    # order as that may not always be the implicit case
    order = [0]
    current_header = 0
    sections = [{
        'name': 'preface',
        'content': '',
        'parent': None
    }]
    header_nr_map = {'': None}
    for page in doc.pages():
        # We sort the text by natural reading order. The flag parameter
        # doesn't preserve images, ligatures nor whitespace
        page_text = page.get_text('dict', flags=0, sort=True)

        # Try to identify headers
        #
        # We assume headers satisfy at least one requirement from each
        # category of the following criteria
        #
        # Category 1
        #  a. is italic
        #  b. is bold
        #
        # Category 2
        #  a. starts with 'x. Title', 'x.y. Title' and so on
        #  b. case and space insensitively equal to some known headers
        #
        # In the case of 2a we are also able to give the section a parent
        # section using the numbers
        line_count = 0
        for block in page_text['blocks']:
            for line in block['lines']:
                # Skip page header
                if line_count < almost_equal_lines:
                    line_count += 1
                    continue

                for span in line['spans']:
                    text = span['text']

                    # Category 1 (check for bold or italic)
                    header = None
                    parent = None
                    parts = []
                    if (span['flags'] & 2 ** 4) or (span['flags'] & 2 ** 1):
                        # Category 2a
                        if text.strip().lower() in KNOWN_HEADERS:
                            header = text

                        # Category 2b
                        nr = None
                        for c in text.lstrip():
                            # On space, success as the rest is the title
                            if c == '.':
                                if nr:
                                    parts.append(nr)
                                    nr = None
                                else:
                                    break
                            elif c.isdigit():
                                if nr == None:
                                    nr = int(c)
                                else:
                                    nr = nr * 10 + int(c)
                            # At least one part (ex. '1.') for a header
                            elif 0 < len(parts):
                                parent = header_nr_map['-'.join(map(str, parts[:-1]))]
                                header = text
                                break
                            else:
                                break

                    # If a header was found, add all content new content to it
                    if header:
                        sections[current_header]['content'] = sections[current_header]['content'].strip()

                        # If an exact (whitespace removed) header match is
                        # found, use that instead. This is to work for
                        # incorrect PDFs with invisible text
                        current_header = None
                        for i, section in enumerate(sections):
                            if section['name'].strip() == header.strip():
                                current_header = i

                        if current_header:
                            # When continuing already created text start on
                            # new paragraph
                            sections[current_header]['content'] += '\n\n'
                        else:
                            if 0 < len(parts):
                                header_nr_map['-'.join(map(str, parts))] = len(sections)

                            current_header = len(sections)
                            sections.append({
                                'name': header,
                                'content': '',
                                'parent': parent
                            })
                            order.append(current_header)
                    else:
                        sections[current_header]['content'] += text + ' '
            sections[current_header]['content'] += '\n\n'

    return {
        'figures': figures,
        'tables': {},
        'sections': sections,
        'section_order': order
    }

# Extract information from XML article
def extract_from_xml(name, path, fig_path, figures_pdf_path=None):
    xml_article = ET.parse(path)

    # Extract all figures (either from XML or PDF)
    if figures_pdf_path is None:
        figures = []
        for xml_figure in xml_article.findall('.//fig'):
            caption = xml_figure.find('caption')
            if caption is not None:
                caption = html2text.html2text(ET.tostring(caption).decode())

            # Get the first graphic hrefs
            href = None
            graphic = xml_figure.find('.//graphic')
            if graphic is not None:
                href = graphic.attrib['{http://www.w3.org/1999/xlink}href']

            if href is None:
                print(f'Failed to identify figure for {path}')
                continue

            # Determinine the best image source and convert it to PNG
            base_path = os.path.join(fig_path, href)
            figure_path = f'{EXPORT_DIRECTORY}/{name}-{href}.{IMAGE_TARGET_FORMAT}'
            for ext in IMAGE_EXTENSION_PRIORITY:
                path = f'{base_path}.{ext}'
                if os.path.isfile(path):
                    Image.open(path).save(figure_path)
                    break

            figures.append({
                'title': xml_figure.findtext('label'),
                'caption': caption,
                'path': figure_path,
            })
    else:
        doc = fitz.open(figures_pdf_path)
        figures = extract_pdf_figures(name, doc)

    # Extract all tables
    tables = []
    for xml_table in xml_article.findall('.//table-wrap'):
        caption = xml_table.find('caption')
        if caption is not None:
            caption = html2text.html2text(ET.tostring(caption).decode())

        content = 'Failed to parse table content'
        if table := xml_table.find('.//table'):
            content = html2text.html2text(ET.tostring(table).decode())

        tables.append({
            'title': xml_table.findtext('label'),
            'caption': caption,
            'content': content
        })

    # Extract all text into sections, keeping track of section headers.
    # This is done using depth first search (DFS) traversing the entire tree,
    # while keeping track of depth
    body = xml_article.find('.//body')
    if body is None:
        return None

    sections = []
    order = []
    header_stack = []
    uid_stack = []
    queue = [body]
    while 0 < len(queue):
        item = queue.pop()

        # If marker item, pop stack and continue
        if item == 'DIVE_MARKER':
            header_stack.pop()
            uid_stack.pop()
            continue

        # Identify the title
        title = item.find('title')
        if title is not None and title.text is not None:
            title = title.text.strip()
        else:
            title = None

        header_stack.append(title)
        queue.append('DIVE_MARKER')

        # Add all section children to queue (and dive marker)
        children = item.findall('sec')
        if 0 < len(children):
            queue.extend(children)

        # Create a UID for this header
        uid = len(sections)
        uid_stack.append(uid)

        if 1 < len(header_stack):
            # Skip the root element when adding to section
            content = ''
            for p in item.findall('.//p'):
                content += ET.tostring(p).decode()

            # Convert to simple text
            content = html2text.html2text(content)

            # Keep track of parent to be able to reconstruct hierarchy, if the uid is not a section, ignore it
            if 2 < len(uid_stack):
                parent_uid = uid_stack[-2]
            else:
                parent_uid = None

            order.append(uid)
            sections.append({
                'name': header_stack[-1],
                'content': content,
                'parent': parent_uid
            })

    # Reverse the order to match the document order
    order.reverse()

    return {
        'figures': figures,
        'tables': tables,
        'sections': sections,
        'section_order': order
    }

# Extracts the metadata from a JSON version of PubMed metadata
def extract_metadata(path):
    if file := open(filepath := os.path.join(path, 'metadata.json')):
        article = json.load(file)
    else:
        print(f'Failed to open file {filepath}')
        exit(-1)

    # Load abstract, if available
    abstract = None
    if os.path.isfile(filepath := os.path.join(path, 'abstract.json')):
        if file := open(filepath):
            abstract = json.load(file)['text']

    return {
        'title': article['Title'],
        'publish date': article['PubDate'],
        'authors': '\n'.join(article['AuthorList']),
        'abstract': abstract,
    }

# Create the export directory
os.makedirs(EXPORT_DIRECTORY, exist_ok=True)

# Configure HTML to text
html2text.config.PAD_TABLES = True
html2text.config.BODY_WIDTH = 0

# Load the download results
if os.path.isfile(path := f'{ARTICLES_PATH}/results.json') and (file := open(path)):
    download_summary = json.load(file)
else:
    print('Failed to load download results, are you sure you have ran the `download.py` script?')
    exit(-1)

# Check for 'mix' argument
force_pdf_figures = False
if 1 < len(sys.argv):
    if sys.argv[1] == 'mix':
        force_pdf_figures = True
    else:
        print(f'Unrecognized command line argument: {sys.argv[1]}')
        exit(-1)

# Extract information from all articles
article_paths = {}
for (name, path) in download_summary['articles'].items():
    print(f'Parsing {name} ', flush=True, end='')

    # Find the first available PDF file
    pdf_path = None
    for filename in os.listdir(path):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(path, filename)
            break

    # Parse XML if available, otherwise default to PDF parsing
    xml_article_path = os.path.join(path, 'article.xml')
    result = None
    found = False
    if os.path.isfile(xml_article_path):
        print(f'as XML ... ', flush=True, end='')
        found = True
        result = extract_from_xml(name, xml_article_path, path, pdf_path if force_pdf_figures else None)
    elif pdf_path is not None:
        print(f'as PDF ... ', flush=True, end='')
        found = True
        result = extract_from_pdf(name, pdf_path)

    # Skip if not found
    if not found:
        print('... skipped')
        continue

    # Ignore on fail
    if result is None:
        print('... failed')
        continue

    # Extract the metadata
    result['metadata'] = extract_metadata(path)

    # Export each article in a separate JSON file
    path = f'{EXPORT_DIRECTORY}/{name}.json'
    if file := open(path, 'w+'):
        json.dump(result, file)
    else:
        print(f'Failed to open file {path}')
        exit(-1)

    article_paths[name] = path

    figure_count = len(result['figures'])
    table_count = len(result['tables'])
    section_count = len(result['sections'])
    print(f' done, {figure_count} figures, {table_count} tables and {section_count} sections')

# Export JSON containing extraction information
if file := open(file_path:=f'{EXPORT_DIRECTORY}/results.json', 'w+'):
    json.dump(article_paths, file)
else:
    print(f'Failed to open file {file_path}')
    exit(-1)
