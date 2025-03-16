import random
import time
import logging
from smap.driver import SmapDriver
from smap.util import periodicSequentialCall

class TemperatureHumidityDriver(SmapDriver):
    def setup(self, opts):
        """Configure the driver with metadata and reporting setup."""
        self.interval = int(opts.get("Interval", 10))  # Default interval is 10 seconds
        self.reporting_url = opts.get("ReportingUrl", "http://localhost:8000/add")  # Default URL
        
        # Set metadata
        self.set_metadata("/", {
            "Extra/Driver": "TemperatureHumidityDriver",
            "Extra/ReportingUrl": self.reporting_url,
        })
        
        # Add timeseries paths
        self.add_timeseries("/temperature", "Celsius", data_type="double", description="Temperature sensor data")
        self.add_timeseries("/humidity", "Percent", data_type="double", description="Humidity sensor data")

    def start(self):
        """Start periodic data collection."""
        periodicSequentialCall(self.poll).start(self.interval)

    def poll(self):
        """Generate random temperature and humidity values and push to sMAP."""
        timestamp = int(time.time() * 1000)  # Get timestamp in milliseconds
        temperature = round(random.uniform(20.0, 30.0), 2)  # Simulated temp between 20-30°C
        humidity = round(random.uniform(40.0, 60.0), 2)  # Simulated humidity between 40-60%

        logging.info(f"Sending Data -> Temperature: {temperature}°C, Humidity: {humidity}%, Timestamp: {timestamp}")

        # Push data
        self.add("/temperature", timestamp, temperature)
        self.add("/humidity", timestamp, humidity)
