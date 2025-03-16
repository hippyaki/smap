import time
from smap import driver, util

class AkiDriver(driver.SmapDriver):
    def setup(self, opts):
        # Add timeseries
        self.add_timeseries('/sensor0', 'V', data_type='long')

        # Corrected metadata with all required fields
        self.set_metadata('/', {
            'SourceName': 'Base Example Driver',
            'Instrument/Manufacturer': 'sMAP Implementer Forum',
            'Instrument/Model': 'ExampleModel',
            'Instrument/PartNumber': '12345',
            'Instrument/SerialNumber': 'SN001',
            'Location/City': 'Gurgaon',
            'Location/Country': 'India',
            'Properties/UnitofMeasure': 'V',
            'Properties/ReadingType': 'integer',
            'Properties/Timezone': 'UTC',
            'Extra/Driver': 'BaseDriver'
        })



        self.counter = int(opts.get('StartVal', 0))

    def start(self):
        util.periodicSequentialCall(self.read).start(1)

    def read(self):
        self.add('/sensor0', time.time(), self.counter)
        self.counter += 1
