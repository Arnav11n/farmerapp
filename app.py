from flask import Flask, jsonify
import ee
from google.oauth2 import service_account

app = Flask(__name__)

# Initialize Earth Engine
key_file = 'ee-arnavnarang11-895b4181b723.json'  # Update with your key file path
scopes = ['https://www.googleapis.com/auth/earthengine']
credentials = service_account.Credentials.from_service_account_file(key_file, scopes=scopes)
ee.Initialize(credentials)

@app.route('/api/data/<float:latitude>/<float:longitude>', methods=['GET'])
def get_data(latitude, longitude):
    # Define the area of interest
    aoi = ee.Geometry.Point([longitude, latitude])
    
    # Define the time period for analysis
    startDate = '2022-01-01'
    endDate = '2022-12-31'

    # 1. Load and calculate the average Land Surface Temperature (LST) from MODIS
    temperatureCollection = ee.ImageCollection('MODIS/006/MOD11A2') \
                                  .filterBounds(aoi) \
                                  .filterDate(startDate, endDate) \
                                  .select('LST_Day_1km')

    # Check if the collection has any images
    hasTemperatureData = temperatureCollection.size().gt(0)
    avgTemperature = None

    if hasTemperatureData.getInfo():
        avgTemperature = temperatureCollection.mean().multiply(0.02).subtract(273.15)  # Convert to Celsius
        temperature = avgTemperature.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=1000
        )
    else:
        return jsonify({'error': 'No temperature data available.'}), 404

    # 2. Load and calculate the total precipitation (rainfall) from CHIRPS
    rainfallCollection = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY') \
                            .filterBounds(aoi) \
                            .filterDate(startDate, endDate)

    totalRainfall = rainfallCollection.sum().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=5000
    )

    # 3. Load and calculate the average soil moisture from SMAP
    soilMoistureCollection = ee.ImageCollection('NASA_USDA/HSL/SMAP10KM_soil_moisture') \
                                   .filterBounds(aoi) \
                                   .filterDate(startDate, endDate)

    hasSoilMoistureData = soilMoistureCollection.size().gt(0)
    avgSoilMoisture = None

    if hasSoilMoistureData.getInfo():
        avgSoilMoisture = soilMoistureCollection.mean()
        soilMoistureValue = avgSoilMoisture.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=10000
        ).get('ssm')
    else:
        return jsonify({'error': 'No soil moisture data available.'}), 404

    # 4. Calculate NDVI using Sentinel-2 imagery
    sentinelCollection = ee.ImageCollection('COPERNICUS/S2') \
                            .filterBounds(aoi) \
                            .filterDate(startDate, endDate) \
                            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))

    ndvi = sentinelCollection.map(lambda image: image.normalizedDifference(['B8', 'B4']).rename('NDVI'))
    avgNDVI = ndvi.mean().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=10
    )

    return jsonify({
        'average_temperature': temperature.get('LST_Day_1km').getInfo(),
        'total_rainfall': totalRainfall.get('precipitation').getInfo(),
        'average_soil_moisture': soilMoistureValue.getInfo(),
        'average_ndvi': avgNDVI.get('NDVI').getInfo()
    })

if __name__ == '__main__':
    app.run(debug=True)
