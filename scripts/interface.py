#!/usr/bin/env python3

'''
A web-based graphical interface for interacting with the data extracted from
articles by `extract.py` and `identify.py`.
'''

from bottle import run, template, get, redirect, static_file, response, post, request
import json
import os
import shutil

# Resource prefix
RES_PREFIX = os.path.dirname(__file__)

# The path of the extract results file
EXTRACT_FILE = './output/extract/results.json'

# The path of the identifed results file
IDENTIFY_FILE = './output/identify/results.json'

# The path to the download results file
DOWNLOAD_FILE = './output/download/results.json'

# The export directory path
EXPORT_DIRECTORY = './output/interface'
EXPORT_SUMMARY_PATH = f'{EXPORT_DIRECTORY}/results.json'

# Global variables keeping track of loaded information
EXTRACT_PATHS = {}
IDENTIFY_PATHS = {}
RESULT_PATHS = {}

# Load the given article (cached)
ARTICLE_CACHE = None
def load_article(article_id):
    global ARTICLE_CACHE

    if ARTICLE_CACHE is not None and ARTICLE_CACHE[0] == article_id:
        return ARTICLE_CACHE[1]

    ARTICLE_CACHE = [article_id, json.load(open(EXTRACT_PATHS[article_id]))]
    return ARTICLE_CACHE[1]

# Load the info associated with the given article (cached)
ARTICLE_INFO_CACHE = None
def load_article_info(article_id):
    global ARTICLE_INFO_CACHE

    if ARTICLE_INFO_CACHE is not None and ARTICLE_INFO_CACHE[0] == article_id:
        return ARTICLE_INFO_CACHE[1]

    ARTICLE_INFO_CACHE = [article_id, json.load(open(IDENTIFY_PATHS[article_id]))]
    return ARTICLE_INFO_CACHE[1]

# Redirect the index to the first article
@get('/')
def index():
    return redirect(f'/{list(EXTRACT_PATHS.keys())[0]}')

# 404 favicon requests
@get('/favicon.ico')
def favicon():
    response.status = 404
    return 'No favicon'

# Load a article
@get('/<article_id>')
def article(article_id):
    return template(open(f'{RES_PREFIX}/web/index.html').read(), article_id=article_id,
                    article=load_article(article_id), articles=list(EXTRACT_PATHS.keys()))

# Load article figure
@get('/<article_id>/img/<figure:int>')
def figure(article_id, figure):
    return static_file(load_article(article_id)['figures'][figure]['path'], './')

# Set the figure in WebPlotDigitizer
@get('/<article_id>/wpd/<figure:int>')
def wpd(article_id, figure):
    # To allow access we copy the figure into the interface export
    # directory. We also output a JSON file containing the path relative
    # to the export directory
    figure = load_article(article_id)['figures'][figure]
    os.makedirs(f'{EXPORT_DIRECTORY}/digitizer', exist_ok=True)

    # Create the output image
    path = f'{EXPORT_DIRECTORY}/digitizer/{figure["path"].split("/")[-1]}'
    shutil.copy(figure['path'], path)

    # Update the digitizer json
    if file := open(file_path := f'{EXPORT_DIRECTORY}/digitizer/digitizer.json', 'w+'):
        json.dump({'path': os.path.relpath(path, EXPORT_DIRECTORY)}, file)
    else:
        print(f'Failed to open file {file_path}')

# Load identified information
@get('/<article_id>/identified/<index:int>')
def identified(article_id, index):
    return load_article_info(article_id)[index]

# Load the number of identified info, the number of pieces of info identified
# for the article
@get('/<article_id>/identified')
def identified_count(article_id):
    return {'length': len(load_article_info(article_id))}

# Returns (or creates) the stored information for the given article
def init_info_store(article_id):
    if article_id in RESULT_PATHS and (file := open(RESULT_PATHS[article_id])):
        info = json.load(file)
    else:
        RESULT_PATHS[article_id] = f'{EXPORT_DIRECTORY}/{article_id}.json'
        info = []

        json.dump(info, open(RESULT_PATHS[article_id], 'w+'))

    json.dump(RESULT_PATHS, open(EXPORT_SUMMARY_PATH, 'w+'))

    return info

# Store information
@post('/<article_id>/store')
def store_info(article_id):
    info = init_info_store(article_id)
    info.append(request.json)
    json.dump(info, open(RESULT_PATHS[article_id], 'w'))

# Load stored information
@get('/<article_id>/info/<index:int>')
def info(article_id, index):
    return init_info_store(article_id)[index]

# Delete stored information
@post('/<article_id>/delete/<uuid>')
def delete_info(article_id, uuid):
    infos = init_info_store(article_id)
    infos = [info for info in infos if info['uuid'] != uuid]
    json.dump(infos, open(RESULT_PATHS[article_id], 'w'))

# Update stored information (from form)
@post('/<article_id>/update/<uuid>')
def update_info(article_id, uuid):
    infos = init_info_store(article_id)

    # Find the uuid
    for info in infos:
        if info['uuid'] != uuid:
            continue

        # Update the info with the form data
        info['title'] = request.forms.get('title')
        info['data'] = request.forms.get('data')
        info['timestamp'] = request.forms.get('timestamp')

        if (sample := request.forms.get('sample')).strip() != '':
            info['sample'] = int(sample)
        else:
            info['sample'] = None

        if request.forms.get('expanding') is None:
            info['expanding'] = False
        else:
            info['expanding'] = True

    # Output result
    json.dump(infos, open(RESULT_PATHS[article_id], 'w'))

# Load the number of stored info, the number of pieces of info stored for the
# article
@get('/<article_id>/info')
def info_count(article_id):
    length = 0
    if article_id in RESULT_PATHS:
        length = len(json.load(open(RESULT_PATHS[article_id])))

    return {'length': length}

# Load article data (metadata)
@get('/<article_id>/metadata/<data>')
def metadata(article_id, data):
    return load_article(article_id)['metadata'][data]

# Load article data
@get('/<article_id>/<kind>/<index:int>')
def data(article_id, kind, index):
    return load_article(article_id)[kind][index]

# Load static files
@get('/res/<path:path>')
def static(path):
    return static_file(path, f'{RES_PREFIX}/web/')

# Load article PDF
@get('/<article_id>/pdf')
def pdf(article_id):
    path = DOWNLOAD_PATHS[article_id]

    # Get the PDF with the shortest name. This improves the chance of finding
    # the article itself instead of supplementary PDFs
    pdf_path = None
    for filename in os.listdir(path):
        if filename.endswith('.pdf'):
            filepath = os.path.join(path, filename)

            if pdf_path is None or len(filepath) < len(pdf_path):
                pdf_path = filepath

    if pdf_path:
        return static_file(pdf_path, './')
    else:
        return None

# Only run if non-library
if __name__ == '__main__':
    # Load the extract results
    if os.path.isfile(EXTRACT_FILE) and (file := open(EXTRACT_FILE)):
        EXTRACT_PATHS = json.load(file)
    else:
        print('Failed to load extract results, are you sure you have ran the `extract.py` script?')
        exit(-1)

    # Load the identify results
    if os.path.isfile(IDENTIFY_FILE) and (file := open(IDENTIFY_FILE)):
        IDENTIFY_PATHS = json.load(file)
    else:
        print('Failed to load identify results, are you sure you have ran the `identify.py` script?')
        exit(-1)

    # Load the download results
    if os.path.isfile(DOWNLOAD_FILE) and (file := open(DOWNLOAD_FILE)):
        DOWNLOAD_PATHS = json.load(file)['articles']
    else:
        print('Failed to load download results, are you sure you have ran the `download.py` script?')
        exit(-1)

    # Create the export directory
    os.makedirs(EXPORT_DIRECTORY, exist_ok=True)

    # Load the output paths
    if os.path.isfile(EXPORT_SUMMARY_PATH) and (file := open(EXPORT_SUMMARY_PATH)):
        RESULT_PATHS = json.load(file)
    else:
        RESULT_PATHS = {}
        json.dump(RESULT_PATHS, open(EXPORT_SUMMARY_PATH, 'w+'))

    # Run webserver
    run(host='localhost', port=3030)
