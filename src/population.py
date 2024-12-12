# import necessary packages and libraries
import rasterio
import geopandas as gpd
from rasterio.mask import mask
import numpy as np

# clip (population) density raster using a shapefile boundary
def clip_raster_with_shapefile(raster_path, shapefile_path, output_path):
    """
    clip a raster using a shapefile boundary
    """
    # read the shapefile
    shape = gpd.read_file(shapefile_path)
    
    # get the geometry in GeoJSON format
    geometry = [feature["geometry"] for feature in shape.to_dict("records")]
    
    # open the raster
    with rasterio.open(raster_path) as src:
        # perform the clip
        clipped_raster, clipped_transform = mask(src, 
                                               geometry,
                                               crop=True)
        
        # copy the metadata from the source
        meta = src.meta.copy()
        
        # update metadata for the clipped raster
        meta.update({
            "height": clipped_raster.shape[1],
            "width": clipped_raster.shape[2],
            "transform": clipped_transform
        })
        
        # write the clipped raster to a new file
        with rasterio.open(output_path, "w", **meta) as dest:
            dest.write(clipped_raster)
            
# convert (population) raster to point GeoJSON, optionallysampling every nth pixel
def raster_to_points(raster_path, output_path, sample_rate=1):
    """
    convert raster to point GeoJSON with optional sampling
    
    Parameters:
    raster_path (str): Path to input raster
    output_path (str): Path for output GeoJSON
    sample_rate (int): Take every nth pixel (1 = all pixels)
    """
    with rasterio.open(raster_path) as src:
        data = src.read(1)  # Read first band
        
        # peport initial size
        print(f"input raster dimensions: {src.width} x {src.height}")
        print(f"total pixels: {src.width * src.height}")
        
        # create coordinate arrays
        rows, cols = np.where(~np.isnan(data))
        
        # apply sampling
        rows = rows[::sample_rate]
        cols = cols[::sample_rate]
        values = data[rows, cols]
        
        # convert pixel coordinates to geographic coordinates
        xs, ys = rasterio.transform.xy(src.transform, rows, cols)
        
        # create geodataframe
        points = gpd.GeoDataFrame({
            'population_density': values
        }, geometry=gpd.points_from_xy(xs, ys))
        
        points.crs = src.crs
        
        # save to GeoJSON
        points.to_file(output_path, driver='GeoJSON')
        
        print(f"\nCreated {len(points)} points")
        print(f"Value range: {points.population_density.min():.2f} to {points.population_density.max():.2f}")
        
        return points