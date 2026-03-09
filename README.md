# PAGE XML to ALTO XML converter

Converts [PAGE XML](http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15) files exported from Transkribus into [ALTO XML v3](http://www.loc.gov/standards/alto/ns-v3#). Multiple PAGE files belonging to the same document are merged into a single ALTO file by default.

## Requirements

Python 3.10+, standard library only.

## Usage

```
python page_to_alto.py <input_folder> [--output-folder <path>] [--no-merge]
```

| Argument | Default | Description |
|---|---|---|
| `input_folder` | *(required)* | Folder containing PAGE XML files |
| `--output-folder`, `-o` | `alto_xml` | Destination folder for ALTO output |
| `--no-merge` | off | Write one ALTO file per PAGE file instead of merging by document |

### Examples

```bash
# Merge pages by document (default)
python page_to_alto.py ./page_xml

# Write one ALTO file per PAGE file
python page_to_alto.py ./page_xml --output-folder ./alto --no-merge
```

## File grouping and naming

Files are grouped by **base name** — everything before the final hyphen-number suffix. For example:

```
gaodhal_0001_0001-0001.xml  →  base: gaodhal_0001_0001  page: 1
gaodhal_0001_0001-0002.xml  →  base: gaodhal_0001_0001  page: 2
```

These two files are merged into a single `gaodhal_0001_0001.xml` ALTO output. Files without a hyphen-number suffix are treated as single-page documents.

## Element mapping

| PAGE XML | ALTO XML |
|---|---|
| `<Page>` | `<Page>` |
| `<TextRegion>` | `<ComposedBlock>` + `<TextBlock>` |
| `<TextLine>` | `<TextLine>` (coordinates from `<Baseline>` if present, else `<Coords>`) |
| `<Word>` | `<String>` |
| `<TextEquiv conf="...">` | `<String WC="...">` (omitted if no confidence value in source) |
| Inter-word spacing | `<SP>` (10px fixed width) |

### Reading order

The PAGE `<ReadingOrder>` block is read and used to sort `<TextRegion>` elements before writing them to ALTO. ALTO has no dedicated reading-order element; order is conveyed implicitly by document sequence. Regions not listed in `<ReadingOrder>` appear last in document order.

### IDs

All ALTO IDs are prefixed with the source filename stem to ensure uniqueness across pages in a merged document, e.g. `gaodhal_0001_0001-0001_r2l1w3`.

## Metadata

The `<Description>` block in the ALTO output is populated from the first page's PAGE `<Metadata>` block:

| PAGE field | ALTO element |
|---|---|
| `<Creator>` `name=` | `processingSoftware/softwareName` |
| `<Creator>` `version=` | `processingSoftware/softwareVersion` |
| `<Created>` | `processingDateTime` |
| `<LastChange>` | `processingStepSettings` |

A conversion note is always appended to `processingStepDescription`:

> Automatically converted from PAGE XML (http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15) by the University of Galway Library.

## Limitations

- Only `<TextRegion>` is converted. `<TableRegion>`, `<ImageRegion>`, `<SeparatorRegion>` and other PAGE region types are ignored.
- Inter-word spacing (`<SP>`) uses a fixed width of 10px rather than a measured value.
- For merged documents, provenance metadata is taken from the first page only.
