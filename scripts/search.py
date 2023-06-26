#!/usr/bin/env python3

'''
A script for searching PubMed with multiple search terms and summerizing the
resulting IDs.

The first argument is the email address to use with the Entrez API. The second
argument specifies the path to a file containing the search terms. A newline
seperated file with one line per search term, with support for comments
prefixed by '#'.

The program output is contained in the `results.json` file within the output
directory. It holds all PubMed IDs fond matching any of the search terms.
'''

from Bio import Entrez
import sys
import json
import os

# The path of the export file
EXPORT_FILE = './output/search/results.json'

# Performs a Entrez search using the given search term, returns the result
def perform_search(term):
    # generate query to Entrez eSearch
    e_search = Entrez.esearch(db='pubmed', term=term, retmax=10000)

    # get e_search result as dict object
    result = Entrez.read(e_search)

    return result

# Returns the matching PubMed ids for all the terms combined
def perform_searches(terms):
    matches_pmids = []
    for term in terms:
        print(f'Searching with \'{term}\' ... ', end="", flush=True)
        ids = perform_search(term)['IdList']
        matches_pmids.extend(ids)
        print(f'done ({len(ids)} results)')

    return matches_pmids

# Remember to specify email address and search terms
if len(sys.argv) == 3:
    Entrez.email = sys.argv[1]
    if file := open(sys.argv[2]):
        search_terms = file.readlines()
    else:
        print(f'Failed to open file {sys.argv[2]}')
        exit(-1)
else:
    print('./search.py email search_terms')
    print('')
    print('email:        The email address for Entrez')
    print('search_terms: path to file with newline seperated search terms')
    exit(-1)

# Create the output directory
os.makedirs(os.path.dirname(EXPORT_FILE), exist_ok=True)

# Parse the list of search terms
search_terms = [term.strip() for term in search_terms
                if term.strip() != "" and not term.startswith('#')]

# Get PubMed IDs
pmids = perform_searches(search_terms)
print(f'\nFound {len(pmids)} PubMed IDs in total')

# Output the result to EXPORT_FILE
if file := open(EXPORT_FILE, 'w+'):
    data = {
            'search_terms': search_terms,
            'pmids': pmids,
        }

    # Export the data
    json.dump(data, file)
else:
    print(f'Failed to open file {EXPORT_FILE}')
    exit(-1)
