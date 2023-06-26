# Literature survey software project

## Main idea

The goal of this project is to create a software that can assist in literature surveys if a few ways:

- Make the search more effective by creating a helpful interface where the article is divided in helpful sections.

- By integrating tools such as plot information extraction software and NLP to help find where certain information is located.

## Usage

Currently, the program consists of different scripts conducting different parts
of the process. They should be run in the following order

- `search.py <entrez_email> <search_terms_path>`
- `download.py <entrez_email>` (note: downloads a lot of data)
- `extract.py`
- **THIS**
  - **THIS**
    - `identify.py`
    - `interface.py`
  - **OR** (deprecated)
    - `identify.py native`
    - `native_interface.py`
  - `aggregate.py`
- **OR**
  - `aggregate.py blind`

The `entrez_email` is the email used for all Entrez API calls, can be any valid
email address. The `search_terms_path` argument is the path to a list containing
all newline-separated Entrez search terms, see `search_terms.txt`. The `blind`
option to `aggregate.py` indicates the output of `identify.py` should be used
directly, skipping the interface.

The `native` option to the `identify.py` script indicates the output should be
compatible with the native interface instead of the standard web interface.

WebPlotDigitizer (WPD) can be used in co-junction with the `interface.py` script.
For that to happen you have to compile a local version of the program. See the
[project repository](https://github.com/ankitrohatgi/WebPlotDigitizer/blob/master/DEVELOPER_GUIDELINES.md)
for build instructions. When the build is completed you have to to create a
symlink for interoperability between the script and program. Modify the
following command depending on your install location.

```sh
ln -s ../../output/interface/digitizer ./WebPlotDigitizer/app/
```

After creating the symlink, start the webserver and then enter the local WPD
website. Upload the `wpd_integration.js` script in the web interface by pressing
"file" and then "run script". After the setup WPD should automatically load any
image that is opened inside of the `interactive.py` script.

The output of each script is stored inside of it's respective folder in the
`output` folder. The final program output is that of the `aggregate.py` script.
This is a CSV file containing the extracted data for all articles, the JSON
output also contains source references.

## Milestones

### Search for articles and download them

- [x] Query PubMed
- [ ] Download articles
  - [x] From PubMed Central open-access dataset
  - [ ] From other common sources
- [x] Retrieve metadata

### Divide the text into its different parts

- [x] PubMed Central XML
  - [x] Identify headers and text body
  - [x] Identify graphs
  - [x] Identify tables
- [ ] Basic PDF
  - [x] Identify headers and text body
  - [x] Identify graphs
  - [ ] Identify tables

### Extract information from tables, text and plots

- [x] Extract information from text
- [ ] Extract information from tables
- [ ] Extract information from plots

### Identify and extract relevant data

#### Method for identifying easy to find information in the text

- [x] Title of paper
- [x] Publishing year
- [x] Sampling year
- [x] Method (single plex or multiplex)
- [x] Sample type
- [x] Is a cite polluted or not
- [ ] Identify and extract information from relevant plots and tables
  - [ ] Abundance of antibiotic resistance genes
  - [ ] Unit of gene abundance (often occurrence/16s rRNA)
- [ ] GPT API integration

### Create an interface where the user can interact with the article in a structured way

- [ ] More to come

## Steps

1. Search for articles and download them. Some can be downloaded from an API, others has to be downloaded from the Chalmers library.

<https://pubmed.ncbi.nlm.nih.gov/download/>

<https://www.ncbi.nlm.nih.gov/books/NBK25501/>

2. Divide the text into its different parts.

- Introduction
- Methods / Material and methods
- Results / Results and discussion
- Discussion
- Figures
- Tables

This could be done with a simple regex, or something like that.


