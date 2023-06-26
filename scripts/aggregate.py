#!/usr/bin/env python3

'''
A script that aggregates the JSON output of `interface.py` into a JSON file
containing per-article information.

If the `blind` keyword is passed, the output of the `identify.py` script is
used directly and the `interface.py` output is ignored. This is useful for
better understanding the identify output and stress testing this script.

For each article and information kind, the latest written piece of information
is used. Thereby newer data will override earlier data.
'''

import json
import csv
import os
import sys

# The path of the interface results file
INTERFACE_RESULT = './output/interface/results.json'

# The path of the identify results file
IDENTIFY_RESULT = './output/identify/results.json'

# The export directory path
EXPORT_DIRECTORY = './output/aggregate'

# Read the output of `identify.py` or `interface.py`
def load(summary_path):
    # Load the summary file
    if os.path.isfile(summary_path) and (file := open(summary_path)):
        summary = json.load(file)
    else:
        print(f'Failed to load {summary_path}, are you sure you have ran the previous script?')
        exit(-1)

    information = {}
    for article_name, path in summary.items():
        if file := open(path):
            article = json.load(file)
        else:
            print(f'Failed to open file {path}')
            exit(-1)

        information[article_name] = {}
        for info in article:
            information[article_name][info['title']] = info

    return information

# Create the export directory
os.makedirs(EXPORT_DIRECTORY, exist_ok=True)

print(f'Filtering through information ... ', flush=True, end='')
if len(sys.argv) == 1:
    information = load(INTERFACE_RESULT)
elif sys.argv[1] == 'blind':
    information = load(IDENTIFY_RESULT)
else:
    print('unrecognized arguments, exiting')
    exit(-1)
print('done')

# We separate the information into two different dictionaries. One for article
# associated data and one for sample associated data. We collect all data
# associated with each sample into a single group
articles, unique_article_titles = {}, set()
samples, unique_sample_titles = [], set()
for (article_name, infos) in information.items():
    articles[article_name] = {}
    article_samples = {}

    for (title, info) in infos.items():
        if info['sample'] is None:
            articles[article_name][title] = info
            unique_article_titles.add(info['title'])
        else:
            nr = int(info['sample'])
            if nr not in article_samples:
                article_samples[nr] = {}

            article_samples[nr][title] = info
            unique_sample_titles.add(info['title'])

    # Add all samples to sample list
    for (nr, sample) in article_samples.items():
        sample['article'] = article_name
        sample['sample number'] = nr
        samples.append(sample)

print(f'Exporting in JSON format ... ', flush=True, end='')
if ((article_file := open(f'{EXPORT_DIRECTORY}/articles.json', 'w+')) and
    (samples_file := open(f'{EXPORT_DIRECTORY}/samples.json', 'w+'))):
    json.dump(articles, article_file)
    json.dump(samples, samples_file)
    print('done')
else:
    print('failed')
    exit(-1)

print(f'Exporting in CSV format ... ', flush=True, end='')
if ((article_file := open(f'{EXPORT_DIRECTORY}/articles.csv', 'w+')) and
    (samples_file := open(f'{EXPORT_DIRECTORY}/samples.csv', 'w+'))):
    article_file = csv.writer(article_file)

    # The header will be the article followed by one field for each unique
    # information title, meaning every row will store one article. The fields
    # specified on the article will be filled out. This will ease information
    # usage in normal spreadsheet programs. In this output format we drop the
    # source, which can be accessed through the JSON export
    headers = ['article id']
    headers.extend(list(unique_article_titles))
    article_file.writerow(headers)

    # Create a header map
    headers_map = dict([(header, i) for (i, header) in enumerate(headers)])

    for article, article_info in articles.items():
        row = [None] * len(headers)

        # Set the data
        row[headers_map['article id']] = article
        for (title, info) in article_info.items():
            row[headers_map[title]] = info['data']

        # Save as row
        article_file.writerow(row)

    # We then have to do almost the same thing for the samples CSV file.
    # The main difference is that we expand expanding information for easier
    # CSV handling

    # Determine all internal fields (fields expanded from expandable infos)
    internal_fields = set()
    for sample in samples:
        for (title, info) in sample.items():
            if title == 'article' or title == 'sample number':
                continue

            if info['expanding'] and info['data'] is not None:
                for line in csv.reader(info['data'].split('\n')):
                    internal_fields.add(line[0].strip().lower())

    # Open the CSV file and write header
    samples_file = csv.writer(samples_file)
    headers = ['article id', 'sample number']
    headers.extend(list(unique_sample_titles))
    headers.extend(list(internal_fields))
    samples_file.writerow(headers)

    # Create a header map
    headers_map = dict([(header, i) for (i, header) in enumerate(headers)])

    for sample in samples:
        row = [None] * len(headers)

        # Set the data
        row[headers_map['article id']] = sample['article']
        row[headers_map['sample number']] = sample['sample number']
        for (title, info) in sample.items():
            if title == 'article' or title == 'sample number':
                continue

            # Expand expanding information
            if info['expanding'] and info['data'] is not None:
                for line in csv.reader(info['data'].split('\n')):
                    name = line[0].strip().lower()
                    value = line[1].strip()

                    row[headers_map[name]] = value

            row[headers_map[title]] = info['data']

        # Save as row
        samples_file.writerow(row)

    print('done')
else:
    print('failed')
    exit(-1)
