#!/usr/bin/python

import time, datetime
import utils

log = utils.get_logger("FusionChartsService")

def getMsObject(date_format, x_axis_values, y_axis_series, caption, x_axis_name, events):
    #for now we will assume the x axis is a time axis...
    time_values = x_axis_values
    data_series = y_axis_series
    log.debug('time values is %i long' % len(time_values))
    # Create the x-axis and y-axis structures needed by fusioncharts
    timeset = []
    datasets = {}
    tvProcessStart = time.time()
    for time_value in time_values:
        # format the time value based on the configured data_format
        time_obj = datetime.datetime.fromtimestamp(int(time_value))
        format_time = time_obj.strftime(date_format)
        timeset.append({unicode('label'): unicode(format_time)})
        for series in data_series:
            label = unicode(series['label'])
            if label not in datasets:
                datasets[label] = []
            # if the series has no entry for the time value, add an entry as '' - this might not be the right thing to do - maybe we should add the previous or next value?
            if str(time_value) in series['data']:
                if series['data'][str(time_value)] in (None, 'None'):
                    datasets[label].append({unicode('value'): unicode('')})
                else:
                    datasets[label].append({unicode('value'): unicode(series['data'][str(time_value)])})
            else:
                log.debug('missing value for time step')
                datasets[label].append({unicode('value'): unicode('')})
    tvProcessTime = time.time() - tvProcessStart
    log.debug('total series processing time: %s' % tvProcessTime)
    # We now have our x-axis and y-axis data, but the y-data isn't correctly formatted yet
    data_structure = []
    time_structure = []
    for data_dict in datasets:
        data_struct = {unicode('seriesname'): unicode(data_dict), unicode('data'): datasets[data_dict]}
        data_structure.append(data_struct)
    time_structure.append({unicode('category'): timeset})
    # figure out the unit of measure we are using, if the series have different units of measure
    #   throw a warning, and display all uom's as a string
    uoms = []
    for series in data_series:
        series_uom = str(series['uom'])
        if series_uom not in uoms:
            uoms.append(series_uom)
    if len(uoms) > 1:
        log.info('Multiple units of measure selected for a single graph')
        uom = ', '.join(uoms)
    else:
        uom = uoms[0]  
    # Now we need to create the chart structure
    chart_structure = {}
    chart_structure[unicode('caption')] = unicode(caption)
    chart_structure[unicode('xaxisname')] = unicode("Time")
    chart_structure[unicode('yaxisname')] = unicode(uom)
    chart_structure[unicode('showvalues')] = unicode("0")
    chart_structure[unicode('dynamicAxis')] = unicode("1")
    chart_structure[unicode('pixelsPerPoint')] = unicode("5")
    chart_structure[unicode('connectnulldata')] = unicode("1")
    # create the sytles structure
    styles = {}
    definition = {}
    application ={}
    definition[unicode('name')] = unicode('CanvasAnim')
    definition[unicode('type')] = unicode('animation')
    definition[unicode('param')] = unicode('_xScale')
    definition[unicode('start')] = unicode('0')
    definition[unicode('duration')] = unicode('1')
    application[unicode('toobject')] = unicode('Canvas')
    application[unicode('styles')] = unicode('CanvasAnim')
    styles[unicode('definition')] = [definition]
    styles[unicode('application')] = [application]
    # create the final chart object to be sent to fusion charts
    chart_object = {}
    chart_object[unicode('chart')] = chart_structure
    chart_object[unicode('categories')] = time_structure
    chart_object[unicode('dataset')] = data_structure
    chart_object[unicode('styles')] = styles
    # add events as vertical trend zones if we have any events
    if events:
        log.debug('including %i events' % len(events['line']))
        chart_object[unicode('vTrendlines')] = [events]
        log.debug('vTrendlines:')
        log.debug([events])
    else:
        log.debug('Not showing events')
    # return the chart_object
    #log.debug('returning fusion chart object: %s' % chart_object)
    return chart_object