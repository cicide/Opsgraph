#!/usr/bin/python

import time, datetime
import utils

log = utils.get_logger("HighChartsService")

def getLineChartObject(date_format, graph_settings, data_series, caption, x_axis_name, events, chart_cell):
    # data_series looks like: [ { data: { <time value>: y_value },
    #                             description: <min/max info>,
    #                             uom: <unit of measure>,
    #                             label: <series label>}
    #                         ]
    
    # create the series object:
    # it looks like [
    #                   { name: <series name>,
    #                     data: [
    #                               [time, value]
    #                           ]
    #                   }, ....
    #               ]
    chart_width = graph_settings['graph_width']
    chart_height = graph_settings['graph_height']
    chart_type = graph_settings['graph_type']
    series_object = []
    uoms = []
    for series in data_series:
        series_name = str(series['label'])
        series_id = str(series['seriesId'])
        data_dict = series['data']
        series_uom = str(series['uom'])
        if series_uom not in uoms:
            uoms.append(series_uom)
        series_item = {}
        series_item[u'name'] = unicode(series_name)
        series_item[u'seriesId'] = unicode(series_id)
        series_data = []
        time_values = data_dict.keys()
        time_values.sort()
        for time_value in time_values:
            #log.debug('adding record %s, %s' % (time_value, data_dict[time_value]))
            if data_dict[time_value]:
                series_data.append([unicode(time_value), unicode(data_dict[time_value])])
        series_item[u'data'] = series_data
        series_object.append(series_item)
    if len(uoms) > 1:
        log.info('Multiple units of measure selected for a single graph')
        uom = ', '.join(uoms)
    else:
        uom = uoms[0]
    plotBands = []
    if events:
        log.debug('including %i events' % len(events['line']))
        for record in events['line']:
            tmp = {}
            tmp[unicode('color')] = record['color']
            tmp[unicode('from')] = record['start']
            tmp[unicode('to')] = record['end']
            tmp[unicode('label')] = {u'text': record['displayValue']}
            tmp[unicode('alpha')] = record['alpha']
            plotBands.append(tmp)
    plotOptions = []
    tooltip = { u'xDateFormat': u'%Y-%m-%d %H:%M'}
    yAxis = { u'title': {u'text': unicode(uom)},
              u'min': 0
            }
    xAxis = { u'type': u'datetime',
              u'plotBands': plotBands}
    title = { u'text': unicode(caption)}
    chart = { u'renderTo': unicode(chart_cell),
              u'type': unicode(chart_type),
              u'zoomType': u'xy',
              u'height': unicode(chart_height),
              u'width': unicode(chart_width)
            }
    chart_object = { u'chart': chart,
                     u'plotOptions': plotOptions,
                     u'title': title,
                     u'xAxis': xAxis,
                     u'yAxis': yAxis,
                     u'tooltip': tooltip,
                     u'series': series_object}
    #log.debug(chart_object)
    return chart_object