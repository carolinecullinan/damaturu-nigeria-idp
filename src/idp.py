import tempfile
import os
from pathlib import Path
import zipfile
import fiona
import geopandas as gpd
import pandas as pd
from bs4 import BeautifulSoup

# extract KMZ (i.e. zipped KML) and convert it to shapefile while cleaning up temporary files
def kmz_to_shapefile(input_kmz, output_shp):
    """
    convert KMZ to shapefile and return as geodataframe
    """
    # create temporary directory in user space
    with tempfile.TemporaryDirectory() as temp_dir:
        # extract KMZ to KML
        with zipfile.ZipFile(input_kmz, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # find the KML file (usually doc.kml)
        kml_file = next(Path(temp_dir).glob("*.kml"))
        
        # register KML driver
        fiona.drvsupport.supported_drivers['KML'] = 'rw'
        
        # read KML directly into geodataframe
        gdf = gpd.read_file(str(kml_file), driver='KML')
        
        # save to shapefile
        gdf.to_file(output_shp)
        
        return gdf
    
# transform IDP site data from geodataframe with Name, Description, and geometry columns into a dataframe with sites as rows and attributes as columns for easier analysis
def transform_idp_description(gdf):
    """
    transform IDP site data from geodatadrame with Name, Description, and geometry columns into a dataframe with sites as rows and attributes as columns for easier analysis
    
    Parameters:
    gdf (GeoDataFrame): Input GeoDataFrame containing IDP sites with HTML Description
    
    Returns:
    DataFrame: Restructured data with sites as rows and attributes as columns
    """
    # create an empty list to store the transformed data
    transformed_data = []
    
    # iterate through each site
    for idx, row in gdf.iterrows():
        # Start with site name and coordinates
        site_data = {
            'site_name': row['Name'],
            'latitude': row.geometry.y,
            'longitude': row.geometry.x
        }
        
        # parse the HTML content from Description column
        soup = BeautifulSoup(row['Description'], 'html.parser')
        
        # find all table rows
        rows = soup.find_all('tr')
        
        # extract key-value pairs from the table
        for table_row in rows:
            cols = table_row.find_all('td')
            if len(cols) == 2:
                # clean up the key name to make it suitable for column name
                key = cols[0].get_text(strip=True)
                key = (key.lower()
                      .replace(' ', '_')
                      .replace('(', '')
                      .replace(')', '')
                      .replace('%', 'pct')
                      .replace('-', '_')
                      .replace('/', '_'))
                value = cols[1].get_text(strip=True)
                site_data[key] = value
        
        transformed_data.append(site_data)
    
    # convert to dataframe
    df = pd.DataFrame(transformed_data)
    
    return df


# transform IDP site data from geodataframe with Name, Description, and geometry columns into a geodataframe with all attributes as columns and geometry as a column for easier analysis
def transform_idp_complete(gdf):
    """
    transform IDP data preserving all information in a clean format
    
    Parameters:
    gdf (GeoDataFrame): Your original IDP GeoDataFrame
    
    Returns:
    GeoDataFrame: Clean GeoDataFrame with all data preserved
    """
    # create list for clean features
    clean_features = []
    
    for idx, row in gdf.iterrows():
        # start with basic properties
        properties = {
            'name': row['Name']
        }
        
        # parse HTML from Description
        soup = BeautifulSoup(row['Description'], 'html.parser')
        
        # extract all data from table
        for tr in soup.find_all('tr'):
            cols = tr.find_all('td')
            if len(cols) == 2:
                key = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)
                
                # try to convert numeric values
                try:
                    if value.replace('.', '').isdigit():
                        value = float(value)
                    elif value.lower() == 'yes':
                        value = True
                    elif value.lower() == 'no':
                        value = False
                except ValueError:
                    pass
                
                # clean key name for column
                clean_key = (key.lower()
                           .replace(' ', '_')
                           .replace('(', '')
                           .replace(')', '')
                           .replace('%', 'percent')
                           .replace('-', '_')
                           .replace('/', '_'))
                
                properties[clean_key] = value
        
        # keep geometry
        properties['geometry'] = row['geometry']
        clean_features.append(properties)
    
    # create new GeoDataFrame with all properties
    clean_gdf = gpd.GeoDataFrame(clean_features)
    
    # set geometry column
    clean_gdf.set_geometry('geometry', inplace=True)
    clean_gdf.set_crs(epsg=4326, inplace=True)
    
    return clean_gdf