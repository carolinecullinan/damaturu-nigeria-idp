# import necessary packages and libraries
import rasterio
import geopandas as gpd
from rasterio.mask import mask
from rasterio.features import shapes
from shapely.geometry import shape, mapping
import numpy as np

## working with population density data (WorldPop Data 2020, 1 km resolution)
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
            
# convert (population density) raster to point GeoJSON, optionally sampling every nth pixel
def raster_to_points(raster_path, output_path, sample_rate=1):
    """
    convert raster to point GeoJSON with optional sampling
    
    Parameters:
    raster_path (str): Path to input raster
    output_path (str): Path for output GeoJSON
    sample_rate (int): Take every nth pixel (1 = all pixels)
    """
    with rasterio.open(raster_path) as src:
        data = src.read(1)  # read first band
        
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
    
# convert (population density) raster to polygon GeoJSON, preserving the grid structure
def raster_to_polygons(raster_path, shapefile_path, output_path):
    """
    convert raster to polygons while preserving the grid structure.
    
    Parameters:
    raster_path (str): Path to input raster
    shapefile_path (str): Path to shapefile for clipping
    output_path (str): Path for output GeoJSON
    """
    
    # read and clip the raster first
    shape = gpd.read_file(shapefile_path)
    geometry = [feature["geometry"] for feature in shape.to_dict("records")]
    
    with rasterio.open(raster_path) as src:
        # clip the raster
        clipped_raster, clipped_transform = rasterio.mask.mask(src, 
                                                             geometry,
                                                             crop=True)
        
        # get the mask of valid data
        mask = ~np.isnan(clipped_raster[0])
        
        # generate shapes from the raster
        results = (
            {'properties': {'population_density': float(v)}, 'geometry': s}
            for s, v in shapes(clipped_raster[0], 
                             mask=mask,
                             transform=clipped_transform)
        )
        
        # convert to geodataframe
        geoms = list(results)
        gdf = gpd.GeoDataFrame.from_features(geoms)
        
        # set CRS from the input raster
        gdf.set_crs(src.crs, inplace=True)
        
        # filter out any NoData values
        gdf = gdf[gdf.population_density != src.nodata]
        
        # save to GeoJSON
        gdf.to_file(output_path, driver='GeoJSON')
        
        print(f"\nCreated {len(gdf)} polygons")
        print(f"Value range: {gdf.population_density.min():.2f} to {gdf.population_density.max():.2f}")
        
        return gdf
    
## working with population data (WorldPop Data 2020, 100 m resolution (- must convert to population density first)
# calculate population density for Damaturu AOI and convert (population density) raster to polygon GeoJSON, preserving the grid structure
def pd_calc_raster_to_polygons(raster_path, shapefile_path, output_path):
    """
    calculate population density for AOI and convert (population density) raster to polygon GeoJSON, preserving the grid structure.
    
    Parameters:
    raster_path (str): Path to input population raster (100m resolution)
    shapefile_path (str): Path to shapefile for clipping
    output_path (str): Path for output GeoJSON
    """
    # read and clip the raster first
    shape = gpd.read_file(shapefile_path)
    geometry = [feature["geometry"] for feature in shape.to_dict("records")]
    
    with rasterio.open(raster_path) as src:
        # clip the raster
        clipped_raster, clipped_transform = rasterio.mask.mask(src,
                                                             geometry,
                                                             crop=True,
                                                             nodata=99999.0,
                                                             all_touched=True) # include cells that intersect the geometryspecify the nodata value
        
        #print(f"Clipped raster min: {clipped_raster.min()}")
        #print(f"Clipped raster max: {clipped_raster.max()}")

        # print the data type and scale                                                     
        #print(f"Original data type: {src.dtypes[0]}")
        #print(f"Clipped data type: {clipped_raster.dtype}")
        #print(f"Scale factors: {src.scales}")
        #print(f"Offsets: {src.offsets}")

        # print values for just the clipped area to compare with original
        print("Values in clipped area before processing:")
        unprocessed = src.read(1, window=src.window(*src.bounds))
        print(f"Unprocessed min in area: {unprocessed.min()}")
        print(f"Unprocessed max in area: {unprocessed.max()}")
        
        # calculate cell area in square kilometers (100m = 0.1km)
        cell_area_km2 = 0.1 * 0.1  # 100m x 100m = 0.01 km²
        
        # convert population to density (people per km²)
        #density_raster = clipped_raster[0] / cell_area_km2 (all cells are exactly the same size (100m x 100m), so raw counts work fine - no need to divide by cell area)
        density_raster = clipped_raster[0]
        print(f"Density raster min: {density_raster.min()}")
        print(f"Density raster max: {density_raster.max()}")


        # get the mask of valid data
        mask = ~np.isnan(density_raster)
        
        # generate shapes from the raster
        results = (
            {'properties': {'population_density': float(v)}, 'geometry': s}
            for s, v in shapes(density_raster,
                             mask=mask,
                             transform=clipped_transform)
        )
        
        # convert to geodataframe
        geoms = list(results)
        gdf = gpd.GeoDataFrame.from_features(geoms)
        
        # set CRS from the input raster
        gdf.set_crs(src.crs, inplace=True)
        
        # filter out any NoData values
        gdf = gdf[gdf.population_density != src.nodata]
        
        # save to GeoJSON
        gdf.to_file(output_path, driver='GeoJSON')
        
        print(f"\nCreated {len(gdf)} polygons")
        print(f"Value range: {gdf.population_density.min():.2f} to {gdf.population_density.max():.2f}")
        
        return gdf


    
