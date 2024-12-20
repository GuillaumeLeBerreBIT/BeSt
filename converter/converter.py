import xml.etree.ElementTree as ET
import pandas as pd
import argparse
import os
import sys
import re
import pyproj
import logging

from constants import (TRANSFORMER, NS, FILE_KEYS_TEST)
from writer import CSVWriter


def get_best_logger(log_file, verbose):
    # Setup logger - (Python logger breaks PEP8 by default)
    logger = logging.getLogger(__name__)
    if verbose:
        logger.setLevel('DEBUG')
    # file_handler logs to file, stream_handler to console
    file_handler = logging.FileHandler(log_file)
    stream_handler = logging.StreamHandler()
    # formatter sets log format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s : %(levelname)s - %(message)s')
    # add formatter to both handlers
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    # add both handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def converter(args):
    """
    Main entry point of the application
    """
    # create a dictionary of all paths to the files
    paths = find_xml_files(args.input_dir)
    # print(paths)
    # create writer
    try:
        writer = CSVWriter(args.output_file)
    except IOError as io:
        logger.fatal(io)
        sys.exit(1)
    # read the addresses from the files
    try:
        read_xml_files(args.region, paths, writer)
    except IOError as io:
        logger.fatal(io)
        sys.exit(1)


def find_xml_files(input_dir):
    """
    Find all the xml files in the given directory
    """
    keys = FILE_KEYS_TEST
    paths = {}
    # print(input_dir)
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.split('.')[-1] == 'xml':
                m = re.search('^([a-zA-Z]+)[0-9]?', file)
                if m:
                    key = m.group(1)
                    # Constants as variables to mach even when letters are capitalized differently
                    if key.upper() in keys:
                        keys.remove(key.upper())
                        paths[key] = os.path.join(root, file)
                    else:
                        logger.warning(
                            'The contents of file %s can not be read by this script', file)
                        
                else:
                    logger.warning(
                        'The contents of file %s can not be read by this script', file)
                    
    if keys:
        logger.error(
            'File for data of type %s was not found in the input folder', keys)
        sys.exit(1)
    return paths


def read_xml_files(region, paths, writer):
    """
    Read all XML files for the specified region
    """
    logger.info('Started reading XML files')

    if region in ['belgium', 'brussels']:
        read_region(
            ET.parse(paths['BrusselsMunicipality']).getroot(),
            ET.parse(paths['BrusselsPostalInfo']).getroot(),
            ET.parse(paths['BrusselsStreetName']).getroot(),
            ET.iterparse(paths['BrusselsAddress']),
            'BE-BRU',
            writer
        )
        logger.info('Read the Brussels addresses')

    if region in ['belgium', 'flanders']:
        read_region(
            ET.parse(paths['FlandersMunicipality']).getroot(),
            ET.parse(paths['FlandersPostalInfo']).getroot(),
            ET.parse(paths['FlandersStreetName']).getroot(),
            ET.iterparse(paths['FlandersAddress']),
            'BE-VLG',
            writer
        )
        logger.info('Read the Flanders addresses')

    if region in ['belgium', 'wallonia']:
        read_region(
            ET.parse(paths['WalloniaMunicipality']).getroot(),
            ET.parse(paths['WalloniaPostalInfo']).getroot(),
            ET.parse(paths['WalloniaStreetName']).getroot(),
            ET.iterparse(paths['WalloniaAddress']),
            'BE-WAL',
            writer
        )
        logger.info('Read the Wallonia addresses')


def write_to_csv(addresses, region, output_dir):
    """
    Write addresses to csv in the output directory
    """
    # convert to pandas dataframe for easy csv writing
    addresses_df = pd.DataFrame(addresses)
    addresses_df.to_csv(os.path.join(output_dir, '%s_addresses.csv' % region))


def read_region(muncipality_root, postalcode_root, streetname_root, address_iter, region_code, writer):
    """Read the XML files for a region
    """
    municipalities = read_municipalities(muncipality_root)
    postalcodes = read_postalinfos(postalcode_root)
    streetnames = read_streetnames(streetname_root)
    
    read_addresses(address_iter, municipalities,
                   postalcodes, streetnames, region_code, writer)


def read_addresses(addresses, municipalities, postcodes, streetnames, region_code, writer):
    count = 0
    for _, element in addresses:
        if 'ADDRESS' == element.tag.split('}')[-1].upper():
            if count % 50_000 == 0:
                logger.info('Read %s addresses of %s region',
                            count, region_code)
            address = read_address(element)
            address_join(address, municipalities, postcodes, streetnames)
            address['region_code'] = region_code
            writer.write_address(address)
            element.clear()
            count += 1


def address_join(address, municipalities, postcodes, streetnames):
    if 'street_id' in address:
        for key, val in streetnames[address['street_id']].items():
            address[key] = val
    else:
        logger.warning('No street id was included address %s',
                       address['address_id'])
    if 'municipality_id' in address:
        for key, val in municipalities[address['municipality_id']].items():
            address[key] = val
    else:
        logger.warning('No muncipality was included for address %s',
                       address['address_id'])
    if 'postcode' in address:
        for key, val in postcodes[address['postcode']].items():
            address[key] = val
    else:
        logger.warning('No postcode was included for address %s',
                       address['address_id'])


def read_address(element):
    address = {}
    for child in element:
        tag = child.tag.split('}')[-1]
        
        if 'code' in tag.lower():
            address['address_id'] = child.findtext(
                'com:objectIdentifier', namespaces=NS)
        elif 'position' == tag:
            lambert_72 = tuple(map(float, child.findtext(
                'com:pointGeometry/com:point/com:pos', namespaces=NS).split(' ')))
            wgs_84 = TRANSFORMER.transform(*lambert_72)

            address['EPSG:31370_x'], address['EPSG:31370_y'] = lambert_72
            address['EPSG:4326_lat'], address['EPSG:4326_lon'] = wgs_84
        elif 'HOUSENUMBER' == tag.upper():
            address['house_number'] = child.text
        elif 'BOXNUMBER' == tag.upper():
            address['box_number'] = child.text
        elif 'ADDRESSSTATUS' == tag.upper():
            address['status'] = child.findtext(
                'com:status', namespaces=NS)
        elif 'HASSTREETNAME' == tag.upper():
            address['street_id'] = child.findtext(
                'com:objectIdentifier', namespaces=NS)
        elif 'HASMUNICIPALITY' == tag.upper():
            address['municipality_id'] = child.findtext(
                'com:objectIdentifier', namespaces=NS)
        elif 'HASPOSTALINFO' == tag.upper():
            address['postcode'] = child.findtext(
                'com:objectIdentifier', namespaces=NS)
        
    return address


def read_streetnames(element):
    streetnames = {}
    for child in element:
        if 'STREETNAME' in child.tag.split('}')[-1].upper():
            streetname = read_streetname(child)
            streetnames[streetname['street_id']] = streetname
    return streetnames


def read_streetname(element):
    streetname = {}
    for child in element:
        tag = child.tag.split('}')[-1]
        
        if 'code' in tag.lower():
            streetname['street_id'] = child.findtext(
                'com:objectIdentifier', namespaces=NS)
        elif 'name' in tag.lower():
            lang = child.findtext(
                'com:language', namespaces=NS)
            streetname['streetname_{}'.format(
                lang)] = child.findtext('com:spelling', namespaces=NS)
    return streetname


def read_postalinfos(element):
    postalinfos = {}

    for child in element:
        if 'POSTALINFO' in child.tag.split('}')[-1].upper():
            postalinfo = read_postalinfo(child)
            postalinfos[postalinfo['postcode']] = postalinfo
    return postalinfos


def read_postalinfo(element):
    postalinfo = {}
    for child in element:
        tag = child.tag.split('}')[-1]
        if 'code' in tag.lower():                                   # Previous name isn' correct == outdated. 
            postalinfo['postcode'] = child.findtext(
                'com:objectIdentifier', namespaces=NS)
        elif 'name' in tag.lower():                                 # Previous name isn' correct == outdated. 
            lang = child.findtext(
                'com:language', namespaces=NS)
            postalinfo['postname_{}'.format(
                lang)] = child.findtext('com:spelling', namespaces=NS)
    return postalinfo


def read_municipalities(element):
    municipalities = {}
    for child in element:
        if 'MUNICIPALITY' in child.tag.split('}')[-1].upper():
            municipality = read_muncipality(child)
            municipalities[municipality['municipality_id']] = municipality
    return municipalities


def read_muncipality(element):
    muncipality = {}
    for child in element:
        tag = child.tag.split('}')[-1]
        if 'code' in tag.lower():
            muncipality['municipality_id'] = child.findtext(
                'com:objectIdentifier', namespaces=NS)
        elif 'name' in tag.lower():
            lang = child.findtext(
                'com:language', namespaces=NS)
            muncipality['municipality_name_{}'.format(
                lang)] = child.findtext('com:spelling', namespaces=NS)
    return muncipality


if __name__ == "__main__":
    # Setup argument parser
    parser = argparse.ArgumentParser(
        description='Convert address XML files to a csv file.')
    parser.add_argument(
        'input_dir', help='input directory of the xml files')
    parser.add_argument('output_file', help='output file')
    parser.add_argument('--log_name', default="conversion.log",
                        help='name of the log file')
    parser.add_argument('--region', help='region to consider', default='belgium',
                        choices=['belgium', 'brussels', 'flanders', 'wallonia'])
    parser.add_argument('--verbose', action="store_true",
                        help="toggle verbose output",  default=False)
    args = parser.parse_args()

    logger = get_best_logger(args.log_name, args.verbose)

    converter(args)
