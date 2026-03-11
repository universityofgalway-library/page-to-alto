# PAGE XML to ALTO XML converter

# page_to_alto.py

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

All four PAGE region types are converted. Non-text regions are identified by `TAGREFS` pointing to `<LayoutTag>` entries declared in the `<Tags>` section of the ALTO file (see [Layout tags](#layout-tags) below).

| PAGE XML | ALTO XML | TAGREFS |
|---|---|---|
| `<TextRegion>` | `<ComposedBlock>` + `<TextBlock>` | `layout_text` |
| `<TableRegion>` | `<ComposedBlock>` + one `<TextBlock>` per `<TableCell>` | `layout_table` |
| `<ImageRegion>` | `<Illustration>` | `layout_image` |
| `<SeparatorRegion>` | `<GraphicalElement>` | `layout_separator` |
| `<TextLine>` | `<TextLine>` (coordinates from `<Baseline>` if present, else `<Coords>`) | — |
| `<Word>` | `<String>` | — |
| `<TextEquiv conf="...">` | `<String WC="...">` (omitted if no confidence value in source) | — |
| Inter-word spacing | `<SP>` (10px fixed width) | — |

### Tables

PAGE tables use `TableRegion > TableCell > TextLine > Word`. ALTO has no native table structure, so each cell becomes its own `<TextBlock>` inside a single `<ComposedBlock>` that spans the full table extent. The `<ComposedBlock>` carries `TAGREFS="layout_table"` so consumers can identify the table boundary. Where `row` and `col` attributes are present on a `<TableCell>`, they are preserved on the corresponding `<TextBlock>` as a `CUSTOM` attribute (`row:N col:N`).

### Images

`<ImageRegion>` marks illustrations or photographs on the page. These carry only coordinate data in PAGE XML — no transcribed text. They are converted to ALTO `<Illustration>` elements preserving the bounding box.

### Separators

`<SeparatorRegion>` in PAGE XML marks ruled lines, column dividers, and other non-textual separators. These carry only coordinate data. They are converted to ALTO `<GraphicalElement>` elements preserving the bounding box.

### Layout tags

A `<Tags>` section is written once at the top of each ALTO file declaring four `<LayoutTag>` entries:

| ID | Label | Applied to |
|---|---|---|
| `layout_text` | `Text` | `<ComposedBlock>` from TextRegion |
| `layout_table` | `Table` | `<ComposedBlock>` from TableRegion |
| `layout_image` | `Figure` | `<Illustration>` from ImageRegion |
| `layout_separator` | `Separator` | `<GraphicalElement>` from SeparatorRegion |

### Reading order

The PAGE `<ReadingOrder>` block is read and used to sort all regions (of all types) before writing them to ALTO. ALTO has no dedicated reading-order element; order is conveyed implicitly by document sequence. Regions not listed in `<ReadingOrder>` appear last in document order.

### IDs

All ALTO IDs are prefixed with the source filename stem to ensure uniqueness across pages in a merged document, e.g. `gaodhal_0001_0001-0001_r2l1w3`. Table cell blocks use the cell's own PAGE `id`; their enclosing `<ComposedBlock>` gets a `_cb` suffix on the table region ID.

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

For merged multi-page documents, provenance metadata is taken from the first page only.

## Known limitation

Inter-word spacing (`<SP>`) uses a fixed width of 10px. Actual gaps could be computed from adjacent word bounding boxes but are not.
