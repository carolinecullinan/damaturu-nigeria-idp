# import necessary packages and libraries
from osgeo import ogr
import geopandas as gpd


# convert KMZ IDP data to shapefile boundary
def kmz_to_shapefile(input_kmz, output_shp):
    """
    convert KMZ to shapefile and return as geodataframe
    """
    # convert KMZ to shapefile
    driver = ogr.GetDriverByName('KML')
    data_source = driver.Open(input_kmz)
    
    # create output shapefile
    out_driver = ogr.GetDriverByName("ESRI Shapefile")
    out_data_source = out_driver.CreateDataSource(output_shp)
    
    # copy the layer
    layer = data_source.GetLayer()
    out_data_source.CopyLayer(layer, layer.GetName())
    
    # close the datasets
    data_source = None
    out_data_source = None
    
    # return as geodataframe
    return gpd.read_file(output_shp)