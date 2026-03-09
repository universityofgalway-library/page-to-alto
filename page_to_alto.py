#!/usr/bin/env python3
"""
Convert and merge PAGE XML files to ALTO XML format.
Groups files by base name (everything before the hyphen) and creates
multi-page ALTO documents.
"""

import argparse
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET


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
    """Convert a PAGE TextRegion to ALTO ComposedBlock + TextBlock."""
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
                                HEIGHT=str(height))

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


def convert_page_to_alto_page(page_root: ET.Element, page_num: int,
                              page_id: str, page_prefix: str) -> ET.Element:
    """Convert a single PAGE XML page to ALTO Page element."""
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

    # Build a reading-order index from the PAGE ReadingOrder block so that
    # ALTO document order matches the intended reading sequence.
    reading_order: dict[str, int] = {}
    ro_elem = page_root.find('.//pc:ReadingOrder', ns)
    if ro_elem is not None:
        for ref in ro_elem.iter('{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}RegionRefIndexed'):
            region_ref = ref.get('regionRef')
            index = ref.get('index')
            if region_ref is not None and index is not None:
                reading_order[region_ref] = int(index)

    # Process text regions in reading order (fall back to document order for
    # any region not listed in ReadingOrder).
    text_regions = page_root.findall('.//pc:TextRegion', ns)
    text_regions.sort(
        key=lambda r: reading_order.get(r.get('id', ''), float('inf'))
    )
    for idx, region in enumerate(text_regions):
        composed_block = convert_textregion(region, ns, page_prefix, idx)
        print_space.append(composed_block)

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

    # Add description
    description = create_alto_header(doc_metadata)
    alto.append(description)

    # Create Layout section
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