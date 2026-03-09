#!/usr/bin/env python3
"""
Convert and merge PAGE XML files to ALTO XML format.
Groups files by base name (everything before the hyphen) and creates
multi-page ALTO documents.

All PAGE region types are preserved:
  - TextRegion  → ComposedBlock > TextBlock (TAGREFS="layout_text")
  - TableRegion → ComposedBlock > one TextBlock per TableCell (TAGREFS="layout_table")
  - ImageRegion → Illustration (TAGREFS="layout_image")
  - SeparatorRegion → GraphicalElement (TAGREFS="layout_separator")

Three LayoutTags are declared once in <Tags> and referenced throughout.
"""

import argparse
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------------------
# Fixed ALTO LayoutTag IDs used throughout the document
# ---------------------------------------------------------------------------
TAG_TABLE     = 'layout_table'
TAG_IMAGE     = 'layout_image'
TAG_SEPARATOR = 'layout_separator'
TAG_TEXT      = 'layout_text'


def parse_filename(filename: str) -> Tuple[str, int]:
    """
    Parse filename to extract base name and page number.

    Args:
        filename: Filename like 'gaodhal_0001_0001-0001.xml'

    Returns:
        Tuple of (base_name, page_number)
    """
    stem = Path(filename).stem
    match = re.match(r'^(.+)-(\d+)$', stem)
    if match:
        base_name = match.group(1)
        page_number = int(match.group(2))
        return base_name, page_number
    else:
        # If no hyphen-number pattern, treat entire stem as base
        return stem, 1


def group_files(input_folder: str) -> Dict[str, List[Tuple[int, str]]]:
    """
    Group PAGE XML files by their base name.

    Args:
        input_folder: Path to folder containing PAGE XML files

    Returns:
        Dictionary mapping base names to lists of (page_number, filepath) tuples
    """
    groups = defaultdict(list)

    for filename in os.listdir(input_folder):
        if filename.endswith('.xml'):
            filepath = os.path.join(input_folder, filename)
            base_name, page_number = parse_filename(filename)
            groups[base_name].append((page_number, filepath))

    # Sort pages within each group
    for base_name in groups:
        groups[base_name].sort(key=lambda x: x[0])

    return groups


def parse_page_xml(filepath: str) -> ET.Element:
    """Parse a PAGE XML file and return the root element."""
    tree = ET.parse(filepath)
    return tree.getroot()


def get_page_dimensions(page_root: ET.Element) -> Tuple[int, int]:
    """Extract page dimensions from PAGE XML."""
    ns = {'pc': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}
    page_elem = page_root.find('.//pc:Page', ns)

    if page_elem is not None:
        width = int(page_elem.get('imageWidth', '0'))
        height = int(page_elem.get('imageHeight', '0'))
        return width, height
    return 0, 0


def convert_coords(coords_str: str) -> Tuple[int, int, int, int]:
    """
    Convert PAGE XML coords to ALTO format (HPOS, VPOS, WIDTH, HEIGHT).

    Args:
        coords_str: Space-separated x,y coordinate pairs

    Returns:
        Tuple of (hpos, vpos, width, height)
    """
    if not coords_str:
        return 0, 0, 0, 0

    points = []
    for point in coords_str.split():
        x, y = map(int, point.split(','))
        points.append((x, y))

    if not points:
        return 0, 0, 0, 0

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    hpos = min(xs)
    vpos = min(ys)
    width = max(xs) - hpos
    height = max(ys) - vpos

    return hpos, vpos, width, height


def extract_page_metadata(page_root: ET.Element) -> dict:
    """
    Extract metadata from a PAGE XML root element.

    Parses the <Metadata> block and returns a plain dict with the
    following keys (all optional, value is None when absent):

        creator     – raw <Creator> string
                      e.g. 'prov=READ-COOP:name=PyLaia@TranskribusPlatform:version=2.3.0:...'
        sw_name     – software name parsed from creator  (e.g. 'PyLaia@TranskribusPlatform')
        sw_version  – version string parsed from creator (e.g. '2.3.0')
        created     – <Created> ISO-8601 timestamp string
        last_change – <LastChange> ISO-8601 timestamp string
        comments    – <Comments> text (stripped)
    """
    ns = {'pc': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}
    meta = page_root.find('pc:Metadata', ns)

    result = {
        'creator': None,
        'sw_name': None,
        'sw_version': None,
        'created': None,
        'last_change': None,
        'comments': None,
    }

    if meta is None:
        return result

    def _text(tag: str) -> str | None:
        el = meta.find(f'pc:{tag}', ns)
        return el.text.strip() if el is not None and el.text else None

    result['creator']     = _text('Creator')
    result['created']     = _text('Created')
    result['last_change'] = _text('LastChange')
    result['comments']    = _text('Comments')

    # Parse the colon-separated key=value pairs in <Creator>
    # e.g. prov=READ-COOP:name=PyLaia@TranskribusPlatform:version=2.3.0:...
    if result['creator']:
        pairs = {}
        for part in result['creator'].split(':'):
            if '=' in part:
                k, _, v = part.partition('=')
                pairs[k.strip()] = v.strip()
        result['sw_name']    = pairs.get('name')
        result['sw_version'] = pairs.get('version')

    return result


def create_alto_tags() -> ET.Element:
    """
    Create the ALTO <Tags> section declaring LayoutTags for all region types.

    These fixed IDs (TAG_TABLE, TAG_IMAGE, TAG_SEPARATOR, TAG_TEXT) are
    referenced via TAGREFS on every layout element produced by this script.
    """
    tags = ET.Element('Tags')
    ET.SubElement(tags, 'LayoutTag', ID=TAG_TEXT,      LABEL='Text')
    ET.SubElement(tags, 'LayoutTag', ID=TAG_TABLE,     LABEL='Table')
    ET.SubElement(tags, 'LayoutTag', ID=TAG_IMAGE,     LABEL='Figure')
    ET.SubElement(tags, 'LayoutTag', ID=TAG_SEPARATOR, LABEL='Separator')
    return tags


def extract_page_metadata(page_root: ET.Element) -> dict:
    """
    Extract metadata from a PAGE XML root element.

    Parses the <Metadata> block and returns a plain dict with the
    following keys (all optional, value is None when absent):

        creator     – raw <Creator> string
                      e.g. 'prov=READ-COOP:name=PyLaia@TranskribusPlatform:version=2.3.0:...'
        sw_name     – software name parsed from creator  (e.g. 'PyLaia@TranskribusPlatform')
        sw_version  – version string parsed from creator (e.g. '2.3.0')
        created     – <Created> ISO-8601 timestamp string
        last_change – <LastChange> ISO-8601 timestamp string
        comments    – <Comments> text (stripped)
    """
    ns = {'pc': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}
    meta = page_root.find('pc:Metadata', ns)

    result = {
        'creator': None,
        'sw_name': None,
        'sw_version': None,
        'created': None,
        'last_change': None,
        'comments': None,
    }

    if meta is None:
        return result

    def _text(tag: str) -> str | None:
        el = meta.find(f'pc:{tag}', ns)
        return el.text.strip() if el is not None and el.text else None

    result['creator']     = _text('Creator')
    result['created']     = _text('Created')
    result['last_change'] = _text('LastChange')

    # Parse the colon-separated key=value pairs in <Creator>
    # e.g. prov=READ-COOP:name=PyLaia@TranskribusPlatform:version=2.3.0:...
    if result['creator']:
        pairs = {}
        for part in result['creator'].split(':'):
            if '=' in part:
                k, _, v = part.partition('=')
                pairs[k.strip()] = v.strip()
        result['sw_name']    = pairs.get('name')
        result['sw_version'] = pairs.get('version')

    return result


def create_alto_header(metadata: dict | None = None) -> ET.Element:
    """
    Create ALTO XML header/description section.

    Args:
        metadata: dict returned by extract_page_metadata(), or None to
                  produce a minimal header with no provenance information.
    """
    description = ET.Element('Description')

    measurement_unit = ET.SubElement(description, 'MeasurementUnit')
    measurement_unit.text = 'pixel'

    ET.SubElement(description, 'sourceImageInformation')

    # Only emit OCRProcessing when we have something meaningful to say
    meta = metadata or {}
    sw_name    = meta.get('sw_name')    or 'Transkribus'
    sw_version = meta.get('sw_version')
    created    = meta.get('created')
    last_change= meta.get('last_change')

    ocr_processing = ET.SubElement(description, 'OCRProcessing', ID='OCR_1')
    ocr_step = ET.SubElement(ocr_processing, 'ocrProcessingStep')

    if created:
        dt_elem = ET.SubElement(ocr_step, 'processingDateTime')
        dt_elem.text = created

    if last_change:
        lc_elem = ET.SubElement(ocr_step, 'processingStepSettings')
        lc_elem.text = f'LastChange: {last_change}'

    conversion_note = (
        'Automatically converted from PAGE XML '
        '(http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15) '
        'by the University of Galway Library.'
    )
    desc_elem = ET.SubElement(ocr_step, 'processingStepDescription')
    desc_elem.text = conversion_note

    processing_sw = ET.SubElement(ocr_step, 'processingSoftware')
    sw_name_elem = ET.SubElement(processing_sw, 'softwareName')
    sw_name_elem.text = sw_name
    if sw_version:
        sw_version_elem = ET.SubElement(processing_sw, 'softwareVersion')
        sw_version_elem.text = sw_version

    return description


def make_id(page_prefix: str, source_id: str) -> str:
    """
    Build a globally unique ALTO ID by combining the page prefix with
    the source PAGE XML id.

    Args:
        page_prefix: Stem of the source PAGE XML filename (e.g. 'gaodhal_0001_0001-0001')
        source_id:   id attribute value from the PAGE XML element (e.g. 'r2l1w3')

    Returns:
        A string suitable for use as an XML ID attribute, e.g.
        'gaodhal_0001_0001-0001_r2l1w3'
    """
    return f'{page_prefix}_{source_id}'


def convert_textline(line_elem: ET.Element, ns: dict,
                     page_prefix: str, block_idx: int, line_idx: int) -> ET.Element:
    """Convert a PAGE TextLine to ALTO TextLine."""
    # Derive line ID from source, falling back to positional index
    src_line_id = line_elem.get('id', f'block{block_idx}_line{line_idx}')
    line_id = make_id(page_prefix, src_line_id)

    # Use Baseline points for HPOS/VPOS/WIDTH/HEIGHT if present,
    # otherwise fall back to Coords
    baseline = line_elem.find('pc:Baseline', ns)
    coords_elem = line_elem.find('pc:Coords', ns)

    if baseline is not None:
        coords_str = baseline.get('points', '')
    elif coords_elem is not None:
        coords_str = coords_elem.get('points', '')
    else:
        coords_str = ''

    hpos, vpos, width, height = convert_coords(coords_str)

    textline = ET.Element('TextLine',
                          ID=line_id,
                          HPOS=str(hpos),
                          VPOS=str(vpos),
                          WIDTH=str(width),
                          HEIGHT=str(height))

    # Process words
    words = line_elem.findall('pc:Word', ns)
    for word_idx, word_elem in enumerate(words):
        src_word_id = word_elem.get('id', f'{src_line_id}_w{word_idx}')
        word_id = make_id(page_prefix, src_word_id)

        word_coords = word_elem.find('pc:Coords', ns)
        if word_coords is not None:
            w_hpos, w_vpos, w_width, w_height = convert_coords(
                word_coords.get('points', ''))
        else:
            w_hpos, w_vpos, w_width, w_height = 0, 0, 0, 0

        # Get word text and optional per-word confidence from PAGE TextEquiv
        text_equiv_elem = word_elem.find('pc:TextEquiv', ns)
        if text_equiv_elem is not None:
            unicode_elem = text_equiv_elem.find('pc:Unicode', ns)
            word_text = (unicode_elem.text or '') if unicode_elem is not None else ''
            conf = text_equiv_elem.get('conf')  # present only when Transkribus exports it
        else:
            word_text = ''
            conf = None

        string_attribs = dict(
            ID=word_id,
            HPOS=str(w_hpos),
            VPOS=str(w_vpos),
            WIDTH=str(w_width),
            HEIGHT=str(w_height),
            CONTENT=word_text,
        )
        if conf is not None:
            string_attribs['WC'] = conf  # map PAGE conf → ALTO WC verbatim

        ET.SubElement(textline, 'String', **string_attribs)

        # Add space after word (except last word)
        if word_idx < len(words) - 1:
            ET.SubElement(textline, 'SP',
                          WIDTH='10',
                          VPOS=str(w_vpos),
                          HPOS=str(w_hpos + w_width))

    return textline


def convert_textregion(region_elem: ET.Element, ns: dict,
                       page_prefix: str, block_idx: int) -> ET.Element:
    """
    Convert a PAGE TextRegion to ALTO ComposedBlock > TextBlock.
    Tagged as layout_text via TAGREFS.
    """
    src_region_id = region_elem.get('id', f'region{block_idx}')
    cblock_id = make_id(page_prefix, f'{src_region_id}_cb')
    block_id  = make_id(page_prefix, src_region_id)

    coords_elem = region_elem.find('pc:Coords', ns)
    coords_str = coords_elem.get('points', '') if coords_elem is not None else ''
    hpos, vpos, width, height = convert_coords(coords_str)

    composed_block = ET.Element('ComposedBlock',
                                ID=cblock_id,
                                HPOS=str(hpos),
                                VPOS=str(vpos),
                                WIDTH=str(width),
                                HEIGHT=str(height),
                                TAGREFS=TAG_TEXT)

    text_block = ET.SubElement(composed_block, 'TextBlock',
                               ID=block_id,
                               HPOS=str(hpos),
                               VPOS=str(vpos),
                               WIDTH=str(width),
                               HEIGHT=str(height))

    # Process text lines
    text_lines = region_elem.findall('pc:TextLine', ns)
    for line_idx, line_elem in enumerate(text_lines):
        textline = convert_textline(line_elem, ns, page_prefix, block_idx, line_idx)
        text_block.append(textline)

    return composed_block


def convert_tableregion(region_elem: ET.Element, ns: dict,
                        page_prefix: str, region_idx: int) -> ET.Element:
    """
    Convert a PAGE TableRegion to ALTO ComposedBlock > one TextBlock per TableCell.

    PAGE tables use TableRegion > TableCell > TextLine > Word. ALTO has no native
    table model; each cell is flattened to an individual TextBlock inside a single
    ComposedBlock that spans the whole table. The ComposedBlock is tagged as
    layout_table via TAGREFS so consumers can identify the table boundary.
    """
    src_region_id = region_elem.get('id', f'table{region_idx}')
    cblock_id = make_id(page_prefix, f'{src_region_id}_cb')

    coords_elem = region_elem.find('pc:Coords', ns)
    coords_str = coords_elem.get('points', '') if coords_elem is not None else ''
    hpos, vpos, width, height = convert_coords(coords_str)

    composed_block = ET.Element('ComposedBlock',
                                ID=cblock_id,
                                HPOS=str(hpos),
                                VPOS=str(vpos),
                                WIDTH=str(width),
                                HEIGHT=str(height),
                                TAGREFS=TAG_TABLE)

    cells = region_elem.findall('.//pc:TableCell', ns)
    for cell_idx, cell_elem in enumerate(cells):
        src_cell_id = cell_elem.get('id', f'{src_region_id}_cell{cell_idx}')
        block_id = make_id(page_prefix, src_cell_id)

        cell_coords = cell_elem.find('pc:Coords', ns)
        cell_coords_str = cell_coords.get('points', '') if cell_coords is not None else ''
        c_hpos, c_vpos, c_width, c_height = convert_coords(cell_coords_str)

        # Carry row/col position as ALTO custom attributes where available
        row = cell_elem.get('row', '')
        col = cell_elem.get('col', '')
        cell_attribs = dict(
            ID=block_id,
            HPOS=str(c_hpos),
            VPOS=str(c_vpos),
            WIDTH=str(c_width),
            HEIGHT=str(c_height),
        )
        if row and col:
            cell_attribs['CUSTOM'] = f'row:{row} col:{col}'

        text_block = ET.SubElement(composed_block, 'TextBlock', **cell_attribs)

        text_lines = cell_elem.findall('pc:TextLine', ns)
        for line_idx, line_elem in enumerate(text_lines):
            textline = convert_textline(line_elem, ns, page_prefix, cell_idx, line_idx)
            text_block.append(textline)

    return composed_block


def convert_imageregion(region_elem: ET.Element, ns: dict,
                        page_prefix: str, region_idx: int) -> ET.Element:
    """
    Convert a PAGE ImageRegion to an ALTO Illustration element.
    Tagged as layout_image via TAGREFS.
    """
    src_region_id = region_elem.get('id', f'image{region_idx}')
    illus_id = make_id(page_prefix, src_region_id)

    coords_elem = region_elem.find('pc:Coords', ns)
    coords_str = coords_elem.get('points', '') if coords_elem is not None else ''
    hpos, vpos, width, height = convert_coords(coords_str)

    illustration = ET.Element('Illustration',
                              ID=illus_id,
                              HPOS=str(hpos),
                              VPOS=str(vpos),
                              WIDTH=str(width),
                              HEIGHT=str(height),
                              TAGREFS=TAG_IMAGE)
    return illustration


def convert_separatorregion(region_elem: ET.Element, ns: dict,
                             page_prefix: str, region_idx: int) -> ET.Element:
    """
    Convert a PAGE SeparatorRegion to an ALTO GraphicalElement.
    Tagged as layout_separator via TAGREFS.

    SeparatorRegion carries only coordinate data (no text). In PAGE XML it
    represents ruled lines, column dividers, and other non-textual separators.
    """
    src_region_id = region_elem.get('id', f'sep{region_idx}')
    gfx_id = make_id(page_prefix, src_region_id)

    coords_elem = region_elem.find('pc:Coords', ns)
    coords_str = coords_elem.get('points', '') if coords_elem is not None else ''
    hpos, vpos, width, height = convert_coords(coords_str)

    graphical = ET.Element('GraphicalElement',
                           ID=gfx_id,
                           HPOS=str(hpos),
                           VPOS=str(vpos),
                           WIDTH=str(width),
                           HEIGHT=str(height),
                           TAGREFS=TAG_SEPARATOR)
    return graphical


def convert_page_to_alto_page(page_root: ET.Element, page_num: int,
                              page_id: str, page_prefix: str) -> ET.Element:
    """Convert a single PAGE XML page to an ALTO Page element."""
    ns = {'pc': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}

    width, height = get_page_dimensions(page_root)

    page = ET.Element('Page',
                      WIDTH=str(width),
                      HEIGHT=str(height),
                      PHYSICAL_IMG_NR=str(page_num),
                      ID=page_id)

    print_space = ET.SubElement(page, 'PrintSpace',
                                HPOS='0',
                                VPOS='0',
                                WIDTH=str(width),
                                HEIGHT=str(height))

    # ── Reading order ──────────────────────────────────────────────────────
    # Build a region_id → index map from the PAGE ReadingOrder block so that
    # ALTO document order (which implies reading order) matches PAGE intent.
    reading_order: dict[str, int] = {}
    ro_elem = page_root.find('.//pc:ReadingOrder', ns)
    if ro_elem is not None:
        for ref in ro_elem.iter(
            '{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}RegionRefIndexed'
        ):
            region_ref = ref.get('regionRef')
            index = ref.get('index')
            if region_ref is not None and index is not None:
                reading_order[region_ref] = int(index)

    # ── Collect all region elements with their type ────────────────────────
    page_elem = page_root.find('.//pc:Page', ns)
    if page_elem is None:
        return page

    region_types = [
        ('pc:TextRegion',      'text'),
        ('pc:TableRegion',     'table'),
        ('pc:ImageRegion',     'image'),
        ('pc:SeparatorRegion', 'separator'),
    ]

    all_regions: list[tuple[int, str, ET.Element]] = []
    region_counters: dict[str, int] = defaultdict(int)

    for xpath, rtype in region_types:
        for region_elem in page_elem.findall(xpath, ns):
            rid = region_elem.get('id', '')
            ro_index = reading_order.get(rid, 10000 + region_counters[rtype])
            all_regions.append((ro_index, rtype, region_elem))
            region_counters[rtype] += 1

    # Sort by reading order index, preserving document order for ties
    all_regions.sort(key=lambda x: x[0])

    # ── Convert each region ────────────────────────────────────────────────
    type_idx: dict[str, int] = defaultdict(int)
    for _, rtype, region_elem in all_regions:
        idx = type_idx[rtype]
        type_idx[rtype] += 1

        if rtype == 'text':
            element = convert_textregion(region_elem, ns, page_prefix, idx)
        elif rtype == 'table':
            element = convert_tableregion(region_elem, ns, page_prefix, idx)
        elif rtype == 'image':
            element = convert_imageregion(region_elem, ns, page_prefix, idx)
        elif rtype == 'separator':
            element = convert_separatorregion(region_elem, ns, page_prefix, idx)
        else:
            continue

        print_space.append(element)

    return page


def convert_page_files_to_alto(page_files: List[Tuple[int, str]],
                                output_path: str) -> None:
    """
    Convert multiple PAGE XML files to a single ALTO XML document.

    Args:
        page_files: List of (page_number, filepath) tuples
        output_path: Path for output ALTO XML file
    """
    # Create ALTO root
    alto = ET.Element('alto',
                      xmlns='http://www.loc.gov/standards/alto/ns-v3#',
                      attrib={
                          '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation':
                          'http://www.loc.gov/standards/alto/ns-v3# '
                          'http://www.loc.gov/alto/v3/alto-3-0.xsd'
                      })

    # Extract metadata from the first page; representative for the whole document.
    first_page_root = parse_page_xml(page_files[0][1])
    doc_metadata = extract_page_metadata(first_page_root)

    # Add Description, Tags, Layout — in the order ALTO schema expects
    description = create_alto_header(doc_metadata)
    alto.append(description)

    tags = create_alto_tags()
    alto.append(tags)

    layout = ET.SubElement(alto, 'Layout')

    # Process each page
    for page_num, filepath in page_files:
        print(f'  Processing page {page_num}: {os.path.basename(filepath)}')
        page_root = parse_page_xml(filepath)

        page_prefix = os.path.splitext(os.path.basename(filepath))[0]
        page_id = page_prefix

        page_elem = convert_page_to_alto_page(page_root, page_num, page_id, page_prefix)
        layout.append(page_elem)

    # Write ALTO XML
    tree = ET.ElementTree(alto)
    ET.indent(tree, space='\t')
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
    print(f'  Created: {output_path}')


def main():
    parser = argparse.ArgumentParser(
        description='Convert PAGE XML files to ALTO XML format, '
                   'merging pages from the same document.')
    parser.add_argument('input_folder',
                       help='Folder containing PAGE XML files')
    parser.add_argument('--output-folder', '-o',
                       default='alto_xml',
                       help='Output folder for ALTO XML files (default: alto_xml)')
    parser.add_argument('--no-merge',
                       action='store_true',
                       help='Create one ALTO file per PAGE file instead of merging by document')

    args = parser.parse_args()

    # Validate input folder
    if not os.path.isdir(args.input_folder):
        print(f'Error: Input folder not found: {args.input_folder}')
        return 1

    # Create output folder
    os.makedirs(args.output_folder, exist_ok=True)

    # Group files by base name
    print('Grouping files by document...')
    file_groups = group_files(args.input_folder)

    if not file_groups:
        print('No XML files found in input folder.')
        return 1

    print(f'Found {len(file_groups)} document(s)')

    # Convert each group
    for base_name, page_files in file_groups.items():
        if args.no_merge:
            # Create one ALTO file per PAGE file
            print(f'\nConverting document: {base_name} ({len(page_files)} pages) - no merge')
            for page_num, filepath in page_files:
                page_basename = os.path.splitext(os.path.basename(filepath))[0]
                output_path = os.path.join(args.output_folder, f'{page_basename}.xml')
                print(f'  Converting: {os.path.basename(filepath)}')
                convert_page_files_to_alto([(page_num, filepath)], output_path)
        else:
            # Merge pages into single ALTO file (default behavior)
            print(f'\nConverting document: {base_name} ({len(page_files)} pages)')
            output_path = os.path.join(args.output_folder, f'{base_name}.xml')
            convert_page_files_to_alto(page_files, output_path)

    print(f'\nConversion complete! Output files in: {args.output_folder}')
    return 0


if __name__ == '__main__':
    exit(main())