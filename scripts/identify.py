#!/usr/bin/env python3

'''
A script for identifiying relevant information from the articles outputed by
`extract.py`.

This is done using a series of filters. Each filter can currently either be a
regex or a function (fancy). Each filter also specifies which sections it
applies to, for example 'method' is written for the method sections.

The script has a single possible argument that can be either 'web' (default) or
'native'. If native, it turns the location (start and end) to TKinter offsets
instead of simple byte offsets.

The script exports one JSON file per article containing all the related pieces
of information and their source. Each piece of information contains the
following information

'title': The information title,
'data': The data contained within the information,
'sample': The sample associated with the information (None for article wide data and -1 for indeterminate sample association),
'expanding': If true, treat the data as a CSV file with two columns (header and data) which will later get expanded
'stamp': The time of information creation,
'uuid': A unique id assoicated with each piece of information,
'source': {
  'article': The name of the article,
  'kind': The type of location within article ('figure caption', 'table caption', 'metadata' or 'section'),
  'subtype': The index of the type targeted,
  'location': {
    'start': The start character range,
    'end': The end character range,
  }
}
'description': {
    'info': A short description of the information,
    'data': A short description of the possible values,
}
'''

from datetime import datetime
import json
import os
import re
import sys
import uuid

# Setup openAI (if key is requested)
OPENAI_ENABLED = False
if 'OPENAI_API_KEY' in os.environ:
    OPENAI_ENABLED = True

    # Initialize openAI
    import openai
    openai.api_key = os.getenv('OPENAI_API_KEY')

    # Warning message
    print('Be wary that you are running with a openAI API key, high API and costs might follow.')
    print('Press enter to confirm your intentions.')
    input()

# The path to the extracted data
EXTRACTED_PATH = './output/extract'

# The export directory path
EXPORT_DIRECTORY = './output/identify'

# All the filters used for identifying information
FILTERS = {
    # The title of the article. Extracted from the article metadata
    'article title': {
        'targets': { 'metadata': ['title'] },
        'regex': re.compile(r'.+', re.DOTALL),
        'description': {
            'info': 'The title of the article',
            'data': 'a string',
        }
    },
    # The publishing date of the article. Extracted from the article metadata
    'publish date': {
        'targets': { 'metadata': ['publish date'] },
        'regex': re.compile(r'.+', re.DOTALL),
        'description': {
            'info': 'The publish date of the article',
            'data': 'any date format',
        }
    },
    # The qPCR method that has been used. Due to most articles not specifying
    # if they use singleplexing we assume all articles not specifying
    # multiplex mode are singleplexed
    'method': {
        'targets': { 'sections': ['method'] },
        'categories': {
            'multiplex': re.compile('|'.join(['multiplex']), re.IGNORECASE),
            'singleplex': None,
        },
        'description': {
            'info': 'The qPCR method used',
            'data': '"multiplex" or "singleplex"',
        }
    },
    # A filter that identifies the sample year from the method section. We
    # assume a year is four digits starting with "19" or "20".
    'sample year': {
        'sample associated': True,
        'targets': { 'sections': ['method'] },
        'regex': re.compile(r'\b(19|20)[0-9]{2}\b'),
        'description': {
            'info': 'The sample year',
            'data': 'four consecutive digits',
        }
    },
    # If a site is polluted or not. We assume all articles not matching any
    # polution keyword is non-pollutetd
    'polluted': {
        'sample associated': True,
        'targets': { 'sections': ['method'] },
        'categories': {
            'yes': re.compile('|'.join(['pollution', 'polluted',
                                        'contamination', 'contaminated']),
                              re.IGNORECASE),
            'no': None,
        },
        'description': {
            'info': 'If sample is polluted or not',
            'data': '"yes" or "no"',
        }
    },
    # The type of sample collected. Can be one of multiple categories
    'sample type': {
        'sample associated': True,
        'targets': { 'sections': ['method'] },
        'categories': {
            'soil': re.compile('|'.join(['soil', 'soils', 'Clay']), re.IGNORECASE),
            'manure': re.compile('|'.join(['manure', 'guano', 'feces']), re.IGNORECASE),
            'sewage': re.compile('|'.join(['sewage', 'waste water']), re.IGNORECASE),
        },
        'description': {
            'info': 'The type of sample',
            'data': '"soil", "manure or "sewage"',
        }
    },
    # Identify figures which may contain the gene abundance. This is done
    # using basic keywords
    #
    # The item is marked with the 'expanding' which causes it to accept and
    # parse CSV data such as the following
    #
    # geneABC, 0.0434
    # geneABB, 0.0343
    # geneABA, 0.0654
    #
    # This is in the same format exported by the bar chart mode in
    # WebPlotDigitizer
    'gene abundance': {
        'sample associated': True,
        'expanding': True,
        'targets': { 'figures': True, 'tables': True },
        'source': re.compile('|'.join(map(lambda str: f'\\b{str}\\b', [
            'abundance', 'Abundance', 'ARG', 'ARGs'
        ]))),
        'description': {
            'info': 'The abundance of antibiotic resistance genes',
            'data': 'A CSV with one row per antibiotic in the format NAME, VALUE'
        }
    }
}

# The (case-insensitive) trigger keywords for each section
SECTION_KEYWORRDS = {
    'abstract': ['abstract'],
    'introduction': ['introduction'],
    'method': ['material', 'method'],
    'results': ['result'],
    'discussion': ['discussion'],
    'acknowledgements': ['acknowledgements'],
    'references': ['references'],
}

def create_location_span(span):
    if TKINTER_OFFSETS:
        return {
            'start': f'1.0+{span[0]}c',
            'end': f'1.0+{span[1]}c',
        }
    else:
        return {
            'start': span[0],
            'end': span[1],
        }

# Adjusts the span using the list of offsets
def adjust_span(span, offsets):
    offset = 0
    for (modified, local_offset) in offsets:
        if span[0] < modified:
            return (span[0] + offset, span[1] + offset)

        offset += local_offset

    return span

# Identify the id of common sections which may be used in the filters
# 'sections' list
def identify_sections(article):
    section_map = dict.fromkeys(SECTION_KEYWORRDS.keys())

    # Find the sections using keywords in the section title
    for id, section in enumerate(article['sections']):
        if section['name'] is None:
            continue

        section_name = section['name'].lower()
        for (name, keywords) in SECTION_KEYWORRDS.items():
            # Check if the section title contains any of the keywords
            if any(map(section_name.__contains__, keywords)):
                section_map[name] = id

    return section_map

# Removes all the references, text enclosed in parenthesis, from the given
# text. Returns the filtered text and offset markers to keep track of original
# offset
def exclude_references(text):
    previous_end = 0
    without_parenthesis = ''
    offsets = []
    for match in re.compile(r'\([^()]*\)').finditer(text):
        span = match.span()

        without_parenthesis += text[previous_end:span[0]]
        previous_end = span[1]

        # Keep track of the offset between the two strings
        offsets.append((len(without_parenthesis), span[1] - span[0]))

    return (without_parenthesis, offsets)

# Returns information given on the text by the given filter
def filter_text(filter_name, filter, text, text_offsets, article_name, kind,
                subtype, sample, expanding):
    information = []

    if 'regex' in filter:
        for match in filter['regex'].finditer(text):
            # We adjust for removed text using a offset
            span = adjust_span(match.span(), text_offsets)

            information.append({
                'title': filter_name,
                'data': match.group(),
                'sample': sample,
                'expanding': expanding,
                'stamp': datetime.now().isoformat(),
                'uuid': str(uuid.uuid4()),
                'source': {
                  'article': article_name,
                  'kind': kind,
                  'subtype': subtype,
                  'location': create_location_span(span),
                },
                'description': filter['description'],
            })
    elif 'source' in filter:
        # We only care about the first match for each section
        if (match := filter['source'].search(text)) is not None:
            # We adjust for removed text using a offset
            span = adjust_span(match.span(), text_offsets)

            information.append({
                'title': filter_name,
                'data': None,
                'sample': sample,
                'expanding': expanding,
                'stamp': datetime.now().isoformat(),
                'uuid': str(uuid.uuid4()),
                'source': {
                  'article': article_name,
                  'kind': kind,
                  'subtype': subtype,
                  'location': create_location_span(span),
                },
                'description': filter['description'],
            })
    elif 'categories' in filter:
        possible_categories = []
        default_category = None
        spans = []
        for (category_name, regex) in filter['categories'].items():
            if regex is None:
                default_category = category_name
            elif match := regex.search(text):
                # We adjust for removed text using a offset
                span = adjust_span(match.span(), text_offsets)

                possible_categories.append(category_name)
                spans.append(span)

        data, location = None, None
        if 0 < len(possible_categories):
            data = '/'.join(possible_categories)
            location = create_location_span(spans[0])
        elif default_category is not None:
            data = default_category
            location = create_location_span([0, 0])

        if data is not None:
            information.append({
                'title': filter_name,
                'data': data,
                'sample': sample,
                'expanding': expanding,
                'stamp': datetime.now().isoformat(),
                'uuid': str(uuid.uuid4()),
                'source': {
                  'article': article_name,
                  'kind': kind,
                  'subtype': subtype,
                  'location': location,
                },
                'description': filter['description'],
            })

    elif 'fancy' in filter:
        information = filter['fancy'](filter_name, text, text_offsets,
                                      article_name, kind, subtype)

    elif 'openai':
        # Only run openAI filter if API is enabled
        if OPENAI_ENABLED:
            print('OpenAI filters are unfortunetely not yet implemented')
            exit(-1)
    else:
        print('Unrecognized filter type')
        exit(-1)

    return information

# Identifies and extract relevant information from article
def identify_information(name, json_path):
    # Load the article
    if file := open(json_path):
        article = json.load(file)
    else:
        print(f'Failed to open file {json_path}')
        exit(-1)

    # All the information identified from the article
    information = []

    # Find the methods section using keywords in the section title
    sections = identify_sections(article)

    # Remove references from each section
    without_references = {}
    for id, section in enumerate(article['sections']):
        # Get the text without references, useful for example extracting years
        no_ref, no_ref_offsets = exclude_references(section['content'])
        without_references[id] = (no_ref, no_ref_offsets)

    for filter_name, filter in FILTERS.items():
        # The sample associated with filter, either unkown or article wide
        sample = -1 if 'sample associated' in filter and filter['sample associated'] else None

        # The expanding flag. If enabled the item can contain a CSV table that
        # will be expanded in `aggregate.py`. It may be displayed as a table
        # in user-facing interfaces
        expanding = True if 'expanding' in filter and filter['expanding'] else False

        # Find all figure caption information
        if 'figures' in filter['targets'] and filter['targets']['figures']:
            for id, figure in enumerate(article['figures']):
                if figure['caption'] is None:
                    continue

                information.extend(filter_text(filter_name, filter, figure['caption'],
                                               [], name, 'figure caption', id, sample, expanding))

        # Find all table caption information
        if 'tables' in filter['targets'] and filter['targets']['tables']:
            for id, table in enumerate(article['tables']):
                if table['caption'] is None:
                    continue

                information.extend(filter_text(filter_name, filter, table['caption'],
                                               [], name, 'table caption', id, sample, expanding))

        # Find all metadata information
        if 'metadata' in filter['targets']:
            # Check if current metadata is any of the metadata given
            for metadata_name in filter['targets']['metadata']:
                information.extend(filter_text(filter_name, filter, article['metadata'][metadata_name],
                                               [], name, 'metadata', metadata_name, sample, expanding))

        # Find all text section information
        if 'sections' in filter['targets']:
            for id, section in enumerate(article['sections']):
                # Check if current section or any of it's ancestors is one of the
                # required sections
                section_ids = map(lambda x: sections[x], filter['targets']['sections'])

                ancestor_id = id
                match = False
                while ancestor_id is not None:
                    if ancestor_id in section_ids:
                        match = True
                        break

                    ancestor_id = article['sections'][ancestor_id]['parent']

                # The section is not targeted by the filter
                if not match:
                    continue

                # Match using the filter
                information.extend(filter_text(filter_name, filter, without_references[id][0],
                                               without_references[id][1], name, 'section', id,
                                               sample, expanding))

    return information

# Create the export directory
os.makedirs(EXPORT_DIRECTORY, exist_ok=True)

# Look for 'web' argument
if len(sys.argv) == 1 or sys.argv[1] == 'web':
    TKINTER_OFFSETS = False
elif sys.argv[1] == 'native':
    TKINTER_OFFSETS = True
else:
    print('unrecognized arguments, exiting')
    exit(-1)

# Load the extract summary
if os.path.isfile(path := f'{EXTRACTED_PATH}/results.json') and (file := open(path)):
    extract_summary = json.load(file)
else:
    print('Failed to load extract results, are you sure you have ran the `extract.py` script?')
    exit(-1)

# Parse each article separately
article_paths = {}
for (name, path) in extract_summary.items():
    print(f'Identifiying information from {name} ... ', flush=True, end='')
    result = identify_information(name, path)
    print('done')

    # Export each article in a separate JSON file
    path = f'{EXPORT_DIRECTORY}/{name}.json'
    if file := open(path, 'w+'):
        json.dump(result, file)
    else:
        print(f'Failed to open file {path}')

    article_paths[name] = path

# Export JSON containing identified information
if file := open(file_path:=f'{EXPORT_DIRECTORY}/results.json', 'w+'):
    json.dump(article_paths, file)
else:
    print(f'Failed to open file {file_path}')
